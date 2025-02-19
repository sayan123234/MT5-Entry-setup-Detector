import logging
from typing import Dict
import MetaTrader5 as mt5
from config_handler import ConfigHandler, TimeFrame
from fvg_finder import FVGFinder
from utils import send_telegram_alert
from alert_cache_handler import AlertCache

class MarketAnalyzer:
    def __init__(self):
        self.config = ConfigHandler()
        if not self.config.validate_timeframe_hierarchy():
            raise ValueError("Invalid timeframe hierarchy configuration")
        if not self.config.validate_symbols():
            self.logger.warning("Some symbols may be unavailable")

        self.fvg_finder = FVGFinder()
        self.logger = logging.getLogger(__name__)
        self.alert_cache = AlertCache()
        
        # Use timeframe hierarchy from config
        self.timeframe_hierarchy = self.config.timeframe_hierarchy
        
    # def is_market_open(self, symbol: str) -> bool:
    #     try:
    #         symbol_info = mt5.symbol_info(symbol)
    #         if symbol_info is None:
    #             return False
                
    #         current_time = mt5.symbol_info_tick(symbol).time
    #         session_starts = symbol_info.session_deals_session_start
    #         session_ends = symbol_info.session_deals_session_end
            
    #         return session_starts <= current_time <= session_ends
    #     except:
    #         return False
        
    def cleanup_analysis_cycle(self):
        """Cleanup after each analysis cycle"""
        try:
            # Clear MT5 rate cache
            self.fvg_finder.get_cached_rates.cache_clear()
            
            # Force garbage collection
            import gc
            gc.collect()
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    
    def analyze_markets(self):
        try:
            symbols = self.config.get_watchlist_symbols()
            self.logger.info(f"Starting analysis for {len(symbols)} symbols")
            
            for symbol in symbols:
                self.analyze_symbol(symbol)
                
        finally:
            self.cleanup_analysis_cycle()

    def analyze_symbol(self, symbol: str):
        # if not self.is_market_open(symbol):
        #     self.logger.info(f"Market closed for {symbol}, skipping analysis")
        #     return
            
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
        swing = analysis['swing']

        # Skip non-confirmed or non-mitigated FVGs
        if not fvg.get('is_confirmed', False) or not fvg.get('mitigated', False):
            return

        # Get lower timeframes to check
        ltf_list = self.timeframe_hierarchy.get(TimeFrame(timeframe), [])
        entry_found = False

        # Check only the first 3 lower timeframes
        for ltf in ltf_list[:3]:  # <-- Add slice here
            try:
                # Analyze lower timeframe
                should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, ltf)
                
                if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type']:
                    # Found matching FVG in lower timeframe
                    self._send_entry_alert(symbol, timeframe, ltf, fvg, ltf_analysis['fvg'])
                    entry_found = True
                    break
                    
            except Exception as e:
                self.logger.error(f"Error checking {ltf} for {symbol}: {e}")
                continue

        # # Send no-entry alert if nothing found
        # if not entry_found:
        #     self._send_no_entry_alert(symbol, timeframe, fvg)

    def _send_entry_alert(self, symbol, htf, ltf, htf_fvg, ltf_fvg):
        """Send alert when entry setup is found"""
        alert_type = f"entry_{ltf_fvg['type']}"
        
        # Check for duplicate before sending
        if self.alert_cache.is_duplicate(symbol, ltf, alert_type):
            self.logger.info(f"Skipping duplicate alert for {symbol} {ltf} {alert_type}")
            return
            
        message = (
            f"🚨 ENTRY SETUP: {symbol}\n"
            f"📈 HTF: {htf} {htf_fvg['type']} FVG (Mitigated)\n"
            f"📉 LTF: {ltf} {ltf_fvg['type']} FVG detected\n"
            f"🔝 LTF Top: {ltf_fvg['top']:.5f}\n"
            f"⬇ LTF Bottom: {ltf_fvg['bottom']:.5f}\n"
            f"🕒 LTF Time: {ltf_fvg['time']}"
        )
        
        if self.config.telegram_config.get('enabled', False):
            send_telegram_alert(message)
            self.alert_cache.add_alert(symbol, ltf, alert_type)  # Add to cache AFTER sending

    # def _send_no_entry_alert(self, symbol, timeframe, fvg):
    #     """Send alert when no entry setups found"""
    #     message = (
    #         f"⏳ No Entry Setup: {symbol}\n"
    #         f"📊 {timeframe} {fvg['type']} FVG was mitigated\n"
    #         f"🔍 No matching LTF FVGs found in:\n"
    #         f"{', '.join(str(tf.value) for tf in self.timeframe_hierarchy.get(TimeFrame(timeframe), []))}"
    #     )
        
    #     if self.config.telegram_config.get('enabled', False):
    #         send_telegram_alert(message)