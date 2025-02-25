import logging
import pandas as pd
from typing import Dict
from config_handler import ConfigHandler, TimeFrame
from fvg_finder import FVGFinder
from utils import send_telegram_alert
from alert_cache_handler import AlertCache
from time_sync import TimeSync
import MetaTrader5 as mt5

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
                if not should_continue and analysis:
                    self._handle_complete_analysis(analysis)
                    break
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol} in {timeframe}: {e}")
                continue

    def _handle_complete_analysis(self, analysis: Dict):
        """Handle complete analysis focusing on reentry setups for lowest timeframe"""
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

        # Handle the lowest timeframe separately - ONLY send alert if reentry FVG is found
        lowest_tf = ltf_list[-1]
        try:
            should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, lowest_tf)
            if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type']:
                rates_df = pd.DataFrame(self.fvg_finder.get_cached_rates(symbol, lowest_tf))
                rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
                reentry_fvg = self.fvg_finder.find_reentry_fvg(rates_df, ltf_analysis['fvg'], lowest_tf, symbol)
                if reentry_fvg:
                    self._send_reentry_alert(symbol, timeframe, lowest_tf, fvg, reentry_fvg)
                    entry_found = True
                # Removed the else clause that would send a regular entry alert if no reentry FVG was found
        except Exception as e:
            self.logger.error(f"Error checking reentry for {symbol} on {lowest_tf}: {e}")

        if not entry_found:
            self._send_no_entry_alert(symbol, timeframe, fvg, ltf_list)

    def _send_entry_alert(self, symbol, htf, ltf, htf_fvg, ltf_fvg):
        """Send alert for normal entry setup with enhanced content"""
        alert_type = f"entry_{ltf_fvg['type']}"
        fvg_time = ltf_fvg['time'].strftime('%Y%m%d%H%M')
        
        if self.alert_cache.is_duplicate(symbol=symbol, timeframe=ltf.value, fvg_type=alert_type, fvg_time=fvg_time):
            self.logger.info(f"Skipping duplicate alert for {symbol} {ltf} {alert_type}")
            return

        # Get symbol info for pip calculation
        symbol_info = mt5.symbol_info(symbol)
        pip_size = symbol_info.point if symbol_info else 0.0001  # Fallback to 0.0001 if unavailable
        fvg_size_pips = (ltf_fvg['top'] - ltf_fvg['bottom']) / pip_size
        
        # Get current price for distance calculation
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.bid if tick else (ltf_fvg['top'] + ltf_fvg['bottom']) / 2  # Fallback to midpoint
        distance_to_top = (ltf_fvg['top'] - current_price) / pip_size if current_price < ltf_fvg['top'] else 0
        distance_to_bottom = (current_price - ltf_fvg['bottom']) / pip_size if current_price > ltf_fvg['bottom'] else 0

        message = (
            f"🚨 ST Setup: {symbol}\n"
            f"📈 HTF: {htf} {htf_fvg['type']} FVG (Mitigated)\n"
            f"📉 LTF: {ltf} {ltf_fvg['type']} FVG detected\n"
            f"🔝 LTF Top: {ltf_fvg['top']:.5f}\n"
            f"⬇ LTF Bottom: {ltf_fvg['bottom']:.5f}\n"
            f"📏 FVG Size: {fvg_size_pips:.1f} pips\n"
            f"📍 Distance to Top: {distance_to_top:.1f} pips\n"
            f"📍 Distance to Bottom: {distance_to_bottom:.1f} pips\n"
            f"🕒 LTF Time: {ltf_fvg['time']}"
        )
        
        if self.config.telegram_config.get('enabled', False):
            send_telegram_alert(message)
            self.alert_cache.add_alert(symbol=symbol, timeframe=ltf.value, fvg_type=alert_type, fvg_time=fvg_time)

    def _send_reentry_alert(self, symbol, htf, ltf, htf_fvg, reentry_fvg):
        """Send alert for reentry setup with enhanced content"""
        alert_type = f"reentry_{reentry_fvg['type']}"
        fvg_time = reentry_fvg['time'].strftime('%Y%m%d%H%M')
        
        if self.alert_cache.is_duplicate(symbol=symbol, timeframe=ltf.value, fvg_type=alert_type, fvg_time=fvg_time):
            self.logger.info(f"Skipping duplicate reentry alert for {symbol} {ltf} {alert_type}")
            return

        # Get symbol info for pip calculation
        symbol_info = mt5.symbol_info(symbol)
        pip_size = symbol_info.point if symbol_info else 0.0001
        fvg_size_pips = (reentry_fvg['top'] - reentry_fvg['bottom']) / pip_size
        
        # Get current price for distance calculation
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.bid if tick else (reentry_fvg['top'] + reentry_fvg['bottom']) / 2
        distance_to_top = (reentry_fvg['top'] - current_price) / pip_size if current_price < reentry_fvg['top'] else 0
        distance_to_bottom = (current_price - reentry_fvg['bottom']) / pip_size if current_price > reentry_fvg['bottom'] else 0

        message = (
            f"🎯 ST+RE Setup: {symbol}\n"
            f"📈 HTF: {htf} {htf_fvg['type']} FVG (Mitigated)\n"
            f"📊 LTF: {ltf} Reentry FVG\n"
            f"🔝 Top: {reentry_fvg['top']:.5f}\n"
            f"⬇ Bottom: {reentry_fvg['bottom']:.5f}\n"
            f"📏 FVG Size: {fvg_size_pips:.1f} pips\n"
            f"📍 Distance to Top: {distance_to_top:.1f} pips\n"
            f"📍 Distance to Bottom: {distance_to_bottom:.1f} pips\n"
            f"🕒 Time: {reentry_fvg['time']}\n"
            f"📍 Original FVG Time: {reentry_fvg['original_fvg_time']}"
        )
        
        if self.config.telegram_config.get('enabled', False):
            send_telegram_alert(message)
            self.alert_cache.add_alert(symbol=symbol, timeframe=ltf.value, fvg_type=alert_type, fvg_time=fvg_time)

    def _send_no_entry_alert(self, symbol, timeframe, fvg, checked_timeframes):
        """Send alert when no entry setups are found with enhanced content"""
        alert_type = f"no_entry_{fvg['type']}"
        fvg_time = fvg['time'].strftime('%Y%m%d%H%M')
        
        if self.alert_cache.is_duplicate(symbol=symbol, timeframe=timeframe, fvg_type=alert_type, fvg_time=fvg_time):
            return

        # Get symbol info for pip calculation
        symbol_info = mt5.symbol_info(symbol)
        pip_size = symbol_info.point if symbol_info else 0.0001
        fvg_size_pips = (fvg['top'] - fvg['bottom']) / pip_size

        message = (
            f"⏳ Watch out for potential entry setups!: {symbol}\n"
            f"📊 {timeframe} {fvg['type']} FVG was mitigated\n"
            f"🔝 Top: {fvg['top']:.5f}\n"
            f"⬇ Bottom: {fvg['bottom']:.5f}\n"
            f"📏 FVG Size: {fvg_size_pips:.1f} pips\n"
            f"🔍 No matching LTF FVGs found in: {', '.join(str(tf.value) for tf in checked_timeframes)}"
        )
        
        if self.config.telegram_config.get('enabled', False):
            send_telegram_alert(message)
            self.alert_cache.add_alert(symbol=symbol, timeframe=timeframe, fvg_type=alert_type, fvg_time=fvg_time)