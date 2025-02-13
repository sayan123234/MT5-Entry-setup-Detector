import requests
import os
import logging
from datetime import datetime

def send_telegram_alert(message: str):
    """Send alert to Telegram"""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not all([token, chat_id]):
        logging.error("Telegram credentials not configured")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        response = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        })
        response.raise_for_status()
        logging.info("Alert sent successfully")
    except Exception as e:
        logging.error(f"Failed to send alert: {str(e)}")