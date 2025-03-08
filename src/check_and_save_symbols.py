import os
import csv
import logging
import MetaTrader5 as mt5
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

def initialize_mt5_from_env() -> Tuple[bool, str]:
    """
    Initialize MT5 using credentials from environment variables.
    
    Returns:
        Tuple[bool, str]: Success status and error message if any
    """
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
    if not mt5.initialize(path=mt5_path, login=login_int, password=password, server=server):
        return False, f"Failed to initialize MT5: {mt5.last_error()}"
    
    return True, ""

def fetch_mt5_symbols() -> Optional[List]:
    """
    Fetch all available symbols from MetaTrader 5.
    
    Returns:
        Optional[List]: List of symbols or None if failed
    """
    try:
        symbols = mt5.symbols_get()
        if symbols is None or len(symbols) == 0:
            logger.warning("No symbols found in MT5")
            return None
        return symbols
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        return None

def save_symbols_to_csv(symbols: List, csv_filename: str = "mt5_symbols.csv") -> bool:
    """
    Save symbols to a CSV file.
    
    Args:
        symbols: List of MT5 symbol objects
        csv_filename: Output CSV filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        output_path = Path(csv_filename)
        output_path.parent.mkdir(exist_ok=True)
        
        # Write to CSV
        with open(output_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Symbol", "Description", "Path", "Spread", "Point", "Digits"])
            
            for symbol in symbols:
                writer.writerow([
                    symbol.name, 
                    symbol.description, 
                    symbol.path,
                    getattr(symbol, 'spread', 'N/A'),
                    getattr(symbol, 'point', 'N/A'),
                    getattr(symbol, 'digits', 'N/A')
                ])
        
        logger.info(f"Saved {len(symbols)} symbols to {csv_filename}")
        return True
    except Exception as e:
        logger.error(f"Error saving symbols to CSV: {e}")
        return False

def fetch_mt5_symbols_to_csv(csv_filename: str = "mt5_symbols.csv") -> bool:
    """
    Fetch all available symbols from MetaTrader 5 and save them to a CSV file.
    
    Args:
        csv_filename: Output CSV filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Setup logging if running as main script
    if logger.level == logging.NOTSET:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    try:
        # Initialize MT5
        success, error_msg = initialize_mt5_from_env()
        if not success:
            logger.error(error_msg)
            return False
        
        # Fetch symbols
        symbols = fetch_mt5_symbols()
        if not symbols:
            mt5.shutdown()
            return False
        
        # Save to CSV
        result = save_symbols_to_csv(symbols, csv_filename)
        
        # Shutdown MT5
        mt5.shutdown()
        return result
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if mt5.terminal_info() is not None:
            mt5.shutdown()
        return False

if __name__ == "__main__":
    success = fetch_mt5_symbols_to_csv()
    exit(0 if success else 1)
