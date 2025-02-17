import yaml
from enum import Enum
from typing import Dict, List, Any
import MetaTrader5 as mt5

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
    def __init__(self, config_file="config\config.yaml"):
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_file, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config file '{self.config_file}': {e}")
            return {}

    def get_watchlist_symbols(self) -> List[str]:
        symbols = []
        for category in self.config.get("symbols", {}).values():
            symbols.extend(category)
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