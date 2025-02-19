import logging
from typing import Dict
from config_handler import ConfigHandler, TimeFrame
from fvg_finder import FVGFinder
from utils import send_telegram_alert
from alert_cache_handler import AlertCache
from time_sync import TimeSync

class MarketAnalyzer:
    def __init__(self, time_sync: TimeSync = None):
        self.config = ConfigHandler()
        if not self.config.validate_timeframe_hierarchy():
            raise ValueError("Invalid timeframe hierarchy configuration")
        if not self.config.validate_symbols():
            self.logger.warning("Some symbols may be unavailable")

        self.fvg_finder = FVGFinder()
        self.logger = logging.getLogger(__name__)
        self.time_sync = time_sync or TimeSync()
        self.alert_cache = AlertCache(time_func=self.time_sync.get_current_broker_time)
        
        self.timeframe_hierarchy = self.config.timeframe_hierarchy
        
    def cleanup_analysis_cycle(self):
        """Cleanup after each analysis cycle"""
        try:
            self.fvg_finder.get_cached_rates.cache_clear()
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
        symbol = analysis['symbol']
        timeframe = analysis['timeframe']
        fvg = analysis['fvg']
        swing = analysis['swing']

        if not fvg.get('is_confirmed', False) or not fvg.get('mitigated', False):
            return

        ltf_list = self.timeframe_hierarchy.get(TimeFrame(timeframe), [])[:3]
        entry_found = False

        for ltf in ltf_list:
            try:
                should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, ltf)
                
                if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type']:
                    self._send_entry_alert(symbol, timeframe, ltf, fvg, ltf_analysis['fvg'])
                    entry_found = True
                    break
                    
            except Exception as e:
                self.logger.error(f"Error checking {ltf} for {symbol}: {e}")
                continue

        if not entry_found:
            self._send_no_entry_alert(symbol, timeframe, fvg, ltf_list)

    def _send_entry_alert(self, symbol, htf, ltf, htf_fvg, ltf_fvg):
        alert_type = f"entry_{ltf_fvg['type']}"
        fvg_time = ltf_fvg['time'].strftime('%Y%m%d%H%M')  # Minute precision
        
        if self.alert_cache.is_duplicate(
            symbol=symbol,
            timeframe=ltf.value,
            fvg_type=alert_type,
            fvg_time=fvg_time
        ):
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
            self.alert_cache.add_alert(
                symbol=symbol,
                timeframe=ltf.value,
                fvg_type=alert_type,
                fvg_time=fvg_time
            )

    def _send_no_entry_alert(self, symbol, timeframe, fvg, checked_timeframes):
        alert_type = f"no_entry_{fvg['type']}"
        fvg_time = fvg['time'].strftime('%Y%m%d%H%M')
        
        if self.alert_cache.is_duplicate(
            symbol=symbol,
            timeframe=timeframe,
            fvg_type=alert_type,
            fvg_time=fvg_time
        ):
            return
            
        message = (
            f"⏳ No Entry Setup, YETT!: {symbol}\n"
            f"📊 {timeframe} {fvg['type']} FVG was mitigated\n"
            f"🔍 No matching LTF FVGs found in:\n"
            f"{', '.join(str(tf.value) for tf in checked_timeframes)}"
        )
        
        if self.config.telegram_config.get('enabled', False):
            send_telegram_alert(message)
            self.alert_cache.add_alert(
                symbol=symbol,
                timeframe=timeframe,
                fvg_type=alert_type,
                fvg_time=fvg_time
            )