import requests
import os
import logging
from functools import lru_cache, wraps
import time
import threading
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypeVar

# Type variables for better type hinting
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

def mt5_operation_with_timeout(operation_name: str, timeout: int = 30) -> Callable[[F], F]:
    """
    Decorator that adds timeout functionality to MT5 operations.
    
    This decorator creates a timer that will raise a TimeoutError if the
    decorated function doesn't complete within the specified timeout period.
    
    Args:
        operation_name: Name of the operation for logging
        timeout: Maximum time in seconds to wait for operation completion
        
    Returns:
        Decorated function with timeout capability
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger(__name__)
            
            # Create exception to be raised on timeout
            timeout_ex = TimeoutError(f"Operation {operation_name} timed out after {timeout} seconds")
            
            # Use threading.Timer for cross-platform support
            timer = threading.Timer(
                timeout, 
                lambda: (_ for _ in ()).throw(timeout_ex)
            )
            
            try:
                logger.debug(f"Starting {operation_name} with {timeout}s timeout")
                timer.start()
                result = func(*args, **kwargs)
                return result
            except TimeoutError as e:
                logger.error(f"Timeout: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error in {operation_name}: {str(e)}")
                raise
            finally:
                timer.cancel()
                
        return wrapper  # type: ignore
    return decorator

def is_trading_day() -> bool:
    """
    Check if today is a trading day (Monday to Friday).
    
    Returns:
        bool: True if it's a weekday, False if it's weekend
    """
    now = datetime.now()
    return now.weekday() < 5  # Monday (0) to Friday (4)

class RateLimiter:
    """Simple rate limiter to prevent sending too many alerts."""
    
    def __init__(self) -> None:
        self._cache: Dict[str, float] = {}
        
    def is_rate_limited(self, key: str, rate_limit_seconds: int) -> bool:
        """Check if an operation is rate limited."""
        last_time = self._cache.get(key)
        current_time = time.time()
        
        if last_time is None or (current_time - last_time) >= rate_limit_seconds:
            self._cache[key] = current_time
            return False
        return True

# Global rate limiter instance
_rate_limiter = RateLimiter()
