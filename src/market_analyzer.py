import logging
from config_handler import TimeFrame, ConfigHandler
from fvg_finder import FVGFinder
from utils import send_telegram_alert

class MarketAnalyzer:
    def __init__(self):
        self.config = ConfigHandler()
        self.fvg_finder = FVGFinder()
        self.logger = logging.getLogger(__name__)
        
    def analyze_markets(self):
        """Analyze all symbols across timeframes"""
        for symbol in self.config.symbols:
            self.logger.info(f"Analyzing {symbol}")
            
            # Check timeframes in order
            for timeframe in [TimeFrame.MONTHLY, TimeFrame.WEEKLY, 
                            TimeFrame.DAILY, TimeFrame.H4]:
                
                analysis = self.fvg_finder.analyze_timeframe(symbol, timeframe)
                
                if analysis and analysis['fvgs']:
                    self.logger.info(f"Found FVGs for {symbol} on {timeframe}")
                    self.process_analysis(symbol, analysis)
                    break  # Stop checking lower timeframes
                
                self.logger.info(f"No FVGs found for {symbol} on {timeframe}")
    
    def process_analysis(self, symbol: str, analysis: dict):
        """Process and alert for found FVGs"""
        # Format alert message
        msg = self.format_alert(symbol, analysis)
        
        # Send alert
        if self.config.telegram_config['enabled']:
            send_telegram_alert(msg)
            
        # Log the finding
        self.logger.info(msg)
    
    def format_alert(self, symbol: str, analysis: dict) -> str:
        """Format alert message for Telegram"""
        msg = f"🔍 FVG Alert for {symbol}\n"
        msg += f"Timeframe: {analysis['timeframe'].name}\n\n"
        
        for fvg in analysis['fvgs']:
            msg += f"Type: {fvg['type'].upper()}\n"
            msg += f"Size: {fvg['size']:.5f}\n"
            msg += f"Time: {fvg['time']}\n"
            msg += f"Price Range: {fvg['bottom']:.5f} - {fvg['top']:.5f}\n\n"
        
        return msg