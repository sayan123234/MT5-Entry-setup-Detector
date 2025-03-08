import logging
import pandas as pd
from typing import Dict, List, Optional
from src.config.config_handler import ConfigHandler, TimeFrame
from src.core.fvg_finder import FVGFinder
from src.services.telegram_service import send_telegram_alert
from src.utils.alert_cache import AlertCache
from src.utils.time_sync import TimeSync
import MetaTrader5 as mt5

class MarketAnalyzer:
    def __init__(self, time_sync: Optional[TimeSync] = None, config: Optional[ConfigHandler] = None):
        """
        Initialize the Market Analyzer.
        
        Args:
            time_sync: TimeSync instance (will create one if None)
            config: ConfigHandler instance (will create one if None)
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize configuration
        self.config = config or ConfigHandler()
        if not self.config.validate_timeframe_hierarchy():
            raise ValueError("Invalid timeframe hierarchy configuration")
        if not self.config.validate_symbols():
            self.logger.warning("Some symbols may be unavailable")

        # Initialize time synchronization
        self.time_sync = time_sync or TimeSync(config=self.config)
        
        # Initialize components with proper dependency injection
        self.fvg_finder = FVGFinder(config=self.config, time_sync=self.time_sync)
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

    def _check_same_timeframe_2cr(self, symbol: str, htf: str, fvg: Dict) -> Optional[Dict]:
        """
        Check for 2CR pattern in the same timeframe as the FVG.
        
        Args:
            symbol: Symbol name
            htf: Higher timeframe
            fvg: FVG information
            
        Returns:
            Two candle rejection pattern information or None if not found
        """
        try:
            # Get data for this timeframe
            rates_df = pd.DataFrame(self.fvg_finder.get_cached_rates(symbol, TimeFrame(htf)))
            if rates_df.empty:
                return None
                
            rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
            
            # Look for 2CR pattern in the same timeframe
            two_cr = self.fvg_finder.find_two_candle_rejection(rates_df, fvg, TimeFrame(htf))
            return two_cr
        except Exception as e:
            self.logger.error(f"Error checking same timeframe 2CR for {symbol} on {htf}: {e}")
            return None

    def _handle_complete_analysis(self, analysis: Dict):
        """
        Handle complete analysis using 2 Candle Rejection (2CR) logic
        
        Implementation focuses on:
        - HTF FVG mitigation
        - Same timeframe 2CR pattern detection
        - LTF 2CR pattern detection
        - Follow-through analysis
        """
        symbol = analysis['symbol']
        htf = analysis['timeframe']
        fvg = analysis['fvg']
        swing = analysis['swing']

        # Skip if not confirmed or not mitigated
        if not fvg.get('is_confirmed', False) or not fvg.get('mitigated', False):
            return

        # First, check for 2CR pattern in the same timeframe as the FVG
        same_tf_two_cr = self._check_same_timeframe_2cr(symbol, htf, fvg)
        if same_tf_two_cr:
            self.logger.info(f"Found 2CR pattern in same timeframe {htf} for {symbol}")
            self._send_same_timeframe_2cr_alert(symbol, htf, fvg, same_tf_two_cr)
            return

        # If no 2CR found in the same timeframe, check lower timeframes
        # Get immediate lower timeframes to check for 2CR patterns
        ltf_list = self.timeframe_hierarchy.get(TimeFrame(htf), [])
        if not ltf_list:
            # If no lower timeframes available, send potential alert for same timeframe
            self._send_potential_2cr_alert(symbol, htf, fvg, [TimeFrame(htf)])
            return

        # Typically check the first two lower timeframes (e.g., Weekly and Daily for Monthly)
        check_tfs = ltf_list[:2]
        two_cr_found = False

        for ltf in check_tfs:
            try:
                # Get data for this timeframe
                rates_df = pd.DataFrame(self.fvg_finder.get_cached_rates(symbol, ltf))
                if rates_df.empty:
                    continue
                    
                rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
                
                # Find FVG in this timeframe
                should_continue, ltf_analysis = self.fvg_finder.analyze_timeframe(symbol, ltf)
                if ltf_analysis and ltf_analysis['fvg']['type'] == fvg['type'] and ltf_analysis['fvg'].get('is_confirmed', False):
                    # Check if FVG is mitigated
                    if self.fvg_finder.is_fvg_mitigated(rates_df, ltf_analysis['fvg']):
                        # Look for 2CR pattern
                        two_cr = self.fvg_finder.find_two_candle_rejection(rates_df, ltf_analysis['fvg'], ltf)
                        
                        if two_cr:
                            self._send_2cr_alert(symbol, htf, ltf, fvg, ltf_analysis['fvg'], two_cr)
                            two_cr_found = True
                            break
            except Exception as e:
                self.logger.error(f"Error checking 2CR for {symbol} on {ltf}: {e}")
                continue

        # If no 2CR found in any timeframe, check for potential opportunities
        if not two_cr_found:
            self._send_potential_2cr_alert(symbol, htf, fvg, check_tfs)

    def _send_2cr_alert(self, symbol, htf, ltf, htf_fvg, ltf_fvg, two_cr):
        """Send alert for 2 Candle Rejection pattern"""
        rejection_type = two_cr['rejection_type']
        alert_type = f"2cr_{rejection_type}_{two_cr['type']}"
        
        # Use the time of the second candle in the 2CR pattern as the identifier
        second_candle_time = two_cr['second_candle']['time']
        fvg_time = second_candle_time.strftime('%Y%m%d%H%M')
        
        if self.alert_cache.is_duplicate(symbol=symbol, timeframe=ltf.value, fvg_type=alert_type, fvg_time=fvg_time):
            self.logger.info(f"Skipping duplicate 2CR alert for {symbol} {ltf} {alert_type}")
            return

        # Get symbol info for pip calculation
        symbol_info = mt5.symbol_info(symbol)
        pip_size = symbol_info.point if symbol_info else 0.0001  # Fallback to 0.0001 if unavailable
        fvg_size_pips = (ltf_fvg['top'] - ltf_fvg['bottom']) / pip_size
        
        # Get current price for distance calculation
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.bid if tick else None
        
        # Build the alert message
        rejection_emoji = "🔄" if rejection_type == "second_candle" else "✅"
        follow_through_status = "✅ Expected" if not two_cr.get('has_follow_through', False) else "✅ Confirmed"
        ugly_warning = "⚠️ Ugly 2CR detected (consolidation likely)" if two_cr.get('is_ugly', False) else ""
        
        message = (
            f"{rejection_emoji} 2CR Setup: {symbol}\n"
            f"📈 HTF: {htf} {htf_fvg['type']} FVG (Mitigated)\n"
            f"📉 LTF: {ltf} 2CR Pattern ({rejection_type.replace('_', ' ')})\n"
            f"🔍 FVG Range: {ltf_fvg['bottom']:.5f} - {ltf_fvg['top']:.5f}\n"
            f"📏 FVG Size: {fvg_size_pips:.1f} pips\n"
            f"🕒 First Candle: {two_cr['first_candle']['time'].strftime('%Y-%m-%d %H:%M')}\n"
            f"🕒 Second Candle: {two_cr['second_candle']['time'].strftime('%Y-%m-%d %H:%M')}\n"
            f"📊 Follow-through: {follow_through_status}\n"
            f"{ugly_warning}"
        )
        
        # Add current price info if available
        if current_price:
            distance_to_top = (ltf_fvg['top'] - current_price) / pip_size if current_price < ltf_fvg['top'] else 0
            distance_to_bottom = (current_price - ltf_fvg['bottom']) / pip_size if current_price > ltf_fvg['bottom'] else 0
            
            if two_cr['type'] == 'bullish':
                target_distance = distance_to_top
                target_label = "to top"
            else:
                target_distance = distance_to_bottom
                target_label = "to bottom"
                
            message += f"\n💰 Current Price: {current_price:.5f}\n"
            message += f"📍 Distance {target_label}: {target_distance:.1f} pips"
        
        # Send the alert
        try:
            send_telegram_alert(message)
            self.logger.info(f"Sent 2CR alert for {symbol} {ltf} {alert_type}")
            
            # Cache the alert to prevent duplicates
            self.alert_cache.add_alert(
                symbol=symbol,
                timeframe=ltf.value,
                fvg_type=alert_type,
                fvg_time=fvg_time
            )
        except Exception as e:
            self.logger.error(f"Failed to send 2CR alert: {e}")

    def _send_same_timeframe_2cr_alert(self, symbol, htf, fvg, two_cr):
        """Send alert for 2 Candle Rejection pattern in the same timeframe as the FVG"""
        rejection_type = two_cr['rejection_type']
        alert_type = f"same_tf_2cr_{rejection_type}_{two_cr['type']}"
        
        # Use the time of the second candle in the 2CR pattern as the identifier
        second_candle_time = two_cr['second_candle']['time']
        fvg_time = second_candle_time.strftime('%Y%m%d%H%M')
        
        if self.alert_cache.is_duplicate(symbol=symbol, timeframe=htf, fvg_type=alert_type, fvg_time=fvg_time):
            self.logger.info(f"Skipping duplicate same timeframe 2CR alert for {symbol} {htf} {alert_type}")
            return

        # Get symbol info for pip calculation
        symbol_info = mt5.symbol_info(symbol)
        pip_size = symbol_info.point if symbol_info else 0.0001  # Fallback to 0.0001 if unavailable
        fvg_size_pips = (fvg['top'] - fvg['bottom']) / pip_size
        
        # Get current price for distance calculation
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.bid if tick else None
        
        # Build the alert message
        rejection_emoji = "🔄" if rejection_type == "second_candle" else "✅"
        follow_through_status = "✅ Expected" if not two_cr.get('has_follow_through', False) else "✅ Confirmed"
        ugly_warning = "⚠️ Ugly 2CR detected (consolidation likely)" if two_cr.get('is_ugly', False) else ""
        
        message = (
            f"{rejection_emoji} SAME TF 2CR Setup: {symbol}\n"
            f"📈 Timeframe: {htf}\n"
            f"📊 Pattern: {fvg['type']} FVG with 2CR ({rejection_type.replace('_', ' ')})\n"
            f"🔍 FVG Range: {fvg['bottom']:.5f} - {fvg['top']:.5f}\n"
            f"📏 FVG Size: {fvg_size_pips:.1f} pips\n"
            f"🕒 First Candle: {two_cr['first_candle']['time'].strftime('%Y-%m-%d %H:%M')}\n"
            f"🕒 Second Candle: {two_cr['second_candle']['time'].strftime('%Y-%m-%d %H:%M')}\n"
            f"📊 Follow-through: {follow_through_status}\n"
            f"{ugly_warning}"
        )
        
        # Add current price info if available
        if current_price:
            distance_to_top = (fvg['top'] - current_price) / pip_size if current_price < fvg['top'] else 0
            distance_to_bottom = (current_price - fvg['bottom']) / pip_size if current_price > fvg['bottom'] else 0
            
            if two_cr['type'] == 'bullish':
                target_distance = distance_to_top
                target_label = "to top"
            else:
                target_distance = distance_to_bottom
                target_label = "to bottom"
                
            message += f"\n💰 Current Price: {current_price:.5f}\n"
            message += f"📍 Distance {target_label}: {target_distance:.1f} pips"
        
        # Send the alert
        try:
            send_telegram_alert(message)
            self.logger.info(f"Sent same timeframe 2CR alert for {symbol} {htf} {alert_type}")
            
            # Cache the alert to prevent duplicates
            self.alert_cache.add_alert(
                symbol=symbol,
                timeframe=htf,
                fvg_type=alert_type,
                fvg_time=fvg_time
            )
        except Exception as e:
            self.logger.error(f"Failed to send same timeframe 2CR alert: {e}")

    def _send_potential_2cr_alert(self, symbol, htf, fvg, check_tfs):
        """Send alert for potential 2CR setup based on HTF FVG mitigation"""
        alert_type = f"potential_2cr_{fvg['type']}"
        fvg_time = pd.to_datetime(fvg['time']).strftime('%Y%m%d%H%M')
        
        # Prevent duplicate alerts
        if self.alert_cache.is_duplicate(symbol=symbol, timeframe=htf, fvg_type=alert_type, fvg_time=fvg_time):
            return
            
        # Only send potential alerts if enabled in config
        if not self.config.get_alert_settings().get('send_potential_2cr_alerts', False):
            return
            
        # Get symbol info for pip calculation
        symbol_info = mt5.symbol_info(symbol)
        pip_size = symbol_info.point if symbol_info else 0.0001
        fvg_size_pips = (fvg['top'] - fvg['bottom']) / pip_size
        
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.bid if tick else None
        
        # Build lower timeframe string
        ltf_str = ", ".join([tf.value for tf in check_tfs])
        
        # Build the alert message
        message = (
            f"⏳ Potential 2CR Setup: {symbol}\n"
            f"📈 HTF: {htf} {fvg['type']} FVG (Mitigated)\n"
            f"👀 Watch for 2CR pattern on: {ltf_str}\n"
            f"🔍 FVG Range: {fvg['bottom']:.5f} - {fvg['top']:.5f}\n"
            f"📏 FVG Size: {fvg_size_pips:.1f} pips\n"
        )
        
        # Add current price info if available
        if current_price:
            if fvg['type'] == 'bullish':
                distance = (fvg['top'] - current_price) / pip_size if current_price < fvg['top'] else 0
                target_label = "to top"
            else:
                distance = (current_price - fvg['bottom']) / pip_size if current_price > fvg['bottom'] else 0
                target_label = "to bottom"
                
            message += f"\n💰 Current Price: {current_price:.5f}\n"
            message += f"📍 Distance {target_label}: {distance:.1f} pips"
        
        # Send the alert
        try:
            send_telegram_alert(message)
            self.logger.info(f"Sent potential 2CR alert for {symbol} {htf}")
            
            # Cache the alert to prevent duplicates
            self.alert_cache.add_alert(
                symbol=symbol,
                timeframe=htf,
                fvg_type=alert_type,
                fvg_time=fvg_time
            )
        except Exception as e:
            self.logger.error(f"Failed to send potential 2CR alert: {e}")
