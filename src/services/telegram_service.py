import requests
import os
import logging
from typing import Optional
from src.utils.helpers import mt5_operation_with_timeout, _rate_limiter

class TelegramService:
    """
    Service for sending alerts to Telegram.
    
    This class handles:
    - Sending messages to Telegram
    - Rate limiting to prevent spam
    - Error handling for Telegram API
    """
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize the Telegram service.
        
        Args:
            token: Telegram bot token (if None, will be loaded from environment)
            chat_id: Telegram chat ID (if None, will be loaded from environment)
        """
        self.logger = logging.getLogger(__name__)
        self.token = token or os.getenv("TELEGRAM_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        
        if not all([self.token, self.chat_id]):
            self.logger.warning("Telegram credentials not fully configured")
    
    @mt5_operation_with_timeout("telegram_alert")
    def send_alert(self, message: str, rate_limit: int = 60) -> bool:
        """
        Send alert to Telegram with rate limiting.
        
        Args:
            message: The message to send
            rate_limit: Minimum seconds between identical messages
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not all([self.token, self.chat_id]):
            self.logger.error("Telegram credentials not configured in .env file")
            return False
            
        # Rate limiting based on message prefix
        cache_key = f"telegram_last_sent_{message[:50]}"
        if _rate_limiter.is_rate_limited(cache_key, rate_limit):
            self.logger.info(f"Alert throttled: {message[:100]}...")
            return False
        
        # Send message
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10  # Add explicit timeout for the HTTP request
            )
            response.raise_for_status()
            return response.status_code == 200
                
        except requests.RequestException as e:
            self.logger.error(f"Failed to send Telegram alert: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram alert: {str(e)}")
            return False

# Singleton instance for global use
telegram_service = TelegramService()

def send_telegram_alert(message: str, rate_limit: int = 60) -> bool:
    """
    Convenience function to send a Telegram alert using the global service.
    
    Args:
        message: The message to send
        rate_limit: Minimum seconds between identical messages
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    return telegram_service.send_alert(message, rate_limit)
