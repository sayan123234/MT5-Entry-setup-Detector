import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from src.config.config_handler import TimeFrame
from src.core.fvg_finder import FVGFinder

class PDRays:
    """
    Identifies and manages Premium/Discount Arrays (PD Rays).
    
    PD Rays are critical price levels where markets reverse or accelerate, including:
    - Fair Value Gaps (FVGs)
    - Swing Highs/Lows
    - Previous Candle Highs/Lows
    """
    
    def __init__(self, fvg_finder: Optional[FVGFinder] = None):
        self.logger = logging.getLogger(__name__)
        self.fvg_finder = fvg_finder or FVGFinder()
    
    def identify_pd_rays(self, df: pd.DataFrame, symbol: str, timeframe: TimeFrame) -> Dict:
        """
        Identify all PD Rays in the given data.
        
        Args:
            df: DataFrame with OHLC data
            symbol: Symbol being analyzed
            timeframe: Timeframe being analyzed
            
        Returns:
            Dictionary with all identified PD Rays
        """
        if df is None or len(df) < 5:
            return {"status": "insufficient_data"}
            
        pd_rays = {
            "fvgs": [],
            "swings": [],
            "prev_candle_levels": [],
            "combined": []
        }
        
        # Get FVGs
        try:
            # Find the most recent swing point
            swing = self.fvg_finder.find_swing(df)
            if swing:
                pd_rays["swings"].append(swing)
                
                # Find FVG before swing
                fvg = self.fvg_finder.find_fvg_before_swing(df, swing['index'], timeframe, symbol)
                if fvg:
                    pd_rays["fvgs"].append(fvg)
        except Exception as e:
            self.logger.error(f"Error finding FVGs and swings: {e}")
        
        # Get previous candle high/low levels
        try:
            if len(df) >= 2:
                prev_candle = df.iloc[-2]
                current_candle = df.iloc[-1]
                
                # Previous candle high
                pd_rays["prev_candle_levels"].append({
                    "type": "high",
                    "price": prev_candle['high'],
                    "time": prev_candle['time'],
                    "broken": current_candle['high'] > prev_candle['high']
                })
                
                # Previous candle low
                pd_rays["prev_candle_levels"].append({
                    "type": "low",
                    "price": prev_candle['low'],
                    "time": prev_candle['time'],
                    "broken": current_candle['low'] < prev_candle['low']
                })
        except Exception as e:
            self.logger.error(f"Error finding previous candle levels: {e}")
        
        # Combine all PD Rays into a single sorted list
        combined = []
        
        # Add FVGs to combined list
        for fvg in pd_rays["fvgs"]:
            combined.append({
                "source": "fvg",
                "type": fvg["type"],
                "price": fvg["top"],
                "secondary_price": fvg["bottom"],
                "time": fvg["time"],
                "details": fvg
            })
        
        # Add swings to combined list
        for swing in pd_rays["swings"]:
            combined.append({
                "source": "swing",
                "type": swing["type"],
                "price": swing["price"],
                "time": swing["time"],
                "details": swing
            })
        
        # Add previous candle levels to combined list
        for level in pd_rays["prev_candle_levels"]:
            combined.append({
                "source": "prev_candle",
                "type": level["type"],
                "price": level["price"],
                "time": level["time"],
                "broken": level["broken"],
                "details": level
            })
        
        # Sort combined list by price
        pd_rays["combined"] = sorted(combined, key=lambda x: x["price"])
        
        return pd_rays
    
    def determine_direction(self, pd_rays: Dict, current_price: float) -> Dict:
        """
        Determine the likely market direction based on PD Rays.
        
        Args:
            pd_rays: Dictionary with identified PD Rays
            current_price: Current market price
            
        Returns:
            Dictionary with direction analysis
        """
        if not pd_rays or "combined" not in pd_rays or not pd_rays["combined"]:
            return {"direction": "neutral", "confidence": 0, "reason": "No PD Rays identified"}
        
        # Count bullish and bearish signals
        bullish_signals = 0
        bearish_signals = 0
        reasons = []
        
        # Check FVGs
        for fvg in pd_rays.get("fvgs", []):
            if fvg["type"] == "bullish" and not fvg.get("mitigated", False):
                bullish_signals += 2  # Unmitigated bullish FVG is a strong bullish signal
                reasons.append(f"Unmitigated bullish FVG at {fvg['bottom']}-{fvg['top']}")
            elif fvg["type"] == "bearish" and not fvg.get("mitigated", False):
                bearish_signals += 2  # Unmitigated bearish FVG is a strong bearish signal
                reasons.append(f"Unmitigated bearish FVG at {fvg['bottom']}-{fvg['top']}")
        
        # Check previous candle levels
        for level in pd_rays.get("prev_candle_levels", []):
            if level["type"] == "high" and level.get("broken", False):
                bullish_signals += 1  # Breaking above previous high is bullish
                reasons.append(f"Broke above previous candle high at {level['price']}")
            elif level["type"] == "low" and level.get("broken", False):
                bearish_signals += 1  # Breaking below previous low is bearish
                reasons.append(f"Broke below previous candle low at {level['price']}")
        
        # Find nearest PD Rays above and below current price
        combined = pd_rays["combined"]
        rays_below = [ray for ray in combined if ray["price"] < current_price]
        rays_above = [ray for ray in combined if ray["price"] > current_price]
        
        nearest_below = rays_below[-1] if rays_below else None
        nearest_above = rays_above[0] if rays_above else None
        
        # Calculate distances to nearest PD Rays
        distance_to_below = current_price - nearest_below["price"] if nearest_below else float('inf')
        distance_to_above = nearest_above["price"] - current_price if nearest_above else float('inf')
        
        # Determine if price is closer to support or resistance
        if nearest_below and nearest_above:
            if distance_to_below < distance_to_above:
                # Closer to support, more likely to bounce up
                bullish_signals += 1
                reasons.append(f"Price closer to support at {nearest_below['price']} than resistance at {nearest_above['price']}")
            else:
                # Closer to resistance, more likely to drop
                bearish_signals += 1
                reasons.append(f"Price closer to resistance at {nearest_above['price']} than support at {nearest_below['price']}")
        
        # Determine overall direction
        if bullish_signals > bearish_signals:
            direction = "bullish"
            confidence = min(100, (bullish_signals / (bullish_signals + bearish_signals)) * 100)
        elif bearish_signals > bullish_signals:
            direction = "bearish"
            confidence = min(100, (bearish_signals / (bullish_signals + bearish_signals)) * 100)
        else:
            direction = "neutral"
            confidence = 50
        
        return {
            "direction": direction,
            "confidence": confidence,
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals,
            "reasons": reasons,
            "nearest_support": nearest_below,
            "nearest_resistance": nearest_above
        }
    
    def establish_narrative(self, pd_rays: Dict, direction: Dict, candle_classifications: List[Dict]) -> Dict:
        """
        Establish a trading narrative based on PD Rays, direction, and candle classifications.
        
        Args:
            pd_rays: Dictionary with identified PD Rays
            direction: Dictionary with direction analysis
            candle_classifications: List of classified candles
            
        Returns:
            Dictionary with narrative analysis
        """
        if not pd_rays or not direction or not candle_classifications:
            return {"narrative": "insufficient_data"}
        
        # Get the most recent candle classification
        current_candle = candle_classifications[-1] if candle_classifications else None
        
        # Initialize narrative
        narrative = {
            "bias": direction["direction"],
            "confidence": direction["confidence"],
            "target": None,
            "stop_loss": None,
            "description": "",
            "entry_strategy": "wait"  # Default to waiting for better setup
        }
        
        # Determine target based on direction
        if direction["direction"] == "bullish":
            # Target is the nearest resistance
            if direction.get("nearest_resistance"):
                narrative["target"] = direction["nearest_resistance"]["price"]
                narrative["target_type"] = direction["nearest_resistance"]["source"]
            
            # Stop loss is below the nearest support
            if direction.get("nearest_support"):
                narrative["stop_loss"] = direction["nearest_support"]["price"] * 0.998  # Slightly below support
        
        elif direction["direction"] == "bearish":
            # Target is the nearest support
            if direction.get("nearest_support"):
                narrative["target"] = direction["nearest_support"]["price"]
                narrative["target_type"] = direction["nearest_support"]["source"]
            
            # Stop loss is above the nearest resistance
            if direction.get("nearest_resistance"):
                narrative["stop_loss"] = direction["nearest_resistance"]["price"] * 1.002  # Slightly above resistance
        
        # Refine entry strategy based on candle classification
        if current_candle:
            if current_candle["type"] == "respect":
                # Respect candle suggests waiting for confirmation
                narrative["entry_strategy"] = "wait_for_confirmation"
                narrative["description"] += f"Respect candle detected. Wait for confirmation before entry. "
            
            elif current_candle["type"] == "disrespect":
                # Disrespect candle suggests potential entry
                if current_candle["direction"] == direction["direction"]:
                    narrative["entry_strategy"] = "enter_now"
                    narrative["description"] += f"Disrespect candle in the direction of the bias. Consider immediate entry. "
                else:
                    narrative["entry_strategy"] = "wait_for_reversal"
                    narrative["description"] += f"Disrespect candle against the bias. Wait for reversal confirmation. "
        
        # Add reasons from direction analysis
        if direction.get("reasons"):
            narrative["description"] += "Reasons: " + "; ".join(direction["reasons"])
        
        return narrative
    
    def calculate_risk_reward(self, entry: float, target: float, stop_loss: float) -> Dict:
        """
        Calculate risk-reward ratio and other trade metrics.
        
        Args:
            entry: Entry price
            target: Target price
            stop_loss: Stop loss price
            
        Returns:
            Dictionary with risk-reward analysis
        """
        if not entry or not target or not stop_loss:
            return {"status": "missing_parameters"}
        
        # Calculate distances
        risk = abs(entry - stop_loss)
        reward = abs(entry - target)
        
        # Calculate risk-reward ratio
        if risk == 0:
            risk_reward_ratio = 0
        else:
            risk_reward_ratio = reward / risk
        
        return {
            "entry": entry,
            "target": target,
            "stop_loss": stop_loss,
            "risk": risk,
            "reward": reward,
            "risk_reward_ratio": risk_reward_ratio,
            "is_favorable": risk_reward_ratio >= 2.0  # Consider favorable if R:R is at least 2:1
        }
