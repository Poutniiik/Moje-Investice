import os
import requests
from datetime import datetime
import json
import traceback

# --- 1. Nastavení a klíče ---

# Načtení klíčů z proměnných prostředí (nastavené v GitHub Actions)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- 2. Funkce pro odeslání zprávy ---

def send_telegram_message(message: str, parse_mode: str = 'MarkdownV2') -> bool:
    """Odešle textovou zprávu na Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: Proměnné TELEGRAM_BOT_TOKEN nebo TELEGRAM_CHAT_ID nejsou nastaveny v prostředí.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Text musí být ošetřen pro režim MarkdownV2 (speciální znaky jako ., -, ( atd. musí být escapovány)
    # Zde použijeme jednoduchou utilitu, která se hodí pro formátování.
    # POZNÁMKA: Pro jednoduchost, pokud neplánuješ složité formátování, 
    # můžeš použít parse_mode='HTML' nebo 'Markdown' (pokud to tvůj bot podporuje)
    
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': parse_mode
    }

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


# --- 3. Funkce pro generování obsahu reportu ---

def generate_report_content() -> str:
    """
    Tato funkce generuje obsah reportu. 
    Zde provádíš veškerou logiku, jako je načítání dat, výpočty a sumarizace.
    """
    
    # 💡 Příklad, jak vygenerovat report (zde si vlož svou Streamlit logiku)
    
    current_time = datetime.now().strftime("%d\\.\\%m\\.\\%Y v %H:%M:%S")
    
    # Předpokládejme, že z tvé Streamlit aplikace bys normálně získal tato data
    total_users = 152
    new_records = 15
    status_message = "Aplikace běžela bez chyb."
    
    # Vytvoření zprávy ve formátu MarkdownV2 (vyžaduje escapování teček, hvězdiček, apod.)
    # Všimni si, že se používá zpětné lomítko \ před speciálními znaky (tečka, pomlčka)
    
    report_text = f"""
*🚀 Streamlit Report: Denní Souhrn*
Datum spuštění: `{current_time}`

\\- \\- \\- \\- \\- \\- \\- \\- \\- \\- \\- \\- \\- \\- \\- \\-

**Přehled metrik:**
* Celkový počet uživatelů: `{total_users}`
* Nových záznamů za den: `{new_records}`
* Důležité info: {status_message}

[Odkaz na aplikaci](https://tvojeaplikace\\.streamlit\\.app/)

*Poznámka:* Text je formátován pomocí `MarkdownV2` pro lepší vzhled\\.
    """
    
    # Pro tento příklad musíme escapovat všechny speciální znaky pro MarkdownV2
    # Nezapomeň escapovat: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    
    # Jednoduchý hack, jak se vyhnout složitému escapování v textu, je použít 'HTML' mód:
    
    html_report_text = f"""
    <b>🚀 Streamlit Report: Denní Souhrn</b>
    <pre>Datum spuštění: {current_time.replace('\\', '')}</pre>
    <hr>
    <b>Přehled metrik:</b>
    <ul>
        <li>Celkový počet uživatelů: <b>{total_users}</b></li>
        <li>Nových záznamů za den: <b>{new_records}</b></li>
        <li>Důležité info: {status_message}</li>
    </ul>
    <a href="https://tvojeaplikace.streamlit.app/">Odkaz na aplikaci</a>
    """
    
    return html_report_text, 'HTML' # Vrátíme text a mód formátování

# --- 4. Hlavní spouštěcí blok ---

if __name__ == '__main__':
    print(f"Spouštím Telegram report generator v {datetime.now().strftime('%H:%M:%S')}...")
    
    try:
        # Generování obsahu a výběr módu formátování
        report_content, parse_mode = generate_report_content()
        
        # Odeslání zprávy
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
