import yaml
import MetaTrader5 as mt5
from typing import List, Dict, Any
import logging
from enum import Enum

class TimeFrame(Enum):
    MONTHLY = mt5.TIMEFRAME_MN1
    WEEKLY = mt5.TIMEFRAME_W1
    DAILY = mt5.TIMEFRAME_D1
    H4 = mt5.TIMEFRAME_H4

class ConfigHandler:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigHandler, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize configuration if not already loaded"""
        if self._config is None:
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Return default configuration"""
        return {
            'timeframes': {
                'monthly': {
                    'value': mt5.TIMEFRAME_MN1,
                    'max_lookback': 12
                },
                'weekly': {
                    'value': mt5.TIMEFRAME_W1,
                    'max_lookback': 24
                },
                'daily': {
                    'value': mt5.TIMEFRAME_D1,
                    'max_lookback': 50
                },
                'h4': {
                    'value': mt5.TIMEFRAME_H4,
                    'max_lookback': 100
                }
            },
            'fvg_settings': {
                'min_size': 0.0001,
                'swing_window': 5
            },
            'telegram': {
                'enabled': True,
                'include_charts': True
            }
        }
    
    def get_watchlist_symbols(self) -> List[str]:
        """Return available symbols for trading system"""
        major_pairs = [
            "EURUSDm", "USDJPYm", "GBPUSDm", "USDCHFm", 
            "USDCADm", "AUDUSDm", "NZDUSDm"
        ]
        
        crosses = [
            "EURGBPm", "EURJPYm", "EURCHFm", "EURAUDm", "EURCADm",
            "GBPJPYm", "GBPCHFm", "GBPAUDm", "GBPCADm"
        ]
        
        metals = ["XAUUSDm", "XAGUSDm"]
        crypto = ["BTCUSDm", "ETHUSDm"]
        
        available_symbols = []
        for symbol in major_pairs + crosses + metals + crypto:
            if mt5.symbol_info(symbol) is not None:
                available_symbols.append(symbol)
        
        return available_symbols
    
    @property
    def timeframes(self) -> Dict:
        """Access to timeframes configuration"""
        return self._config['timeframes']
    
    @property
    def fvg_settings(self) -> Dict:
        """Access to FVG settings"""
        return self._config['fvg_settings']
    
    @property
    def telegram_config(self) -> Dict:
        """Access to telegram configuration"""
        return self._config['telegram']