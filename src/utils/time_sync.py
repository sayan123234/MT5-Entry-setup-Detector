import MetaTrader5 as mt5
from datetime import datetime
import logging
import time
import pandas as pd
from typing import Optional
from src.config.config_handler import ConfigHandler, TimeFrame

class TimeSync:
    def __init__(self, config: ConfigHandler = None):
        """
        Initialize time synchronization with MT5.
        
        Args:
            config: ConfigHandler instance (will create one if None)
        """
        self.logger = logging.getLogger(__name__)
        self._time_offset = None
        self.config = config or ConfigHandler()
        self.symbol = self._get_reference_symbol()
        self.calculate_time_offset()

    def _get_reference_symbol(self) -> str:
        """Get first available symbol for time checks"""
        symbols = self.config.get_watchlist_symbols()
        for symbol in symbols:
            if mt5.symbol_info(symbol) is not None:
                return symbol
        
        # Fallback to a common symbol
        fallback = "EURUSD.sml"
        self.logger.warning(f"No configured symbols available; using fallback '{fallback}'")
        return fallback

    def calculate_time_offset(self) -> None:
        """Calculate the offset between local and server time with retries"""
        max_retries = 5
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None:
                    raise Exception(f"Failed to get tick data for {self.symbol}")
                
                server_time = tick.time
                server_dt = datetime.fromtimestamp(server_time)
                local_dt = datetime.now()
                self._time_offset = server_dt - local_dt
                self.logger.info(f"Time offset calculated: {self._time_offset}")
                return
                
            except Exception as e:
                self.logger.error(f"Failed to get server time from MT5 on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        
        self.logger.error("Failed to calculate time offset after all retries")
        self._time_offset = None

    def get_current_broker_time(self) -> datetime:
        """Get current broker time, falling back to local time if MT5 fails"""
        try:
            if self._time_offset is not None:
                return datetime.now() + self._time_offset
            else:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is not None:
                    return datetime.fromtimestamp(tick.time)
                self.logger.warning(f"Tick data unavailable for {self.symbol}; falling back to local time")
                return datetime.now()
        except Exception as e:
            self.logger.error(f"Error getting broker time: {e}")
            return datetime.now()
            
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
        """Check if a candle is closed based on current broker time"""
        try:
            current_time = pd.Timestamp(self.get_current_broker_time())
            next_candle = self.get_next_candle_time(pd.Timestamp(candle_time), timeframe)
            
            if next_candle is None:
                return False
                
            return current_time >= next_candle
            
        except Exception as e:
            self.logger.error(f"Error checking candle closure: {e}")
            return False
