import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import hashlib
import time
from datetime import datetime

# --- KONSTANTY (Databáze) ---
REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv"
SOUBOR_WATCHLIST = "watchlist.csv"
SOUBOR_DIVIDENDY = "dividends.csv"
SOUBOR_STATS = "user_stats.csv"
SOUBOR_STRATEGIE = "strategy_history.csv"
RISK_FREE_RATE = 0.04 

# --- PŘIPOJENÍ (GitHub) ---
try: 
    if "github" in st.secrets:
        GITHUB_TOKEN = st.secrets["github"]["token"]
    else:
        GITHUB_TOKEN = ""
except Exception: 
    GITHUB_TOKEN = ""

def get_repo(): 
    if not GITHUB_TOKEN: 
        st.error("⚠️ GitHub Token nenalezen v Secrets. Ukládání nebude fungovat.")
        return None
    try:
        return Github(GITHUB_TOKEN).get_repo(REPO_NAZEV)
    except Exception as e:
        st.error(f"Chyba při připojení k repozitáři: {e}")
        return None

def zasifruj(text): 
    return hashlib.sha256(str(text).encode()).hexdigest()

# --- DATABÁZOVÉ FUNKCE (CRUD) ---

def uloz_csv_bezpecne(df, nazev_souboru, zprava):
    """
    Vylepšená verze ukládání s ochranou proti výpadkům sítě.
    Returns: True při úspěchu, False při selhání.
    """
    repo = get_repo()
    if not repo:
        st.error("❌ CRITICAL: Nelze se připojit ke GitHubu. Data NEULOŽENA!")
        return False

    csv_content = df.to_csv(index=False)
    
    pokusy = 3
    for i in range(pokusy):
        try:
            contents = repo.get_contents(nazev_souboru)
            repo.update_file(contents.path, zprava, csv_content, contents.sha)
            return True 
            
        except Exception as e:
            if "404" in str(e):
                try:
                    repo.create_file(nazev_souboru, zprava, csv_content)
                    return True 
                except Exception as create_err:
                    st.warning(f"⚠️ Pokus {i+1}/{pokusy}: Chyba vytvoření souboru: {create_err}")
            else:
                st.warning(f"⚠️ Pokus {i+1}/{pokusy}: GitHub neodpovídá, zkouším znovu... ({e})")
                time.sleep(1) 
    
    st.error(f"❌ CHYBA UKLÁDÁNÍ: Soubor {nazev_souboru} se nepodařilo uložit.")
    return False

def uloz_csv(df, nazev_souboru, zprava):
    """WRAPPER: Pro zpětnou kompatibilitu."""
    return uloz_csv_bezpecne(df, nazev_souboru, zprava)

def nacti_csv(nazev_souboru):
    """Načte data z GitHubu a převede typy na správné formáty."""
    try:
        repo = get_repo()
        if not repo: raise Exception("No repo")
        file = repo.get_contents(nazev_souboru)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        
        for col in ['Datum', 'Date']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        
        numeric_cols = ['Pocet', 'Cena', 'Castka', 'Kusu', 'Prodejka', 'Zisk', 'TotalUSD', 'Investice', 'Target', 'TargetBuy', 'TargetSell']
        for col in numeric_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        if nazev_souboru == SOUBOR_WATCHLIST:
             if 'Target' in df.columns and 'TargetBuy' not in df.columns:
                 df['TargetBuy'] = df['Target']
             
             if 'TargetBuy' not in df.columns: df['TargetBuy'] = 0.0
             if 'TargetSell' not in df.columns: df['TargetSell'] = 0.0
             
             if 'Target' in df.columns: df = df.drop(columns=['Target'])
        
        if nazev_souboru == SOUBOR_DATA:
            if 'Sektor' not in df.columns: df['Sektor'] = "Doplnit"
            if 'Poznamka' not in df.columns: df['Poznamka'] = ""
        
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        
        df['Owner'] = df['Owner'].astype(str)
        return df
    except Exception:
        cols = ["Ticker", "Pocet", "Cena", "Datum", "Owner", "Sektor", "Poznamka"]
        if nazev_souboru == SOUBOR_HISTORIE: cols = ["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_CASH: cols = ["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_VYVOJ: cols = ["Date", "TotalUSD", "Owner"]
        if nazev_souboru == SOUBOR_WATCHLIST: cols = ["Ticker", "TargetBuy", "TargetSell", "Owner"]
        if nazev_souboru == SOUBOR_DIVIDENDY: cols = ["Ticker", "Castka", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_UZIVATELE: cols = ["username", "password", "recovery_key"]
        if nazev_souboru == SOUBOR_STATS: cols = ["Owner", "XP", "LastLogin", "Level", "CompletedQuests"]
        if nazev_souboru == SOUBOR_STRATEGIE: cols = ["Timestamp", "Owner", "Sentiment", "Advice"]
        return pd.DataFrame(columns=cols)

def uloz_data_uzivatele(user_df, username, nazev_souboru):
    """Uloží data pouze pro konkrétního uživatele, aniž by smazala ostatní."""
    full_df = nacti_csv(nazev_souboru)
    full_df = full_df[full_df['Owner'] != str(username)]
    if not user_df.empty:
        user_df['Owner'] = str(username)
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    
    # 👇 KLÍČOVÁ OPRAVA: Musíme zachytit výsledek uložení a vrátit ho!
    success = uloz_csv(full_df, nazev_souboru, f"Update {username}")
    
    # Vyčištění cache pro všechny funkce v aplikaci
    st.cache_data.clear()
    
    return success

def nacti_uzivatele(): 
    return nacti_csv(SOUBOR_UZIVATELE)

# --- ALIASY PRO MODULY ---
save_df_to_github = uloz_data_uzivatele
nacti_data_z_github = nacti_csv

def ziskej_info(ticker):
    """Pomocná funkce pro získání ceny přes yfinance pro moduly."""
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.last_price if hasattr(t, 'fast_info') else 0
        return price, "USD", ticker
    except:
        return 0, "USD", ticker
