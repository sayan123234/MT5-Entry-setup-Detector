import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import os

class AlertCache:
    def __init__(self, cache_dir: str = "cache", time_func=None):
        self.logger = logging.getLogger(__name__)
        self.cache_dir = Path(cache_dir)
        self.time_func = time_func or datetime.now
        
        try:
            self.cache_dir.mkdir(exist_ok=True, mode=0o755)
        except Exception as e:
            self.logger.error(f"Failed to create cache directory: {e}")
            raise

        self.cache_file = self.cache_dir / f"fvg_alerts_{self.time_func().strftime('%Y%m%d')}.json"
        self.last_cleanup = None
        self.alerts = self._load_cache()
        self.manage_cache_size()

    def _load_cache(self) -> dict:
        """Load the cache file for the current day or create a new one"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    if self._is_cache_expired():
                        return {}
                    return data
            return {}
        except Exception as e:
            self.logger.error(f"Error loading cache file: {e}")
            return {}

    def _save_cache(self) -> None:
        """Save the current cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.alerts, f)
        except Exception as e:
            self.logger.error(f"Error saving cache file: {e}")

    def _is_cache_expired(self) -> bool:
        """Check if the current cache file is from a previous day"""
        if not self.cache_file.exists():
            return True
            
        file_date = datetime.strptime(
            self.cache_file.stem.split('_')[-1], 
            '%Y%m%d'
        ).date()
        current_date = self.time_func().date()
        return file_date < current_date

    def _generate_alert_key(self, symbol: str, timeframe: str, fvg_type: str, fvg_time: str) -> str:
        """Generate a unique key for the alert using symbol, timeframe, type, and time"""
        return f"{symbol}|{timeframe}|{fvg_type}|{fvg_time}"

    def is_duplicate(self, symbol: str, timeframe: str, fvg_type: str, fvg_time: str) -> bool:
        """Check if this exact FVG instance has already been alerted"""
        self.check_and_cleanup()
        alert_key = self._generate_alert_key(symbol, timeframe, fvg_type, fvg_time)
        return alert_key in self.alerts

    def add_alert(self, symbol: str, timeframe: str, fvg_type: str, fvg_time: str) -> None:
        """Add a new alert to the cache"""
        alert_key = self._generate_alert_key(symbol, timeframe, fvg_type, fvg_time)
        self.alerts[alert_key] = self.time_func().isoformat()
        self._save_cache()

    def check_and_cleanup(self) -> None:
        """Check if cache needs cleanup and perform if necessary"""
        current_time = self.time_func()
        
        if self.last_cleanup is None:
            self.last_cleanup = current_time
            
        if current_time.date() > self.last_cleanup.date():
            self.logger.info("New day detected, cleaning up cache...")
            self._cleanup()
            self.last_cleanup = current_time

    def _cleanup(self) -> None:
        """Clean up the cache for the new day"""
        try:
            self.alerts = {}
            self.cache_file = self.cache_dir / f"fvg_alerts_{self.time_func().strftime('%Y%m%d')}.json"
            self._save_cache()
            
            for cache_file in self.cache_dir.glob('fvg_alerts_*.json'):
                if cache_file != self.cache_file:
                    try:
                        os.remove(cache_file)
                    except Exception as e:
                        self.logger.error(f"Error removing old cache file {cache_file}: {e}")
                        
            self.logger.info("Cache cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {e}")
            
    def manage_cache_size(self):
        """Cleanup old cache files if total size exceeds limit"""
        try:
            MAX_CACHE_SIZE = 100 * 1024 * 1024  # 100MB
            total_size = 0
            cache_files = sorted(
                self.cache_dir.glob('fvg_alerts_*.json'),
                key=lambda x: x.stat().st_mtime
            )
            
            for file in cache_files:
                total_size += file.stat().st_size
                if total_size > MAX_CACHE_SIZE:
                    try:
                        file.unlink()
                        self.logger.info(f"Removed old cache file: {file}")
                    except Exception as e:
                        self.logger.error(f"Failed to remove cache file: {e}")
        except Exception as e:
            self.logger.error(f"Cache management error: {e}")