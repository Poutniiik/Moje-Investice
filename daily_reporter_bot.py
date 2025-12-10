# daily_reporter_bot.py - Samostatný skript pro GitHub Actions
#
# ZÁKLADNÍ ÚČEL: Načíst data portfolia z GitHubu, získat živé ceny/kurzy,
#                vypočítat denní metriky a odeslat shrnutí na Telegram.

import requests
import pandas as pd
import numpy as np
import yfinance as yf
import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from github import Github
from io import StringIO
import sys
import feedparser

# --- 1. KONSTANTY A FUNKCE Z data_manager.py (KRITICKÉ PRO PŘÍSTUP K GITHUB) ---
# Použijeme tvé konstanty a logiku pro načítání z GitHubu.

# Tvé konstanty
REPO_NAZEV: str = "Poutniiik/Moje-Investice" 
SOUBOR_DATA: str = "portfolio_data.csv"
SOUBOR_VYVOJ: str = "value_history.csv"
SOUBOR_WATCHLIST: str = "watchlist.csv"
SOUBOR_CASH: str = "cash_data.csv"
SOUBOR_DIVIDENDY: str = "dividends.csv"
RISK_FREE_RATE: float = 0.04 

# Získání tokenu pro GHA (Vždy se spoléháme na proměnnou prostředí GHA)
GITHUB_TOKEN: Optional[str] = os.environ.get("GH_TOKEN")

def get_repo() -> Optional[Github.Repository]: 
    """Vrací instanci GitHub repozitáře nebo None s chybou."""
    if not GITHUB_TOKEN: 
        print("❌ CHYBA: GITHUB_TOKEN (GH_TOKEN) není nastaven v proměnných prostředí.")
        return None
    try:
        # Používáme tvůj token a tvůj název repozitáře
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(REPO_NAZEV.split('/')[1])
        return repo
    except Exception as e:
        print(f"❌ CHYBA PŘIPOJENÍ GITHUB: {e}")
        return None

def nacti_csv(nazev_souboru: str) -> pd.DataFrame:
    """Načte CSV soubor z GitHub repozitáře a vrátí DataFrame."""
    repo = get_repo()
    if not repo:
        # Zajištění bezpečného prázdného DataFrame s očekávanými sloupci
        if nazev_souboru == SOUBOR_DATA: return pd.DataFrame(columns=["Ticker", "Pocet", "Cena", "Datum", "Owner", "Sektor", "Poznamka"])
        if nazev_souboru == SOUBOR_VYVOJ: return pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
        if nazev_souboru == SOUBOR_WATCHLIST: return pd.DataFrame(columns=["Ticker", "Owner", "TargetBuy", "TargetSell"])
        return pd.DataFrame(columns=[])

    try:
        # Získání obsahu souboru z GitHubu
        contents = repo.get_contents(nazev_souboru)
        decoded = contents.content # Obsah je base64, .content už vrací dekódovaný string v Python 3
        df = pd.read_csv(StringIO(decoded))
        
        # POZNÁMKA: V tvém Streamlit kódu filtruješ za konkrétního uživatele ('Filip')
        # Pro bota budeme filtrovat pouze na jednoho uživatele 'Filip', jak to naznačuje tvůj kód
        # Můžeš to změnit, pokud potřebuješ dynamického uživatele, ale pro Cron je 'Filip' bezpečný start.
        if 'Owner' in df.columns:
            df = df[df['Owner'] == 'Filip'].copy()
            
        return df
    except Exception as e:
        print(f"❌ CHYBA NAČÍTÁNÍ SOUBORU '{nazev_souboru}': {e}")
        # Vracíme prázdný DF, aby kód nepadl
        return pd.DataFrame(columns=[])

# --- 2. FUNKCE Z notification_engine.py (TELEGRAM API) ---
def init_telegram() -> Tuple[Optional[str], Optional[str]]:
    """Načte klíče pro Telegram ze systémových proměnných."""
    # Priorita: 1. Systémové proměnné (pro GHA bota)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") 
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    return token, chat_id

def poslat_zpravu(text: str) -> Tuple[bool, str]:
    """Odešle zprávu přes Telegram Bota (Používá HTML formátování)."""
    token, chat_id = init_telegram()
    
    if not token or not chat_id:
        return False, "❌ Chybí konfigurace Telegramu v proměnných prostředí."
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML" # Používáme HTML, stejně jako tvůj původní kód
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, "✅ Zpráva odeslána na Telegram!"
        else:
            error_detail = response.json().get("description", response.text[:100])
            return False, f"❌ Chyba Telegram API: {error_detail}"
            
    except Exception as e:
        return False, f"❌ Chyba spojení: {str(e)}"

# --- 3. FUNKCE Z utils.py (ŽIVÁ DATA) ---

# Nahradíme @st.cache_data za jednoduchý Python cache mechanismus v rámci GHA.
_YFINANCE_CACHE: Dict[str, Tuple[float, Optional[str], float]] = {}

def ziskej_info(ticker: str) -> Tuple[Optional[float], Optional[str], float]:
    """
    Získá aktuální cenu, měnu a denní změnu (v %) pro jeden ticker pomocí YFinance.
    Tato funkce je závislá na YFinance a ne na cache (Cache je v rámci get_ceny_hromadne)
    """
    if ticker in _YFINANCE_CACHE:
        return _YFINANCE_CACHE[ticker]

    # Použijeme zjednodušené volání, protože to je fallback
    try:
        data = yf.download(ticker, period="1d", progress=False)
        if data.empty:
            return None, None, 0.0

        if 'Close' in data.columns:
            cena = data['Close'].iloc[-1]
            try:
                # Denní změna (Close / Open - 1)
                zmena_pct = (data['Close'].iloc[-1] / data['Open'].iloc[-1]) - 1
            except Exception:
                zmena_pct = 0.0
            
            # Získání měny je složitější, ale můžeme se spolehnout na info objekt
            info = yf.Ticker(ticker).info
            mena = info.get('currency', 'USD')
            
            # Uložíme do lokální cache pro rychlé opakované volání
            _YFINANCE_CACHE[ticker] = (cena, mena, zmena_pct)
            return cena, mena, zmena_pct
        
    except Exception as e:
        print(f"Chyba při ziskávání info pro {ticker}: {e}")
        return None, None, 0.0
        
def ziskej_fear_greed() -> Tuple[Optional[int], str]:
    """Získá Fear & Greed Index z CNN (tvůj původní kód)."""
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        score = int(data['fear_greed']['score'])
        rating = data['fear_greed']['rating'].upper()
        return score, rating
    except Exception as e:
        print(f"Chyba F&G: {e}")
        return None, "NEDOSTUPNÉ"

def ziskej_kurzy() -> Dict[str, float]:
    """Získá aktuální směnné kurzy (EURUSD, CZKUSD) pro přepočet."""
    # Používáme tvůj přístup s yfinance pro kurzy
    tickers = ["EURUSD=X", "CZK=X"]
    kurzy = {"CZK": 20.85, "EUR": 1.16} # Fallback hodnoty (CZK/USD, EUR/USD)
    
    try:
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        # CZK=X (Kurz USD/CZK, např. 22.0)
        if "CZK=X" in data.columns:
            kurzy["CZK"] = data["CZK=X"].iloc[-1]
            
        # EURUSD=X (Kurz EUR/USD, např. 1.08)
        if "EURUSD=X" in data.columns:
            kurzy["EUR"] = data["EURUSD=X"].iloc[-1]
            
    except Exception as e:
        print(f"Chyba kurzů: {e}")
        
    return kurzy

def ziskej_ceny_hromadne(tickers_list: list) -> Dict[str, Dict[str, Any]]:
    """
    Získá hromadně cenu, denní změnu a měnu pro seznam tickerů.
    Vrací slovník pro snadný přístup (LIVE_DATA).
    """
    if not tickers_list:
        return {}
        
    LIVE_DATA = {}
    try:
        # Přidáme kurzové tickery, které potřebujeme pro přepočty
        full_list = list(set(tickers_list + ["EURUSD=X", "CZK=X"]))
        
        # Stáhneme data za 2 dny, abychom měli Open Price pro výpočet denní změny
        batch = yf.download(full_list, period="2d", interval="1d", progress=False)
        
        for tkr in full_list:
            if tkr in batch.columns.levels[0]:
                data = batch[tkr]
            elif 'Close' in batch.columns and len(full_list) == 1:
                 # Single ticker download returns flat columns
                data = batch
            else:
                continue

            if not data.empty and len(data) >= 1:
                price = data['Close'].iloc[-1]
                
                # Výpočet denní změny (porovnáme Close vs. Open nebo Close vs. Předchozí Close)
                try:
                    open_price = data['Open'].iloc[-1]
                    zmena_pct = (price / open_price - 1) if open_price > 0 else 0.0
                except Exception:
                    # Fallback na předchozí close
                    if len(data) > 1 and data['Close'].iloc[-2] > 0:
                         zmena_pct = (price / data['Close'].iloc[-2]) - 1
                    else:
                        zmena_pct = 0.0

                # Měnu získáme přes ziskej_info nebo metadata (kvůli rychlosti použijeme ziskej_info)
                _, currency, _ = ziskej_info(tkr)
                
                LIVE_DATA[tkr] = {
                    "price": float(price),
                    "curr": currency or "USD",
                    "daily_change_pct": zmena_pct
                }
                
    except Exception as e:
        print(f"Chyba hromadného stahování: {e}")
        
    return LIVE_DATA


# --- 4. FUNKCE Z web_investice.py (JÁDRO VÝPOČTŮ) ---

def aktualizuj_graf_vyvoje(USER: str, aktualni_hodnota_usd: float) -> pd.DataFrame:
    """
    Simuluje aktualizaci historie vývoje (ale jen ji načte, neuloží zpět do GitHubu,
    protože to je nebezpečné bez transakční kontroly. Uloží se až v main bloku).
    Pro report bota jen načteme poslední 2 dny.
    """
    if pd.isna(aktualni_hodnota_usd): return pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    
    # Načteme celou historii (nacti_csv filtruje za 'Filip')
    full_hist = nacti_csv(SOUBOR_VYVOJ)
    
    # Zkontrolujeme a vrátíme jen to co potřebujeme pro výpočet 24h změny
    if full_hist.empty:
        # Vytvoříme falešnou včerejší hodnotu, aby kód nepadl
        return pd.DataFrame([
            {"Date": datetime.now() - timedelta(days=1), "TotalUSD": aktualni_hodnota_usd, "Owner": USER},
            {"Date": datetime.now(), "TotalUSD": aktualni_hodnota_usd, "Owner": USER}
        ])

    full_hist['Date'] = pd.to_datetime(full_hist['Date'])
    full_hist = full_hist.sort_values('Date', ascending=False).head(2)

    return full_hist

def calculate_all_data(USER: str) -> Dict[str, Any]:
    """
    Spouští všechny složité výpočty portfolia.
    """
    
    # 1. NAČTENÍ ZÁKLADNÍCH DAT
    df = nacti_csv(SOUBOR_DATA) # Portfolio
    df_watch = nacti_csv(SOUBOR_WATCHLIST) # Watchlist
    df_cash = nacti_csv(SOUBOR_CASH) # Hotovost
    kurzy = ziskej_kurzy() # Kurzy
    
    # Helper: Získání zůstatků hotovosti
    zustatky = df_cash.groupby('Mena')['Castka'].sum().to_dict() if not df_cash.empty else {}
    
    # 2. SESTAVENÍ LISTU TICKERŮ PRO LIVE DATA
    all_tickers = []
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    
    # 3. ZÍSKÁNÍ ŽIVÝCH DAT A FUNDAMENTŮ
    LIVE_DATA = ziskej_ceny_hromadne(list(set(all_tickers)))
    
    # Aktualizace kurzů, pokud je LIVE_DATA obsahuje
    if LIVE_DATA.get("CZK=X"): kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
    if LIVE_DATA.get("EURUSD=X"): kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]
    
    # 4. VÝPOČET PORTFOLIA HODNOT
    viz_data = []
    celk_hod_usd: float = 0.0
    celk_inv_usd: float = 0.0

    if not df.empty:
        # Seskupení pro výpočet průměrné ceny
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum'}).reset_index()
        # Přidání sloupce Investice (celková vložená částka pro každý ticker)
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        df_g['Průměr'] = df_g['Investice'] / df_g['Pocet']

        for _, row in df_g.iterrows():
            tkr = row['Ticker']
            # Získání živé ceny z hromadného stahování
            live_info = LIVE_DATA.get(tkr, {})
            p: Optional[float] = live_info.get('price')
            m: Optional[str] = live_info.get('curr', 'USD')
            d_zmena: float = live_info.get('daily_change_pct', 0.0)

            # Fallback na průměrnou cenu, pokud není live data (pád API)
            if p is None: p = row['Průměr']

            # Zjištění sektoru (bereme první nalezený sektor z transakcí)
            try:
                raw_sektor = df[df['Ticker'] == tkr]['Sektor'].iloc[0]
                sektor = str(raw_sektor) if pd.notna(raw_sektor) and str(raw_sektor).strip() != "" else "Doplnit"
            except Exception: sektor = "Doplnit"

            # --- Přepočet na USD (Tvá původní logika) ---
            hod = row['Pocet'] * p
            inv = row['Investice']
            z = hod - inv

            k = 1.0 # default pro USD
            if m == "CZK": k = 1.0 / kurzy.get("CZK", 20.85)
            elif m == "EUR": k = kurzy.get("EUR", 1.16)

            celk_hod_usd += hod * k
            celk_inv_usd += inv * k

            viz_data.append({
                "Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m,
                "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Průměr'], "Investice": inv, 
                "Dnes": d_zmena, # Denní změna (v des. čísle, např. 0.01 = 1%)
            })

    vdf = pd.DataFrame(viz_data) if viz_data else pd.DataFrame()

    # 5. VÝPOČET DENNÍ ZMĚNY
    hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    zmena_24h: float = 0.0
    pct_24h: float = 0.0
    
    if len(hist_vyvoje) >= 2:
        # Příklad: Dnes (index 0) vs Včera (index 1)
        dnesni_hodnota = hist_vyvoje.iloc[0]['TotalUSD']
        vcerejsi_hodnota = hist_vyvoje.iloc[1]['TotalUSD']
        
        if pd.notnull(vcerejsi_hodnota) and vcerejsi_hodnota > 0:
            zmena_24h = dnesni_hodnota - vcerejsi_hodnota
            pct_24h = (zmena_24h / vcerejsi_hodnota * 100)
        else:
            # Pokud je včerejší hodnota 0 (např. první den záznamu), zkusíme investice
            pct_24h = (dnesni_hodnota / celk_inv_usd * 100) if celk_inv_usd > 0 else 0.0


    # 6. VÝPOČET HOTOVOSTI (USD ekvivalent)
    cash_usd = (zustatky.get('USD', 0)) + \
               (zustatky.get('CZK', 0) / kurzy.get("CZK", 20.85)) + \
               (zustatky.get('EUR', 0) * kurzy.get("EUR", 1.16))

    # 7. SESTAVENÍ A ULOŽENÍ Data Core
    data_core = {
        'vdf': vdf,
        'celk_hod_usd': celk_hod_usd,
        'celk_inv_usd': celk_inv_usd,
        'hist_vyvoje': hist_vyvoje,
        'zmena_24h': zmena_24h,
        'pct_24h': pct_24h,
        'cash_usd': cash_usd,
        'kurzy': kurzy,
        'LIVE_DATA': LIVE_DATA,
        'df_watch': df_watch,
    }
    return data_core

def send_daily_telegram_report(USER: str, data_core: Dict[str, Any], kurzy: Dict[str, float]) -> Tuple[bool, str]:
    """
    Sestaví ucelený denní report a odešle jej na Telegram. (Upraveno pro HTML)
    """
    try:
        # Extrakce dat z data_core
        celk_hod_usd: float = data_core['celk_hod_usd']
        pct_24h: float = data_core['pct_24h']
        cash_usd: float = data_core['cash_usd']
        vdf: pd.DataFrame = data_core['vdf']
        df_watch: pd.DataFrame = data_core['df_watch']
        LIVE_DATA: Dict[str, Any] = data_core['LIVE_DATA']
        
        # Přepočet na CZK
        kurz_czk = kurzy.get("CZK", 20.85)
        celk_hod_czk = celk_hod_usd * kurz_czk
        
        # Fear & Greed
        score, rating = ziskej_fear_greed()
        
        # --- 1. HLAVIČKA A SHRNUTÍ ---
        # Používáme HTML formátování (značky <b>, <i>, <br>)
        summary_text = f"<b>💸 DENNÍ REPORT: {USER.upper()}</b><br>"
        summary_text += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}<br>"
        summary_text += "--------------------------------------<br>"
        summary_text += f"Celkové jmění: <b>{celk_hod_czk:,.0f} CZK</b><br>"
        
        # Změna 24h
        zmena_emoji = '🟢' if pct_24h >= 0 else '🔴'
        summary_text += f"24h Změna: {zmena_emoji} <b>{pct_24h:+.2f}%</b><br>"
        
        # Hotovost
        summary_text += f"Volná hotovost: ${cash_usd:,.0f}<br>"
        summary_text += f"Nálada trhu: <b>{rating}</b> ({score}/100)<br>"
        summary_text += "--------------------------------------<br>"
        
        # --- 2. CENOVÉ ALERTY (WATCHLIST) ---
        alerts = []
        if not df_watch.empty:
            for _, r in df_watch.iterrows():
                tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']
                
                # Zjištění ceny z LIVE_DATA
                price = LIVE_DATA.get(tk, {}).get('price')
                
                if price:
                    if buy_trg > 0 and price <= buy_trg:
                        alerts.append(f"🔥 {tk}: KUPNÍ ALERT! Cena {price:.2f} &lt;= {buy_trg:.2f}")
                    if sell_trg > 0 and price >= sell_trg:
                        alerts.append(f"💰 {tk}: PRODEJ: {price:.2f} &gt;= {sell_trg:.2f}")

        if alerts:
            summary_text += "<b>🚨 AKTIVNÍ ALERTY:</b><br>"
            summary_text += "<br>".join(alerts) + "<br>"
            summary_text += "--------------------------------------<br>"
            
        # --- 3. TOP/FLOP MOVERS (3 nejlepší/nejhorší) ---
        movers_text = "<b>📈 Největší pohyby (Dnes):</b><br>"
        
        if not vdf.empty and 'Dnes' in vdf.columns:
            # Bereme změnu v % (Dnes je v des. čísle, takže *100)
            vdf_sorted_all = vdf.sort_values('Dnes', ascending=False) 
            
            # Top Movers (kladná změna)
            movers_text += "🔝 Vítězové:<br>"
            has_winners = False
            for _, row in vdf_sorted_all[vdf_sorted_all['Dnes'] > 0.001].head(3).iterrows():
                movers_text += f"  🚀 {row['Ticker']}: <b>{row['Dnes']*100:+.2f}%</b><br>"
                has_winners = True
            if not has_winners: movers_text += "  (Žádný velký vítěz)<br>"
            
            # Flop Movers (záporná změna)
            movers_text += "🔻 Poražení:<br>"
            has_losers = False
            for _, row in vdf_sorted_all[vdf_sorted_all['Dnes'] < -0.001].tail(3).iterrows():
                movers_text += f"  💀 {row['Ticker']}: <b>{row['Dnes']*100:+.2f}%</b><br>"
                has_losers = True
            if not has_losers: movers_text += "  (Žádný velký poražený)<br>"

            summary_text += movers_text
            summary_text += "--------------------------------------<br>"

        # --- 4. ZÁVĚR ---
        summary_text += "<i>Automaticky generováno tvým botem. Mějte úspěšný den!</i>"
        
        # Odeslání zprávy přes Telegram Engine
        return poslat_zpravu(summary_text)

    except Exception as e:
        print(f"Chyba generování reportu: {e}")
        return False, f"❌ Chyba generování reportu: {e}"


# --- HLAVNÍ BLOK PRO SPUŠTĚNÍ ---
if __name__ == "__main__":
    
    # Účel: Zajištění, že GHA má klíče
    if not os.environ.get("GH_TOKEN") or not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_CHAT_ID"):
        print("⚠️ KRITICKÁ CHYBA: Chybí jeden nebo více klíčů (GH_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) v proměnných prostředí.")
        sys.exit(1) # Ukončíme skript s chybou
        
    USER = "Filip" # Tvůj pevný uživatel
    
    # 1. Spuštění výpočtů a získání Data Core
    print("🚀 Spouštím výpočet datového jádra (načítání z GitHubu a živých cen)...")
    try:
        data_core = calculate_all_data(USER)
    except Exception as e:
        print(f"❌ CHYBA: Selhal calculate_all_data: {e}")
        sys.exit(1)

    # 2. Extrakce kurzů (potřebné pro send_daily_telegram_report)
    kurzy = data_core['kurzy']
    
    # 3. Odeslání reportu
    print("📡 Odesílám denní report na Telegram...")
    ok, msg = send_daily_telegram_report(USER, data_core, kurzy)
    
    print(f"--- VÝSLEDEK ODESLÁNÍ ---")
    print(msg)
    
    if not ok:
        # Ukončíme skript s chybou, pokud se zpráva neodešle
        sys.exit(1)
