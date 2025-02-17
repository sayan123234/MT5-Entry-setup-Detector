import MetaTrader5 as mt5
import logging
from datetime import datetime
from market_analyzer import MarketAnalyzer
import time
from pathlib import Path
from dotenv import load_dotenv
import os
import atexit
import signal

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

def initialize_mt5() -> bool:
    """Initialize MT5 connection"""
    if not mt5.initialize():
        logging.error(f"Failed to initialize MT5: {mt5.last_error()}")
        return False
        
    account = int(os.getenv("MT5_LOGIN"))
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    
    if not mt5.login(account, password=password, server=server):
        logging.error(f"Failed to login: {mt5.last_error()}")
        return False
        
    return True

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
    exit(0)

def main():
    load_dotenv()
    setup_logging()
    Path("cache").mkdir(exist_ok=True)
    
    # Register cleanup handlers
    atexit.register(cleanup_cache)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not initialize_mt5():
        return
        
    analyzer = MarketAnalyzer()
    
    try:
        while True:
            analyzer.analyze_markets()
            logging.info("Analysis cycle completed. Waiting for 5 minutes...")
            time.sleep(300)  # 5 minute interval
            
    except KeyboardInterrupt:
        logging.info("Manual shutdown initiated. Cleaning up...")
        # Cleanup will be handled by signal_handler
        
    except Exception as e:
        logging.error(f"Error in main loop: {str(e)}")
        logging.info("Retrying in 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main()