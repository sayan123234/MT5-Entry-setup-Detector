from typing import Dict
import logging
from datetime import datetime
from config_handler import TimeFrame, ConfigHandler
from fvg_finder import FVGFinder
from utils import send_telegram_alert

class MarketAnalyzer:
    def __init__(self):
        self.config = ConfigHandler()
        self.fvg_finder = FVGFinder()
        self.logger = logging.getLogger(__name__)
        self.signal_cache = {}  # Format: {symbol_timeframe: timestamp}
    
    def is_duplicate_signal(self, symbol: str, timeframe: TimeFrame) -> bool:
        """Check if we've already sent a signal for this symbol/timeframe today"""
        key = f"{symbol}_{timeframe.name}"
        if key in self.signal_cache:
            last_signal_time = self.signal_cache[key]
            now = datetime.now()
            return (last_signal_time.date() == now.date())
        return False
    
    def update_signal_cache(self, symbol: str, timeframe: TimeFrame):
        """Update the signal cache with current timestamp"""
        key = f"{symbol}_{timeframe.name}"
        self.signal_cache[key] = datetime.now()

    def analyze_markets(self):
        """Analyze all symbols across timeframes"""
        available_symbols = self.config.get_watchlist_symbols()
        
        if not available_symbols:
            return
        
        for symbol in available_symbols:
            try:
                self.analyze_symbol(symbol)
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {str(e)}")
                continue
    
    def analyze_symbol(self, symbol: str):
        """Analyze a single symbol through timeframe hierarchy"""
        for timeframe in [TimeFrame.MONTHLY, TimeFrame.WEEKLY, 
                         TimeFrame.DAILY, TimeFrame.H4]:
            
            if self.is_duplicate_signal(symbol, timeframe):
                continue
            
            analysis = self.fvg_finder.analyze_timeframe(symbol, timeframe)
            
            if analysis and 'fvg' in analysis:
                self.logger.info(f"Found FVG for {symbol} on {timeframe.name}")
                self.process_results(symbol, timeframe, analysis)
                break
    
    def process_results(self, symbol: str, timeframe: TimeFrame, analysis: Dict):
        """Process and notify analysis results"""
        try:
            alert_data = {
                'symbol': symbol,
                'timeframe': timeframe.name,
                'analysis': analysis
            }
            
            message = self.format_alert_message(alert_data)
            if send_telegram_alert(message):
                self.logger.info(f"Alert sent for {symbol}")
            else:
                self.logger.error(f"Failed to send alert for {symbol}")
            
            self.update_signal_cache(symbol, timeframe)
                
        except Exception as e:
            self.logger.error(f"Error processing results for {symbol}: {str(e)}")
    
    def format_alert_message(self, data: Dict) -> str:
        """Format alert message for Telegram"""
        try:
            msg = f"🔍 FVG Alert for {data['symbol']}\n"
            msg += f"Timeframe: {data['timeframe']}\n\n"
            
            fvg = data['analysis']['fvg']
            msg += f"Type: {fvg['type'].upper()}\n"
            msg += f"Size: {fvg['size']:.5f}\n"
            msg += f"Time: {fvg['time'].strftime('%Y-%m-%d %H:%M')}\n"
            msg += f"Price Range: {fvg['bottom']:.5f} - {fvg['top']:.5f}\n"
            
            return msg
        except Exception as e:
            self.logger.error(f"Error formatting alert message: {str(e)}")
            return f"Error formatting alert for {data['symbol']}"