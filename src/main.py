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
import sys
from typing import List, Optional
from market_analyzer import MarketAnalyzer
from time_sync import TimeSync
from utils import is_trading_day
from check_and_save_symbols import initialize_mt5_from_env

# Constants
LOG_DIR = "logs"
CACHE_DIR = "cache"
ANALYSIS_INTERVAL = 300  # 5 minutes
WEEKEND_SLEEP = 3600  # 1 hour
RECONNECT_WAIT = 60  # 1 minute
MT5_STABILIZE_WAIT = 2  # 2 seconds

# Initialize logger at module level
logger = logging.getLogger(__name__)

def setup_logging(log_level: int = logging.INFO) -> None:
    """
    Setup logging configuration with daily rotation.
    
    Args:
        log_level: Logging level (default: INFO)
    """
    try:
        Path(LOG_DIR).mkdir(exist_ok=True)
        
        # File handler with rotation
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=f'{LOG_DIR}/fvg_detector.log',
            when='midnight',
            interval=1,
            backupCount=7
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            handlers=[file_handler, console_handler]
        )
        
        logger.info("Logging initialized")
    except Exception as e:
        print(f"Error setting up logging: {e}")
        sys.exit(1)

def check_mt5_connection() -> bool:
    """
    Check MT5 connection status and attempt reconnection if lost.
    
    Returns:
        bool: True if connected, False otherwise
    """
    if not mt5.terminal_info():
        logger.warning("MT5 connection lost. Attempting to reconnect...")
        success, error_msg = initialize_mt5_from_env()
        if success:
            logger.info("MT5 connection restored")
            return True
        else:
            logger.error(f"Failed to restore MT5 connection: {error_msg}")
            return False
    return True

def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}. Shutting down...")
        cleanup()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register cleanup on normal exit
    atexit.register(cleanup)

def cleanup() -> None:
    """Perform cleanup operations before exit"""
    logger.info("Performing cleanup...")
    if mt5.terminal_info():
        mt5.shutdown()
    logger.info("Cleanup completed")

def check_unavailable_symbols(analyzer: MarketAnalyzer) -> List[str]:
    """
    Check for unavailable symbols in the watchlist.
    
    Args:
        analyzer: Initialized MarketAnalyzer instance
        
    Returns:
        List of unavailable symbols
    """
    unavailable = []
    for symbol in analyzer.config.get_watchlist_symbols():
        if mt5.symbol_info(symbol) is None:
            unavailable.append(symbol)
    
    if unavailable:
        logger.warning(f"These symbols are unavailable in MT5: {', '.join(unavailable)}")
    
    return unavailable

def main() -> None:
    """Main application entry point"""
    # Load environment variables
    load_dotenv(override=True)
    
    # Setup logging and signal handlers
    setup_logging()
    setup_signal_handlers()
    
    # Create necessary directories
    try:
        Path(CACHE_DIR).mkdir(exist_ok=True, mode=0o755)
    except Exception as e:
        logger.error(f"Failed to create cache directory: {e}")
        return

    # Initialize MT5
    success, error_msg = initialize_mt5_from_env()
    if not success:
        logger.error(f"MT5 initialization failed: {error_msg}")
        return

    # Wait briefly to ensure MT5 connection stabilizes
    logger.info(f"Waiting {MT5_STABILIZE_WAIT}s for MT5 to stabilize...")
    time.sleep(MT5_STABILIZE_WAIT)

    # Initialize time synchronization
    time_sync = TimeSync()
    if time_sync._time_offset is None:
        logger.warning("Failed to synchronize time with MT5; proceeding with local time")
    else:
        logger.info(f"Time synchronized with broker. Offset: {time_sync._time_offset}")
    
    # Initialize market analyzer
    try:
        logger.info("Initializing market analyzer...")
        analyzer = MarketAnalyzer(time_sync)
        check_unavailable_symbols(analyzer)
        logger.info("Market analyzer initialized successfully")
    except ValueError as e:
        logger.error(f"Failed to initialize analyzer: {e}")
        cleanup()
        return

    # Main analysis loop
    logger.info("Starting main analysis loop")
    while True:
        try:
            # Check MT5 connection
            if not check_mt5_connection():
                logger.info(f"Waiting {RECONNECT_WAIT}s before retrying due to MT5 connection failure...")
                time.sleep(RECONNECT_WAIT)
                continue
                
            # Check if it's a trading day
            if not is_trading_day():
                logger.info(f"Weekend detected. Sleeping for {WEEKEND_SLEEP}s...")
                time.sleep(WEEKEND_SLEEP)
                continue
                
            # Run analysis
            logger.info("Starting market analysis cycle...")
            analyzer.analyze_markets()
            logger.info(f"Analysis cycle completed. Waiting for {ANALYSIS_INTERVAL}s...")
            time.sleep(ANALYSIS_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Manual shutdown initiated")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)
            logger.info(f"Retrying in {RECONNECT_WAIT}s...")
            time.sleep(RECONNECT_WAIT)
    
    # Final cleanup
    cleanup()

if __name__ == "__main__":
    main()
