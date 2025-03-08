import pandas as pd
import logging
from typing import Dict, Optional, Tuple, List
from config_handler import TimeFrame

class TwoCandleRejection:
    """
    Detects Two Candle Rejection (2CR) patterns based on Fair Value Gaps and price action.
    
    A 2CR involves two possible scenarios:
    1. First candle rejects a PD array (FVG) with a long wick and closes in the opposite direction
    2. First candle doesn't reject, but second candle sweeps previous high/low and then rejects
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def find_2cr_pattern(self, df: pd.DataFrame, fvg: Dict, timeframe: TimeFrame) -> Optional[Dict]:
        """
        Find 2CR pattern after price interacts with an FVG.
        
        Args:
            df: DataFrame with OHLC data
            fvg: FVG information including type, top, bottom, time
            timeframe: The timeframe being analyzed
            
        Returns:
            Dictionary with 2CR pattern details or None if no pattern found
        """
        if not isinstance(df, pd.DataFrame) or df.empty or len(df) < 3:
            return None
            
        # Get data after FVG formation
        post_fvg_df = df[df['time'] > fvg['time']].copy()
        if len(post_fvg_df) < 3:
            return None
            
        # Find when price entered the FVG (mitigation)
        mitigation_idx = None
        fvg_type = fvg['type']
        fvg_top = fvg['top']
        fvg_bottom = fvg['bottom']
        
        for idx in range(len(post_fvg_df)):
            candle = post_fvg_df.iloc[idx]
            
            if fvg_type == 'bullish' and candle['low'] <= fvg_top:
                mitigation_idx = idx
                break
            elif fvg_type == 'bearish' and candle['high'] >= fvg_bottom:
                mitigation_idx = idx
                break
                
        if mitigation_idx is None:
            # FVG not yet mitigated
            return None
            
        # Get data after mitigation for analysis
        post_mitigation_df = post_fvg_df.iloc[mitigation_idx:].copy()
        if len(post_mitigation_df) < 3:
            return None
        
        # Look for 2CR pattern after mitigation
        for i in range(len(post_mitigation_df) - 2):
            candle1 = post_mitigation_df.iloc[i]
            candle2 = post_mitigation_df.iloc[i + 1]
            candle3 = post_mitigation_df.iloc[i + 2] if i + 2 < len(post_mitigation_df) else None
            
            # Scenario 1: First candle rejects
            first_candle_rejection = self._check_first_candle_rejection(candle1, fvg_type, fvg_top, fvg_bottom)
            
            # Scenario 2: Second candle sweeps and rejects
            second_candle_rejection = False
            if not first_candle_rejection and i > 0:  # Need previous candle for sweeping
                prev_candle = post_mitigation_df.iloc[i - 1]
                second_candle_rejection = self._check_second_candle_rejection(
                    prev_candle, candle1, candle2, fvg_type
                )
            
            # If either rejection pattern is detected
            if first_candle_rejection or second_candle_rejection:
                # Check if we have a third candle for follow-through
                has_follow_through = False
                follow_through_candle = None
                if candle3 is not None:
                    has_follow_through, follow_through_details = self._check_follow_through(
                        candle2, candle3, fvg_type
                    )
                    if has_follow_through:
                        follow_through_candle = candle3
                
                return {
                    "type": fvg_type,
                    "rejection_type": "first_candle" if first_candle_rejection else "second_candle",
                    "first_candle": {
                        "time": candle1['time'],
                        "open": candle1['open'],
                        "high": candle1['high'],
                        "low": candle1['low'],
                        "close": candle1['close']
                    },
                    "second_candle": {
                        "time": candle2['time'],
                        "open": candle2['open'],
                        "high": candle2['high'],
                        "low": candle2['low'],
                        "close": candle2['close']
                    },
                    "has_follow_through": has_follow_through,
                    "follow_through_candle": {
                        "time": follow_through_candle['time'],
                        "open": follow_through_candle['open'],
                        "high": follow_through_candle['high'],
                        "low": follow_through_candle['low'],
                        "close": follow_through_candle['close']
                    } if follow_through_candle is not None else None,
                    "fvg_mitigation_time": post_fvg_df.iloc[mitigation_idx]['time'],
                    "is_ugly": self._is_ugly_rejection(candle1, candle2, candle3, fvg_type) if candle3 is not None else False
                }
                
        return None
    
    def _check_first_candle_rejection(self, candle: pd.Series, fvg_type: str, fvg_top: float, fvg_bottom: float) -> bool:
        """Check if the first candle shows a rejection pattern"""
        
        if fvg_type == 'bullish':
            # For bullish FVG, rejection is shown by a long lower wick and upward close
            body_size = abs(candle['close'] - candle['open'])
            lower_wick = candle['open'] - candle['low'] if candle['open'] > candle['low'] else candle['close'] - candle['low']
            is_up_candle = candle['close'] > candle['open']
            
            # Check for rejection: long lower wick, upward close, and price touching the FVG
            if is_up_candle and lower_wick > body_size * 0.7 and candle['low'] <= fvg_top:
                return True
                
        elif fvg_type == 'bearish':
            # For bearish FVG, rejection is shown by a long upper wick and downward close
            body_size = abs(candle['close'] - candle['open'])
            upper_wick = candle['high'] - candle['open'] if candle['open'] < candle['high'] else candle['high'] - candle['close']
            is_down_candle = candle['close'] < candle['open']
            
            # Check for rejection: long upper wick, downward close, and price touching the FVG
            if is_down_candle and upper_wick > body_size * 0.7 and candle['high'] >= fvg_bottom:
                return True
                
        return False
    
    def _check_second_candle_rejection(self, prev_candle: pd.Series, first_candle: pd.Series, 
                                     second_candle: pd.Series, fvg_type: str) -> bool:
        """Check if the second candle sweeps previous candle high/low and then rejects"""
        
        if fvg_type == 'bullish':
            # Second candle needs to sweep below the previous candle low and then close up
            sweep_occurred = second_candle['low'] < first_candle['low']
            is_up_candle = second_candle['close'] > second_candle['open']
            
            # Check for significant lower wick showing rejection
            body_size = abs(second_candle['close'] - second_candle['open'])
            lower_wick = second_candle['open'] - second_candle['low'] if second_candle['open'] > second_candle['low'] else second_candle['close'] - second_candle['low']
            
            return sweep_occurred and is_up_candle and lower_wick > body_size * 0.5
            
        elif fvg_type == 'bearish':
            # Second candle needs to sweep above the previous candle high and then close down
            sweep_occurred = second_candle['high'] > first_candle['high']
            is_down_candle = second_candle['close'] < second_candle['open']
            
            # Check for significant upper wick showing rejection
            body_size = abs(second_candle['close'] - second_candle['open'])
            upper_wick = second_candle['high'] - second_candle['open'] if second_candle['open'] < second_candle['high'] else second_candle['high'] - second_candle['close']
            
            return sweep_occurred and is_down_candle and upper_wick > body_size * 0.5
            
        return False
    
    def _check_follow_through(self, reject_candle: pd.Series, next_candle: pd.Series, fvg_type: str) -> Tuple[bool, Dict]:
        """Check if the candle after rejection shows follow-through in the expected direction"""
        
        if fvg_type == 'bullish':
            # For bullish FVG, expecting upward continuation
            is_up_candle = next_candle['close'] > next_candle['open']
            is_expansion = next_candle['high'] > reject_candle['high']
            follow_through = is_up_candle and is_expansion
            
            return follow_through, {
                "is_up_candle": is_up_candle,
                "is_expansion": is_expansion
            }
            
        elif fvg_type == 'bearish':
            # For bearish FVG, expecting downward continuation
            is_down_candle = next_candle['close'] < next_candle['open']
            is_expansion = next_candle['low'] < reject_candle['low']
            follow_through = is_down_candle and is_expansion
            
            return follow_through, {
                "is_down_candle": is_down_candle,
                "is_expansion": is_expansion
            }
            
        return False, {}
    
    def _is_ugly_rejection(self, candle1: pd.Series, candle2: pd.Series, candle3: pd.Series, fvg_type: str) -> bool:
        """
        Check if this is an 'ugly' 2 candle rejection.
        
        An ugly 2CR happens when the third candle does not show clear expansion
        and takes multiple candles to continue in the expected direction.
        """
        if fvg_type == 'bullish':
            # For bullish, ugly if third candle has long lower wick and no clear upward movement
            body_size = abs(candle3['close'] - candle3['open'])
            lower_wick = candle3['open'] - candle3['low'] if candle3['open'] > candle3['low'] else candle3['close'] - candle3['low']
            
            # If third candle has a significant lower wick and doesn't close above second candle high
            return lower_wick > body_size * 1.5 and candle3['close'] < candle2['high']
            
        elif fvg_type == 'bearish':
            # For bearish, ugly if third candle has long upper wick and no clear downward movement
            body_size = abs(candle3['close'] - candle3['open'])
            upper_wick = candle3['high'] - candle3['open'] if candle3['open'] < candle3['high'] else candle3['high'] - candle3['close']
            
            # If third candle has a significant upper wick and doesn't close below second candle low
            return upper_wick > body_size * 1.5 and candle3['close'] > candle2['low']
            
        return False