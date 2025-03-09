import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

class CandleClassifier:
    """
    Classifies candles based on their appearance and behavior.
    
    Key classifications:
    - Disrespect Candle: Large body with small wicks, indicates strong trend continuation
    - Respect Candle: Long wicks with small body, indicates price respecting a key level
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def classify_candle(self, candle: pd.Series) -> Dict:
        """
        Classify a single candle based on its characteristics.
        
        Args:
            candle: A pandas Series containing OHLC data for a single candle
            
        Returns:
            Dictionary with candle classification details
        """
        # Calculate candle metrics
        body_size = abs(candle['close'] - candle['open'])
        candle_range = candle['high'] - candle['low']
        
        if candle_range == 0:  # Avoid division by zero
            body_to_range_ratio = 0
        else:
            body_to_range_ratio = body_size / candle_range
            
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        
        is_bullish = candle['close'] > candle['open']
        is_bearish = candle['close'] < candle['open']
        
        # Classify candle
        classification = {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "body_size": body_size,
            "candle_range": candle_range,
            "body_to_range_ratio": body_to_range_ratio,
            "upper_wick": upper_wick,
            "lower_wick": lower_wick
        }
        
        # Disrespect Candle: Large body with small wicks (body takes up most of the candle range)
        if body_to_range_ratio > 0.7:
            classification["type"] = "disrespect"
            classification["strength"] = body_to_range_ratio  # Higher ratio = stronger disrespect
            classification["direction"] = "bullish" if is_bullish else "bearish"
            
        # Respect Candle: Long wicks with small body
        elif body_to_range_ratio < 0.3:
            classification["type"] = "respect"
            
            # Determine which level is being respected based on wick length
            if upper_wick > lower_wick * 2:
                classification["respect_direction"] = "resistance"  # Respecting resistance (upper level)
            elif lower_wick > upper_wick * 2:
                classification["respect_direction"] = "support"  # Respecting support (lower level)
            else:
                classification["respect_direction"] = "both"  # Respecting both levels (indecision)
                
            classification["strength"] = 1 - body_to_range_ratio  # Lower ratio = stronger respect
            
        # Neutral Candle: Neither clear respect nor disrespect
        else:
            classification["type"] = "neutral"
            classification["strength"] = 0.5  # Moderate strength
            
        return classification
    
    def analyze_candle_sequence(self, df: pd.DataFrame, lookback: int = 5) -> List[Dict]:
        """
        Analyze a sequence of candles to identify patterns and context.
        
        Args:
            df: DataFrame with OHLC data
            lookback: Number of recent candles to analyze
            
        Returns:
            List of dictionaries with candle classifications
        """
        if len(df) < lookback:
            return []
            
        # Get the most recent candles
        recent_candles = df.iloc[-lookback:].copy()
        
        # Classify each candle
        classifications = []
        for i in range(len(recent_candles)):
            candle = recent_candles.iloc[i]
            classification = self.classify_candle(candle)
            
            # Add candle time and index
            classification["time"] = candle['time']
            classification["index"] = i
            
            classifications.append(classification)
            
        return classifications
    
    def detect_candle_pattern(self, classifications: List[Dict]) -> Optional[Dict]:
        """
        Detect patterns in a sequence of classified candles.
        
        Args:
            classifications: List of candle classifications
            
        Returns:
            Dictionary with pattern details or None if no significant pattern found
        """
        if not classifications or len(classifications) < 2:
            return None
            
        # Get the two most recent candles
        current = classifications[-1]
        previous = classifications[-2]
        
        # Check for strong disrespect after respect (breakout pattern)
        if previous["type"] == "respect" and current["type"] == "disrespect":
            return {
                "pattern": "breakout",
                "direction": current["direction"],
                "strength": current["strength"] * 1.5,  # Amplify strength for this pattern
                "description": f"{current['direction'].capitalize()} breakout after respect candle"
            }
            
        # Check for respect after disrespect (reversal pattern)
        if previous["type"] == "disrespect" and current["type"] == "respect":
            # Determine if this is a potential reversal
            if (previous["direction"] == "bullish" and current["respect_direction"] == "resistance") or \
               (previous["direction"] == "bearish" and current["respect_direction"] == "support"):
                return {
                    "pattern": "potential_reversal",
                    "direction": "bearish" if previous["direction"] == "bullish" else "bullish",
                    "strength": current["strength"],
                    "description": f"Potential {previous['direction']} to {current['respect_direction']} reversal"
                }
                
        # Check for consecutive disrespect candles (strong trend)
        if previous["type"] == "disrespect" and current["type"] == "disrespect" and \
           previous["direction"] == current["direction"]:
            return {
                "pattern": "strong_trend",
                "direction": current["direction"],
                "strength": (previous["strength"] + current["strength"]) / 2,
                "description": f"Strong {current['direction']} trend continuation"
            }
            
        # Check for consecutive respect candles (consolidation)
        if previous["type"] == "respect" and current["type"] == "respect":
            return {
                "pattern": "consolidation",
                "direction": "neutral",
                "strength": (previous["strength"] + current["strength"]) / 2,
                "description": "Price consolidation at key level"
            }
            
        return None
