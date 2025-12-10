import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import hashlib
import time
from datetime import datetime
import os

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
def get_github_token():
    """Získá token ze secrets (různé varianty) nebo ENV."""
    # 1. Nejčastější varianta (GH_TOKEN přímo v rootu) - TOTO TI CHYBĚLO!
    if "GH_TOKEN" in st.secrets:
        return st.secrets["GH_TOKEN"]

    # 2. Varianta v sekci [github]
    if "github" in st.secrets and "token" in st.secrets["github"]:
        return st.secrets["github"]["token"]
    
    # 3. Environment Variables (Fallback)
    return os.environ.get("GH_TOKEN")

def get_repo(): 
    token = get_github_token()
    if not token: 
        # Tichý režim nebo logování chyby
        print("⚠️ GitHub Token nenalezen v Secrets ani ENV.")
        return None
    try:
        return Github(token).get_repo(REPO_NAZEV)
    except Exception as e:
        print(f"Chyba při připojení k repozitáři: {e}")
        return None

def zasifruj(text): 
    return hashlib.sha256(str(text).encode()).hexdigest()

# --- DATABÁZOVÉ FUNKCE (CRUD) ---

def uloz_csv_bezpecne(df, nazev_souboru, zprava):
    repo = get_repo()
    if not repo:
        return False

    csv_content = df.to_csv(index=False)
    pokusy = 3
    for i in range(pokusy):
        try:
            contents = repo.get_contents(nazev_souboru)
            repo.update_file(contents.path, zprava, csv_content, contents.sha)
            return True 
        except Exception as e:
            if "404" in str(e): # Soubor neexistuje, vytvoříme ho
                try:
                    repo.create_file(nazev_souboru, zprava, csv_content)
                    return True 
                except Exception: pass
            time.sleep(1)
            
    print(f"❌ CHYBA UKLÁDÁNÍ: {nazev_souboru}")
    return False

def uloz_csv(df, nazev_souboru, zprava):
    return uloz_csv_bezpecne(df, nazev_souboru, zprava)

def nacti_csv(nazev_souboru):
    try:
        repo = get_repo()
        if not repo: raise Exception("No repo")
        file = repo.get_contents(nazev_souboru)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        
        # Konverze sloupců
        for col in ['Datum', 'Date']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        for col in ['Pocet', 'Cena', 'Castka', 'Kusu', 'Prodejka', 'Zisk', 'TotalUSD', 'Investice', 'Target', 'TargetBuy', 'TargetSell']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        # Migrace sloupců (kompatibilita)
        if nazev_souboru == SOUBOR_WATCHLIST:
             if 'Target' in df.columns and 'TargetBuy' not in df.columns: df['TargetBuy'] = df['Target']
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
        # Vrátí prázdný DF se správnou strukturou
        cols = ["Ticker", "Pocet", "Cena", "Datum", "Owner", "Sektor", "Poznamka"]
        if nazev_souboru == SOUBOR_HISTORIE: cols = ["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_CASH: cols = ["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_VYVOJ: cols = ["Date", "TotalUSD", "Owner"]
        if nazev_souboru == SOUBOR_WATCHLIST: cols = ["Ticker", "TargetBuy", "TargetSell", "Owner"]
        if nazev_souboru == SOUBOR_DIVIDENDY: cols = ["Ticker", "Castka", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_UZIVATELE: cols = ["username", "password", "recovery_key"]
        return pd.DataFrame(columns=cols)

def uloz_data_uzivatele(user_df, username, nazev_souboru):
    full_df = nacti_csv(nazev_souboru)
    full_df = full_df[full_df['Owner'] != str(username)]
    if not user_df.empty:
        user_df['Owner'] = str(username)
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    uloz_csv(full_df, nazev_souboru, f"Update {username}")
    
    try: st.cache_data.clear()
    except: pass

def nacti_uzivatele(): 
    return nacti_csv(SOUBOR_UZIVATELE)
