import pandas as pd
import MetaTrader5 as mt5
import logging
from config_handler import TimeFrame,ConfigHandler

class TimeframeUtils:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = ConfigHandler()

    def get_reference_symbol(self) -> str:
        """Get first available symbol for time checks"""
        for symbol in self.config.get_watchlist_symbols():
            if mt5.symbol_info(symbol) is not None:
                return symbol
        raise RuntimeError("No valid symbols available for time sync")

    def get_next_candle_time(self, candle_time: pd.Timestamp, timeframe: TimeFrame) -> pd.Timestamp:
        """Calculate the start time of the next candle based on timeframe."""
        try:
            if timeframe == TimeFrame.MONTHLY:
                if candle_time.month == 12:
                    return candle_time.replace(year=candle_time.year + 1, month=1, day=1)
                return candle_time.replace(month=candle_time.month + 1, day=1)
                
            elif timeframe == TimeFrame.WEEKLY:
                next_candle = candle_time + pd.Timedelta(days=(7 - candle_time.weekday()))
                return next_candle.replace(hour=0, minute=0, second=0, microsecond=0)
                
            elif timeframe == TimeFrame.DAILY:
                next_candle = candle_time + pd.Timedelta(days=1)
                return next_candle.replace(hour=0, minute=0, second=0, microsecond=0)
                
            elif timeframe == TimeFrame.H4:
                current_block = candle_time.hour // 4
                next_hour = (current_block + 1) * 4
                if next_hour >= 24:
                    next_candle = candle_time + pd.Timedelta(days=1)
                    return next_candle.replace(hour=0, minute=0, second=0, microsecond=0)
                return candle_time.replace(hour=next_hour, minute=0, second=0, microsecond=0)
                
            elif timeframe == TimeFrame.H1:
                next_hour = (candle_time.hour + 1) % 24
                if next_hour == 0:
                    next_candle = candle_time + pd.Timedelta(days=1)
                    return next_candle.replace(hour=0, minute=0, second=0, microsecond=0)
                return candle_time.replace(hour=next_hour, minute=0, second=0, microsecond=0)
                
            elif timeframe in [TimeFrame.M15, TimeFrame.M5, TimeFrame.M1]:
                minutes_map = {
                    TimeFrame.M15: 15,
                    TimeFrame.M5: 5,
                    TimeFrame.M1: 1
                }
                minutes_interval = minutes_map[timeframe]
                current_block = candle_time.minute // minutes_interval
                next_minute = (current_block + 1) * minutes_interval
                
                if next_minute >= 60:
                    return self.get_next_candle_time(
                        candle_time.replace(minute=0) + pd.Timedelta(hours=1),
                        TimeFrame.H1
                    )
                return candle_time.replace(minute=next_minute, second=0, microsecond=0)
                
        except Exception as e:
            self.logger.error(f"Error calculating next candle time: {e}")
            return None

    def is_candle_closed(self, candle_time: pd.Timestamp, timeframe: TimeFrame) -> bool:
        try:
            symbol = self.get_reference_symbol()  # Use new method instead of hardcoded EURUSDm
            current_tick = mt5.symbol_info_tick(symbol)
            if current_tick is None:
                self.logger.error("Failed to get server time from MT5")
                return False
                
            current_time = pd.Timestamp.fromtimestamp(current_tick.time)
            next_candle = self.get_next_candle_time(pd.Timestamp(candle_time), timeframe)
            
            if next_candle is None:
                return False
                
            return current_time >= next_candle
            
        except Exception as e:
            self.logger.error(f"Error checking candle closure: {e}")
            return False