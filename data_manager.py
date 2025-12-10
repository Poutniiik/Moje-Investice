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
# BEZPEČNĚJŠÍ ZÍSKÁNÍ TOKENU:
GITHUB_TOKEN = os.environ.get("GH_TOKEN") 

if not GITHUB_TOKEN:
    # 2. Fallback pro Streamlit (čteme tvůj původní název 'token' z secrets.toml)
    try: 
        if "github" in st.secrets:
            GITHUB_TOKEN = st.secrets["github"]["token"]
        else:
            GITHUB_TOKEN = ""
    except Exception: 
        GITHUB_TOKEN = ""

def get_repo(): 
    """Vrací instanci GitHub repozitáře nebo None s chybou."""
    if not GITHUB_TOKEN: 
        # Zobrazí varování jen, pokud se jej pokusíme volat (v CRUD funkcích)
        return None
    try:
        return Github(GITHUB_TOKEN).get_repo(REPO_NAZEV)
    except Exception as e:
        # Použijeme st.warning namísto st.error, aby aplikace nepadla hned na začátku
        st.warning(f"⚠️ GitHub: Chyba při připojení k repozitáři ({e}).")
        return None

def zasifruj(text): 
    """Šifruje text (heslo nebo recovery key) pomocí SHA256."""
    return hashlib.sha256(str(text).encode()).hexdigest()

# --- DATABÁZOVÉ FUNKCE (CRUD) ---

def uloz_csv_bezpecne(df, nazev_souboru, zprava):
    """
    Uloží DataFrame do GitHubu s retry logikou.
    """
    repo = get_repo()
    if not repo:
        # Tady již vypsalo get_repo varování o tokenu.
        return False

    csv_content = df.to_csv(index=False)
    pokusy = 3
    
    # 1. Zkusíme vytvořit/přepsat
    try:
        contents = repo.get_contents(nazev_souboru)
        # Soubor existuje -> Aktualizujeme
        repo.update_file(contents.path, zprava, csv_content, contents.sha)
        return True
    except Exception as e:
        # Soubor neexistuje (Chyba 404/UnknownObjectException) nebo jiná chyba
        pass # Pokračujeme na retry logiku

    # 2. Retry logika pro vytvoření/aktualizaci
    for i in range(pokusy):
        try:
            # Zkusíme VŽDY NEJDŘÍVE PŘEČÍST, abychom získali SHA pro UPDATE
            contents = repo.get_contents(nazev_souboru)
            repo.update_file(contents.path, zprava, csv_content, contents.sha)
            return True 
        except Exception:
            try:
                # Soubor neexistuje -> Vytvoříme
                repo.create_file(nazev_souboru, zprava, csv_content)
                return True
            except Exception as create_err:
                # Pokud nepomohlo, čekáme a zkoušíme znovu
                st.warning(f"⚠️ Pokus {i+1}/{pokusy}: Ukládání selhalo. Zkouším znovu. {create_err}")
                time.sleep(1) 
    
    st.error(f"❌ CHYBA UKLÁDÁNÍ: Soubor {nazev_souboru} se nepodařilo uložit. Data jsou jen v paměti!")
    return False

def uloz_csv(df, nazev_souboru, zprava):
    """WRAPPER: Pro zpětnou kompatibilitu."""
    return uloz_csv_bezpecne(df, nazev_souboru, zprava)

def nacti_csv(nazev_souboru):
    """Načítá soubor z GitHubu a zajišťuje správné typování sloupců."""
    try:
        repo = get_repo()
        if not repo: raise Exception("GitHub Token není k dispozici.")
        
        # Při načítání z repozitáře neděláme .copy()
        file = repo.get_contents(nazev_souboru)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        
        # Robustnější typování (ZLEPŠENÍ)
        date_cols = [col for col in df.columns if col in ['Datum', 'Date']]
        numeric_cols = [col for col in df.columns if col in ['Pocet', 'Cena', 'Castka', 'Kusu', 'Prodejka', 'Zisk', 'TotalUSD', 'Investice', 'TargetBuy', 'TargetSell']]

        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        # Zpětná kompatibilita Watchlistu
        if nazev_souboru == SOUBOR_WATCHLIST:
             if 'Target' in df.columns:
                 if 'TargetBuy' not in df.columns: df['TargetBuy'] = df['Target']
                 df = df.drop(columns=['Target'])
             if 'TargetBuy' not in df.columns: df['TargetBuy'] = 0.0
             if 'TargetSell' not in df.columns: df['TargetSell'] = 0.0
        
        # Zajištění kritických sloupců
        if nazev_souboru == SOUBOR_DATA:
            if 'Sektor' not in df.columns: df['Sektor'] = "Doplnit"
            if 'Poznamka' not in df.columns: df['Poznamka'] = ""
        
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        df['Owner'] = df['Owner'].astype(str)
        return df
        
    except Exception:
        # Vracíme prázdný DataFrame se správnými sloupci při chybě
        cols = ["Ticker", "Pocet", "Cena", "Datum", "Owner", "Sektor", "Poznamka"]
        if nazev_souboru == SOUBOR_HISTORIE: cols = ["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_CASH: cols = ["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_VYVOJ: cols = ["Date", "TotalUSD", "Owner"]
        if nazev_souboru == SOUBOR_WATCHLIST: cols = ["Ticker", "TargetBuy", "TargetSell", "Owner"]
        if nazev_souboru == SOUBOR_DIVIDENDY: cols = ["Ticker", "Castka", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_UZIVATELE: cols = ["username", "password", "recovery_key"]
        return pd.DataFrame(columns=cols)

def uloz_data_uzivatele(user_df, username, nazev_souboru):
    """Uloží DataFrame konkrétního uživatele do hlavního souboru (přepíše jeho data)."""
    full_df = nacti_csv(nazev_souboru)
    full_df = full_df[full_df['Owner'] != str(username)].copy() # Vždy pracovat s kopií!
    if not user_df.empty:
        user_df['Owner'] = str(username)
        # Zajištění, že se sloupce shodují (Při concat to je lepší)
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    
    # NEVOLAT st.cache_data.clear() zde, nechat to na transakční funkci
    uloz_csv(full_df, nazev_souboru, f"Update {username}")


def nacti_uzivatele(): 
    return nacti_csv(SOUBOR_UZIVATELE)
