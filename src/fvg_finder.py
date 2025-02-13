import pandas as pd
import MetaTrader5 as mt5
from typing import Dict, List, Optional
import logging
from config_handler import TimeFrame, ConfigHandler
from datetime import datetime

class FVGFinder:
    def __init__(self):
        self.config = ConfigHandler()
        self.logger = logging.getLogger(__name__)

    def analyze_timeframe(self, symbol: str, timeframe: TimeFrame) -> Optional[Dict]:
        """Analyze a specific timeframe for FVGs working backwards from current candle"""
        try:
            max_lookback = self.config.timeframes[timeframe.name.lower()]['max_lookback']
            window = self.config.fvg_settings['swing_window']
            
            rates = mt5.copy_rates_from_pos(symbol, timeframe.value, 0, max_lookback)
            if rates is None:
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            if len(df) < (2 * window + 1):
                return None

            for i in range(len(df) - window - 1, window - 1, -1):
                current_high = df.iloc[i]['high']
                current_low = df.iloc[i]['low']
                
                # Check for swing high
                is_swing_high = all(current_high > df.iloc[j]['high'] for j in range(i-window, i)) and \
                               all(current_high > df.iloc[j]['high'] for j in range(i+1, i+window+1))
                               
                # Check for swing low
                is_swing_low = all(current_low < df.iloc[j]['low'] for j in range(i-window, i)) and \
                              all(current_low < df.iloc[j]['low'] for j in range(i+1, i+window+1))
                
                if is_swing_high or is_swing_low:
                    return None
                
                if i < len(df) - 2:
                    # Bullish FVG
                    if df.iloc[i+2]['low'] > df.iloc[i]['high']:
                        size = df.iloc[i+2]['low'] - df.iloc[i]['high']
                        if size >= self.config.fvg_settings['min_size']:
                            return {
                                'timeframe': timeframe,
                                'fvg': {
                                    'type': 'bullish',
                                    'top': df.iloc[i+2]['low'],
                                    'bottom': df.iloc[i]['high'],
                                    'size': size,
                                    'time': df.iloc[i+1]['time'],
                                    'candle_index': i+1
                                }
                            }
                    
                    # Bearish FVG
                    elif df.iloc[i+2]['high'] < df.iloc[i]['low']:
                        size = df.iloc[i]['low'] - df.iloc[i+2]['high']
                        if size >= self.config.fvg_settings['min_size']:
                            return {
                                'timeframe': timeframe,
                                'fvg': {
                                    'type': 'bearish',
                                    'top': df.iloc[i]['low'],
                                    'bottom': df.iloc[i+2]['high'],
                                    'size': size,
                                    'time': df.iloc[i+1]['time'],
                                    'candle_index': i+1
                                }
                            }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} on {timeframe}: {str(e)}")
            return None