import MetaTrader5 as mt5
from datetime import datetime
import logging

class TimeSync:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._time_offset = None
        self.symbol = "EURUSDm"  # Use your most liquid symbol

    def calculate_time_offset(self) -> None:
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                self.logger.error("Failed to get server time from MT5")
                return
                
            server_time = tick.time
            server_dt = datetime.fromtimestamp(server_time)
            local_dt = datetime.now()
            self._time_offset = server_dt - local_dt
            self.logger.info(f"Time offset calculated: {self._time_offset}")
            
        except Exception as e:
            self.logger.error(f"Error calculating time offset: {e}")
            self._time_offset = None

    def get_current_broker_time(self) -> datetime:
        try:
            if self._time_offset is not None:
                return datetime.now() + self._time_offset
            else:
                tick = mt5.symbol_info_tick(self.symbol)
                return datetime.fromtimestamp(tick.time)
        except Exception as e:
            self.logger.error(f"Error getting broker time: {e}")
            return datetime.now()