import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
import MetaTrader5 as mt5
from src.config.config_handler import TimeFrame, ConfigHandler
from src.core.fvg_finder import FVGFinder
from src.core.two_candle_rejection import TwoCandleRejection
from src.core.candle_classifier import CandleClassifier
from src.core.pd_rays import PDRays

class TradingStrategy:
    """
    Implements the complete trading strategy framework.
    
    This class integrates all components of the trading strategy:
    1. Identify PD Rays (FVGs, Swings, Previous Candle Highs/Lows)
    2. Determine Direction
    3. Establish Narrative
    4. Two Candle Rejection Strategy
    5. Entries and Risk Management
    """
    
    def __init__(self, config: Optional[ConfigHandler] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or ConfigHandler()
        
        # Initialize components
        self.fvg_finder = FVGFinder(config=self.config)
        self.two_candle_rejection = TwoCandleRejection()
        self.candle_classifier = CandleClassifier()
        self.pd_rays = PDRays(fvg_finder=self.fvg_finder)
    
    def analyze_timeframe(self, symbol: str, timeframe: TimeFrame) -> Dict:
        """
        Perform complete analysis on a single timeframe.
        
        Args:
            symbol: Symbol to analyze
            timeframe: Timeframe to analyze
            
        Returns:
            Dictionary with complete analysis results
        """
        try:
            # Get market data
            max_lookback = self.config.get_timeframes().get(timeframe, 100)
            df = self.fvg_finder.get_rates_safe(symbol, timeframe, max_lookback)
            
            if df is None or len(df) < 5:
                return {"status": "insufficient_data"}
                
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            current_price = tick.bid if tick else df.iloc[-1]['close']
            
            # Step 1: Identify PD Rays
            pd_rays = self.pd_rays.identify_pd_rays(df, symbol, timeframe)
            
            # Step 2: Determine Direction
            direction = self.pd_rays.determine_direction(pd_rays, current_price)
            
            # Classify candles
            candle_classifications = self.candle_classifier.analyze_candle_sequence(df, lookback=5)
            candle_pattern = self.candle_classifier.detect_candle_pattern(candle_classifications)
            
            # Step 3: Establish Narrative
            narrative = self.pd_rays.establish_narrative(pd_rays, direction, candle_classifications)
            
            # Step 4: Check for Two Candle Rejection
            two_cr = None
            for fvg in pd_rays.get("fvgs", []):
                if fvg.get("mitigated", False):
                    two_cr = self.fvg_finder.find_two_candle_rejection(df, fvg, timeframe)
                    if two_cr:
                        break
            
            # Step 5: Calculate Risk-Reward if we have entry, target, and stop loss
            risk_reward = None
            if narrative.get("target") and narrative.get("stop_loss"):
                risk_reward = self.pd_rays.calculate_risk_reward(
                    entry=current_price,
                    target=narrative["target"],
                    stop_loss=narrative["stop_loss"]
                )
            
            # Compile results
            return {
                "status": "complete",
                "symbol": symbol,
                "timeframe": timeframe.value,
                "current_price": current_price,
                "pd_rays": pd_rays,
                "direction": direction,
                "candle_classifications": candle_classifications,
                "candle_pattern": candle_pattern,
                "narrative": narrative,
                "two_cr": two_cr,
                "risk_reward": risk_reward
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} on {timeframe}: {e}")
            return {"status": "error", "error": str(e)}
    
    def analyze_multi_timeframe(self, symbol: str, timeframes: List[TimeFrame]) -> Dict:
        """
        Perform analysis across multiple timeframes.
        
        Args:
            symbol: Symbol to analyze
            timeframes: List of timeframes to analyze, in order from highest to lowest
            
        Returns:
            Dictionary with multi-timeframe analysis results
        """
        results = {}
        
        # Analyze each timeframe
        for tf in timeframes:
            results[tf.value] = self.analyze_timeframe(symbol, tf)
        
        # Determine overall bias based on higher timeframes
        overall_bias = self._determine_overall_bias(results)
        
        return {
            "symbol": symbol,
            "timeframe_results": results,
            "overall_bias": overall_bias
        }
    
    def _determine_overall_bias(self, timeframe_results: Dict) -> Dict:
        """
        Determine overall market bias based on multiple timeframe results.
        
        Args:
            timeframe_results: Dictionary with results for each timeframe
            
        Returns:
            Dictionary with overall bias analysis
        """
        # Initialize counters
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        total_confidence = 0
        total_timeframes = 0
        
        # Weight factors for different timeframes (higher timeframes have more weight)
        weights = {
            "MN1": 5.0,  # Monthly
            "W1": 4.0,   # Weekly
            "D1": 3.0,   # Daily
            "H4": 2.0,   # 4-hour
            "H1": 1.5,   # 1-hour
            "M15": 1.0,  # 15-minute
            "M5": 0.8,   # 5-minute
            "M1": 0.5    # 1-minute
        }
        
        # Analyze each timeframe result
        for tf, result in timeframe_results.items():
            if result.get("status") != "complete":
                continue
                
            direction = result.get("direction", {})
            bias = direction.get("direction", "neutral")
            confidence = direction.get("confidence", 50)
            weight = weights.get(tf, 1.0)
            
            if bias == "bullish":
                bullish_count += weight
            elif bias == "bearish":
                bearish_count += weight
            else:
                neutral_count += weight
                
            total_confidence += confidence * weight
            total_timeframes += weight
        
        # Calculate overall bias
        if total_timeframes == 0:
            return {"bias": "neutral", "confidence": 0, "description": "No valid timeframe data"}
            
        if bullish_count > bearish_count and bullish_count > neutral_count:
            bias = "bullish"
            strength = bullish_count / total_timeframes
        elif bearish_count > bullish_count and bearish_count > neutral_count:
            bias = "bearish"
            strength = bearish_count / total_timeframes
        else:
            bias = "neutral"
            strength = neutral_count / total_timeframes
            
        avg_confidence = total_confidence / total_timeframes if total_timeframes > 0 else 50
        
        return {
            "bias": bias,
            "strength": strength * 100,  # Convert to percentage
            "confidence": avg_confidence,
            "bullish_weight": bullish_count,
            "bearish_weight": bearish_count,
            "neutral_weight": neutral_count,
            "description": f"{bias.capitalize()} bias with {avg_confidence:.1f}% confidence across timeframes"
        }
    
    def generate_trade_plan(self, symbol: str) -> Dict:
        """
        Generate a complete trade plan for a symbol.
        
        Args:
            symbol: Symbol to analyze
            
        Returns:
            Dictionary with complete trade plan
        """
        # Define timeframe hierarchy for analysis
        timeframes = [
            TimeFrame.MONTHLY,
            TimeFrame.WEEKLY,
            TimeFrame.DAILY,
            TimeFrame.H4,
            TimeFrame.H1
        ]
        
        # Perform multi-timeframe analysis
        mtf_analysis = self.analyze_multi_timeframe(symbol, timeframes)
        
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.bid if tick else None
        
        # Find the most relevant timeframe for entry (usually H4 or H1)
        entry_timeframe = None
        for tf in [TimeFrame.H4, TimeFrame.H1]:
            tf_result = mtf_analysis["timeframe_results"].get(tf.value, {})
            if tf_result.get("status") == "complete":
                entry_timeframe = tf
                break
                
        if not entry_timeframe:
            return {
                "status": "no_entry_timeframe",
                "symbol": symbol,
                "message": "Could not find suitable entry timeframe"
            }
            
        # Get entry timeframe analysis
        entry_analysis = mtf_analysis["timeframe_results"][entry_timeframe.value]
        
        # Check if we have a valid narrative and risk-reward
        narrative = entry_analysis.get("narrative", {})
        risk_reward = entry_analysis.get("risk_reward", {})
        
        if not narrative or not risk_reward or not risk_reward.get("is_favorable", False):
            return {
                "status": "no_favorable_setup",
                "symbol": symbol,
                "message": "No favorable trading setup found",
                "mtf_analysis": mtf_analysis
            }
            
        # Generate trade plan
        trade_plan = {
            "status": "complete",
            "symbol": symbol,
            "current_price": current_price,
            "overall_bias": mtf_analysis["overall_bias"],
            "entry_timeframe": entry_timeframe.value,
            "entry_strategy": narrative.get("entry_strategy", "wait"),
            "entry_price": current_price,
            "target_price": narrative.get("target"),
            "stop_loss_price": narrative.get("stop_loss"),
            "risk_reward_ratio": risk_reward.get("risk_reward_ratio"),
            "description": narrative.get("description", ""),
            "mtf_analysis": mtf_analysis
        }
        
        # Add breakeven rule
        if trade_plan["entry_price"] and trade_plan["target_price"] and trade_plan["stop_loss_price"]:
            # Calculate breakeven level (1/3 of the way to target)
            if trade_plan["target_price"] > trade_plan["entry_price"]:  # Long trade
                distance_to_target = trade_plan["target_price"] - trade_plan["entry_price"]
                trade_plan["breakeven_price"] = trade_plan["entry_price"] + (distance_to_target / 3)
            else:  # Short trade
                distance_to_target = trade_plan["entry_price"] - trade_plan["target_price"]
                trade_plan["breakeven_price"] = trade_plan["entry_price"] - (distance_to_target / 3)
                
            trade_plan["breakeven_rule"] = "Move stop to breakeven once a new FVG forms in the direction of the trade"
        
        return trade_plan
