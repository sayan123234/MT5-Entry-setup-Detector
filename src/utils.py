import requests
import os
import logging
from functools import lru_cache
import time
import threading
from datetime import datetime

def mt5_operation_with_timeout(operation_name: str, timeout: int = 30):
    """
    Decorator that adds timeout functionality to MT5 operations
    
    Args:
        operation_name: Name of the operation for logging
        timeout: Maximum time in seconds to wait for operation completion
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Use threading.Timer instead of signal for cross-platform support
            timer = threading.Timer(timeout, lambda: (_ for _ in ()).throw(TimeoutError(f"Operation {operation_name} timed out")))
            try:
                timer.start()  # Start the timeout timer
                result = func(*args, **kwargs)  # Execute the function
            finally:
                timer.cancel()  # Ensure the timer is canceled once function completes
            return result

        return wrapper
    return decorator

def is_trading_day():
    """
    Check if today is a trading day (Monday to Friday)
    
    Returns:
        bool: True if it's a weekday, False if it's weekend
    """
    now = datetime.now()
    return now.weekday() < 5  # Monday (0) to Friday (4)

@mt5_operation_with_timeout("telegram_alert")
def send_telegram_alert(message: str, rate_limit: int = 60) -> bool:
    """
    Send alert to Telegram with rate limiting.
    
    Args:
        message: The message to send
        rate_limit: Minimum seconds between identical messages
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    # Create a simple in-memory cache if not exists
    if not hasattr(send_telegram_alert, '_cache'):
        send_telegram_alert._cache = {}
    
    cache_key = f"telegram_last_sent_{message[:50]}"
    last_sent = send_telegram_alert._cache.get(cache_key)
    
    if last_sent and time.time() - last_sent < rate_limit:
        logging.info(f"Alert throttled: {message[:100]}...")
        return False
        
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not all([token, chat_id]):
        logging.error("Telegram credentials not configured in .env file")
        return False
    
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
        )
        response.raise_for_status()
        success = response.status_code == 200
        if success:
            send_telegram_alert._cache[cache_key] = time.time()
        return success
            
    except Exception as e:
        logging.error(f"Failed to send Telegram alert: {str(e)}")
        return False