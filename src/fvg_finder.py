import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import logging
from config_handler import TimeFrame, ConfigHandler

class FVGFinder:
    def __init__(self):
        self.config = ConfigHandler()
        self.logger = logging.getLogger(__name__)

    def find_swing_points(self, df: pd.DataFrame) -> dict:
        """Find swing highs and lows in the given dataframe"""
        window = self.config.fvg_settings['swing_window']
        swing_points = {'highs': [], 'lows': []}
        
        for i in range(window, len(df) - window):
            # Check for swing high
            if all(df.iloc[i]['high'] > df.iloc[j]['high'] for j in range(i-window, i)) and \
               all(df.iloc[i]['high'] > df.iloc[j]['high'] for j in range(i+1, i+window+1)):
                swing_points['highs'].append({
                    'index': i,
                    'price': df.iloc[i]['high'],
                    'time': df.iloc[i]['time']
                })
            
            # Check for swing low
            if all(df.iloc[i]['low'] < df.iloc[j]['low'] for j in range(i-window, i)) and \
               all(df.iloc[i]['low'] < df.iloc[j]['low'] for j in range(i+1, i+window+1)):
                swing_points['lows'].append({
                    'index': i,
                    'price': df.iloc[i]['low'],
                    'time': df.iloc[i]['time']
                })
        
        return swing_points

    def find_fvg(self, df: pd.DataFrame) -> list:
        """Find Fair Value Gaps in the given dataframe"""
        fvgs = []
        min_size = self.config.fvg_settings['min_size']
        
        for i in range(1, len(df) - 1):
            # Bullish FVG
            if df.iloc[i+1]['low'] > df.iloc[i-1]['high']:
                size = df.iloc[i+1]['low'] - df.iloc[i-1]['high']
                if size >= min_size:
                    fvgs.append({
                        'type': 'bullish',
                        'top': df.iloc[i+1]['low'],
                        'bottom': df.iloc[i-1]['high'],
                        'size': size,
                        'time': df.iloc[i]['time'],
                        'index': i
                    })
            
            # Bearish FVG
            elif df.iloc[i+1]['high'] < df.iloc[i-1]['low']:
                size = df.iloc[i-1]['low'] - df.iloc[i+1]['high']
                if size >= min_size:
                    fvgs.append({
                        'type': 'bearish',
                        'top': df.iloc[i-1]['low'],
                        'bottom': df.iloc[i+1]['high'],
                        'size': size,
                        'time': df.iloc[i]['time'],
                        'index': i
                    })
        
        return fvgs

    def analyze_timeframe(self, symbol: str, timeframe: TimeFrame) -> dict:
        """Analyze a specific timeframe for FVGs between swing points"""
        try:
            # Get maximum lookback periods for the timeframe
            max_lookback = self.config.timeframes[timeframe.name.lower()]['max_lookback']
            
            # Get historical data
            rates = mt5.copy_rates_from_pos(symbol, timeframe.value, 0, max_lookback)
            if rates is None:
                self.logger.error(f"Failed to get data for {symbol} on {timeframe}")
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Find swing points
            swing_points = self.find_swing_points(df)
            
            if not swing_points['highs'] and not swing_points['lows']:
                return None
            
            # Get the most recent swing point
            latest_swing = max(
                swing_points['highs'] + swing_points['lows'],
                key=lambda x: x['time']
            )
            
            # Look for FVGs from current candle to the swing point
            current_data = df.iloc[latest_swing['index']:]
            fvgs = self.find_fvg(current_data)
            
            if not fvgs:
                return None
                
            return {
                'timeframe': timeframe,
                'swing_points': swing_points,
                'fvgs': fvgs
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} on {timeframe}: {str(e)}")
            return None