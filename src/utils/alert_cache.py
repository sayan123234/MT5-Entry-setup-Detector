import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import os
from typing import Callable, Dict, Optional

class AlertCache:
    """
    Manages alert caching to prevent duplicate alerts.
    
    This class handles:
    - Daily cache files with automatic rotation
    - Duplicate alert detection
    - Cache size management
    - Automatic cleanup of old cache files
    """
    
    MAX_CACHE_SIZE = 100 * 1024 * 1024  # 100MB
    
    def __init__(self, cache_dir: str = "cache", time_func: Optional[Callable[[], datetime]] = None):
        """
        Initialize the alert cache system.
        
        Args:
            cache_dir: Directory to store cache files
            time_func: Function to get current time (useful for testing and time sync)
        """
        self.logger = logging.getLogger(__name__)
        self.cache_dir = Path(cache_dir)
        self.time_func = time_func or datetime.now
        
        # Ensure cache directory exists
        try:
            self.cache_dir.mkdir(exist_ok=True, mode=0o755)
        except Exception as e:
            self.logger.error(f"Failed to create cache directory: {e}")
            raise
            
        # Initialize cache state
        self.current_date = self.time_func().date()
        self.cache_file = self._get_cache_filename(self.current_date)
        self.last_cleanup = self.time_func()
        self.alerts = self._load_cache()
        
        # Perform initial cache maintenance
        self._manage_cache_size()

    def _get_cache_filename(self, date) -> Path:
        """Get the cache filename for a specific date"""
        return self.cache_dir / f"fvg_alerts_{date.strftime('%Y%m%d')}.json"

    def _load_cache(self) -> Dict:
        """Load the cache file for the current day or create a new one"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
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

    def _check_date_change(self) -> bool:
        """Check if the date has changed and update cache file if needed"""
        current_date = self.time_func().date()
        if current_date > self.current_date:
            self.logger.info("New day detected, rotating cache...")
            self.current_date = current_date
            self.cache_file = self._get_cache_filename(current_date)
            self.alerts = {}
            self._save_cache()
            self._cleanup_old_files()
            return True
        return False

    def _generate_alert_key(self, symbol: str, timeframe: str, fvg_type: str, fvg_time: str) -> str:
        """Generate a unique key for the alert"""
        return f"{symbol}|{timeframe}|{fvg_type}|{fvg_time}"

    def is_duplicate(self, symbol: str, timeframe: str, fvg_type: str, fvg_time: str) -> bool:
        """Check if this exact alert has already been sent"""
        self._check_date_change()
        alert_key = self._generate_alert_key(symbol, timeframe, fvg_type, fvg_time)
        return alert_key in self.alerts

    def add_alert(self, symbol: str, timeframe: str, fvg_type: str, fvg_time: str) -> None:
        """Add a new alert to the cache"""
        alert_key = self._generate_alert_key(symbol, timeframe, fvg_type, fvg_time)
        self.alerts[alert_key] = self.time_func().isoformat()
        self._save_cache()
        
        # Periodically check cache size (not on every add to improve performance)
        current_time = self.time_func()
        if (current_time - self.last_cleanup).total_seconds() > 3600:  # Once per hour
            self._manage_cache_size()
            self.last_cleanup = current_time

    def _cleanup_old_files(self) -> None:
        """Remove old cache files (keep only the current one)"""
        try:
            for cache_file in self.cache_dir.glob('fvg_alerts_*.json'):
                if cache_file != self.cache_file:
                    try:
                        os.remove(cache_file)
                        self.logger.info(f"Removed old cache file: {cache_file}")
                    except Exception as e:
                        self.logger.error(f"Error removing old cache file {cache_file}: {e}")
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {e}")

    def _manage_cache_size(self) -> None:
        """Cleanup old cache files if total size exceeds limit"""
        try:
            total_size = 0
            cache_files = sorted(
                self.cache_dir.glob('fvg_alerts_*.json'),
                key=lambda x: x.stat().st_mtime
            )
            
            # Keep current day's file regardless of size
            current_files = [f for f in cache_files if f == self.cache_file]
            old_files = [f for f in cache_files if f != self.cache_file]
            
            # Calculate size and remove old files if needed
            for file in old_files:
                total_size += file.stat().st_size
                if total_size > self.MAX_CACHE_SIZE:
                    try:
                        file.unlink()
                        self.logger.info(f"Removed old cache file due to size limit: {file}")
                    except Exception as e:
                        self.logger.error(f"Failed to remove cache file: {e}")
        except Exception as e:
            self.logger.error(f"Cache management error: {e}")
            
    # For backward compatibility
    def check_and_cleanup(self) -> None:
        """Legacy method for compatibility"""
        self._check_date_change()
