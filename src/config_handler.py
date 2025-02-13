import yaml
import MetaTrader5 as mt5
from enum import Enum
from pathlib import Path

class TimeFrame(Enum):
    MONTHLY = mt5.TIMEFRAME_MN1
    WEEKLY = mt5.TIMEFRAME_W1
    DAILY = mt5.TIMEFRAME_D1
    H4 = mt5.TIMEFRAME_H4

class ConfigHandler:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigHandler, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        config_path = Path("config/config.yaml")
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
    
    @property
    def timeframes(self):
        return self.config['timeframes']
    
    @property
    def symbols(self):
        return self.config['symbols']
    
    @property
    def fvg_settings(self):
        return self.config['fvg_settings']
    
    @property
    def telegram_config(self):
        return self.config['telegram']