import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import logging

class TimeSync:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._time_offset = None

    def calculate_time_offset(self) -> None:
        """
        Calculate the time offset between local time and broker server time.
        This should be called during initialization and periodically to maintain accuracy.
        """
        try:
            # Get current broker server time
            server_time = mt5.symbol_info_tick("EURUSDm").time
            if server_time is None:
                self.logger.error("Failed to get server time from MT5")
                return
                
            # Convert server time to pandas Timestamp (server time is in seconds since epoch)
            server_timestamp = pd.Timestamp.fromtimestamp(server_time)
            local_timestamp = pd.Timestamp.now()
            
            # Calculate offset
            self._time_offset = server_timestamp - local_timestamp
            self.logger.info(f"Time offset calculated: {self._time_offset}")
            
        except Exception as e:
            self.logger.error(f"Error calculating time offset: {e}")
            self._time_offset = None

    def get_current_broker_time(self) -> pd.Timestamp:
        """
        Get the current broker time, using the calculated offset.
        If offset calculation failed, falls back to MT5 server time.
        """
        try:
            if self._time_offset is not None:
                return pd.Timestamp.now() + self._time_offset
            else:
                # Fallback to direct server time if offset isn't available
                server_time = mt5.symbol_info_tick("EURUSDm").time
                return pd.Timestamp.fromtimestamp(server_time)
        except Exception as e:
            self.logger.error(f"Error getting broker time: {e}")
            # If all else fails, return local time but log the error
            return pd.Timestamp.now()

    def is_candle_closed(self, candle_time: pd.Timestamp) -> bool:
        """
        Check if a candle has closed by comparing its timestamp with current broker time.
        """
        try:
            broker_time = self.get_current_broker_time()
            return candle_time < broker_time
        except Exception as e:
            self.logger.error(f"Error checking candle closure: {e}")
            # In case of error, be conservative and return False
            return False