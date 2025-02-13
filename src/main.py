import MetaTrader5 as mt5
import logging
from datetime import datetime
from market_analyzer import MarketAnalyzer
from config_handler import ConfigHandler
import time
from pathlib import Path
from dotenv import load_dotenv
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/fvg_detector_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

def initialize_mt5():
    """Initialize MT5 connection"""
    if not mt5.initialize():
        logging.error(f"Failed to initialize MT5: {mt5.last_error()}")
        return False
        
    # MT5 login credentials from environment variables
    account = int(os.getenv("MT5_ACCOUNT"))
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    
    if not mt5.login(account, password=password, server=server):
        logging.error(f"Failed to login: {mt5.last_error()}")
        return False
        
    return True

def main():
    # Load environment variables
    load_dotenv()
    
    # Create necessary directories
    Path("logs").mkdir(exist_ok=True)
    
    # Initialize MT5
    if not initialize_mt5():
        return
        
    try:
        analyzer = MarketAnalyzer()
        
        while True:
            try:
                analyzer.analyze_markets()
                time.sleep(300)  # 5 minute interval
                
            except KeyboardInterrupt:
                logging.info("Shutting down...")
                break
                
            except Exception as e:
                logging.error(f"Error in main loop: {str(e)}")
                time.sleep(60)  # Wait before retrying
                
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()