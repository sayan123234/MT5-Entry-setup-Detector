import yaml
from enum import Enum
from typing import Dict, List, Any
import MetaTrader5 as mt5
import logging
from pathlib import Path

class TimeFrame(Enum):
    MONTHLY = "MN1"
    WEEKLY = "W1"
    DAILY = "D1"
    H4 = "H4"

    @property
    def mt5_timeframe(self):
        """Get the corresponding MT5 timeframe constant"""
        mapping = {
            "MN1": mt5.TIMEFRAME_MN1,
            "W1": mt5.TIMEFRAME_W1,
            "D1": mt5.TIMEFRAME_D1,
            "H4": mt5.TIMEFRAME_H4
        }
        return mapping[self.value]

    def __str__(self):
        return self.value

class ConfigHandler:
    def __init__(self, config_file=Path("config") / "config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.symbol_suffix = self._get_symbol_suffix()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_file, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Error loading config file '{self.config_file}': {e}")
            return {}

    def _get_symbol_suffix(self) -> str:
        """Get the symbol suffix from config or return empty string if not set"""
        suffix = self.config.get("symbol_suffix", "")
        if suffix:
            # If suffix starts with '.', keep it as is, otherwise add it to the symbol directly
            if suffix.startswith('.'):
                return suffix
            return f"{suffix}"
        return ""

    def _apply_suffix(self, symbol: str) -> str:
        """Apply the broker-specific suffix to a symbol"""
        if not self.symbol_suffix:
            return symbol
        return f"{symbol}{self.symbol_suffix}"

    def get_watchlist_symbols(self) -> List[str]:
        """Get list of symbols with proper suffix applied"""
        symbols = []
        for category in self.config.get("symbols", {}).values():
            # Apply suffix to each symbol
            symbols.extend(self._apply_suffix(symbol) for symbol in category)
        return symbols

    def get_timeframes(self) -> Dict[TimeFrame, int]:
        timeframes_config = self.config.get("timeframes", {})
        timeframes = {}
        for tf_name, details in timeframes_config.items():
            timeframes[TimeFrame(tf_name)] = details.get("max_lookback", 100)
        return timeframes

    @property
    def fvg_settings(self) -> Dict[str, Any]:
        return self.config.get("fvg_settings", {})

    @property
    def telegram_config(self) -> Dict[str, Any]:
        return self.config.get("telegram", {})