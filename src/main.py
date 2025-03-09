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
from typing import List, Optional, Dict

from src.core.market_analyzer import MarketAnalyzer
from src.core.trading_strategy import TradingStrategy
from src.utils.time_sync import TimeSync
from src.utils.helpers import is_trading_day
from src.services.mt5_service import mt5_service
from src.config.config_handler import ConfigHandler

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
    if not mt5_service.is_connected():
        logger.warning("MT5 connection lost. Attempting to reconnect...")
        success, error_msg = mt5_service.initialize()
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
    mt5_service.shutdown()
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

def analyze_single_symbol(symbol: str, config: ConfigHandler, time_sync: TimeSync) -> None:
    """
    Perform detailed analysis on a single symbol using the trading strategy framework.
    
    Args:
        symbol: Symbol to analyze
        config: Configuration handler
        time_sync: Time synchronization handler
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting detailed analysis for {symbol}")
    
    try:
        # Initialize trading strategy
        strategy = TradingStrategy(config=config)
        
        # Generate trade plan
        trade_plan = strategy.generate_trade_plan(symbol)
        
        if trade_plan.get("status") == "complete":
            # Log trade plan details
            logger.info(f"Trade plan generated for {symbol}")
            logger.info(f"Bias: {trade_plan['overall_bias']['bias']} with {trade_plan['overall_bias']['confidence']:.1f}% confidence")
            
            if trade_plan.get("entry_strategy") == "enter_now":
                logger.info(f"Entry strategy: Enter now at {trade_plan.get('entry_price')}")
            else:
                logger.info(f"Entry strategy: {trade_plan.get('entry_strategy')}")
                
            logger.info(f"Target: {trade_plan.get('target_price')}")
            logger.info(f"Stop loss: {trade_plan.get('stop_loss_price')}")
            logger.info(f"Risk-reward ratio: {trade_plan.get('risk_reward_ratio'):.2f}")
            
            # Send detailed trade plan alert
            send_trade_plan_alert(trade_plan)
        else:
            logger.info(f"No favorable trade setup found for {symbol}: {trade_plan.get('message')}")
            
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)

def send_trade_plan_alert(trade_plan: Dict) -> None:
    """
    Send a detailed trade plan alert via Telegram.
    
    Args:
        trade_plan: Dictionary with trade plan details
    """
    from src.services.telegram_service import send_telegram_alert
    
    symbol = trade_plan["symbol"]
    bias = trade_plan["overall_bias"]["bias"]
    confidence = trade_plan["overall_bias"]["confidence"]
    
    # Determine emoji based on bias
    bias_emoji = "📈" if bias == "bullish" else "📉" if bias == "bearish" else "↔️"
    
    # Build message
    message = (
        f"{bias_emoji} Trade Plan: {symbol}\n"
        f"📊 Bias: {bias.capitalize()} ({confidence:.1f}%)\n"
        f"⏱️ Entry Timeframe: {trade_plan['entry_timeframe']}\n"
    )
    
    # Add entry strategy
    entry_strategy = trade_plan.get("entry_strategy", "wait")
    if entry_strategy == "enter_now":
        message += f"✅ Entry: Enter now at {trade_plan['entry_price']:.5f}\n"
    elif entry_strategy == "wait_for_confirmation":
        message += f"⏳ Entry: Wait for confirmation\n"
    elif entry_strategy == "wait_for_reversal":
        message += f"⏳ Entry: Wait for reversal confirmation\n"
    else:
        message += f"⏳ Entry: {entry_strategy}\n"
    
    # Add target and stop loss
    if trade_plan.get("target_price"):
        message += f"🎯 Target: {trade_plan['target_price']:.5f}\n"
    if trade_plan.get("stop_loss_price"):
        message += f"🛑 Stop Loss: {trade_plan['stop_loss_price']:.5f}\n"
    
    # Add risk-reward and breakeven
    if trade_plan.get("risk_reward_ratio"):
        message += f"⚖️ Risk-Reward: 1:{trade_plan['risk_reward_ratio']:.2f}\n"
    if trade_plan.get("breakeven_price"):
        message += f"🔒 Breakeven: {trade_plan['breakeven_price']:.5f}\n"
    if trade_plan.get("breakeven_rule"):
        message += f"📝 Breakeven Rule: {trade_plan['breakeven_rule']}\n"
    
    # Add description
    if trade_plan.get("description"):
        message += f"\n📋 Analysis:\n{trade_plan['description']}"
    
    # Send the alert
    try:
        send_telegram_alert(message)
        logging.getLogger(__name__).info(f"Sent trade plan alert for {symbol}")
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to send trade plan alert: {e}")

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
    success, error_msg = mt5_service.initialize()
    if not success:
        logger.error(f"MT5 initialization failed: {error_msg}")
        return

    # Wait briefly to ensure MT5 connection stabilizes
    logger.info(f"Waiting {MT5_STABILIZE_WAIT}s for MT5 to stabilize...")
    time.sleep(MT5_STABILIZE_WAIT)

    # Initialize configuration
    logger.info("Initializing configuration...")
    config = ConfigHandler()
    
    # Initialize time synchronization
    logger.info("Initializing time synchronization...")
    time_sync = TimeSync(config=config)
    if time_sync._time_offset is None:
        logger.warning("Failed to synchronize time with MT5; proceeding with local time")
    else:
        logger.info(f"Time synchronized with broker. Offset: {time_sync._time_offset}")
    
    # Initialize market analyzer with proper dependency injection
    try:
        logger.info("Initializing market analyzer...")
        analyzer = MarketAnalyzer(time_sync=time_sync, config=config)
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
            
            # Run detailed analysis on selected symbols
            if config.config.get("detailed_analysis", {}).get("enabled", False):
                detailed_symbols = config.config.get("detailed_analysis", {}).get("symbols", [])
                if detailed_symbols:
                    logger.info(f"Running detailed analysis on {len(detailed_symbols)} symbols")
                    for symbol in detailed_symbols:
                        analyze_single_symbol(symbol, config, time_sync)
            
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
