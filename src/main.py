import MetaTrader5 as mt5
import logging
import logging.handlers
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
    """Setup logging configuration with daily rotation"""
    Path("logs").mkdir(exist_ok=True)
    handler = logging.handlers.TimedRotatingFileHandler(
        filename='logs/fvg_detector.log',
        when='midnight',
        interval=1,
        backupCount=7
    )
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler, logging.StreamHandler()]
    )

def initialize_mt5():
    """Initialize MT5 with credentials from environment variables"""
    max_retries = 3
    retry_delay = 30
    
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    mt5_path = os.getenv("MT5_PATH")
    
    if not all([login, password, server, mt5_path]):
        logging.error("MT5 credentials or path not properly configured in .env file")
        return False
    
    try:
        login = int(login)
    except ValueError:
        logging.error("MT5_LOGIN must be a number")
        return False
    
    for attempt in range(max_retries):
        try:
            if not mt5.initialize(path=mt5_path):
                raise Exception(f"Failed to initialize MT5: {mt5.last_error()}")
            if not mt5.login(login=login, password=password, server=server):
                raise Exception(f"Failed to login: {mt5.last_error()}")
            logging.info("Successfully connected to MT5")
            return True
        except Exception as e:
            logging.error(f"MT5 initialization attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logging.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
    return False

def check_mt5_connection():
    """Check MT5 connection status and attempt reconnection if lost"""
    if not mt5.terminal_info():
        logging.warning("MT5 connection lost. Attempting to reconnect...")
        if initialize_mt5():
            logging.info("MT5 connection restored")
            return True
        else:
            logging.error("Failed to restore MT5 connection")
            return False
    return True

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logging.info("Shutdown signal received. Cleaning up...")
    mt5.shutdown()
    exit(0)

def main():
    load_dotenv(override=True)
    setup_logging()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        Path("cache").mkdir(exist_ok=True, mode=0o755)
    except Exception as e:
        logging.error(f"Failed to create cache directory: {e}")
        return

    if not initialize_mt5():
        return

    # Wait briefly to ensure MT5 connection stabilizes
    time.sleep(2)  # Give MT5 time to load symbol data

    time_sync = TimeSync()
    if time_sync._time_offset is None:
        logging.error("Failed to synchronize time with MT5; proceeding with local time")
    
    try:
        analyzer = MarketAnalyzer(time_sync)
        unavailable_symbols = [s for s in analyzer.config.get_watchlist_symbols() 
                             if mt5.symbol_info(s) is None]
        if unavailable_symbols:
            logging.warning(f"These symbols are unavailable in MT5: {unavailable_symbols}")
    except ValueError as e:
        logging.error(f"Failed to initialize analyzer: {e}")
        mt5.shutdown()
        return

    while True:
        try:
            if not check_mt5_connection():
                logging.info("Waiting 60 seconds before retrying due to MT5 connection failure...")
                time.sleep(60)
                continue
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