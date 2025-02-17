import requests
import os
import logging

def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram"""
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
        return response.status_code == 200
            
    except Exception as e:
        logging.error(f"Failed to send Telegram alert: {str(e)}")
        return False