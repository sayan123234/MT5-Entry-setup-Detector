import pandas as pd
import MetaTrader5 as mt5
import logging
from config_handler import TimeFrame

class TimeframeUtils:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def is_candle_closed(self, candle_time: pd.Timestamp, timeframe: TimeFrame) -> bool:
        """Check if a candle has closed by comparing its start time with current broker time."""
        try:
            current_tick = mt5.symbol_info_tick("EURUSDm")
            if current_tick is None:
                self.logger.error("Failed to get server time from MT5")
                return False
                
            current_time = pd.Timestamp.fromtimestamp(current_tick.time)
            candle_time = pd.Timestamp(candle_time)

            if timeframe == TimeFrame.MONTHLY:
                if candle_time.month == 12:
                    next_candle = candle_time.replace(year=candle_time.year + 1, month=1, day=1)
                else:
                    next_candle = candle_time.replace(month=candle_time.month + 1, day=1)
                
            elif timeframe == TimeFrame.WEEKLY:
                next_candle = candle_time + pd.Timedelta(days=(7 - candle_time.weekday()))
                next_candle = next_candle.replace(hour=0, minute=0, second=0, microsecond=0)
                
            elif timeframe == TimeFrame.DAILY:
                next_candle = candle_time + pd.Timedelta(days=1)
                next_candle = next_candle.replace(hour=0, minute=0, second=0, microsecond=0)
                
            elif timeframe == TimeFrame.H4:
                current_block = candle_time.hour // 4
                next_hour = (current_block + 1) * 4
                if next_hour >= 24:
                    next_candle = candle_time + pd.Timedelta(days=1)
                    next_candle = next_candle.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    next_candle = candle_time.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            
            return current_time >= next_candle
            
        except Exception as e:
            self.logger.error(f"Error checking candle closure: {e}")
            return False