import logging
from typing import Dict
from config_handler import ConfigHandler, TimeFrame
from fvg_finder import FVGFinder
from utils import send_telegram_alert
from alert_cache_handler import AlertCache

class MarketAnalyzer:
    def __init__(self):
        self.config = ConfigHandler()
        self.fvg_finder = FVGFinder()
        self.logger = logging.getLogger(__name__)
        self.alert_cache = AlertCache()
        self.timeframe_hierarchy = [
            TimeFrame.MONTHLY,
            TimeFrame.WEEKLY,
            TimeFrame.DAILY,
            TimeFrame.H4
        ]

    def analyze_markets(self):
        """Analyze all markets for FVG patterns"""
        # Cache cleanup is now handled automatically in is_duplicate()
        symbols = self.config.get_watchlist_symbols()
        self.logger.info(f"Starting analysis for {len(symbols)} symbols")

        for symbol in symbols:
            self.analyze_symbol(symbol)

    def analyze_symbol(self, symbol: str):
        self.logger.info(f"Analyzing {symbol}")

        for timeframe in self.timeframe_hierarchy:
            try:
                should_continue, analysis = self.fvg_finder.analyze_timeframe(symbol, timeframe)
                
                if not should_continue and analysis:  # Found an FVG
                    self._handle_complete_analysis(analysis)
                    break  # Stop checking lower timeframes
                
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol} in {timeframe}: {e}")
                continue

    def _handle_complete_analysis(self, analysis: Dict):
        """Handle completed analysis and send alerts if needed"""
        symbol = analysis['symbol']
        timeframe = analysis['timeframe']
        fvg = analysis['fvg']

        # Determine if this is a potential or confirmed FVG
        is_confirmed = fvg.get('is_confirmed', False)
        alert_type = f"{fvg['type']}_{'confirmed' if is_confirmed else 'potential'}"
        
        # Check for duplicate before creating alert
        if self.alert_cache.is_duplicate(symbol, timeframe, alert_type):
            self.logger.debug(f"Skipping duplicate alert for {symbol} on {timeframe}")
            return

        # Create alert message
        alert_prefix = "⚠️ Potential" if not is_confirmed else "🔍 Confirmed"
        message = (
            f"{alert_prefix} FVG Detected on {symbol}\n"
            f"⏱ Timeframe: {timeframe}\n"
            f"📊 Type: {fvg['type']}\n"
            f"💹 Size: {fvg['size']:.5f}\n"
            f"🔝 Top: {fvg['top']:.5f}\n"
            f"⬇ Bottom: {fvg['bottom']:.5f}\n"
            f"🕒 Time: {fvg['time']}\n"
        )

        if not is_confirmed:
            message += "\n📊 Candle Status:"
            for candle_num, status in fvg['candle_status'].items():
                closed_status = "✅ Closed" if status['closed'] else "⏳ Forming"
                message += f"\n{candle_num}: {closed_status}"

        self.logger.info(f"Found {'potential' if not is_confirmed else 'confirmed'} FVG for {symbol} on {timeframe}")

        # Send alert and cache it
        if self.config.telegram_config.get('enabled', False):
            if send_telegram_alert(message):
                self.alert_cache.add_alert(symbol, timeframe, alert_type)