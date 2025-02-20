import logging
import pandas as pd
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
        
        # Filter timeframe hierarchy to only include H1 and above
        self.timeframe_hierarchy = self._filter_timeframe_hierarchy()
        
    def _filter_timeframe_hierarchy(self) -> Dict[TimeFrame, list]:
        """Filter timeframe hierarchy to only include H1 and above timeframes"""
        valid_timeframes = [
            TimeFrame.MONTHLY,
            TimeFrame.WEEKLY,
            TimeFrame.DAILY,
            TimeFrame.H4,
            TimeFrame.H1
        ]
        
        filtered_hierarchy = {}
        original_hierarchy = self.config.timeframe_hierarchy
        
        for tf, lower_tfs in original_hierarchy.items():
            if tf in valid_timeframes:
                filtered_hierarchy[tf] = lower_tfs
                
        return filtered_hierarchy

    def cleanup_analysis_cycle(self):
        """Cleanup after each analysis cycle"""
        try:
            self.fvg_finder.get_cached_rates.cache_clear()
            import gc
            gc.collect()
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    def analyze_markets(self):
        """Analyze all markets in the watchlist"""
        try:
            symbols = self.config.get_watchlist_symbols()
            self.logger.info(f"Starting analysis for {len(symbols)} symbols")
            
            for symbol in symbols:
                self.analyze_symbol(symbol)
                
        finally:
            self.cleanup_analysis_cycle()

    def analyze_symbol(self, symbol: str):
        """Analyze a single symbol across all timeframes"""
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
        """Handle complete analysis including both normal and reentry setups"""
        symbol = analysis['symbol']
        timeframe = analysis['timeframe']
        fvg = analysis['fvg']
        swing = analysis['swing']

        if not fvg.get('is_confirmed', False) or not fvg.get('mitigated', False):
            return

        ltf_list = self.timeframe_hierarchy.get(TimeFrame(timeframe), [])[:3]
        if not ltf_list:
            return

        entry_found = False
        
        # Process all timeframes except the lowest one for normal alerts
        for ltf in ltf_list[:-1]:
            try:
                should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, ltf)
                
                if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type']:
                    self._send_entry_alert(symbol, timeframe, ltf, fvg, ltf_analysis['fvg'])
                    entry_found = True
                    
            except Exception as e:
                self.logger.error(f"Error checking {ltf} for {symbol}: {e}")
                continue

        # Handle the lowest timeframe separately for reentry setup
        lowest_tf = ltf_list[-1]
        try:
            should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, lowest_tf)
            
            if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type']:
                # Get rates for reentry analysis
                rates_df = pd.DataFrame(self.fvg_finder.get_cached_rates(symbol, lowest_tf))
                rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
                
                # Check for reentry FVG
                reentry_fvg = self.fvg_finder.find_reentry_fvg(
                    rates_df,
                    ltf_analysis['fvg'],
                    lowest_tf
                )
                
                if reentry_fvg:
                    self._send_reentry_alert(symbol, timeframe, lowest_tf, fvg, reentry_fvg)
                    entry_found = True
                else:
                    # If no reentry found, send normal alert for lowest timeframe
                    self._send_entry_alert(symbol, timeframe, lowest_tf, fvg, ltf_analysis['fvg'])
                    entry_found = True
                    
        except Exception as e:
            self.logger.error(f"Error checking reentry for {symbol} on {lowest_tf}: {e}")

        if not entry_found:
            self._send_no_entry_alert(symbol, timeframe, fvg, ltf_list)

    def _send_entry_alert(self, symbol, htf, ltf, htf_fvg, ltf_fvg):
        """Send alert for normal entry setup"""
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
            f"🚨 ST Setup: {symbol}\n"
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

    def _send_reentry_alert(self, symbol, htf, ltf, htf_fvg, reentry_fvg):
        """Send alert for reentry setup"""
        alert_type = f"reentry_{reentry_fvg['type']}"
        fvg_time = reentry_fvg['time'].strftime('%Y%m%d%H%M')  # Minute precision
        
        if self.alert_cache.is_duplicate(
            symbol=symbol,
            timeframe=ltf.value,
            fvg_type=alert_type,
            fvg_time=fvg_time
        ):
            self.logger.info(f"Skipping duplicate reentry alert for {symbol} {ltf} {alert_type}")
            return
            
        message = (
            f"🎯 ST+RE Setup: {symbol}\n"
            f"📈 HTF: {htf} {htf_fvg['type']} FVG (Mitigated)\n"
            f"📊 LTF: {ltf} Reentry FVG\n"
            f"🔝 Top: {reentry_fvg['top']:.5f}\n"
            f"⬇ Bottom: {reentry_fvg['bottom']:.5f}\n"
            f"🕒 Time: {reentry_fvg['time']}\n"
            f"📍 Original FVG Time: {reentry_fvg['original_fvg_time']}"
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
        """Send alert when no entry setups are found"""
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
            f"⏳ Watch out for potential entry setups!: {symbol}\n"
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