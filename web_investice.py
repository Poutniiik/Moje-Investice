import streamlit as st
import pandas as pd
import numpy as np # Přidán numpy pro Monte Carlo a Sharpe Ratio
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots 
from github import Github
from io import StringIO
from datetime import datetime, timedelta
import hashlib
import time
import zipfile
import io
import requests
import feedparser
from streamlit_lottie import st_lottie
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from fpdf import FPDF
import extra_streamlit_components as stx
import random

# --- KONFIGURACE ---
# Musí být vždy jako první příkaz Streamlitu
st.set_page_config(
    page_title="Terminal Pro",
    layout="wide",
    page_icon="💹",
    initial_sidebar_state="expanded"
)

# --- KONSTANTY ---
REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv"
SOUBOR_WATCHLIST = "watchlist.csv"
SOUBOR_DIVIDENDY = "dividends.csv"
RISK_FREE_RATE = 0.04 # 4% Annual Risk-Free Rate (Bezriziková sazba pro Sharpe Ratio)

# --- ZDROJE ZPRÁV ---
RSS_ZDROJE = [
    "https://news.google.com/rss/search?q=akcie+burza+ekonomika&hl=cs&gl=CZ&ceid=CZ:cs",
    "https://servis.idnes.cz/rss.aspx?c=ekonomika", 
    "https://www.investicniweb.cz/rss"
]

# --- CITÁTY ---
CITATY = [
    "„Cena je to, co zaplatíš. Hodnota je to, co dostaneš.“ — Warren Buffett",
    "„Riziko pochází z toho, že nevíte, co děláte.“ — Warren Buffett",
    "„Trh je nástroj k přesunu peněz od netrpělivých k trpělivým.“ — Warren Buffett",
    "„Investování bez výzkumu je jako hrát poker a nedívat se na karty.“ — Peter Lynch",
    "„V krátkodobém horizontu je trh hlasovací stroj, v dlouhodobém váha.“ — Benjamin Graham",
    "„Neutrácejte to, co zbude po utrácení. Utrácejte to, co zbude po spoření.“ — Warren Buffett",
    "„Znáte ten pocit, když trh padá? To je výprodej. Nakupujte.“ — Neznámý",
    "„Bohatství není o tom mít hodně peněz, ale o tom mít hodně možností.“ — Chris Rock"
]

# --- ANALÝZA SENTIMENTU ---
KW_POSITIVNI = ["RŮST", "ZISK", "REKORD", "DIVIDEND", "POKLES INFLACE", "BÝČÍ", "UP", "PROFIT", "HIGHS", "SKOK", "VYDĚLAL"]
KW_NEGATIVNI = ["PÁD", "ZTRÁTA", "KRIZE", "MEDVĚDÍ", "DOWN", "LOSS", "CRASH", "PRODĚLAL", "VÁLKA", "BANKROT", "INFLACE", "POKLES"]

# --- MANUÁL PRO AI ---
APP_MANUAL = """
Jsi asistent v aplikaci 'Terminal Pro'.
Tvá role: Radit s investicemi, pomáhat s ovládáním a analyzovat zprávy z trhu.

MAPA APLIKACE:
1. '🏠 Přehled': Dashboard, Jmění, Hotovost, Síň slávy, Detailní tabulka.
2. '📈 Analýza': Rentgen akcie, Mapa trhu, Měnové riziko, Srovnání s S&P 500, Věštec, Crash Test.
3. '📰 Zprávy': Čtečka novinek z trhu + AI shrnutí.
4. '💸 Obchod & Peníze': Nákup/Prodej akcií, Vklady, Směnárna.
5. '💎 Dividendy': Historie a graf dividend.
6. '⚙️ Správa Dat': Zálohy a editace.
"""

# --- AI SETUP ---
try:
    if "google" in st.secrets:
        GOOGLE_API_KEY = st.secrets["google"]["api_key"]
        genai.configure(api_key=GOOGLE_API_KEY)
        AI_MODEL = genai.GenerativeModel('gemini-2.5-flash') 
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False
except Exception:
    AI_AVAILABLE = False

# --- STYLY (MODERNÍ TERMINÁL - FULL + MOBILE FIXES) ---
st.markdown("""
<style>
    /* Hlavní barvy a fonty */
    .stApp {background-color: #0E1117; font-family: 'Roboto Mono', monospace;}
    
    /* Vylepšení metrik */
    div[data-testid="stMetric"] {
        background-color: #161B22; 
        border: 1px solid #30363D; 
        padding: 15px; 
        border-radius: 8px; 
        color: #E6EDF3;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #58A6FF;
    }
    div[data-testid="stMetricLabel"] {font-size: 0.85rem; color: #8B949E; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;}
    div[data-testid="stMetricValue"] {font-size: 1.6rem; color: #E6EDF3; font-weight: bold;}
    
    /* Nadpisy */
    h1, h2, h3 {color: #E6EDF3 !important; font-family: 'Roboto Mono', monospace; text-transform: uppercase; letter-spacing: 1.5px;}
    
    /* Tlačítka - Větší pro dotyk */
    div[data-testid="column"] button {
        border: 1px solid #30363D; 
        background-color: #21262D; 
        color: #C9D1D9;
        border-radius: 6px;
        min-height: 45px; /* Větší výška pro prsty */
        transition: all 0.3s;
    }
    div[data-testid="column"] button:hover {
        border-color: #58A6FF;
        color: #58A6FF;
    }
    
    /* Tabs (Záložky) - REDESIGN */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        padding-bottom: 5px;
        flex-wrap: wrap; /* Zalomení na mobilu */
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px; /* Větší pro dotyk */
        white-space: pre-wrap;
        background-color: #0d1117; 
        border: 1px solid #30363D; 
        border-radius: 6px;
        color: #8B949E;
        font-family: 'Roboto Mono', monospace;
        font-size: 0.9rem;
        transition: all 0.2s ease;
        padding: 0px 20px;
        margin-bottom: 5px; /* Mezera při zalomení */
    }
    .stTabs [data-baseweb="tab"]:hover {
        border-color: #8B949E;
        color: #E6EDF3;
        background-color: #161B22;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636 !important;
        border-color: #2ea043 !important; 
        color: white !important;
        font-weight: bold;
        box-shadow: 0 0 10px rgba(35, 134, 54, 0.3); 
    }

    /* Odkazy */
    a {text-decoration: none; color: #58A6FF !important;} 
    
    /* Progress bar - Zelený styl */
    .stProgress > div > div > div > div {
        background-color: #238636;
    }

    /* --- PLOVOUCÍ AI BOT (RESPONZIVNÍ AVATAR STYLE) --- */
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) {
        position: fixed !important;
        bottom: 20px !important;
        right: 20px !important;
        width: 380px !important; /* PC velikost */
        max-width: 85vw !important; /* Mobilní limit */
        z-index: 99999 !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details {
        border-radius: 20px !important;
        background-color: #161B22 !important;
        border: 1px solid #30363D !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.8) !important;
        transition: all 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55);
    }

    /* HLAVIČKA - ZAVŘENÁ (AVATAR) */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary {
        background-color: transparent !important;
        color: transparent !important;
        height: 70px !important; /* Trochu menší na mobil */
        width: 70px !important;
        border-radius: 50% !important;
        padding: 0 !important;
        margin-left: auto !important;
        
        /* --- ZDE SE MĚNÍ OBRÁZEK (URL) --- */
        background-image: url('https://i.postimg.cc/cK5DmzZv/1000001805.jpg'); 
        
        background-size: cover;
        background-position: center;
        border: 3px solid #238636 !important;
        box-shadow: 0 0 15px rgba(35, 134, 54, 0.5);
        
        animation: float 6s ease-in-out infinite;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary:hover {
        transform: scale(1.1) rotate(5deg);
        box-shadow: 0 0 25px rgba(35, 134, 54, 0.8);
        cursor: pointer;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary svg {
        display: none !important;
    }

    /* OTEVŘENÝ STAV */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary {
        width: 100% !important;
        height: 40px !important;
        border-radius: 15px 15px 0 0 !important;
        background-image: none !important;
        background-color: #238636 !important;
        color: white !important;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: none !important;
        border: none !important;
        margin: 0 !important;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary::after {
        content: "❌ ZAVŘÍT CHAT";
        font-weight: bold;
        font-size: 0.9rem;
        color: white;
    }

    /* OBSAH CHATU */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) div[data-testid="stExpanderDetails"] {
        max-height: 400px; /* Menší výška pro mobily */
        overflow-y: auto;
        background-color: #0d1117;
        border-bottom-left-radius: 20px;
        border-bottom-right-radius: 20px;
        border-top: 1px solid #30363D;
        padding: 15px;
    }

    @keyframes float {
        0% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-10px); }}
        100% {{ transform: translateY(0px); }}
    }
    
    /* Mobilní úpravy pro Ticker Tape */
    @media (max-width: 600px) {
        .ticker-text {
            font-size: 0.8rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- PŘIPOJENÍ ---
try: 
    if "github" in st.secrets:
        GITHUB_TOKEN = st.secrets["github"]["token"]
    else:
        st.warning("⚠️ GitHub Token nenalezen v Secrets. Aplikace běží v demo režimu (bez ukládání).")
        GITHUB_TOKEN = ""
except Exception: 
    st.error("❌ CHYBA: Problém s načtením Secrets!")
    st.stop()

def get_repo(): 
    if not GITHUB_TOKEN: return None
    try:
        return Github(GITHUB_TOKEN).get_repo(REPO_NAZEV)
    except Exception as e:
        st.error(f"Chyba při připojení k repozitáři: {e}")
        return None

def zasifruj(text): 
    return hashlib.sha256(str(text).encode()).hexdigest()

# --- COOKIE MANAGER ---
def get_manager():
    return stx.CookieManager(key="cookie_manager_inst")

# --- EXTERNÍ DATA ---
@st.cache_data(ttl=3600)
def ziskej_fear_greed():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        score = int(data['fear_and_greed']['score'])
        rating = data['fear_and_greed']['rating']
        return score, rating
    except: return None, None

@st.cache_data(ttl=3600)
def ziskej_zpravy():
    news = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    for url in RSS_ZDROJE:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                for entry in feed.entries[:5]: 
                    datum = entry.get('published', datetime.now().strftime("%d.%m.%Y"))
                    news.append({"title": entry.title, "link": entry.link, "published": datum})
        except Exception: 
            pass
    return news

@st.cache_data(ttl=86400)
def ziskej_yield(ticker):
    try:
        t = yf.Ticker(str(ticker))
        d = t.info.get('dividendYield')
        if d and d > 0.30: return d / 100 
        return d if d else 0
    except Exception: return 0

# --- POKROČILÉ CACHING FUNKCE PRO RENTGEN ---

# 1. Funkce pro získání INFO (statická data) - Cache na 24h, uložení na disk
@st.cache_data(ttl=86400, show_spinner=False, persist="disk")
def _ziskej_info_cached(ticker):
    """
    Získá detailní info o firmě. Pokud data nejsou kompletní,
    VYVOLÁ CHYBU, aby se špatný výsledek neuložil do cache.
    """
    t = yf.Ticker(str(ticker))
    info = t.info
    
    # Validace: Pokud chybí klíčová data, považujeme to za chybu API
    # a vyvoláme výjimku -> Streamlit si to NEuloží do cache.
    if not info or len(info) < 5 or "Yahoo API limit" in info.get("longBusinessSummary", ""):
        raise ValueError("Neúplná data z Yahoo API")
    
    return info

# 2. Funkce pro získání HISTORIE (graf) - Cache na 1h
@st.cache_data(ttl=3600, show_spinner=False)
def _ziskej_historii_cached(ticker):
    try:
        t = yf.Ticker(str(ticker))
        return t.history(period="1y")
    except:
        return None

def ziskej_detail_akcie(ticker):
    info = {}
    hist = None
    
    # A) Zkusíme načíst INFO z "trezoru" (cache)
    try:
        info = _ziskej_info_cached(ticker)
    except Exception:
        # Pokud cache selže (nebo API hodí chybu), spustíme "Záchranný režim" (Fallback)
        # TENTO FALLBACK SE NEUKLÁDÁ DO DLOUHODOBÉ CACHE!
        # Takže při příštím načtení se aplikace znova pokusí získat kvalitní data.
        try:
            t = yf.Ticker(str(ticker))
            fi = t.fast_info
            info = {
                "longName": ticker,
                "longBusinessSummary": "MISSING_SUMMARY", # Značka pro AI
                "recommendationKey": "N/A",
                "targetMeanPrice": 0,
                "trailingPE": 0,
                "currency": fi.currency,
                "currentPrice": fi.last_price,
                "website": ""
            }
        except:
            # Úplné selhání
            info = {
                "longName": ticker, 
                "currency": "USD", 
                "currentPrice": 0, 
                "longBusinessSummary": "Data nedostupná."
            }

    # B) Historii načítáme zvlášť (kratší cache)
    hist = _ziskej_historii_cached(ticker)
    
    return info, hist

# --- PDF GENERATOR ---
def clean_text(text):
    # Jednoduchá transliterace pro české znaky do PDF (bez nutnosti fontů)
    replacements = {
        'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 'ě': 'e', 'í': 'i', 'ň': 'n', 'ó': 'o', 'ř': 'r', 'š': 's', 'ť': 't', 'ú': 'u', 'ů': 'u', 'ý': 'y', 'ž': 'z',
        'Á': 'A', 'Č': 'C', 'Ď': 'D', 'É': 'E', 'Ě': 'E', 'Í': 'I', 'Ň': 'N', 'Ó': 'O', 'Ř': 'R', 'Š': 'S', 'Ť': 'T', 'Ú': 'U', 'Ů': 'U', 'Ý': 'Y', 'Ž': 'Z'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def vytvor_pdf_report(user, total_czk, cash_usd, profit_czk, data_list):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(f"INVESTICNI REPORT: {user}"), ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)
    
    # Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "SOUHRN", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, clean_text(f"Celkove jmeni: {total_czk:,.0f} CZK"), ln=True)
    pdf.cell(0, 10, clean_text(f"Hotovost: {cash_usd:,.0f} USD"), ln=True)
    pdf.cell(0, 10, clean_text(f"Celkovy zisk/ztrata: {profit_czk:,.0f} CZK"), ln=True)
    pdf.ln(10)
    
    # Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(30, 10, "Ticker", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Kusy", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Cena (Avg)", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Hodnota (USD)", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Zisk (USD)", 1, 1, 'C', 1)
    
    # Table Rows
    pdf.set_font("Arial", size=10)
    for item in data_list:
        pdf.cell(30, 10, str(item['Ticker']), 1)
        pdf.cell(30, 10, f"{item['Kusy']:.2f}", 1)
        pdf.cell(40, 10, f"{item['Průměr']:.2f}", 1)
        pdf.cell(40, 10, f"{item['HodnotaUSD']:.0f}", 1)
        pdf.cell(40, 10, f"{item['Zisk']:.0f}", 1, 1)
        
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- DATABÁZE ---
def uloz_csv(df, nazev_souboru, zprava):
    repo = get_repo()
    if not repo: return
    csv = df.to_csv(index=False)
    try:
        file = repo.get_contents(nazev_souboru)
        repo.update_file(file.path, zprava, csv, file.sha)
    except Exception: 
        repo.create_file(nazev_souboru, zprava, csv)

def nacti_csv(nazev_souboru):
    try:
        repo = get_repo()
        if not repo: raise Exception("No repo")
        file = repo.get_contents(nazev_souboru)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        
        # Konverze sloupců
        for col in ['Datum', 'Date']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        for col in ['Pocet', 'Cena', 'Castka', 'Kusu', 'Prodejka', 'Zisk', 'TotalUSD', 'Investice', 'Target']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        # Doplnění chybějících sloupců pro kompatibilitu
        if 'Sektor' not in df.columns and nazev_souboru == SOUBOR_DATA: df['Sektor'] = "Doplnit"
        if 'Poznamka' not in df.columns and nazev_souboru == SOUBOR_DATA: df['Poznamka'] = ""
        if nazev_souboru == SOUBOR_WATCHLIST and 'Target' not in df.columns: df['Target'] = 0.0
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        
        df['Owner'] = df['Owner'].astype(str)
        return df
    except Exception:
        # Fallback pokud soubor neexistuje
        cols = ["Ticker", "Pocet", "Cena", "Datum", "Owner", "Sektor", "Poznamka"]
        if nazev_souboru == SOUBOR_HISTORIE: cols = ["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_CASH: cols = ["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_VYVOJ: cols = ["Date", "TotalUSD", "Owner"]
        if nazev_souboru == SOUBOR_WATCHLIST: cols = ["Ticker", "Target", "Owner"]
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
    st.cache_data.clear()

def nacti_uzivatele(): 
    return nacti_csv(SOUBOR_UZIVATELE)

def pridat_do_watchlistu(ticker, target, user):
    df_w = st.session_state['df_watch']
    if ticker not in df_w['Ticker'].values:
        new = pd.DataFrame([{"Ticker": ticker, "Target": float(target), "Owner": user}])
        updated = pd.concat([df_w, new], ignore_index=True)
        st.session_state['df_watch'] = updated
        uloz_data_uzivatele(updated, user, SOUBOR_WATCHLIST)
        return True
    return False

def odebrat_z_watchlistu(ticker, user):
    df_w = st.session_state['df_watch']
    updated = df_w[df_w['Ticker'] != ticker]
    st.session_state['df_watch'] = updated
    uloz_data_uzivatele(updated, user, SOUBOR_WATCHLIST)

def get_zustatky(user):
    df_cash = st.session_state.get('df_cash', pd.DataFrame())
    if df_cash.empty: return {}
    return df_cash.groupby('Mena')['Castka'].sum().to_dict()

def pohyb_penez(castka, mena, typ, poznamka, user):
    df_cash = st.session_state['df_cash']
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash = pd.concat([df_cash, novy], ignore_index=True)
    st.session_state['df_cash'] = df_cash
    uloz_data_uzivatele(df_cash, user, SOUBOR_CASH)

def pridat_dividendu(ticker, castka, mena, user):
    df_div = st.session_state['df_div']
    novy = pd.DataFrame([{"Ticker": ticker, "Castka": float(castka), "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_div = pd.concat([df_div, novy], ignore_index=True)
    st.session_state['df_div'] = df_div
    uloz_data_uzivatele(df_div, user, SOUBOR_DIVIDENDY)
    pohyb_penez(castka, mena, "Dividenda", f"Divi {ticker}", user)

def aktualizuj_graf_vyvoje(user, aktualni_hodnota_usd):
    if pd.isna(aktualni_hodnota_usd): return pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    full_hist = nacti_csv(SOUBOR_VYVOJ)
    today = datetime.now().strftime("%Y-%m-%d")
    user_hist = full_hist[full_hist['Owner'] == str(user)].copy()
    dnes_zapsano = False
    
    if not user_hist.empty:
        last_date = user_hist.iloc[-1]['Date']
        if pd.notnull(last_date) and last_date.strftime("%Y-%m-%d") == today:
            dnes_zapsano = True
            full_hist.at[user_hist.index[-1], 'TotalUSD'] = aktualni_hodnota_usd
            
    if not dnes_zapsano:
        new_row = pd.DataFrame([{"Date": datetime.now(), "TotalUSD": aktualni_hodnota_usd, "Owner": str(user)}])
        full_hist = pd.concat([full_hist, new_row], ignore_index=True)
        
    uloz_csv(full_hist, SOUBOR_VYVOJ, "Daily snapshot")
    return full_hist[full_hist['Owner'] == str(user)]

def proved_prodej(ticker, kusy, cena, user, mena):
    df_p = st.session_state['df'].copy()
    df_h = st.session_state['df_hist'].copy()
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')
    
    if df_t.empty or df_t['Pocet'].sum() < kusy: 
        return False, "Nedostatek kusů."
        
    zbyva, zisk, trzba = kusy, 0, kusy * cena
    
    for idx, row in df_t.iterrows():
        if zbyva <= 0: break
        ukrojeno = min(row['Pocet'], zbyva)
        zisk += (cena - row['Cena']) * ukrojeno
        if ukrojeno == row['Pocet']: 
            df_p = df_p.drop(idx)
        else: 
            df_p.at[idx, 'Pocet'] -= ukrojeno
        zbyva -= ukrojeno
        
    new_h = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_h = pd.concat([df_h, new_h], ignore_index=True)
    pohyb_penez(trzba, mena, "Prodej", f"Prodej {ticker}", user)
    
    st.session_state['df'] = df_p
    st.session_state['df_hist'] = df_h
    uloz_data_uzivatele(df_p, user, SOUBOR_DATA)
    uloz_data_uzivatele(df_h, user, SOUBOR_HISTORIE)
    return True, f"Prodáno! +{trzba:,.2f}"

def odeslat_email(prijemce, predmet, telo):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        msg = MIMEText(telo, 'html')
        msg['Subject'] = predmet
        msg['From'] = sender_email
        msg['To'] = prijemce
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, prijemce, msg.as_string())
        return True
    except Exception as e: return f"Chyba: {e}"

@st.cache_data(ttl=3600)
def ziskej_ceny_hromadne(tickers):
    data = {}
    if not tickers: return data
    try:
        ts = list(set(tickers + ["CZK=X", "EURUSD=X"]))
        df_y = yf.download(ts, period="1d", group_by='ticker', progress=False)
        for t in ts:
            try:
                if isinstance(df_y.columns, pd.MultiIndex): price = df_y[t]['Close'].iloc[-1]
                else: price = df_y['Close'].iloc[-1]
                curr = "USD"
                if ".PR" in t: curr = "CZK"
                elif ".DE" in t: curr = "EUR"
                if pd.notnull(price): data[t] = {"price": float(price), "curr": curr}
            except Exception: pass
    except Exception: pass
    return data

@st.cache_data(ttl=3600)
def ziskej_kurzy(): 
    # Tyto hodnoty jsou použity jako fallback, pokud selže yfinance (CZK=X)
    return {"USD": 1.0, "CZK": 20.85, "EUR": 1.16}

@st.cache_data(ttl=3600)
def ziskej_info(ticker):
    mena = "USD"
    if str(ticker).endswith(".PR"): mena = "CZK"
    elif str(ticker).endswith(".DE"): mena = "EUR"
    try: 
        t = yf.Ticker(str(ticker))
        price = t.fast_info.last_price
        prev = t.fast_info.previous_close
        zmena = ((price/prev)-1) if prev else 0
        api_curr = t.fast_info.currency
        if api_curr and api_curr != "N/A": mena = api_curr
        return price, mena, zmena
    except Exception: return None, mena, 0

def proved_smenu(castka, z_meny, do_meny, user):
    kurzy = ziskej_kurzy()
    # Simplified conversion logic - real app should use live cross rates
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy.get("CZK", 20.85)
    elif z_meny == "EUR": castka_usd = castka * kurzy.get("EUR", 1.16) # EUR/USD rate
    
    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurzy.get("CZK", 20.85)
    elif do_meny == "EUR": vysledna = castka_usd / kurzy.get("EUR", 1.16)
    
    pohyb_penez(-castka, z_meny, "Směna", f"Směna na {do_meny}", user)
    pohyb_penez(vysledna, do_meny, "Směna", f"Směna z {z_meny}", user)
    return True, f"Směněno: {vysledna:,.2f} {do_meny}"

def render_ticker_tape(data_dict):
    if not data_dict: return
    content = ""
    for ticker, info in data_dict.items():
        price = info.get('price', 0)
        curr = info.get('curr', '')
        content += f"&nbsp;&nbsp;&nbsp;&nbsp; <b>{ticker}</b>: {price:,.2f} {curr}"
    
    st.markdown(f"""
        <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 5px; padding: 8px; margin-bottom: 20px; white-space: nowrap; overflow: hidden;">
            <div style="display: inline-block; animation: marquee 20s linear infinite; color: #00CC96; font-family: 'Roboto Mono', monospace; font-weight: bold;" class="ticker-text">
                {content} {content} {content}
            </div>
        </div>
        <style>
            @keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}
        </style>
    """, unsafe_allow_html=True)

# --- FINANČNÍ FUNKCE ---
def calculate_sharpe_ratio(returns, risk_free_rate=RISK_FREE_RATE, periods_per_year=252):
    """Vypočítá anualizované Sharpe Ratio."""
    if returns.empty or returns.std() == 0:
        return 0.0
    daily_risk_free_rate = risk_free_rate / periods_per_year
    excess_returns = returns - daily_risk_free_rate
    sharpe_ratio = np.sqrt(periods_per_year) * (excess_returns.mean() / returns.std())
    return sharpe_ratio

# --- HLAVNÍ FUNKCE ---
def main():
    # 1. Start Cookie Manager
    cookie_manager = get_manager()
    
    # 2. Inicializace stavu (Session State)
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False
        st.session_state['user'] = ""
    
    # 3. ZPOŽDĚNÍ PRO COOKIES (Nutné pro stx)
    time.sleep(0.3)
    
    # 4. LOGIKA PŘIHLÁŠENÍ (Gatekeeper)
    if not st.session_state['prihlasen']:
        cookie_user = cookie_manager.get("invest_user")
        if cookie_user:
            st.session_state['prihlasen'] = True
            st.session_state['user'] = cookie_user
            st.rerun()

    # --- ZOBRAZENÍ LOGIN FORMULÁŘE ---
    if not st.session_state['prihlasen']:
        c1,c2,c3 = st.columns([1, 2, 1])
        with c2:
            st.title("🔐 INVESTIČNÍ TERMINÁL")
            t1, t2, t3 = st.tabs(["PŘIHLÁŠENÍ", "REGISTRACE", "OBNOVA HESLA"])
            with t1:
                with st.form("l"):
                    u=st.text_input("Uživatelské jméno")
                    p=st.text_input("Heslo", type="password")
                    if st.form_submit_button("VSTOUPIT", use_container_width=True):
                        df_u = nacti_uzivatele()
                        row = df_u[df_u['username'] == u] if not df_u.empty else pd.DataFrame()
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            cookie_manager.set("invest_user", u, expires_at=datetime.now() + timedelta(days=30))
                            st.session_state.update({'prihlasen':True, 'user':u})
                            st.toast("Přihlašování...", icon="⏳")
                            time.sleep(1)
                            st.rerun()
                        else: st.toast("Chyba přihlášení", icon="❌")
            with t2:
                with st.form("r"):
                    nu=st.text_input("Nové jméno")
                    new_pass=st.text_input("Nové heslo", type="password") 
                    nr=st.text_input("Záchranný kód", help="Slouží pro obnovu zapomenutého hesla.")
                    if st.form_submit_button("VYTVOŘIT ÚČET", use_container_width=True):
                        df_u = nacti_uzivatele()
                        if not df_u.empty and nu in df_u['username'].values: 
                            st.toast("Jméno již existuje.", icon="⚠️")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(new_pass), "recovery_key": zasifruj(nr)}])
                            uloz_csv(pd.concat([df_u, new], ignore_index=True), SOUBOR_UZIVATELE, "New user")
                            st.toast("Účet vytvořen!", icon="✅")
            with t3:
                st.caption("Zapomněl jsi heslo?")
                with st.form("recovery"):
                    ru = st.text_input("Jméno")
                    rk = st.text_input("Záchranný kód")
                    rnp = st.text_input("Nové heslo", type="password")
                    if st.form_submit_button("OBNOVIT"):
                        df_u = nacti_uzivatele()
                        user_row = df_u[df_u['username'] == ru]
                        if not user_row.empty and user_row.iloc[0]['recovery_key'] == zasifruj(rk):
                            df_u.at[user_row.index[0], 'password'] = zasifruj(rnp)
                            uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}")
                            st.success("Heslo změněno!")
                        else: st.error("Chyba údajů.")
        return

    # =========================================================================
    # ZDE ZAČÍNÁ APLIKACE PRO PŘIHLÁŠENÉHO UŽIVATELE
    # =========================================================================
    
    USER = st.session_state['user']
    
    # --- 2. NAČTENÍ DAT ---
    if 'df' not in st.session_state:
        with st.spinner("NAČÍTÁM DATA..."):
            st.session_state['df'] = nacti_csv(SOUBOR_DATA).query(f"Owner=='{USER}'").copy()
            st.session_state['df_hist'] = nacti_csv(SOUBOR_HISTORIE).query(f"Owner=='{USER}'").copy()
            st.session_state['df_cash'] = nacti_csv(SOUBOR_CASH).query(f"Owner=='{USER}'").copy()
            st.session_state['df_div'] = nacti_csv(SOUBOR_DIVIDENDY).query(f"Owner=='{USER}'").copy()
            st.session_state['df_watch'] = nacti_csv(SOUBOR_WATCHLIST).query(f"Owner=='{USER}'").copy()
            st.session_state['hist_vyvoje'] = aktualizuj_graf_vyvoje(USER, 0)

    df = st.session_state['df']
    df_cash = st.session_state['df_cash']
    df_div = st.session_state['df_div']
    df_watch = st.session_state['df_watch']
    zustatky = get_zustatky(USER)
    kurzy = ziskej_kurzy()

    # --- 3. VÝPOČTY ---
    all_tickers = []
    viz_data = []
    celk_hod_usd = 0
    celk_inv_usd = 0
    
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    
    LIVE_DATA = ziskej_ceny_hromadne(list(set(all_tickers)))
    if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
    if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]

    # --- 3.5. KONTROLA WATCHLISTU (ALERTY) ---
    alerts = []
    if not df_watch.empty:
        for _, r in df_watch.iterrows():
            tk = r['Ticker']; trg = r['Target']
            if trg > 0:
                inf = LIVE_DATA.get(tk, {})
                price = inf.get('price')
                if not price: # Fallback if not in batch
                    price, _, _ = ziskej_info(tk)
                
                if price and price <= trg:
                    alerts.append(f"{tk}: {price:.2f} <= {trg:.2f}")
                    st.toast(f"🔔 {tk} je ve slevě! ({price:.2f})", icon="🔥")

    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        df_g['Cena'] = df_g['Investice'] / df_g['Pocet']
        
        for i, (idx, row) in enumerate(df_g.iterrows()):
            tkr = row['Ticker']
            p, m, d_zmena = ziskej_info(tkr)
            if p is None: p = row['Cena']
            if m is None or m == "N/A": m = "USD"
            
            try:
                raw_sektor = df[df['Ticker'] == tkr]['Sektor'].iloc[0]
                sektor = str(raw_sektor) if not pd.isna(raw_sektor) and str(raw_sektor).strip() != "" else "Doplnit"
            except Exception: sektor = "Doplnit"
            
            nakupy_data = df[df['Ticker'] == tkr]['Datum']
            dnes = datetime.now()
            limit_dni = 1095 
            vsechny_ok = True
            vsechny_fail = True
            
            for d in nakupy_data:
                if (dnes - d).days < limit_dni: vsechny_ok = False 
                else: vsechny_fail = False 
            
            if vsechny_ok: dan_status = "🟢 Free"      
            elif vsechny_fail: dan_status = "🔴 Zdanit" 
            else: dan_status = "🟠 Mix" 
            
            # --- URČENÍ ZEMĚ ---
            country = "United States" # Default USA
            tkr_upper = str(tkr).upper()
            if tkr_upper.endswith(".PR"): country = "Czechia"
            elif tkr_upper.endswith(".DE"): country = "Germany"
            elif tkr_upper.endswith(".L"): country = "United Kingdom"
            elif tkr_upper.endswith(".PA"): country = "France"
            
            div_vynos = ziskej_yield(tkr)
            hod = row['Pocet']*p
            inv = row['Investice']
            z = hod-inv
            
            try: 
                # Přepočet na USD
                if m == "CZK": k = 1.0 / kurzy.get("CZK", 20.85)
                elif m == "EUR": k = kurzy.get("EUR", 1.16)
                else: k = 1.0
            except Exception: k = 1.0
            
            celk_hod_usd += hod*k
            celk_inv_usd += inv*k
            
            viz_data.append({
                "Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m, 
                "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Cena'], "Dan": dan_status, "Investice": inv, "Divi": div_vynos, "Dnes": d_zmena,
                "Země": country
            })
    
    # Vytvoření DataFrame pro globální použití
    vdf = pd.DataFrame(viz_data) if viz_data else pd.DataFrame()

    hist_vyvoje = st.session_state['hist_vyvoje']
    if celk_hod_usd > 0 and pd.notnull(celk_hod_usd): 
        hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    
    kurz_czk = kurzy.get("CZK", 20.85)
    celk_hod_czk = celk_hod_usd * kurz_czk
    celk_inv_czk = celk_inv_usd * kurz_czk
    
    zmena_24h = 0
    pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if pd.notnull(vcera) and vcera > 0: 
            zmena_24h = celk_hod_usd - vcera
            pct_24h = (zmena_24h / vcera * 100)
    
    try: 
        # Hotovost přepočítána na USD
        cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))
    except Exception: cash_usd = 0

    # --- 4. SIDEBAR ---
    with st.sidebar:
        st.header(f"👤 {USER.upper()}")
        
        # --- GAME LEVELING SYSTEM ---
        level_name = "Novic"
        level_progress = 0.0
        
        if celk_hod_czk < 10000:
            level_name = "Novic 🧒"
            level_progress = min(celk_hod_czk / 10000, 1.0)
        elif celk_hod_czk < 50000:
            level_name = "Učeň 🧑‍🎓"
            level_progress = min((celk_hod_czk - 10000) / 40000, 1.0)
        elif celk_hod_czk < 100000:
            level_name = "Trader 💼"
            level_progress = min((celk_hod_czk - 50000) / 50000, 1.0)
        elif celk_hod_czk < 500000:
            level_name = "Profi 🎩"
            level_progress = min((celk_hod_czk - 100000) / 400000, 1.0)
        else:
            level_name = "Velryba 🐋"
            level_progress = 1.0
            
        st.caption(f"Úroveň: **{level_name}**")
        st.progress(level_progress)
        
        # --- WALLET IN SIDEBAR ---
        st.write("") 
        st.caption("Stav peněženky:")
        for mena in ["USD", "CZK", "EUR"]:
            castka = zustatky.get(mena, 0.0)
            sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
            st.info(f"**{castka:,.2f} {sym}**", icon="💰")
        
        # --- SIDEBAR ALERTS ---
        if alerts:
            st.divider()
            st.error("🔔 CENOVÉ ALERTY!", icon="🔥")
            for a in alerts:
                st.markdown(f"- **{a}**")

        st.divider(); st.subheader("NAVIGACE")
        page = st.radio("Jít na:", ["🏠 Přehled", "👀 Sledování", "📈 Analýza", "📰 Zprávy", "💸 Obchod", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení"], label_visibility="collapsed")
        
        st.divider()
        if st.button("📧 ODESLAT RANNÍ REPORT", use_container_width=True):
            msg = f"<h2>Report {USER}</h2><p>Jmění: {celk_hod_czk:,.0f} Kč</p>"
            if odeslat_email(st.secrets["email"]["sender"], "Report", msg) == True: st.success("Odesláno!")
            else: st.error("Chyba")
        
        # Přesunutí PDF generace do download buttonu
        pdf_data = vytvor_pdf_report(USER, celk_hod_czk, cash_usd, (celk_hod_czk - celk_inv_czk), viz_data)
        st.download_button(label="📄 STÁHNOUT PDF REPORT", data=pdf_data, file_name=f"report_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)

        st.divider()
        with st.expander("🔐 Změna hesla"):
            with st.form("pass_change"):
                old = st.text_input("Staré", type="password"); new = st.text_input("Nové", type="password"); conf = st.text_input("Potvrdit", type="password")
                if st.form_submit_button("Změnit"):
                    df_u = nacti_uzivatele(); row = df_u[df_u['username'] == USER]
                    if not row.empty and row.iloc[0]['password'] == zasifruj(old):
                        if new == conf and len(new) > 0:
                            df_u.at[row.index[0], 'password'] = zasifruj(new); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Pass change {USER}"); st.success("Hotovo!")
                        else: st.error("Chyba v novém hesle.")
                    else: st.error("Staré heslo nesedí.")
        
        if st.button("🚪 ODHLÁSIT", use_container_width=True): 
            cookie_manager.delete("invest_user")
            st.session_state.clear()
            st.rerun()

    # BĚŽÍCÍ PÁS 
    if page not in ["🎮 Gamifikace", "⚙️ Nastavení"]:
        render_ticker_tape(LIVE_DATA)

    # --- 5. STRÁNKY ---
    if page == "🏠 Přehled":
        st.title(f"🏠 PŘEHLED: {USER.upper()}")
        
        # HLAVNÍ METRIKY
        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} Zisk")
            k2.metric("JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{(celk_hod_usd-celk_inv_usd)*kurzy['CZK']:+,.0f} Kč")
            k3.metric("ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
            k4.metric("HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné")
        
        st.write("")
        
        # --- FEAR & GREED INDEX (TACHOMETR) ---
        score, rating = ziskej_fear_greed()
        if score is not None:
            st.subheader(f"😨🤑 TRŽNÍ NÁLADA: {rating} ({score})")
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': "white"},
                    'bgcolor': "black",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, 25], 'color': '#FF4136'},   # Extrémní strach (červená)
                        {'range': [25, 45], 'color': '#FF851B'},  # Strach (oranžová)
                        {'range': [45, 55], 'color': '#AAAAAA'},  # Neutrál (šedá)
                        {'range': [55, 75], 'color': '#7FDBFF'},  # Chamtivost (světle modrá)
                        {'range': [75, 100], 'color': '#2ECC40'}  # Extrémní chamtivost (zelená)
                    ],
                }
            ))
            fig_gauge.update_layout(paper_bgcolor="#161B22", font={'color': "white", 'family': "Arial"}, height=250, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
        
        st.divider()

        col_graf1, col_graf2 = st.columns([2, 1])

        with col_graf1:
            if not hist_vyvoje.empty:
                st.subheader("🌊 VÝVOJ MAJETKU (CZK)")
                chart_data = hist_vyvoje.copy()
                chart_data['Date'] = pd.to_datetime(chart_data['Date'])
                chart_data['TotalCZK'] = chart_data['TotalUSD'] * kurzy.get("CZK", 20.85)
                fig_area = px.area(chart_data, x='Date', y='TotalCZK', template="plotly_dark", color_discrete_sequence=['#00CC96'])
                fig_area.update_layout(xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
                st.plotly_chart(fig_area, use_container_width=True)
        
        with col_graf2:
            if not vdf.empty:
                st.subheader("🍰 SEKTORY")
                fig_pie = px.pie(vdf, values='HodnotaUSD', names='Sektor', hole=0.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=300)
                st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("💰 INVESTOVÁNO DLE MĚN")
        inv_usd, inv_czk, inv_eur = 0, 0, 0
        if viz_data:
            for item in viz_data:
                if item['Měna'] == 'USD': inv_usd += item['Investice']
                elif item['Měna'] == 'CZK': inv_czk += item['Investice']
                elif item['Měna'] == 'EUR': inv_eur += item['Investice']
        
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Investováno (USD)", f"${inv_usd:,.0f}")
        ic2.metric("Investováno (CZK)", f"{inv_czk:,.0f} Kč")
        ic3.metric("Investováno (EUR)", f"{inv_eur:,.0f} €")
        
        st.divider()

        st.subheader("📋 PORTFOLIO LIVE")
        if not vdf.empty:
            st.caption("Legenda daní: 🟢 > 3 roky (Osvobozeno) | 🔴 < 3 roky (Zdanit) | 🟠 Mix nákupů")
            st.dataframe(
                vdf,
                column_config={
                    "Ticker": st.column_config.TextColumn("Symbol", help="Zkratka akcie"),
                    "Sektor": st.column_config.TextColumn("Sektor", help="Odvětví"),
                    "HodnotaUSD": st.column_config.ProgressColumn("Velikost", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"])),
                    "Zisk": st.column_config.NumberColumn("Zisk/Ztráta", format="%.2f"),
                    "Dnes": st.column_config.NumberColumn("Dnes %", format="%.2f%%"),
                    "Divi": st.column_config.NumberColumn("Yield", format="%.2f%%"),
                    "Dan": st.column_config.TextColumn("Daně", help="🟢 > 3 roky (Osvobozeno)\n🔴 < 3 roky (Zdanit)\n🟠 Mix nákupů"),
                    "Země": "Země"
                },
                column_order=["Ticker", "Sektor", "Měna", "Země", "Kusy", "Průměr", "Cena", "Dnes", "HodnotaUSD", "Zisk", "Divi", "Dan"],
                use_container_width=True,
                hide_index=True
            )
        else: st.info("Portfolio je prázdné.")

    elif page == "👀 Sledování":
        st.title("👀 WATCHLIST (Hlídač)")
        with st.expander("➕ Přidat novou akcii", expanded=False):
            with st.form("add_w", clear_on_submit=True):
                c1,c2 = st.columns([3,1])
                with c1: t = st.text_input("Symbol (např. AAPL)").upper()
                with c2: tg = st.number_input("Cílová cena ($)", min_value=0.0)
                if st.form_submit_button("Sledovat"):
                    if t: pridat_do_watchlistu(t, tg, USER); st.rerun()
        
        if not df_watch.empty:
            w_data = []
            for _, r in df_watch.iterrows():
                tk = r['Ticker']; trg = r['Target']
                inf = LIVE_DATA.get(tk, {}); p = inf.get('price'); cur = inf.get('curr', 'USD')
                if not p: p, _, _ = ziskej_info(tk)
                diff_str = "---"
                if p and trg > 0:
                    diff = ((p/trg)-1)*100
                    diff_str = f"{diff:+.1f}%"
                status = "💤"
                if p and trg > 0:
                    if p <= trg: status = "🔥 SLEVA! KUPUJ"
                    elif p <= trg * 1.05: status = "👀 BLÍZKO"
                w_data.append({"Symbol": tk, "Aktuální Cena": p, "Měna": cur, "Cílová Cena": trg, "Odchylka": diff_str, "Status": status})
            
            wdf = pd.DataFrame(w_data)
            st.dataframe(wdf, use_container_width=True, hide_index=True)
            st.divider()
            c_del1, c_del2 = st.columns([3, 1])
            with c_del2:
                to_del = st.selectbox("Vyber pro smazání:", df_watch['Ticker'].unique())
                if st.button("🗑️ Smazat ze sledování", use_container_width=True): 
                    odebrat_z_watchlistu(to_del, USER); st.rerun()
        else:
            st.info("Zatím nic nesleduješ. Přidej první akcii nahoře.")

    elif page == "🎮 Gamifikace":
        st.title("🎮 INVESTIČNÍ ARÉNA")
        st.subheader(f"Tvá úroveň: {level_name}")
        st.progress(level_progress)
        if celk_hod_czk < 500000:
             st.caption(f"Do další úrovně ti chybí majetek.")
        else: st.success("Gratulace! Dosáhl jsi maximální úrovně Velryba 🐋")
        
        st.divider()
        st.subheader("🏆 SÍŇ SLÁVY (Odznaky)")
        c1,c2,c3,c4 = st.columns(4)
        has_first = not df.empty
        cnt = len(df['Ticker'].unique()) if not df.empty else 0
        divi_total = 0
        if not df_div.empty:
            # Správný výpočet dividendy v CZK
            divi_total = df_div.apply(lambda r: r['Castka'] * (kurzy.get('CZK', 20.85) if r['Mena'] == 'USD' else (kurzy.get('CZK', 20.85) / kurzy.get('EUR', 1.16) if r['Mena'] == 'EUR' else 1)), axis=1).sum()
        
        def render_badge(col, title, desc, cond, icon, color):
            with col:
                with st.container(border=True):
                    if cond:
                        st.markdown(f"<div style='text-align:center; color:{color}'><h1>{icon}</h1><h3>{title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)
                        st.success("ZÍSKÁNO")
                    else:
                        st.markdown(f"<div style='text-align:center; color:gray; opacity:0.3'><h1>{icon}</h1><h3>{title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)
                        st.caption("UZAMČENO")

        render_badge(c1, "Začátečník", "Kup první akcii", has_first, "🥉", "#CD7F32")
        render_badge(c2, "Stratég", "Drž 3 různé firmy", cnt >= 3, "🥈", "#C0C0C0")
        render_badge(c3, "Boháč", "Portfolio > 100k", celk_hod_czk > 100000, "🥇", "#FFD700")
        render_badge(c4, "Rentiér", "Dividendy > 500 Kč", divi_total > 500, "💎", "#00BFFF")
        st.divider()
        st.subheader("💡 Moudro dne")
        if 'quote' not in st.session_state: st.session_state['quote'] = random.choice(CITATY)
        st.info(f"*{st.session_state['quote']}*")

    elif page == "💸 Obchod":
        st.title("💸 OBCHODNÍ TERMINÁL")
        t1, t2, t3, t4 = st.tabs(["NÁKUP", "PRODEJ", "SMĚNÁRNA", "VKLADY/VÝBĚRY"])
        with t1:
            c1, c2 = st.columns(2)
            with c1:
                t = st.text_input("Ticker (např. AAPL)").upper()
                k = st.number_input("Počet kusů", 0.0, step=0.1)
                c = st.number_input("Nákupní cena ($)", 0.0, step=0.1)
            with c2:
                st.info("Zkontroluj zůstatek v peněžence!")
                if st.button("KOUPIT AKCIE", use_container_width=True):
                    _, m, _ = ziskej_info(t)
                    cost = k*c
                    if zustatky.get(m, 0) >= cost:
                        pohyb_penez(-cost, m, "Nákup", t, USER)
                        d = pd.DataFrame([{"Ticker": t, "Pocet": k, "Cena": c, "Datum": datetime.now(), "Owner": USER, "Sektor": "Doplnit", "Poznamka": ""}])
                        st.session_state['df'] = pd.concat([df, d], ignore_index=True)
                        uloz_data_uzivatele(st.session_state['df'], USER, SOUBOR_DATA)
                        st.success("OK"); time.sleep(1); st.rerun()
                    else: st.error("Nedostatek peněz")
        with t2:
            ts = df['Ticker'].unique() if not df.empty else []
            s_t = st.selectbox("Prodat:", ts)
            s_k = st.number_input("Kusy", 0.0, step=0.1, key="sk")
            s_c = st.number_input("Cena ($)", 0.0, step=0.1, key="sc")
            if st.button("PRODAT", use_container_width=True):
                _, m, _ = ziskej_info(s_t)
                ok, msg = proved_prodej(s_t, s_k, s_c, USER, m)
                if ok: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)
        with t3:
            col1, col2, col3 = st.columns(3)
            with col1: am = st.number_input("Částka", 0.0)
            with col2: fr = st.selectbox("Z", ["USD", "CZK", "EUR"])
            with col3: to = st.selectbox("Do", ["CZK", "USD", "EUR"])
            if st.button("SMĚNIT", use_container_width=True):
                if zustatky.get(fr, 0) >= am:
                    proved_smenu(am, fr, to, USER); st.success("Hotovo"); time.sleep(1); st.rerun()
                else: st.error("Chybí prostředky")
        with t4:
            c1, c2 = st.columns(2)
            with c1:
                v_a = st.number_input("Vklad/Výběr", 0.0)
                v_m = st.selectbox("Měna", ["USD", "CZK", "EUR"], key="vm")
                if st.button("VLOŽIT"): pohyb_penez(v_a, v_m, "Vklad", "Man", USER); st.rerun()
                if st.button("VYBRAT"): pohyb_penez(-v_a, v_m, "Výběr", "Man", USER); st.rerun()
            with c2:
                st.dataframe(df_cash.sort_values('Datum', ascending=False).head(10), use_container_width=True, hide_index=True)

    elif page == "📈 Analýza":
        st.title("📈 HLOUBKOVÁ ANALÝZA")
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA & SEKTORY", "🔮 VĚŠTEC", "🏆 BENCHMARK", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE"])
        
        with tab1:
            st.write("")
            vybrana_akcie = st.selectbox("Vyber firmu:", df['Ticker'].unique() if not df.empty else [])
            if vybrana_akcie:
                with st.spinner(f"Načítám data pro {vybrana_akcie}..."):
                    t_info, hist_data = ziskej_detail_akcie(vybrana_akcie)
                    if t_info or (hist_data is not None and not hist_data.empty):
                        try:
                            long_name = t_info.get('longName', vybrana_akcie) if t_info else vybrana_akcie
                            summary = t_info.get('longBusinessSummary', '') if t_info else ''
                            recommendation = t_info.get('recommendationKey', 'N/A').upper().replace('_', ' ') if t_info else 'N/A'
                            target_price = t_info.get('targetMeanPrice', 0) if t_info else 0
                            pe_ratio = t_info.get('trailingPE', 0) if t_info else 0
                            currency = t_info.get('currency', '?') if t_info else '?'
                            current_price = t_info.get('currentPrice', 0) if t_info else 0

                            if (not summary or summary == "MISSING_SUMMARY" or "Yahoo" in summary) and AI_AVAILABLE:
                                try:
                                    prompt_desc = f"Napíš krátký popis (max 2 věty) pro firmu {vybrana_akcie} v češtině. Jde o investiční aplikaci."
                                    res_desc = AI_MODEL.generate_content(prompt_desc)
                                    summary = f"🤖 AI Shrnutí: {res_desc.text}"
                                except: summary = "Popis není k dispozici."
                            elif not summary or "Yahoo" in summary: summary = "Popis není k dispozici."

                            c_d1, c_d2 = st.columns([1, 3])
                            with c_d1:
                                if recommendation != "N/A":
                                    barva_rec = "green" if "BUY" in recommendation else ("red" if "SELL" in recommendation else "orange")
                                    st.markdown(f"### :{barva_rec}[{recommendation}]")
                                    st.caption("Názor analytiků")
                                else:
                                    st.markdown("### 🤷‍♂️ Neznámé"); st.caption("Bez doporučení")
                                
                                if target_price > 0: st.metric("Cílová cena", f"{target_price} {currency}")
                                else: st.metric("Cílová cena", "---")
                                
                                if pe_ratio > 0: st.metric("P/E Ratio", f"{pe_ratio:.2f}")
                                else: st.metric("P/E Ratio", "---")
                                    
                            with c_d2:
                                col_h1, col_h2 = st.columns([3, 1])
                                with col_h1: st.subheader(long_name)
                                with col_h2: 
                                    if current_price > 0: st.metric("Cena", f"{current_price:,.2f} {currency}")
                                st.info(summary)
                                if t_info and t_info.get('website'): st.link_button("🌍 Web firmy", t_info.get('website'))
                                else: st.link_button("🔍 Hledat na Google", f"https://www.google.com/search?q={vybrana_akcie}+stock")
                            
                            st.subheader(f"📈 Cenový vývoj: {vybrana_akcie}")
                            if hist_data is not None and not hist_data.empty:
                                # Bollinger Bands Calculation
                                hist_data['BB_Middle'] = hist_data['Close'].rolling(window=20).mean()
                                hist_data['BB_Std'] = hist_data['Close'].rolling(window=20).std()
                                hist_data['BB_Upper'] = hist_data['BB_Middle'] + (hist_data['BB_Std'] * 2)
                                hist_data['BB_Lower'] = hist_data['BB_Middle'] - (hist_data['BB_Std'] * 2)

                                delta = hist_data['Close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                                rs = gain / loss
                                hist_data['RSI'] = 100 - (100 / (1 + rs))
                                
                                fig_candle = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                                fig_candle.add_trace(go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], name=vybrana_akcie), row=1, col=1)

                                # Bollinger Bands Traces
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['BB_Upper'], mode='lines', name='BB Upper', line=dict(color='gray', width=1)), row=1, col=1)
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['BB_Lower'], mode='lines', name='BB Lower', line=dict(color='gray', width=1), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.1)'), row=1, col=1)

                                hist_data['SMA20'] = hist_data['Close'].rolling(window=20).mean()
                                hist_data['SMA50'] = hist_data['Close'].rolling(window=50).mean()
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['SMA20'], mode='lines', name='SMA 20 (Trend)', line=dict(color='orange', width=1.5)), row=1, col=1)
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['SMA50'], mode='lines', name='SMA 50 (Dlouhý)', line=dict(color='cyan', width=1.5)), row=1, col=1)
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['RSI'], mode='lines', name='RSI', line=dict(color='#A56CC1', width=2)), row=2, col=1)
                                fig_candle.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1, annotation_text="Překoupené (70)", annotation_position="top right")
                                fig_candle.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1, annotation_text="Přeprodané (30)", annotation_position="bottom right")
                                fig_candle.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=600, margin=dict(l=0, r=0, t=30, b=0), legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0)"))
                                fig_candle.update_yaxes(title_text="Cena", row=1, col=1); fig_candle.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
                                st.plotly_chart(fig_candle, use_container_width=True)
                            else: st.warning("Graf historie není k dispozici.")
                        except Exception as e: st.error(f"Chyba zobrazení rentgenu: {e}")
                    else: st.error("Nepodařilo se načíst data o firmě.")

        with tab2:
            st.subheader("⚔️ SOUBOJ AKCIÍ")
            c_f1, c_f2 = st.columns(2)
            with c_f1: t1 = st.text_input("Bojovník 1", "AAPL").upper()
            with c_f2: t2 = st.text_input("Bojovník 2", "MSFT").upper()
            if st.button("SROVNAT", type="primary"):
                if t1 and t2:
                    with st.spinner("Probíhá analýza..."):
                        i1, h1 = ziskej_detail_akcie(t1); i2, h2 = ziskej_detail_akcie(t2)
                        if i1 and i2:
                            mc1 = i1.get('marketCap', 0); mc2 = i2.get('marketCap', 0)
                            pe1 = i1.get('trailingPE', 0); pe2 = i2.get('trailingPE', 0)
                            dy1 = i1.get('dividendYield', 0); dy2 = i2.get('dividendYield', 0)
                            perf1 = ((h1['Close'].iloc[-1] / h1['Close'].iloc[0]) - 1) * 100 if not h1.empty else 0
                            perf2 = ((h2['Close'].iloc[-1] / h2['Close'].iloc[0]) - 1) * 100 if not h2.empty else 0
                            
                            cc1, cc2, cc3, cc4 = st.columns(4)
                            cc1.metric(f"Kapitalizace {t1}", f"${mc1/1e9:.1f}B", delta_color="normal")
                            cc1.metric(f"Kapitalizace {t2}", f"${mc2/1e9:.1f}B", delta=f"{(mc2-mc1)/1e9:.1f}B")
                            comp_data = {
                                "Metrika": ["Cena", "P/E Ratio", "Dividenda", "Změna 1R"],
                                t1: [f"{i1.get('currentPrice')} {i1.get('currency')}", f"{pe1:.2f}", f"{dy1*100:.2f}%" if dy1 else "0%", f"{perf1:+.2f}%"],
                                t2: [f"{i2.get('currentPrice')} {i2.get('currency')}", f"{pe2:.2f}", f"{dy2*100:.2f}%" if dy2 else "0%", f"{perf2:+.2f}%"]
                            }
                            st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)
                            if not h1.empty and not h2.empty:
                                h1['Norm'] = (h1['Close'] / h1['Close'].iloc[0] - 1) * 100
                                h2['Norm'] = (h2['Close'] / h2['Close'].iloc[0] - 1) * 100
                                st.line_chart(pd.concat([h1['Norm'].rename(t1), h2['Norm'].rename(t2)], axis=1))
                        else: st.error("Chyba načítání dat.")

        with tab3:
            if not vdf.empty:
                st.subheader("🌍 MAPA IMPÉRIA")
                try:
                    df_map = vdf.groupby('Země')['HodnotaUSD'].sum().reset_index()
                    fig_map = px.scatter_geo(df_map, locations="Země", locationmode="country names", hover_name="Země", size="HodnotaUSD", projection="orthographic", color="Země", template="plotly_dark")
                    fig_map.update_geos(bgcolor="#161B22", showcountries=True, countrycolor="#30363D", showocean=True, oceancolor="#0E1117", showland=True, landcolor="#1c2128")
                    fig_map.update_layout(paper_bgcolor="#161B22", font={"color": "white"}, height=500, margin={"r":0,"t":0,"l":0,"b":0})
                    st.plotly_chart(fig_map, use_container_width=True)
                except Exception as e: st.error(f"Chyba mapy: {e}")
                st.divider()
                st.caption("MAPA TRHU (Sektory)")
                try:
                    fig = px.treemap(vdf, path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'], values='HodnotaUSD', color='Zisk', color_continuous_scale=['red', '#161B22', 'green'], color_continuous_midpoint=0)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception: st.error("Chyba mapy.")
            else: st.info("Portfolio je prázdné.")

        with tab4:
            st.subheader("🔮 FINANČNÍ STROJ ČASU"); 
            with st.container(border=True):
                col_v1, col_v2 = st.columns([1, 2])
                with col_v1:
                    vklad = st.number_input("Měsíční vklad (Kč)", value=5000, step=500)
                    roky = st.slider("Počet let", 5, 40, 15)
                    urok = st.slider("Očekávaný úrok p.a. (%)", 1.0, 15.0, 8.0)
                with col_v2:
                    data_budoucnost = []; aktualni_hodnota = celk_hod_czk; vlozeno = celk_hod_czk
                    for r in range(1, roky + 1):
                        rocni_vklad = vklad * 12; vlozeno += rocni_vklad
                        aktualni_hodnota = (aktualni_hodnota + rocni_vklad) * (1 + urok/100)
                        data_budoucnost.append({"Rok": datetime.now().year + r, "Hodnota": round(aktualni_hodnota), "Vklady": round(vlozeno)})
                    st.area_chart(pd.DataFrame(data_budoucnost).set_index("Rok"), color=["#00FF00", "#333333"])
                    st.metric(f"Hodnota v roce {datetime.now().year + roky}", f"{aktualni_hodnota:,.0f} Kč", f"Zisk: {aktualni_hodnota - vlozeno:,.0f} Kč")
            
            st.divider()
            st.subheader("🎲 MONTE CARLO: Simulace budoucnosti")
            st.info("Simulace 50 možných scénářů vývoje tvého portfolia na základě volatility trhu.")
            c_mc1, c_mc2 = st.columns(2)
            with c_mc1:
                mc_years = st.slider("Délka simulace (roky)", 1, 20, 5, key="mc_years")
                mc_volatility = st.slider("Očekávaná volatilita (%)", 5, 50, 20, key="mc_vol") / 100
            with c_mc2:
                mc_return = st.slider("Očekávaný výnos p.a. (%)", -5, 20, 8, key="mc_ret") / 100
                start_val = celk_hod_czk if celk_hod_czk > 0 else 100000 
            if st.button("🔮 SPUSTIT SIMULACI", type="primary"):
                days = mc_years * 252; dt = 1/252; mu = mc_return; sigma = mc_volatility; num_simulations = 50
                sim_data = pd.DataFrame()
                for i in range(num_simulations):
                    price_path = [start_val]
                    for _ in range(days):
                        shock = np.random.normal(0, 1)
                        price = price_path[-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shock)
                        price_path.append(price)
                    sim_data[f"Sim {i}"] = price_path
                fig_mc = go.Figure()
                for col in sim_data.columns: fig_mc.add_trace(go.Scatter(y=sim_data[col], mode='lines', line=dict(width=1), opacity=0.3, showlegend=False))
                sim_data['Average'] = sim_data.mean(axis=1)
                fig_mc.add_trace(go.Scatter(y=sim_data['Average'], mode='lines', name='Průměrný scénář', line=dict(color='yellow', width=4)))
                fig_mc.update_layout(title=f"Monte Carlo: {num_simulations} scénářů na {mc_years} let", xaxis_title="Dny", yaxis_title="Hodnota (CZK)", template="plotly_dark")
                st.plotly_chart(fig_mc, use_container_width=True)
                st.success(f"Průměrná hodnota na konci: {sim_data['Average'].iloc[-1]:,.0f} Kč")

            st.divider()
            st.subheader("💥 CRASH TEST")
            with st.container(border=True):
                propad = st.slider("Simulace pádu trhu (%)", 5, 80, 20, step=5)
                ztrata_czk = (celk_hod_usd * (propad / 100)) * kurzy["CZK"]
                zbytek_czk = (celk_hod_usd * (1 - propad / 100)) * kurzy["CZK"]
                c_cr1, c_cr2 = st.columns(2)
                with c_cr1: st.error(f"📉 ZTRÁTA: -{ztrata_czk:,.0f} Kč"); st.warning(f"💰 ZBYDE TI: {zbytek_czk:,.0f} Kč")
                with c_cr2: st.progress(1.0 - (propad / 100))

        with tab5:
            st.subheader("🏆 SROVNÁNÍ S TRHEM (S&P 500) & SHARPE RATIO")
            if not hist_vyvoje.empty and len(hist_vyvoje) > 1:
                user_df = hist_vyvoje.copy()
                user_df['Date'] = pd.to_datetime(user_df['Date']); user_df = user_df.sort_values('Date').set_index('Date')
                start_val = user_df['TotalUSD'].iloc[0]
                if start_val > 0: user_df['MyReturn'] = ((user_df['TotalUSD'] / start_val) - 1) * 100
                else: user_df['MyReturn'] = 0
                start_date = user_df.index[0].strftime('%Y-%m-%d')
                
                # --- VÝPOČET SHARPE RATIO ---
                my_returns = user_df['TotalUSD'].pct_change().dropna()
                my_sharpe = calculate_sharpe_ratio(my_returns)
                # -------------------------------
                
                try:
                    sp500 = yf.download("^GSPC", start=start_date, progress=False)
                    if not sp500.empty:
                        if isinstance(sp500.columns, pd.MultiIndex): close_col = sp500['Close'].iloc[:, 0]
                        else: close_col = sp500['Close']
                        sp500_start = close_col.iloc[0]
                        sp500_norm = ((close_col / sp500_start) - 1) * 100
                        
                        # --- VÝPOČET SHARPE RATIO pro S&P 500 ---
                        sp500_returns = close_col.pct_change().dropna()
                        sp500_sharpe = calculate_sharpe_ratio(sp500_returns)
                        # ------------------------------------------
                        
                        fig_bench = go.Figure()
                        fig_bench.add_trace(go.Scatter(x=user_df.index, y=user_df['MyReturn'], mode='lines', name='Moje Portfolio', line=dict(color='#00CC96', width=3)))
                        fig_bench.add_trace(go.Scatter(x=sp500_norm.index, y=sp500_norm, mode='lines', name='S&P 500', line=dict(color='#808080', width=2, dash='dot')))
                        fig_bench.update_layout(title="Výkonnost v % od začátku měření", xaxis_title="", yaxis_title="Změna (%)", template="plotly_dark", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
                        st.plotly_chart(fig_bench, use_container_width=True)
                        
                        my_last = user_df['MyReturn'].iloc[-1]; sp_last = sp500_norm.iloc[-1]; diff = my_last - sp_last
                        c_b1, c_b2, c_b3, c_b4 = st.columns(4)
                        
                        # Metriky výnosu
                        c_b1.metric("Můj výnos", f"{my_last:+.2f} %")
                        c_b2.metric("S&P 500 výnos", f"{sp_last:+.2f} %")
                        c_b3.metric("Můj Sharpe", f"{my_sharpe:+.2f}", help="Měří výnos na jednotku rizika.")
                        c_b4.metric("S&P 500 Sharpe", f"{sp500_sharpe:+.2f}", help="Měří výnos na jednotku rizika indexu.")

                        if diff > 0: st.success("🎉 Gratuluji! Porážíš trh na výnosu.")
                        else: st.warning("📉 Trh zatím vede na výnosu. Zvaž indexové ETF.")
                        
                        st.divider()
                        if my_sharpe > sp500_sharpe and my_sharpe > 0:
                            st.markdown("✅ **Analýza rizika (Sharpe):** Tvé portfolio dosahuje lepších výnosů v poměru k podstoupenému riziku než S&P 500. Skvělá práce s rizikem!")
                        elif my_sharpe < sp500_sharpe and my_sharpe > 0:
                            st.markdown("⚠️ **Analýza rizika (Sharpe):** S&P 500 dosahuje vyššího výnosu na jednotku rizika. Zkus zvážit diverzifikaci pro snížení volatility.")
                        else:
                            st.markdown("ℹ️ **Analýza rizika (Sharpe):** Pro smysluplné Sharpe Ratio potřebujeme více dat nebo kladné výnosy.")


                    else: st.warning("Nepodařilo se stáhnout data S&P 500.")
                except Exception as e: st.error(f"Chyba benchmarku: {e}")
            else: st.info("Pro srovnání potřebuješ historii alespoň za 2 dny.")
        
        with tab6:
            st.subheader("💱 MĚNOVÝ SIMULÁTOR")
            st.info("Jak změna kurzu koruny ovlivní hodnotu tvého portfolia?")
            assets_by_curr = {"USD": 0, "EUR": 0, "CZK": 0}
            if viz_data:
                for item in viz_data:
                    curr = item['Měna']; val = item['Hodnota']
                    if curr in assets_by_curr: assets_by_curr[curr] += val
                    else: assets_by_curr["USD"] += item['HodnotaUSD'] # Pokud se mena neurci spravne, je v USD
            kurz_usd_now = kurzy.get("CZK", 20.85); kurz_eur_now = kurzy.get("EUR", 1.16) * kurz_usd_now
            col_s1, col_s2 = st.columns(2)
            with col_s1: sim_usd = st.slider(f"Kurz USD/CZK (Aktuálně: {kurz_usd_now:.2f})", 15.0, 30.0, float(kurz_usd_now))
            with col_s2: sim_eur = st.slider(f"Kurz EUR/CZK (Aktuálně: {kurz_eur_now:.2f})", 15.0, 35.0, float(kurz_eur_now))
            val_now_czk = (assets_by_curr["USD"] * kurz_usd_now) + (assets_by_curr["EUR"] * kurz_eur_now) + assets_by_curr["CZK"]
            val_sim_czk = (assets_by_curr["USD"] * sim_usd) + (assets_by_curr["EUR"] * sim_eur) + assets_by_curr["CZK"]
            diff = val_sim_czk - val_now_czk
            st.divider()
            c_m1, c_m2 = st.columns(2)
            c_m1.metric("Hodnota Portfolia (Simulace)", f"{val_sim_czk:,.0f} Kč", delta=f"{diff:,.0f} Kč")
            impact_data = pd.DataFrame({
                "Měna": ["USD Aktiva", "EUR Aktiva", "CZK Aktiva"],
                "Hodnota CZK (Teď)": [assets_by_curr["USD"] * kurz_usd_now, assets_by_curr["EUR"] * kurz_eur_now, assets_by_curr["CZK"]],
                "Hodnota CZK (Simulace)": [assets_by_curr["USD"] * sim_usd, assets_by_curr["EUR"] * sim_eur, assets_by_curr["CZK"]]
            })
            fig_curr = go.Figure(data=[
                go.Bar(name='Teď', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Teď)"], marker_color='#555555'),
                go.Bar(name='Simulace', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Simulace)"], marker_color='#00CC96')
            ])
            fig_curr.update_layout(barmode='group', template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_curr, use_container_width=True)
            if diff < 0: st.warning(f"📉 Pokud koruna posílí, přijdeš o {abs(diff):,.0f} Kč jen na kurzu!")
            elif diff > 0: st.success(f"📈 Pokud koruna oslabí, vyděláš {diff:,.0f} Kč navíc.")
        
        with tab7:
            st.subheader("⚖️ REBALANČNÍ KALKULAČKA")
            if not vdf.empty:
                df_reb = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
                total_val = df_reb['HodnotaUSD'].sum()
                st.write("Nastav cílové váhy pro sektory:")
                targets = {}; cols = st.columns(3)
                for i, row in df_reb.iterrows():
                    current_pct = (row['HodnotaUSD'] / total_val) * 100
                    with cols[i % 3]:
                        targets[row['Sektor']] = st.number_input(f"{row['Sektor']} (%)", min_value=0.0, max_value=100.0, value=float(round(current_pct, 1)), step=1.0, key=f"reb_{row['Sektor']}")
                total_target = sum(targets.values())
                if abs(total_target - 100) > 0.1: st.warning(f"⚠️ Součet cílů je {total_target:.1f}%. Měl by být 100%.")
                df_reb['Cíl %'] = df_reb['Sektor'].map(targets)
                df_reb['Cílová Hodnota'] = total_val * (df_reb['Cíl %'] / 100)
                df_reb['Rozdíl'] = df_reb['Cílová Hodnota'] - df_reb['HodnotaUSD']
                st.divider(); st.subheader("🛠️ Návrh akcí")
                for _, r in df_reb.iterrows():
                    diff = r['Rozdíl']
                    if abs(diff) > 1:
                        if diff > 0: st.success(f"🟢 **{r['Sektor']}**: DOKOUPIT za {diff:,.0f} USD")
                        else: st.error(f"🔴 **{r['Sektor']}**: PRODAT za {abs(diff):,.0f} USD")
                st.dataframe(df_reb.style.format({"HodnotaUSD": "{:,.0f}", "Cílová Hodnota": "{:,.0f}", "Rozdíl": "{:+,.0f}"}))
            else: st.info("Portfolio je prázdné.")
        
        with tab8:
            st.subheader("📊 MATICE KORELACE (Diversifikace)")
            st.info("Jak moc se tvé akcie hýbou společně? Čím více 'modrá', tím lepší diverzifikace.")
            if not df.empty:
                tickers_list = df['Ticker'].unique().tolist()
                if len(tickers_list) > 1:
                    try:
                        with st.spinner("Počítám korelace..."):
                            hist_data = yf.download(tickers_list, period="1y")['Close']
                            returns = hist_data.pct_change().dropna()
                            corr_matrix = returns.corr()
                            fig_corr = px.imshow(corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", origin='lower')
                            fig_corr.update_layout(template="plotly_dark", height=600)
                            st.plotly_chart(fig_corr, use_container_width=True)
                            avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix.values, 1)].mean()
                            st.metric("Průměrná korelace portfolia", f"{avg_corr:.2f}")
                            if avg_corr > 0.7: st.error("⚠️ Vysoká korelace! Tvé akcie se hýbou stejně.")
                            elif avg_corr < 0.3: st.success("✅ Nízká korelace! Dobrá diverzifikace.")
                            else: st.warning("⚖️ Střední korelace. Portfolio je vyvážené.")
                    except Exception as e: st.error(f"Chyba při výpočtu korelace: {e}")
                else: st.warning("Pro výpočet korelace potřebuješ alespoň 2 různé akcie.")
            else: st.info("Portfolio je prázdné.")

    elif page == "📰 Zprávy":
        st.title("📰 BURZOVNÍ ZPRAVODAJSTVÍ")
        if AI_AVAILABLE:
            if st.button("🧠 SPUSTIT AI SENTIMENT 2.0", type="primary"):
                with st.spinner("AI analyzuje trh..."):
                    raw_news = ziskej_zpravy()
                    titles = [n['title'] for n in raw_news[:8]]
                    titles_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
                    prompt = f"""Jsi finanční analytik. Analyzuj tyto novinové titulky a urči jejich sentiment.\nTITULKY:\n{titles_str}\nPro každý titulek vrať přesně tento formát na jeden řádek (bez odrážek):\nINDEX|SKÓRE(0-100)|VYSVĚTLENÍ (česky, max 1 věta)"""
                    try:
                        response = AI_MODEL.generate_content(prompt)
                        analysis_map = {}
                        for line in response.text.strip().split('\n'):
                            parts = line.split('|')
                            if len(parts) == 3:
                                try:
                                    idx = int(parts[0].replace('.', '').strip()) - 1; score = int(parts[1].strip()); reason = parts[2].strip()
                                    analysis_map[idx] = {'score': score, 'reason': reason}
                                except: pass
                        st.session_state['ai_news_analysis'] = analysis_map
                        st.session_state['news_timestamp'] = datetime.now()
                        st.success("Analýza dokončena!")
                    except Exception as e: st.error(f"Chyba AI: {e}")
        
        news = ziskej_zpravy()
        ai_results = st.session_state.get('ai_news_analysis', {})
        if news:
            c1, c2 = st.columns(2)
            for i, n in enumerate(news):
                col = c1 if i % 2 == 0 else c2
                with col:
                    with st.container(border=True):
                        if i in ai_results:
                            res = ai_results[i]; score = res['score']; reason = res['reason']
                            if score >= 60: color = "green"; emoji = "🟢 BÝČÍ"
                            elif score <= 40: color = "red"; emoji = "🔴 MEDVĚDÍ"
                            else: color = "orange"; emoji = "🟡 NEUTRÁL"
                            st.markdown(f"#### {n['title']}")
                            st.caption(f"📅 {n['published']}")
                            st.markdown(f"**{emoji} (Skóre: {score}/100)**"); st.progress(score); st.info(f"🤖 {reason}")
                        else:
                            title_upper = n['title'].upper(); sentiment = "neutral"
                            for kw in KW_POSITIVNI:
                                if kw in title_upper: sentiment = "positive"; break
                            if sentiment == "neutral":
                                for kw in KW_NEGATIVNI:
                                    if kw in title_upper: sentiment = "negative"; break
                            if sentiment == "positive": st.success(f"🟢 **BÝČÍ ZPRÁVA**")
                            elif sentiment == "negative": st.error(f"🔴 **MEDVĚDÍ SIGNÁL**")
                            st.markdown(f"### {n['title']}"); st.caption(f"📅 {n['published']}")
                        st.link_button("Číst článek", n['link'])
        else: st.info("Žádné nové zprávy.")

    elif page == "💎 Dividendy":
        st.title("💎 DIVIDENDY")
        if not df_div.empty:
            df_div['Datum'] = pd.to_datetime(df_div['Datum']); df_div['Mesic'] = df_div['Datum'].dt.strftime('%Y-%m')
            # Správný přepočet na CZK s ohledem na aktuální kurzy
            df_div['CastkaCZK'] = df_div.apply(lambda r: r['Castka'] * (kurzy.get('CZK', 20.85) if r['Mena'] == 'USD' else (kurzy.get('CZK', 20.85) / kurzy.get('EUR', 1.16) if r['Mena'] == 'EUR' else 1)), axis=1)
            monthly_data = df_div.groupby('Mesic')['CastkaCZK'].sum()
            with st.container(border=True):
                k1, k2 = st.columns([2, 1])
                with k1: st.subheader("📅 Pasivní příjem (CZK)"); st.bar_chart(monthly_data, color="#00FF00")
                with k2: st.metric("CELKEM VYPLACENO", f"{df_div['CastkaCZK'].sum():,.0f} Kč"); st.write("Poslední 3 měsíce:"); st.dataframe(monthly_data.sort_index(ascending=False).head(3), use_container_width=True)
            st.divider()
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.form("div"):
                t = st.text_input("Ticker").upper(); a = st.number_input("Částka", 0.01); c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                if st.form_submit_button("PŘIPSAT"): pridat_dividendu(t, a, c, USER); st.toast("Připsáno", icon="💎"); st.balloons(); time.sleep(2); st.rerun()
        with c2:
            if not df_div.empty: st.dataframe(df_div[["Datum", "Ticker", "Castka", "Mena", "CastkaCZK"]].sort_values("Datum", ascending=False).style.format({"Castka": "{:,.2f}", "CastkaCZK": "{:,.0f} Kč", "Datum": "{:%d.%m.%Y}"}), use_container_width=True, hide_index=True)

    elif page == "⚙️ Nastavení":
        st.title("⚙️ DATA & SPRÁVA")
        st.info("Zde můžeš editovat data natvrdo.")
        t1, t2 = st.tabs(["PORTFOLIO", "HISTORIE"])
        with t1:
            new_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Portfolio"): st.session_state['df'] = new_df; uloz_data_uzivatele(new_df, USER, SOUBOR_DATA); st.success("Uloženo")
        with t2:
            new_h = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Historii"): st.session_state['df_hist'] = new_h; uloz_data_uzivatele(new_h, USER, SOUBOR_HISTORIE); st.success("Uloženo")
        st.divider(); st.subheader("📦 ZÁLOHA")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for n, d in [(SOUBOR_DATA, 'df'), (SOUBOR_HISTORIE, 'df_hist'), (SOUBOR_CASH, 'df_cash'), (SOUBOR_DIVIDENDY, 'df_div'), (SOUBOR_WATCHLIST, 'df_watch')]:
                if d in st.session_state: zf.writestr(n, st.session_state[d].to_csv(index=False))
        st.download_button("Stáhnout Data", buf.getvalue(), f"backup_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")

    with st.expander("🤖 AI ASISTENT"):
        st.markdown('<span id="floating-bot-anchor"></span>', unsafe_allow_html=True)
        if "chat_messages" not in st.session_state: st.session_state["chat_messages"] = [{"role": "assistant", "content": "Ahoj! Jsem tvůj AI průvodce. Co pro tebe mohu udělat?"}]
        for msg in st.session_state["chat_messages"]: st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("Zeptej se..."):
            if not AI_AVAILABLE: st.error("Chybí API klíč.")
            else: st.session_state["chat_messages"].append({"role": "user", "content": prompt}); st.rerun()
        if st.session_state["chat_messages"][-1]["role"] == "user":
            with st.spinner("Přemýšlím..."):
                last_user_msg = st.session_state["chat_messages"][-1]["content"]
                portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
                if viz_data: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data])
                full_prompt = f"{APP_MANUAL}\n\nDATA:\n{portfolio_context}\n\nDOTAZ: {last_user_msg}"
                try: response = AI_MODEL.generate_content(full_prompt); ai_reply = response.text
                except Exception as e: ai_reply = f"Chyba: {str(e)}"
                st.session_state["chat_messages"].append({"role": "assistant", "content": ai_reply}); st.rerun()

if __name__ == "__main__":
    main()

