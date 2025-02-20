import MetaTrader5 as mt5
import logging
from datetime import datetime
import time
from pathlib import Path
from dotenv import load_dotenv
import os
import atexit
import signal
from market_analyzer import MarketAnalyzer
from time_sync import TimeSync

def setup_logging():
    """Setup logging configuration"""
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/fvg_detector_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )

def initialize_mt5():
    """Initialize MT5 with credentials from environment variables"""
    max_retries = 3
    retry_delay = 30  # seconds
    
    # Get credentials and path from environment variables
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    mt5_path = os.getenv("MT5_PATH")
    
    # Validate credentials and path
    if not all([login, password, server, mt5_path]):
        logging.error("MT5 credentials or path not properly configured in .env file")
        return False
    
    # Convert login to integer as required by MT5
    try:
        login = int(login)
    except ValueError:
        logging.error("MT5_LOGIN must be a number")
        return False
    
    for attempt in range(max_retries):
        try:
            # Initialize MT5 with the specified path
            if not mt5.initialize(path=mt5_path):
                raise Exception(f"Failed to initialize MT5: {mt5.last_error()}")
            
            # Attempt login
            if not mt5.login(
                login=login,
                password=password,
                server=server
            ):
                raise Exception(f"Failed to login: {mt5.last_error()}")
            
            logging.info("Successfully connected to MT5")
            return True
                
        except Exception as e:
            logging.error(f"MT5 initialization attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logging.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                
    return False

def cleanup_cache():
    """Clean up cache files on program exit"""
    try:
        cache_dir = Path("cache")
        if cache_dir.exists():
            for cache_file in cache_dir.glob('fvg_alerts_*.json'):
                try:
                    cache_file.unlink()
                    logging.info(f"Removed cache file: {cache_file}")
                except Exception as e:
                    logging.error(f"Error removing cache file {cache_file}: {e}")
    except Exception as e:
        logging.error(f"Error during cache cleanup: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logging.info("Shutdown signal received. Cleaning up...")
    cleanup_cache()
    mt5.shutdown()  # Added MT5 shutdown
    exit(0)

def main():
    load_dotenv()
    setup_logging()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup_cache)
    
    try:
        Path("cache").mkdir(exist_ok=True, mode=0o755)
    except Exception as e:
        logging.error(f"Failed to create cache directory: {e}")
        return

    if not initialize_mt5():
        return

    # Initialize time synchronization
    time_sync = TimeSync()
    time_sync.calculate_time_offset()

    try:
        analyzer = MarketAnalyzer(time_sync)
    except ValueError as e:
        logging.error(f"Failed to initialize analyzer: {e}")
        mt5.shutdown()
        return

    while True:
        try:
            analyzer.analyze_markets()
            logging.info("Analysis cycle completed. Waiting for 5 minutes...")
            time.sleep(300)
        except KeyboardInterrupt:
            logging.info("Manual shutdown initiated. Cleaning up...")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")
            logging.info("Retrying in 60 seconds...")
            time.sleep(60)
            continue
    
    mt5.shutdown()

if __name__ == "__main__":
    main()