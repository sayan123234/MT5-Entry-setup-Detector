import os
import logging
import MetaTrader5 as mt5
from dotenv import load_dotenv
from typing import List, Optional, Tuple, Dict, Any
import pandas as pd
from functools import lru_cache
from src.utils.helpers import mt5_operation_with_timeout

class MT5Service:
    """
    Service for interacting with MetaTrader 5.
    
    This class handles:
    - MT5 initialization and connection
    - Rate data retrieval with caching
    - Symbol information
    """
    
    def __init__(self):
        """Initialize the MT5 service."""
        self.logger = logging.getLogger(__name__)
        self.initialized = False
        
    def initialize(self) -> Tuple[bool, str]:
        """
        Initialize MT5 using credentials from environment variables.
        
        Returns:
            Tuple[bool, str]: Success status and error message if any
        """
        if self.initialized and mt5.terminal_info():
            return True, ""
            
        # Load environment variables
        load_dotenv(override=True)
        
        # Get credentials from environment
        login = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")
        mt5_path = os.getenv("MT5_PATH")
        
        # Validate credentials
        if not all([login, password, server, mt5_path]):
            return False, "MT5 credentials or path not properly configured in .env file"
        
        try:
            login_int = int(login)
        except ValueError:
            return False, "MT5_LOGIN must be a number"
        
        # Initialize MT5
        try:
            if not mt5.initialize(path=mt5_path, login=login_int, password=password, server=server):
                return False, f"Failed to initialize MT5: {mt5.last_error()}"
                
            self.initialized = True
            return True, ""
        except Exception as e:
            return False, f"Exception during MT5 initialization: {str(e)}"
    
    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        if self.initialized:
            mt5.shutdown()
            self.initialized = False
            self.logger.info("MT5 connection closed")
    
    def is_connected(self) -> bool:
        """Check if MT5 is connected."""
        return self.initialized and mt5.terminal_info() is not None
    
    @mt5_operation_with_timeout("get_symbols")
    def get_symbols(self) -> Optional[List[str]]:
        """
        Get all available symbols from MT5.
        
        Returns:
            Optional[List[str]]: List of symbol names or None if failed
        """
        try:
            if not self.is_connected():
                success, msg = self.initialize()
                if not success:
                    self.logger.error(f"Failed to initialize MT5: {msg}")
                    return None
                    
            symbols = mt5.symbols_get()
            if symbols is None or len(symbols) == 0:
                self.logger.warning("No symbols found in MT5")
                return None
                
            return [symbol.name for symbol in symbols]
        except Exception as e:
            self.logger.error(f"Error fetching symbols: {e}")
            return None
    
    @mt5_operation_with_timeout("get_symbol_info")
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Optional[Dict[str, Any]]: Symbol information or None if not found
        """
        try:
            if not self.is_connected():
                success, msg = self.initialize()
                if not success:
                    self.logger.error(f"Failed to initialize MT5: {msg}")
                    return None
                    
            info = mt5.symbol_info(symbol)
            if info is None:
                return None
                
            # Convert to dictionary
            result = {}
            for prop in dir(info):
                if not prop.startswith('_'):
                    try:
                        result[prop] = getattr(info, prop)
                    except:
                        pass
                        
            return result
        except Exception as e:
            self.logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None
    
    @lru_cache(maxsize=100)
    @mt5_operation_with_timeout("get_rates")
    def get_rates(self, symbol: str, timeframe: int, count: int = 100) -> Optional[pd.DataFrame]:
        """
        Get historical rates for a symbol.
        
        Args:
            symbol: Symbol name
            timeframe: MT5 timeframe constant
            count: Number of candles to retrieve
            
        Returns:
            Optional[pd.DataFrame]: DataFrame with OHLC data or None if failed
        """
        try:
            if not self.is_connected():
                success, msg = self.initialize()
                if not success:
                    self.logger.error(f"Failed to initialize MT5: {msg}")
                    return None
                    
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is None:
                self.logger.error(f"Failed to get rates for {symbol}")
                return None
                
            df = pd.DataFrame(rates)
            if len(df) < count * 0.8:
                self.logger.warning(f"Insufficient data for {symbol}")
                
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            self.logger.error(f"Error getting rates for {symbol}: {e}")
            return None
    
    def clear_rate_cache(self) -> None:
        """Clear the rate data cache."""
        self.get_rates.cache_clear()
        self.logger.debug("Rate cache cleared")

# Singleton instance for global use
mt5_service = MT5Service()
