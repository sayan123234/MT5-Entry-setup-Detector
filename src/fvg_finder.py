import pandas as pd
import MetaTrader5 as mt5
import logging
from config_handler import TimeFrame, ConfigHandler
from typing import Dict, Optional, Tuple
from timeframe_utils import TimeframeUtils
from functools import lru_cache

class FVGFinder:
    def __init__(self):
        self.config = ConfigHandler()
        self.logger = logging.getLogger(__name__)
        self.timeframe_utils = TimeframeUtils()

    def find_swing(self, df: pd.DataFrame) -> Optional[Dict]:
        """Find the first swing point scanning backwards from current candle."""
        if len(df) < 4:
            return None
            
        for i in range(len(df) - 2, 2, -1):
            # Check for swing high
            curr_high = df.iloc[i+1]['high']
            pivot_high = df.iloc[i]['high']
            prev_high = df.iloc[i-1]['high']
            prev2_high = df.iloc[i-2]['high']
            
            is_swing_high = ((pivot_high > curr_high and pivot_high > prev_high) or
                            (pivot_high > curr_high and pivot_high == prev_high and pivot_high > prev2_high))
            
            if is_swing_high:
                return {
                    "type": "high",
                    "time": df.iloc[i]['time'],
                    "price": pivot_high,
                    "index": i
                }
                
            # Check for swing low
            curr_low = df.iloc[i+1]['low']
            pivot_low = df.iloc[i]['low']
            prev_low = df.iloc[i-1]['low']
            prev2_low = df.iloc[i-2]['low']
            
            is_swing_low = ((pivot_low < curr_low and pivot_low < prev_low) or
                           (pivot_low < curr_low and pivot_low == prev_low and pivot_low < prev2_low))
            
            if is_swing_low:
                return {
                    "type": "low",
                    "time": df.iloc[i]['time'],
                    "price": pivot_low,
                    "index": i
                }
        
        return None

    def find_fvg_before_swing(self, df: pd.DataFrame, swing_index: int, timeframe: TimeFrame) -> Optional[Dict]:
        """Find both confirmed and potential FVGs between current candle and swing point"""
        min_size = self.config.fvg_settings['min_size']
        
        for i in range(len(df) - 3, swing_index, -1):
            candle1_time = df.iloc[i]['time']
            candle2_time = df.iloc[i + 1]['time']
            candle3_time = df.iloc[i + 2]['time']
            
            candles_closed = [
                self.timeframe_utils.is_candle_closed(t, timeframe) 
                for t in [candle1_time, candle2_time, candle3_time]
            ]
            
            all_candles_closed = all(candles_closed)
            
            # Check for bearish FVG
            if df.iloc[i + 2]['high'] < df.iloc[i]['low']:
                gap_size = df.iloc[i]['low'] - df.iloc[i + 2]['high']
                if gap_size >= min_size:
                    return {
                        "type": "bearish",
                        "top": df.iloc[i]['low'],
                        "bottom": df.iloc[i + 2]['high'],
                        "size": gap_size,
                        "time": df.iloc[i + 2]['time'],
                        "is_confirmed": all_candles_closed,
                        "candle_status": {
                            "candle1": {"time": candle1_time, "closed": candles_closed[0]},
                            "candle2": {"time": candle2_time, "closed": candles_closed[1]},
                            "candle3": {"time": candle3_time, "closed": candles_closed[2]}
                        }
                    }
            
            # Check for bullish FVG
            if df.iloc[i + 2]['low'] > df.iloc[i]['high']:
                gap_size = df.iloc[i + 2]['low'] - df.iloc[i]['high']
                if gap_size >= min_size:
                    return {
                        "type": "bullish",
                        "top": df.iloc[i + 2]['low'],
                        "bottom": df.iloc[i]['high'],
                        "size": gap_size,
                        "time": df.iloc[i + 2]['time'],
                        "is_confirmed": all_candles_closed,
                        "candle_status": {
                            "candle1": {"time": candle1_time, "closed": candles_closed[0]},
                            "candle2": {"time": candle2_time, "closed": candles_closed[1]},
                            "candle3": {"time": candle3_time, "closed": candles_closed[2]}
                        }
                    }
        
        return None

    def is_fvg_mitigated(self, df: pd.DataFrame, fvg: Dict) -> bool:
        """Check if price has entered the FVG zone"""
        fvg_top = fvg['top']
        fvg_bottom = fvg['bottom']
        
        # Get candles after FVG formation
        post_fvg_df = df[df['time'] > fvg['time']]
        
        if fvg['type'] == 'bullish':
            # Check if price dipped into bullish FVG
            return (post_fvg_df['low'] < fvg_top).any()
        elif fvg['type'] == 'bearish':
            # Check if price rallied into bearish FVG
            return (post_fvg_df['high'] > fvg_bottom).any()
        return False
    
    @lru_cache(maxsize=100)
    def get_cached_rates(self, symbol: str, timeframe: TimeFrame):
        max_lookback = self.config.get_timeframes().get(timeframe, 100)
        return mt5.copy_rates_from_pos(symbol, timeframe.mt5_timeframe, 0, max_lookback)
    
    def get_rates_safe(self, symbol: str, timeframe: TimeFrame, count: int) -> Optional[pd.DataFrame]:
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe.mt5_timeframe, 0, count)
            if rates is None:
                self.logger.error(f"Failed to get rates for {symbol} {timeframe}")
                return None
                
            df = pd.DataFrame(rates)
            if len(df) < count * 0.8:  # Check if we got enough data
                self.logger.warning(f"Insufficient data for {symbol} {timeframe}")
                return None
                
            return df
        except Exception as e:
            self.logger.error(f"Error getting rates: {e}")
            return None
    
    def analyze_timeframe(self, symbol: str, timeframe: TimeFrame):
        """Analyze a single timeframe for FVG or swing point."""
        try:
            max_lookback = self.config.get_timeframes().get(timeframe, 100)  # Default to 100 if missing
            df = self.get_rates_safe(symbol, timeframe, max_lookback)

            if df is None:
                return True, None
            
            df['time'] = pd.to_datetime(df['time'], unit='s')

            swing = self.find_swing(df)
            if swing is None:
                return True, None

            fvg = self.find_fvg_before_swing(df, swing['index'], timeframe)
            if fvg:
                # Add mitigation check for confirmed FVGs
                if fvg['is_confirmed']:
                    fvg['mitigated'] = self.is_fvg_mitigated(df, fvg)
                
                return False, {
                    'status': 'complete',
                    'symbol': symbol,
                    'timeframe': timeframe.value,
                    'fvg': fvg,
                    'swing': swing
                }

            return True, None

        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} on {timeframe}: {e}")
            return True, None