import os
import requests
from datetime import datetime
import traceback
from typing import Tuple, Optional 

# --- 1. Nastavení a klíče ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- 2. Funkce pro odeslání zprávy (Finální verze) ---

def send_telegram_message(message: str, parse_mode: Optional[str] = None) -> bool:
    """Odešle textovou zprávu na Telegram. Bezpečně přidává parse_mode, jen pokud je nastaven."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: Klíče nejsou nastaveny.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    
    # Přidáme parse_mode jen pro HTML/Markdown, nikoli pro None
    if parse_mode:
        payload['parse_mode'] = parse_mode

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status() 

        response_json = response.json()
        if response_json.get("ok"):
            print("Zpráva úspěšně odeslána na Telegram.")
            return True
        else:
            print(f"Chyba z Telegram API: {response_json.get('description', 'Neznámá chyba')}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Kritická chyba při komunikaci s Telegram API: {e}")
        return False


# --- 3. Funkce pro generování obsahu reportu (Zapnutí HTML) ---

def generate_report_content() -> Tuple[str, Optional[str]]:
    """Generuje obsah reportu ve formátu HTML."""
    
    current_time = datetime.now().strftime("%d.%m.%Y v %H:%M:%S")
    
    # Příklad dat z tvé aplikace
    total_users = 155 
    new_records = 3 
    status_message = "Dnes bez incidentů."
    
    # Vytvoření zprávy v HTML formátu
    html_report_text = f"""
    <b>🚀 Streamlit Report: Denní Souhrn</b>
    <pre>Datum spuštění: {current_time}</pre>
    <hr>
    <b>Přehled metrik:</b>
    <ul>
        <li>Celkový počet uživatelů: <b>{total_users}</b></li>
        <li>Nových záznamů za den: <b>{new_records}</b></li>
        <li>Stav aplikace: {status_message}</li>
    </ul>
    <a href="https://tvojeaplikace.streamlit.app/">Odkaz na tvou Streamlit aplikaci</a>
    """
    
    # Vrátíme HTML text a specifikujeme mód 'HTML'
    return html_report_text, 'HTML' 


# --- 4. Hlavní spouštěcí blok ---

if __name__ == '__main__':
    print(f"Spouštím Telegram report generator v {datetime.now().strftime('%H:%M:%S')}...")
    
    try:
        report_content, parse_mode = generate_report_content()
        
        # Odeslání zprávy.
        success = send_telegram_message(report_content, parse_mode=parse_mode)
        
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
