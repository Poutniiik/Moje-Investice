import os
import requests
import json

# --- 1. Nastavení konstant a tajných klíčů ---
# Bezpečně načítáme klíče z prostředí. TOTO JE KLÍČOVÉ pro GitHub Actions!
# Na GitHubu je uložíme jako "Secrets" (Tajemství), aby nebyly viditelné v kódu.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") # TVOJE osobní ID chatu/skupiny

GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def get_portfolio_data():
    """
    Simuluje získání aktuálních dat portfolia.
    Tuto funkci budeš muset PŘEPSAT podle toho, odkud data získáváš (např. z burzy, z databáze).
    """
    print("Načítám aktuální data portfolia...")
    
    # Nyní jen vracíme fiktivní, ale realistická data
    portfolio_status = {
        "celková_hodnota": 125000.50,
        "dnešní_změna_procenta": 1.75,
        "dnešní_změna_hodnota": 2150.00,
        "hlavní_držby": [
            {"název": "Akcie Google", "procento": "40%"},
            {"název": "Bitcoin", "procento": "30%"},
            {"název": "Státní dluhopisy", "procento": "20%"}
        ],
        "sentiment": "optimistický"
    }
    
    # Převedeme data na čitelný řetězec, který pošleme Gemini
    data_string = json.dumps(portfolio_status, ensure_ascii=False, indent=2)
    return f"Zde jsou data mého aktuálního portfolia:\n{data_string}"

def generate_report(portfolio_prompt: str) -> str:
    """
    Volá Gemini API a generuje profesionální finanční report.
    """
    if not GEMINI_API_KEY:
        return "CHYBA: GEMINI_API_KEY není nastaven."

    print("Generuji report pomocí modelu Gemini...")

    # Zde definujeme instrukce pro model (System Instruction)
    system_prompt = (
        "Jsi Senior Finanční Analytik. Tvým úkolem je na základě dodaných dat "
        "o portfoliu vytvořit stručný, profesionální a povzbudivý denní report. "
        "Zvýrazni klíčové denní změny a shrň alokaci. Použij formátování Markdown."
    )
    
    user_query = f"Vytvoř denní finanční report pro následující data portfolia:\n\n{portfolio_prompt}"

    # Nastavení API Payload
    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        # Zde nepoužíváme Google Search Grounding, protože data jsou z TVÉHO portfolia, ne z webu.
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }

    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=30)
        response.raise_for_status() # Vyhodí chybu pro špatné status kódy (4xx nebo 5xx)
        
        result = response.json()
        
        report_text = result['candidates'][0]['content']['parts'][0]['text']
        return report_text

    except requests.exceptions.RequestException as e:
        print(f"Chyba při volání Gemini API: {e}")
        return "CHYBA: Nepodařilo se kontaktovat Gemini API."
    except Exception as e:
        print(f"Neočekávaná chyba při zpracování odpovědi Gemini: {e}")
        return "CHYBA: Chyba při zpracování odpovědi Gemini."


def send_telegram_message(text: str):
    """
    Odesílá textovou zprávu na Telegram.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: TELEGRAM_BOT_TOKEN nebo TELEGRAM_CHAT_ID nejsou nastaveny. Zprávu nelze odeslat.")
        return

    print("Odesílám report na Telegram...")

    # Nastavení Payload pro Telegram
    # parse_mode='Markdown' zajistí, že formátování z Gemini bude viditelné i na Telegramu.
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown' 
    }

    try:
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("Report úspěšně odeslán na Telegram!")

    except requests.exceptions.RequestException as e:
        print(f"Chyba při odesílání na Telegram: {e}")
    except Exception as e:
        print(f"Neočekávaná chyba: {e}")


def main():
    """
    Hlavní logika skriptu.
    """
    # 1. Získej surová data
    portfolio_data_string = get_portfolio_data()
    
    # 2. Vygeneruj report
    final_report = generate_report(portfolio_data_string)
    
    # 3. Odešli report na Telegram
    send_telegram_message(final_report)

if __name__ == "__main__":
    main()
    # 3. Odešli report na Telegram
    send_telegram_message(final_report)

if __name__ == "__main__":
    main()
