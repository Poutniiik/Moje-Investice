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

# --- ČTENÍ DAT ---
# Odstranili jsme @st.cache_data, protože cachování řešíme nyní v session_state ve web_investice.py
def nacti_csv(nazev_souboru):
    repo = get_repo()
    if not repo: return pd.DataFrame()
    
    try:
        content = repo.get_contents(nazev_souboru)
        csv_data = content.decoded_content.decode("utf-8")
        df = pd.read_csv(StringIO(csv_data))
        if 'Owner' in df.columns: df['Owner'] = df['Owner'].astype(str)
        return df
    except Exception:
        # Definice sloupců pro prázdné soubory
        cols = ["Ticker", "Pocet", "Cena", "Datum", "Owner", "Sektor", "Poznamka"]
        if nazev_souboru == SOUBOR_HISTORIE: cols = ["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_CASH: cols = ["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_VYVOJ: cols = ["Date", "TotalUSD", "Owner"]
        if nazev_souboru == SOUBOR_WATCHLIST: cols = ["Ticker", "TargetBuy", "TargetSell", "Owner"]
        if nazev_souboru == SOUBOR_DIVIDENDY: cols = ["Ticker", "Castka", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_UZIVATELE: cols = ["username", "password", "recovery_key"]
        return pd.DataFrame(columns=cols)

def uloz_data_uzivatele(user_df, username, nazev_souboru):
    """
    Stáhne aktuální CSV z GitHubu, odstraní stará data uživatele,
    připojí nová data uživatele a nahraje zpět.
    """
    full_df = nacti_csv(nazev_souboru)
    
    # Odstraníme stará data uživatele (aby nedošlo k duplicitám při celkovém přepsání, 
    # NEBO pokud appendujeme jen jeden řádek, musíme to dělat jinak. 
    # V naší logice "df" v appce držíme všechna data uživatele. 
    # Takže bezpečné je: vzít full_df, vymazat usera, a přidat jeho aktuální verzi.)
    
    # POZOR: Pokud user_df obsahuje jen JEDEN NOVÝ řádek (při optimalizaci),
    # tak bychom neměli mazat všechna jeho data.
    # Ale naše "web_investice" callbacky posílají jen ten jeden řádek.
    # Takže musíme APPENDOVAT.
    
    if not user_df.empty:
        user_df['Owner'] = str(username)
        # Zde je změna pro efektivitu - prostě připojíme na konec
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    
    uloz_csv(full_df, nazev_souboru)

def uloz_csv(df, nazev_souboru):
    repo = get_repo()
    if not repo: return
    try:
        content = repo.get_contents(nazev_souboru)
        repo.update_file(content.path, f"Update {nazev_souboru}", df.to_csv(index=False), content.sha)
    except Exception:
        repo.create_file(nazev_souboru, f"Create {nazev_souboru}", df.to_csv(index=False))

def nacti_uzivatele():
    df = nacti_csv(SOUBOR_UZIVATELE)
    if df.empty: return {}
    return df.set_index("username").T.to_dict()
