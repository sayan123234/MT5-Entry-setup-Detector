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
        self.fvg_min_sizes = self.config.fvg_settings.get('min_size', {'default': 0.0001})

    def _get_min_size(self, symbol: str) -> float:
        """Get minimum FVG size based on symbol type"""
        if 'XAU' in symbol or 'XAG' in symbol:
            return self.fvg_min_sizes.get('metals', self.fvg_min_sizes['default'])
        elif any(crypto in symbol for crypto in ['BTC', 'ETH']):
            return self.fvg_min_sizes.get('crypto', self.fvg_min_sizes['default'])
        return self.fvg_min_sizes['default']

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

    def find_fvg_before_swing(self, df: pd.DataFrame, swing_index: int, timeframe: TimeFrame, symbol: str) -> Optional[Dict]:
        """Find both confirmed and potential FVGs between current candle and swing point"""
        min_size = self._get_min_size(symbol)
        
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

    def find_reentry_fvg(self, df: pd.DataFrame, original_fvg: Dict, timeframe: TimeFrame, symbol: str) -> Optional[Dict]:
        """
        Find FVG formation after price re-enters original FVG zone.
        """
        try:
            if not isinstance(df, pd.DataFrame) or df.empty:
                self.logger.error("Invalid or empty DataFrame provided")
                return None
                
            if not isinstance(original_fvg, dict) or 'time' not in original_fvg:
                self.logger.error("Invalid original FVG format")
                return None
                
            if isinstance(original_fvg['time'], str):
                original_fvg['time'] = pd.to_datetime(original_fvg['time'])
                
            post_fvg_df = df[df['time'] > original_fvg['time']].copy()
            if len(post_fvg_df) < 3:
                return None
            
            fvg_top = original_fvg['top']
            fvg_bottom = original_fvg['bottom']
            min_size = self._get_min_size(symbol)
            
            reentry_found = False
            reentry_idx = None
            reentry_candle = None
            
            for idx in range(len(post_fvg_df) - 1):
                candle = post_fvg_df.iloc[idx]
                next_candle = post_fvg_df.iloc[idx + 1]
                
                if original_fvg['type'] == 'bullish':
                    if candle['low'] >= fvg_top and next_candle['low'] < fvg_top:
                        reentry_found = True
                        reentry_idx = idx + 1
                        reentry_candle = next_candle
                        break
                else:  # bearish
                    if candle['high'] <= fvg_bottom and next_candle['high'] > fvg_bottom:
                        reentry_found = True
                        reentry_idx = idx + 1
                        reentry_candle = next_candle
                        break
            
            if not reentry_found:
                return None
                
            reentry_df = post_fvg_df.iloc[reentry_idx:reentry_idx + 20]
            
            for i in range(len(reentry_df) - 3):
                candle1 = reentry_df.iloc[i]
                candle2 = reentry_df.iloc[i + 1]
                candle3 = reentry_df.iloc[i + 2]
                
                candles_closed = [
                    self.timeframe_utils.is_candle_closed(t, timeframe) 
                    for t in [candle1['time'], candle2['time'], candle3['time']]
                ]
                
                all_candles_closed = all(candles_closed)
                
                if original_fvg['type'] == 'bullish':
                    if candle3['low'] > candle1['high']:
                        gap_size = candle3['low'] - candle1['high']
                        if (gap_size >= min_size and 
                            candle2['high'] < candle3['low'] and
                            candle1['time'] >= reentry_candle['time']):
                            return {
                                "type": "bullish",
                                "top": candle3['low'],
                                "bottom": candle1['high'],
                                "size": gap_size,
                                "time": candle3['time'],
                                "is_confirmed": all_candles_closed,
                                "reentry": True,
                                "original_fvg_time": original_fvg['time'],
                                "reentry_time": reentry_candle['time'],
                                "reentry_price": reentry_candle['low']
                            }
                else:  # bearish
                    if candle3['high'] < candle1['low']:
                        gap_size = candle1['low'] - candle3['high']
                        if (gap_size >= min_size and 
                            candle2['low'] > candle3['high'] and
                            candle1['time'] >= reentry_candle['time']):
                            return {
                                "type": "bearish",
                                "top": candle1['low'],
                                "bottom": candle3['high'],
                                "size": gap_size,
                                "time": candle3['time'],
                                "is_confirmed": all_candles_closed,
                                "reentry": True,
                                "original_fvg_time": original_fvg['time'],
                                "reentry_time": reentry_candle['time'],
                                "reentry_price": reentry_candle['high']
                            }
            
            return None
                
        except Exception as e:
            self.logger.error(f"Error finding reentry FVG: {e}")
            return None

    def is_fvg_mitigated(self, df: pd.DataFrame, fvg: Dict) -> bool:
        """Check if price has entered the FVG zone"""
        fvg_top = fvg['top']
        fvg_bottom = fvg['bottom']
        
        post_fvg_df = df[df['time'] > fvg['time']]
        
        if fvg['type'] == 'bullish':
            return (post_fvg_df['low'] < fvg_top).any()
        elif fvg['type'] == 'bearish':
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
            if len(df) < count * 0.8:
                self.logger.warning(f"Insufficient data for {symbol} {timeframe}")
                return None
                
            df.name = symbol  # Store symbol in DataFrame for later use
            return df
        except Exception as e:
            self.logger.error(f"Error getting rates: {e}")
            return None
    
    def analyze_timeframe(self, symbol: str, timeframe: TimeFrame):
        """Analyze a single timeframe for FVG or swing point."""
        try:
            max_lookback = self.config.get_timeframes().get(timeframe, 100)
            df = self.get_rates_safe(symbol, timeframe, max_lookback)

            if df is None:
                return True, None
            
            df['time'] = pd.to_datetime(df['time'], unit='s')

            swing = self.find_swing(df)
            if swing is None:
                return True, None

            fvg = self.find_fvg_before_swing(df, swing['index'], timeframe, symbol)
            if fvg:
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