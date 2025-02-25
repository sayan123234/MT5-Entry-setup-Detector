import MetaTrader5 as mt5
from datetime import datetime
import logging
import time
from config_handler import ConfigHandler

class TimeSync:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._time_offset = None
        config = ConfigHandler()
        symbols = config.get_watchlist_symbols()
        # Select first available symbol
        self.symbol = None
        for symbol in symbols:
            if mt5.symbol_info(symbol) is not None:
                self.symbol = symbol
                break
        if not self.symbol:
            self.symbol = "EURUSD"  # Fallback
            self.logger.warning("No configured symbols available; using fallback 'EURUSD'")
        self.calculate_time_offset()

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