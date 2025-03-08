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
    H1 = "H1"
    M15 = "M15"
    M5 = "M5"
    M1 = "M1"
    
    def __lt__(self, other):
        order = ["MN1", "W1", "D1", "H4", "H1", "M15", "M5", "M1"]
        return order.index(self.value) > order.index(other.value)

    @property
    def mt5_timeframe(self):
        mapping = {
            "MN1": mt5.TIMEFRAME_MN1,
            "W1": mt5.TIMEFRAME_W1,
            "D1": mt5.TIMEFRAME_D1,
            "H4": mt5.TIMEFRAME_H4,
            "H1": mt5.TIMEFRAME_H1,
            "M15": mt5.TIMEFRAME_M15,
            "M5": mt5.TIMEFRAME_M5,
            "M1": mt5.TIMEFRAME_M1
        }
        return mapping[self.value]

class ConfigHandler:
    def __init__(self, config_file=None):
        if config_file is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.config_file = base_dir / "config" / "config.yaml"
        else:
            self.config_file = Path(config_file)
        self.logger = logging.getLogger(__name__)
        self.config = {}
        self._load_config()
        if not self.validate_config(self.config):
            raise ValueError("Invalid configuration")
        self.symbol_suffix = self._get_symbol_suffix()
        self.timeframe_hierarchy = self._setup_timeframe_hierarchy()

    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            if not self.config_file.exists():
                self.logger.error(f"Configuration file not found: {self.config_file}")
                raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)

            if not self.config:
                raise ValueError("Empty configuration file")

        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML configuration: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def _setup_timeframe_hierarchy(self) -> Dict[TimeFrame, List[TimeFrame]]:
        """Setup the hierarchy of timeframes"""
        timeframes = list(TimeFrame)
        hierarchy = {}
        for i, tf in enumerate(timeframes):
            hierarchy[tf] = timeframes[i+1:]
        return hierarchy

    def validate_timeframe_hierarchy(self) -> bool:
        """Validate that the timeframe hierarchy is properly configured"""
        try:
            configured_timeframes = set(TimeFrame(tf) for tf in self.config.get('timeframes', {}))
            for htf, ltf_list in self.timeframe_hierarchy.items():
                if htf not in configured_timeframes:
                    continue
                for ltf in ltf_list:
                    if ltf in configured_timeframes and not htf > ltf:
                        self.logger.error(f"Invalid timeframe relationship: {htf.value} should be higher than {ltf.value}")
                        return False
            return True
        except Exception as e:
            self.logger.error(f"Error validating timeframe hierarchy: {e}")
            return False

    def validate_symbols(self) -> bool:
        """Validate that configured symbols are available in MT5"""
        valid_symbols = True
        for symbol in self.get_watchlist_symbols():
            if mt5.symbol_info(symbol) is None:
                self.logger.warning(f"Symbol not available: {symbol}")
                valid_symbols = False
        return valid_symbols

    def validate_config(self, config: dict) -> bool:
        """Validate the configuration structure"""
        required_fields = ['timeframes', 'symbols', 'fvg_settings']
        if not all(field in config for field in required_fields):
            self.logger.error("Missing required configuration fields")
            return False
            
        # Updated validation for nested min_size
        fvg_settings = config.get('fvg_settings', {})
        min_size = fvg_settings.get('min_size')
        if isinstance(min_size, dict):
            # Check that 'default' exists and is a number
            if 'default' not in min_size or not isinstance(min_size['default'], (int, float)):
                self.logger.error("Invalid FVG min_size configuration: 'default' must be a number")
                return False
            # Optionally validate other keys
            for key, value in min_size.items():
                if not isinstance(value, (int, float)):
                    self.logger.error(f"Invalid FVG min_size value for {key}: must be a number")
                    return False
        elif not isinstance(min_size, (int, float)):
            self.logger.error("Invalid FVG min_size configuration: must be a number or dict with 'default'")
            return False

        return True

    def _get_symbol_suffix(self) -> str:
        """Get the symbol suffix from config or return empty string if not set"""
        suffix = self.config.get("symbol_suffix", "")
        if suffix:
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
            symbols.extend(self._apply_suffix(symbol) for symbol in category)
        return symbols

    def get_alert_settings(self) -> Dict[str, Any]:
        return self.config.get("alert_settings", {})
    
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
