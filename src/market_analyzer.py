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
        """
        Handle complete analysis with hierarchical rules:
        1. Check immediate lower timeframes for ST alerts
        2. If no ST alerts found, check next lower timeframe for ST+RE
        3. If neither found, send potential entry alert
        """
        symbol = analysis['symbol']
        timeframe = analysis['timeframe']
        fvg = analysis['fvg']
        swing = analysis['swing']

        # Skip if not confirmed or not mitigated
        if not fvg.get('is_confirmed', False) or not fvg.get('mitigated', False):
            return

        # Get all lower timeframes
        ltf_list = self.timeframe_hierarchy.get(TimeFrame(timeframe), [])
        if not ltf_list:
            return

        # Step 1: Check immediate lower timeframes for ST alerts (e.g., Weekly and Daily for Monthly)
        # For typical case with Monthly HTF, this would check Weekly and Daily
        immediate_ltf_count = min(2, len(ltf_list))
        immediate_ltfs = ltf_list[:immediate_ltf_count]
        st_found = False

        for ltf in immediate_ltfs:
            try:
                should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, ltf)
                if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type']:
                    # Only proceed if LTF FVG is confirmed
                    if ltf_analysis['fvg'].get('is_confirmed', False):
                        self._send_entry_alert(symbol, timeframe, ltf, fvg, ltf_analysis['fvg'])
                        st_found = True
                        # We found an ST setup, don't need to check other immediate timeframes
                        break
            except Exception as e:
                self.logger.error(f"Error checking {ltf} for {symbol}: {e}")
                continue

        # Step 2: If no ST found in immediate timeframes, check next lower timeframe for ST+RE
        re_found = False
        if not st_found and len(ltf_list) > immediate_ltf_count:
            re_timeframe = ltf_list[immediate_ltf_count]  # Get the next timeframe (e.g., H4)
            try:
                # First check if there's a regular FVG in this timeframe
                should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, re_timeframe)
                if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type'] and ltf_analysis['fvg'].get('is_confirmed', False):
                    # Get data for reentry analysis
                    rates_df = pd.DataFrame(self.fvg_finder.get_cached_rates(symbol, re_timeframe))
                    rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
                    
                    # First check if the original FVG is mitigated
                    if self.fvg_finder.is_fvg_mitigated(rates_df, ltf_analysis['fvg']):
                        # Then look for reentry FVG
                        reentry_fvg = self.fvg_finder.find_reentry_fvg(rates_df, ltf_analysis['fvg'], re_timeframe, symbol)
                        
                        if reentry_fvg and reentry_fvg.get('is_confirmed', False):
                            self._send_reentry_alert(symbol, timeframe, re_timeframe, fvg, reentry_fvg)
                            re_found = True
            except Exception as e:
                self.logger.error(f"Error checking reentry for {symbol} on {re_timeframe}: {e}")

        # Step 3: If neither ST nor ST+RE found, send potential entry alert
        if not st_found and not re_found:
            # We're checking the timeframes we actually looked at
            checked_timeframes = immediate_ltfs
            if len(ltf_list) > immediate_ltf_count:
                checked_timeframes.append(ltf_list[immediate_ltf_count])
                
            self._send_no_entry_alert(symbol, timeframe, fvg, checked_timeframes)

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
        """Send alert for reentry setup with enhanced content for all chain depths"""
        # Determine alert type based on chain depth
        chain_depth = reentry_fvg.get('chain_depth', 0)
        alert_type = f"reentry_{reentry_fvg['type']}"
        if chain_depth > 1:
            alert_type = f"reentry_chain_{reentry_fvg['type']}"
        
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

        # Calculate time since original FVG and mitigation
        original_time = reentry_fvg.get('original_fvg_time')
        mitigation_time = reentry_fvg.get('mitigation_time')
        
        time_info = ""
        if original_time and isinstance(original_time, pd.Timestamp):
            elapsed_time = (reentry_fvg['time'] - original_time).total_seconds() / 60  # in minutes
            time_info += f"\n⏱ Time since original: {int(elapsed_time)} mins"
        
        if mitigation_time and isinstance(mitigation_time, pd.Timestamp):
            mins_since_mitigation = (reentry_fvg['time'] - mitigation_time).total_seconds() / 60
            time_info += f"\n⏱ Formed {int(mins_since_mitigation)} mins after mitigation"

        # Customize emoji and title based on chain depth
        if chain_depth > 1:
            setup_emoji = "🔄"
            setup_title = f"Chain-RE Setup (Depth: {chain_depth})"
        else:
            setup_emoji = "🎯"
            setup_title = "ST+RE Setup"

        message = (
            f"{setup_emoji} {setup_title}: {symbol}\n"
            f"📈 HTF: {htf} {htf_fvg['type']} FVG (Mitigated)\n"
            f"📊 LTF: {ltf} Reentry FVG\n"
            f"🔝 Top: {reentry_fvg['top']:.5f}\n"
            f"⬇ Bottom: {reentry_fvg['bottom']:.5f}\n"
            f"📏 FVG Size: {fvg_size_pips:.1f} pips\n"
            f"📍 Distance to Top: {distance_to_top:.1f} pips\n"
            f"📍 Distance to Bottom: {distance_to_bottom:.1f} pips\n"
            f"🕒 Time: {reentry_fvg['time']}{time_info}"
        )
        
        # Add original FVG time and mitigation time if available
        if original_time:
            message += f"\n📍 Original FVG Time: {original_time}"
        if mitigation_time:
            message += f"\n📍 Mitigation Time: {mitigation_time}"
        
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