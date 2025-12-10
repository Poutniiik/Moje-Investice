# telegram_bot.py
import requests
import time
import os
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# --- NASTAVENÍ PRO TELEGRAM (Změň tyto hodnoty!) ---
BOT_TOKEN: str = "TVUJ_TELEGRAM_BOT_TOKEN" # Sem vlož svůj Bot Token
CHAT_ID: str = "TVUJ_CHAT_ID"             # Sem vlož své Chat ID
# -------------------------------------

# --- NASTAVENÍ PRO GITHUB (Změň tyto hodnoty!) ---
# POZNÁMKA: V produkci je ideální získávat tyto hodnoty z Proměnných Prostředí (os.environ)!
GITHUB_TOKEN: str = "TVUJ_GITHUB_PERSONAL_ACCESS_TOKEN" # Vygenerovaný token s právy 'repo'
REPO_OWNER: str = "TVUJ_GITHUB_UZIVATEL"          # Např. "JanaNovak"
REPO_NAME: str = "TVUJ_STREAMLIT_REPO"             # Např. "streamlit-app-report"
DATA_FILE_PATH: str = "metrics/daily_data.json"   # Cesta k souboru s daty v repozitáři
# -------------------------------------


def get_github_file_content() -> Optional[Dict[str, Any]]:
    """
    Načte obsah konkrétního souboru z GitHub repozitáře pomocí GitHub API.
    Očekává, že soubor je ve formátu JSON.

    Returns:
        Optional[Dict[str, Any]]: Parsovaná data ze souboru jako slovník, nebo None.
    """
    if not all([GITHUB_TOKEN, REPO_OWNER, REPO_NAME, DATA_FILE_PATH]):
        print("CHYBA: GitHub nastavení není kompletní.")
        return None

    # URL adresa pro získání obsahu souboru v GitHub API
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{DATA_FILE_PATH}"

    # Hlavičky pro autentizaci
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw" # Žádáme surový (RAW) obsah souboru
    }

    try:
        print(f"Načítám data z GitHubu: {api_url}...")
        response = requests.get(api_url, headers=headers)
        response.raise_for_status() # Vyvolá výjimku pro chybové stavy

        # Raw obsah je text, který musíme parslovat (předpokládáme JSON)
        file_content = response.text
        
        # Parsujeme JSON data
        data = json.loads(file_content)
        print("Data úspěšně načtena a parslována.")
        return data

    except requests.exceptions.RequestException as e:
        print(f"CHYBA PŘI NAČÍTÁNÍ DAT Z GITHUB: {e}")
        return None
    except json.JSONDecodeError:
        print("CHYBA: Obsah souboru není platný JSON.")
        return None


def send_telegram_message(message: str) -> Optional[dict]:
    """
    Odešle textovou zprávu na definovaný CHAT_ID pomocí Telegram Bot API.
    (Tato funkce zůstala stejná jako v Kroku 1)
    """
    if not all([BOT_TOKEN, CHAT_ID]) or BOT_TOKEN == "TVUJ_TELEGRAM_BOT_TOKEN":
        print("CHYBA: BOT_TOKEN nebo CHAT_ID nejsou správně nastaveny.")
        return None

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        print(f"Odesílám zprávu na chat ID: {CHAT_ID}...")
        response = requests.post(url, data=payload)
        response.raise_for_status()

        print("Zpráva byla úspěšně odeslána!")
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"CHYBA PŘI ODESÍLÁNÍ ZPRÁVY: {e}")
        return None


def generate_report(data: Dict[str, Any]) -> str:
    """
    Sestaví denní report ve formátu Markdown z načtených dat.
    """
    today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Zde vytvoříme formátovaný report na základě obsahu dat
    report_lines = [
        f"**Dení Report Streamlit Aplikace** 📊",
        f"Datum: {today}",
        "---",
    ]

    # Dynamické přidávání obsahu z načtených dat
    if data:
        report_lines.append(f"✅ **Dnes bylo navštíveno:** {data.get('views_today', 'N/A')}x")
        report_lines.append(f"⭐ **Nové komentáře:** {data.get('new_comments', 0)}")
        report_lines.append(f"🔥 **Nejlepší metrika (Ukázka):** {data.get('top_metric_name', 'N/A')}: {data.get('top_metric_value', 'N/A')}")
    else:
        report_lines.append("⚠️ Data pro report nebyla nalezena nebo byla neplatná.")
        report_lines.append("Zkontrolujte soubor metrics/daily_data.json.")

    report_lines.append("---")
    report_lines.append("*Automaticky generováno tvým botem.*")

    return "\n".join(report_lines)


if __name__ == "__main__":
    # 1. Získání dat z GitHubu
    report_data = get_github_file_content()

    # 2. Generování zprávy
    final_report = generate_report(report_data)

    # 3. Odeslání zprávy do Telegramu
    send_telegram_message(final_report)
