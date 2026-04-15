import requests
from django.conf import settings

def send_telegram_alert(message):
    """
    Sends a formatted HTML message to the designated Telegram group.
    Fails silently so it never crashes the main app if Telegram is down.
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)

    if not token or not chat_id:
        print("Telegram Alert Failed: Token or Chat ID is missing.")
        return False 

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML', 
        'disable_web_page_preview': True
    }
    
    try:
        # Send the ping to Telegram
        response = requests.post(url, data=payload, timeout=5)
        
        # --- THE FIX: Force it to print Telegram's exact rejection reason ---
        if not response.ok:
            print(f"\n❌ TELEGRAM REJECTED THE MESSAGE!")
            print(f"Reason: {response.text}\n")
            return False
            
        return True
        
    except Exception as e:
        print(f"\n❌ TELEGRAM NETWORK ERROR: {e}\n")
        return False