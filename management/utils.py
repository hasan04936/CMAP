import requests
from .models import Company

def send_telegram_alert(message):
    """
    Sends a formatted HTML message to the designated Telegram group.
    Fails silently so it never crashes the main app if Telegram is down.
    """
    try:
        # --- THE UPGRADE: Pull credentials from the Database, NOT settings.py ---
        company = Company.objects.first()
        
        if not company or not company.telegram_bot_token or not company.telegram_chat_id:
            print("Telegram Alert Skipped: Token or Chat ID is not configured in Settings.")
            return False 

        token = company.telegram_bot_token
        chat_id = company.telegram_chat_id
        # ------------------------------------------------------------------------

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML', 
            'disable_web_page_preview': True
        }
        
        # Send the ping to Telegram
        response = requests.post(url, data=payload, timeout=5)
        
        # Force it to print Telegram's exact rejection reason
        if not response.ok:
            print(f"\n❌ TELEGRAM REJECTED THE MESSAGE!")
            print(f"Reason: {response.text}\n")
            return False
            
        return True
        
    except Exception as e:
        print(f"\n❌ TELEGRAM NETWORK ERROR: {e}\n")
        return False