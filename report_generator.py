import os
import requests
from datetime import datetime
import traceback
from typing import Tuple, Optional 

# --- 1. Nastavení a klíče ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- 2. Funkce pro odeslání zprávy (Nejbezpečnější verze) ---

def send_telegram_message(message: str) -> bool: # Odstranili jsme parse_mode z argumentů
    """Odešle textovou zprávu na Telegram jako PLAIN TEXT."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: Klíče nejsou nastaveny.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Payload, který posílá pouze text a chat ID (NEJBEZPEČNĚJŠÍ)
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    
    # Všimni si, že parse_mode se neposílá vůbec!

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status() 

        response_json = response.json()
        if response_json.get("ok"):
            print("Zpráva úspěšně odeslána na Telegram.")
            return True
        else:
            # Tohle nám napoví, co je špatně, pokud to selže
            print(f"Chyba z Telegram API: {response_json.get('description', 'Neznámá chyba')}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Kritická chyba při komunikaci s Telegram API: {e}")
        return False


# --- 3. Funkce pro generování obsahu reportu ---

def generate_report_content() -> Tuple[str, Optional[str]]:
    """Generuje obsah reportu ve formátu HTML, používá pouze bezpečné tagy."""
    
    current_time = datetime.now().strftime("%d.%m.%Y v %H:%M:%S")
    
    # Zde můžeš vložit logiku pro získání dat z tvé Streamlit aplikace
    total_users = 158 
    new_records = 3 
    status_message = "Vše běží hladce, data OK."
    
    # Používáme jen základní, osvědčené HTML tagy: <b> (tučné), <pre> (předformátovaný text)
    html_report_text = f"""
    <b>🚀 Streamlit Report: Denní Souhrn</b>
    
    Datum: <pre>{current_time}</pre>
    
    <b>Přehled metrik:</b>
    
    \u2022 Celkový počet uživatelů: <b>{total_users}</b>
    \u2022 Nových záznamů za den: <b>{new_records}</b>
    \u2022 Stav: <i>{status_message}</i>
    
    Odkaz na aplikaci: https://tvojeaplikace.streamlit.app/
    """
    
    # Vrátíme HTML text a specifikujeme mód 'HTML'
    return html_report_text, 'HTML' 


# --- 4. Hlavní spouštěcí blok ---

if __name__ == '__main__':
    print(f"Spouštím Telegram report generator v {datetime.now().strftime('%H:%M:%S')}...")
    
    try:
        # Nyní generujeme POUZE text
        report_content = generate_report_content()
        
        # Odeslání zprávy. parse_mode neposíláme.
        success = send_telegram_message(report_content)
        
        if success:
            print("Skript dokončen úspěšně.")
        else:
            print("Skript dokončen, ale zpráva se nepodařila odeslat.")
            exit(1)
            
    except Exception as e:
        print(f"Kritická chyba v report_generator.py: {e}")
        print("-" * 30)
        traceback.print_exc()
        print("-" * 30)
        exit(1)
# --- Zbytek kódu (Sekce 4) ---
# ...
