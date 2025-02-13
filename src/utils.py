import requests
import os
import logging
from datetime import datetime
from typing import Optional

def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram"""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not all([token, chat_id]):
        logging.error("Telegram credentials not configured in .env file")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        response = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        })
        response.raise_for_status()  # Will raise an exception for 4XX/5XX status codes
        
        if response.status_code == 200:
            logging.debug("Telegram alert sent successfully")  # Changed to debug level
            return True
        else:
            logging.error(f"Telegram API returned unexpected status code: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Telegram alert: {str(e)}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error sending Telegram alert: {str(e)}")
        return False