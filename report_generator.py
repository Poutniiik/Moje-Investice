import os
import requests
from datetime import datetime
import traceback
from typing import Tuple, Optional # Import pro type hinting

# --- 1. Nastavení a klíče ---

# Načtení klíčů z proměnných prostředí (nastavené v GitHub Actions)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- 2. Funkce pro odeslání zprávy (OPRAVENO: Odstranění parse_mode, pokud je None) ---

def send_telegram_message(message: str, parse_mode: Optional[str] = None) -> bool:
    """Odešle textovou zprávu na Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: Proměnné TELEGRAM_BOT_TOKEN nebo TELEGRAM_CHAT_ID nejsou nastaveny v prostředí.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Základní payload
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    
    # DŮLEŽITÉ: parse_mode se přidá do payloadu POUZE, pokud je hodnota (např. 'HTML')
    if parse_mode:
        payload['parse_mode'] = parse_mode

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status() # Vyhodí chybu pro stavové kódy 4xx/5xx

        # Kontrola odpovědi z Telegram API
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


# --- 3. Funkce pro generování obsahu reportu (OPRAVENO: Vrací jen testovací text) ---

def generate_report_content() -> Tuple[str, Optional[str]]:
    """
    Tato funkce generuje obsah reportu. 
    Pro debugování vrací pouze čistý, neformátovaný text.
    """
    
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    # Testovací text bez jakéhokoliv speciálního formátování (pro eliminaci chyby 400)
    test_text = f"Test cisteho textu z GitHub Actions. Datum: {current_time}. Klice byly nacteny. Pokud toto vidite, problem neni ve formatovani."

    # Vracíme text a None jako mód (aby se neposílal parse_mode)
    return test_text, None 
    
    # Původní kód je odsud níže nedostupný, což je pro debug správné.


# --- 4. Hlavní spouštěcí blok ---

if __name__ == '__main__':
    print(f"Spouštím Telegram report generator v {datetime.now().strftime('%H:%M:%S')}...")
    
    try:
        # Generování obsahu a výběr módu formátování
        report_content, parse_mode = generate_report_content()
        
        # Odeslání zprávy.
        success = send_telegram_message(report_content, parse_mode=parse_mode)
        
        if success:
            print("Skript dokončen úspěšně.")
        else:
            print("Skript dokončen, ale zpráva se nepodařila odeslat.")
            # Ukončení s chybovým kódem, aby GitHub Actions nahlásil selhání
            exit(1)
            
    except Exception as e:
        # V případě kritické chyby vypíšeme zásobník volání pro debugování
        print(f"Kritická chyba v report_generator.py: {e}")
        print("-" * 30)
        traceback.print_exc()
        print("-" * 30)
        exit(1) # Ukončení s chybovým kódem pro selhání Actions
