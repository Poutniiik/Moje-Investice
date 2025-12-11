# =========================================================================
# SOUBOR: report_generator.py
# Cíl: Nezávislý skript pro GitHub Actions
# Autor: Beith (Tvůj Senior Lead Developer)
# ZMĚNA: Odstranění FutureWarnings pro vyšší stabilitu
# =========================================================================

import os
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
import yfinance as yf
import numpy as np
from github import Github # Potřebujeme pro přístup k repositáři

# === 1. KONSTANTY & NASTAVENÍ ===
# POUŽÍVÁME POUZE ENVIRONMENT PROSTŘEDÍ Z GITHUB ACTIONS
GITHUB_TOKEN_REPORT = os.environ.get("GITHUB_TOKEN_REPORT", os.environ.get("GITHUB_TOKEN"))
REPO_NAZEV_REPORT = "Poutniiik/Moje-Investice" # Tvé repo
USER = "Filip" # Uživatel, pro kterého report generujeme

# Konstanty pro soubory
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_WATCHLIST = "watchlist.csv"

# === 2. ADAPTOVANÉ FUNKCE PRO GITHUB ACTIONS (GHA) ===

def get_repo_gha():
    """Získá objekt repozitáře pomocí tokenu z ENV."""
    if not GITHUB_TOKEN_REPORT:
        print("Chyba: GITHUB_TOKEN_REPORT nenalezen.")
        return None
    try:
        # Použijeme PyGithub
        return Github(GITHUB_TOKEN_REPORT).get_repo(REPO_NAZEV_REPORT)
    except Exception as e:
        print(f"Chyba při připojení k repozitáři: {e}")
        return None

def nacti_csv_gha(nazev_souboru):
    """Načte CSV soubor přímo z GitHubu bez Streamlitu."""
    try:
        # Používáme přímý přístup na raw.githubusercontent.com
        # To je nejrychlejší a nejspolehlivější pro GHA
        headers = {"Authorization": f"token {GITHUB_TOKEN_REPORT}"}
        url = f"https://raw.githubusercontent.com/{REPO_NAZEV_REPORT}/main/{nazev_souboru}"
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Vyhodí chybu, pokud je status > 400
        
        df = pd.read_csv(StringIO(response.text))
        
        # Převedení sloupců na správné typy (jako v data_manager.py)
        for col in ['Datum', 'Date']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        for col in ['Pocet', 'Cena', 'Castka']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        return df
    except Exception as e:
        print(f"Chyba nacteni {nazev_souboru}: {e}")
        return pd.DataFrame()

def get_kurzy_gha(): 
    """Získá live kurzy (CZK a EUR vs USD)."""
    try:
        ts = ["CZK=X", "EURUSD=X"]
        # ZMĚNA 1 (ŘÁDEK 68): Přidání auto_adjust=True pro potlačení FutureWarning
        df_y = yf.download(ts, period="1d", group_by='ticker', progress=False, auto_adjust=True)
        czk_price = df_y["CZK=X"]['Close'].iloc[-1] if not df_y["CZK=X"].empty else 20.85
        eur_usd = df_y["EURUSD=X"]['Close'].iloc[-1] if not df_y["EURUSD=X"].empty else 1.16
        return {"USD": 1.0, "CZK": czk_price, "EUR": eur_usd}
    except Exception:
         return {"USD": 1.0, "CZK": 20.85, "EUR": 1.16}

def get_live_data_gha(tickers):
    """Stáhne aktuální ceny (bez Streamlit cache)."""
    data = {}
    if not tickers: return data
    try:
        # ZMĚNA 2 (ŘÁDEK 80): Přidání auto_adjust=True pro potlačení FutureWarning
        df_y = yf.download(tickers, period="1d", group_by='ticker', progress=False, auto_adjust=True)
        for t in tickers:
            try:
                if isinstance(df_y.columns, pd.MultiIndex): price = df_y[t]['Close'].iloc[-1]
                else: price = df_y['Close'].iloc[-1]
                if pd.isna(price): continue
                curr = "USD"
                if ".PR" in t.upper(): curr = "CZK"
                elif ".DE" in t.upper(): curr = "EUR"
                data[t] = {"price": float(price), "curr": curr}
            except Exception: pass
    except Exception: pass
    return data

# === 3. TELEGRAM MOTOR (Upraveno pro ENV) ===

def init_telegram_gha():
    """Načte tokeny z ENV."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    return token, chat_id

def poslat_zpravu_gha(text):
    """Odešle zprávu na Telegram."""
    token, chat_id = init_telegram_gha()
    if not token or not chat_id:
        print("Chyba: Chybí konfigurace Telegramu v ENV.")
        return False, "❌ Chybí konfigurace Telegramu v ENV"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return True, "✅ Zpráva odeslána na Telegram!"
        else:
            return False, f"❌ Chyba Telegramu: {response.text}"
    except Exception as e:
        return False, f"❌ Chyba spojení: {str(e)}"

# === 4. JÁDRO VÝPOČTU A GENERÁTOR REPORTU ===

def calculate_gha(df_p, df_c, kurzy):
    """Vypočte základní metriky portfolia (Hodnota, Hotovost)."""
    
    all_tickers = df_p['Ticker'].unique().tolist()
    LIVE_DATA = get_live_data_gha(all_tickers)
    
    viz_data = []
    celk_hod_usd = 0
    celk_inv_usd = 0
    
    if not df_p.empty:
        df_g = df_p.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        # ZMĚNA 3 (ŘÁDEK 133): Přidání include_groups=False pro potlačení FutureWarning
        df_g['Investice'] = df_p.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum(), include_groups=False).values
        
        for _, row in df_g.iterrows():
            tkr = row['Ticker']
            kusy = row['Pocet']
            prumerna_cena = row['Cena']
            
            live_info = LIVE_DATA.get(tkr, {})
            live_price = live_info.get('price', prumerna_cena)
            live_mena = live_info.get('curr', "USD")
            
            hodnota = kusy * live_price
            investice = row['Investice']
            
            # Konverze do USD
            if live_mena == "CZK": k = 1.0 / kurzy.get("CZK", 20.85)
            elif live_mena == "EUR": k = kurzy.get("EUR", 1.16)
            else: k = 1.0
            
            hodnota_usd = hodnota * k
            investice_usd = investice * k

            celk_hod_usd += hodnota_usd
            celk_inv_usd += investice_usd
            
            # Přidání do viz_data pro report
            viz_data.append({"Ticker": tkr, "HodnotaUSD": hodnota_usd, "Investice": investice_usd, "Měna": live_mena})
    
    # Výpočet hotovosti (USD ekvivalent)
    zustatky = df_c.groupby('Mena')['Castka'].sum().to_dict() if not df_c.empty else {}
    cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))
    
    return celk_hod_usd, celk_inv_usd, cash_usd, viz_data

def send_daily_telegram_report_gha(USER, data_core, kurzy):
    """Generuje a odesílá denní report."""
    
    celk_hod_usd = data_core['celk_hod_usd']
    celk_inv_usd = data_core['celk_inv_usd']
    cash_usd = data_core['cash_usd']
    vdf = data_core['vdf']
    
    kurz_czk = kurzy.get("CZK", 20.85)
    celk_hod_czk = celk_hod_usd * kurz_czk
    celk_zisk_czk = (celk_hod_usd - celk_inv_usd) * kurz_czk
    
    # --- 1. HLAVIČKA A SHRNUTÍ ---
    summary_text = f"<b>💸 DENNÍ REPORT: {USER.upper()}</b>\n"
    summary_text += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    summary_text += "--------------------------------------\n"
    summary_text += f"Celkové jmění: <b>{celk_hod_czk:,.0f} CZK</b>\n"
    
    # Celkový zisk/ztráta
    zisk_emoji = '🟢' if celk_zisk_czk >= 0 else '🔴'
    summary_text += f"Celkový zisk: {zisk_emoji} <b>{celk_zisk_czk:+.0f} CZK</b> (od počátku)\n"
    
    # Hotovost
    summary_text += f"Volná hotovost: ${cash_usd:,.0f} USD\n"
    summary_text += "--------------------------------------\n"
    
    # --- 2. POZICE ---
    summary_text += "<b>📋 Největší pozice:</b>\n"
    
    if vdf and len(vdf) > 0:
        # Třídění podle hodnoty USD
        vdf_sorted = sorted(vdf, key=lambda x: x.get('HodnotaUSD', 0), reverse=True) 
        
        # Top 3 pozice
        for row in vdf_sorted[:3]:
            # Výpočet zisku v %
            zisk_pct = (row.get('HodnotaUSD', 0) / row.get('Investice', 1.0)) - 1.0
            
            summary_text += f"  - {row['Ticker']}: ${row['HodnotaUSD']:,.0f} ({zisk_pct*100:+.1f}%)\n"
    else:
         summary_text += "  - Portfolio je prázdné.\n"

    summary_text += "--------------------------------------\n"
    summary_text += "<i>Mějte úspěšný investiční den!</i>"
    
    return poslat_zpravu_gha(summary_text)

# === 5. HLAVNÍ SPOUŠTĚČ ===

def run_report():
    print(f"Spouštím report pro uživatele: {USER}")
    
    # 1. Stáhneme aktuální kurzy
    kurzy = get_kurzy_gha()
    
    # 2. Stáhneme data z GitHubu
    df_p = nacti_csv_gha(SOUBOR_DATA)
    df_c = nacti_csv_gha(SOUBOR_CASH)
    
    # Filtrujeme data pro daného uživatele
    df_p_user = df_p[df_p['Owner'] == USER]
    df_c_user = df_c[df_c['Owner'] == USER]
    
    if df_p_user.empty and df_c_user.empty:
        print(f"Uživatel {USER} nemá žádná data. Report vynechán.")
        return

    # 3. Spustíme kalkulace
    celk_hod_usd, celk_inv_usd, cash_usd, viz_data = calculate_gha(df_p_user, df_c_user, kurzy)
    
    # 4. Sestavíme Data Core
    data_core = {
        'celk_hod_usd': celk_hod_usd,
        'celk_inv_usd': celk_inv_usd,
        'cash_usd': cash_usd,
        'vdf': viz_data,
    }
    
    # 5. Odešleme report
    ok, msg = send_daily_telegram_report_gha(USER, data_core, kurzy)
    
    if ok:
        print("Automatický report úspěšně odeslán.")
    else:
        print(f"CHYBA: Automatický report selhal. {msg}")

if __name__ == "__main__":
    run_report()

if __name__ == "__main__":
    run_report()
