import streamlit as st
import pandas as pd
import numpy as np
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
import pytz # Přidáno pro časová pásma

# --- KONFIGURACE ---
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
RISK_FREE_RATE = 0.04 

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
6. ⚙️ Správa Dat': Zálohy a editace.
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

# --- STYLY (ULTIMATE VISUAL UPGRADE - ANIMATED) ---
st.markdown("""
<style>
    /* 1. ANIMOVANÉ POZADÍ (Breathing Gradient) */
    @keyframes gradient {
        0% {background-position: 0% 50%;}
        50% {background-position: 100% 50%;}
        100% {background-position: 0% 50%;}
    }
    .stApp {
        background: linear-gradient(-45deg, #05070a, #0E1117, #161b22, #0d1117);
        background-size: 400% 400%;
        animation: gradient 20s ease infinite;
        font-family: 'Roboto Mono', monospace;
    }

    /* 2. CRT SCANLINE EFEKT (Retro-Futuristic Overlay) */
    .stApp::before {
        content: " ";
        display: block;
        position: absolute;
        top: 0;
        left: 0;
        bottom: 0;
        right: 0;
        background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.1) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.03), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.03));
        z-index: 2;
        background-size: 100% 2px, 3px 100%;
        pointer-events: none;
    }

    /* 3. Vylepšený Scrollbar */
    ::-webkit-scrollbar {width: 8px; height: 8px; background: #0E1117;}
    ::-webkit-scrollbar-thumb {background: #30363D; border-radius: 4px;}
    ::-webkit-scrollbar-thumb:hover {background: #58A6FF; box-shadow: 0 0 10px #58A6FF;}

    /* 4. PULZUJÍCÍ METRIKY */
    @keyframes pulse-border {
        0% { border-color: #30363D; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        50% { border-color: #58A6FF; box-shadow: 0 0 15px rgba(88, 166, 255, 0.15); }
        100% { border-color: #30363D; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    }
    div[data-testid="stMetric"] {
        background-color: rgba(22, 27, 34, 0.8); /* Průhlednost pro efekt pozadí */
        backdrop-filter: blur(5px);
        border: 1px solid #30363D; 
        padding: 15px; 
        border-radius: 8px; 
        color: #E6EDF3;
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px) scale(1.02);
        animation: pulse-border 2s infinite;
        z-index: 10;
    }
    div[data-testid="stMetricLabel"] {font-size: 0.85rem; color: #8B949E; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;}
    div[data-testid="stMetricValue"] {font-size: 1.6rem; color: #E6EDF3; font-weight: bold; text-shadow: 0 0 10px rgba(230, 237, 243, 0.3);}
    
    /* Nadpisy s Glitch efektem (pouze statický styl pro čistotu) */
    h1, h2, h3 {
        color: #E6EDF3 !important; 
        font-family: 'Roboto Mono', monospace; 
        text-transform: uppercase; 
        letter-spacing: 2px;
        text-shadow: 2px 2px 0px rgba(0,0,0,0.5);
    }
    
    /* Tlačítka - Neon Style */
    div[data-testid="column"] button {
        border: 1px solid #30363D; 
        background-color: #21262D; 
        color: #C9D1D9;
        border-radius: 6px;
        min-height: 45px;
        transition: all 0.3s;
        position: relative;
        overflow: hidden;
    }
    div[data-testid="column"] button:hover {
        border-color: #58A6FF;
        color: #58A6FF;
        box-shadow: 0 0 15px rgba(88, 166, 255, 0.4);
        text-shadow: 0 0 5px rgba(88, 166, 255, 0.8);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {gap: 8px; background-color: transparent; padding-bottom: 5px; flex-wrap: wrap;}
    .stTabs [data-baseweb="tab"] {
        height: 45px; white-space: pre-wrap; background-color: #0d1117; border: 1px solid #30363D; 
        border-radius: 6px; color: #8B949E; font-family: 'Roboto Mono', monospace; font-size: 0.9rem; 
        transition: all 0.2s ease; padding: 0px 20px; margin-bottom: 5px;
    }
    .stTabs [data-baseweb="tab"]:hover {border-color: #58A6FF; color: #58A6FF; background-color: #161B22;}
    .stTabs [aria-selected="true"] {
        background-color: #238636 !important; border-color: #2ea043 !important; color: white !important; 
        font-weight: bold; box-shadow: 0 0 15px rgba(35, 134, 54, 0.5); 
    }
    
    a {text-decoration: none; color: #58A6FF !important; transition: color 0.3s;} 
    a:hover {color: #79c0ff !important; text-shadow: 0 0 5px #79c0ff;}

    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #238636, #2ea043);
        box-shadow: 0 0 10px rgba(35, 134, 54, 0.5);
    }
    
    /* Bot Floating Window - Hover Levitation */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary {
        background-color: transparent !important; color: transparent !important;
        height: 70px !important; width: 70px !important; border-radius: 50% !important;
        padding: 0 !important; margin-left: auto !important;
        background-image: url('https://i.postimg.cc/cK5DmzZv/1000001805.jpg'); 
        background-size: cover; background-position: center;
        border: 3px solid #238636 !important;
        box-shadow: 0 0 15px rgba(35, 134, 54, 0.5);
        animation: float 6s ease-in-out infinite;
        transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55), box-shadow 0.3s;
    }
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary:hover {
        transform: scale(1.1) rotate(10deg);
        box-shadow: 0 0 30px rgba(35, 134, 54, 0.9);
        cursor: pointer;
    }
    /* Zbytek bota... */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) {position: fixed !important; bottom: 20px !important; right: 20px !important; width: 380px !important; max-width: 85vw !important; z-index: 99999 !important; background-color: transparent !important; border: none !important; box-shadow: none !important;}
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details {border-radius: 20px !important; background-color: #161B22 !important; border: 1px solid #30363D !important; box-shadow: 0 10px 30px rgba(0,0,0,0.8) !important;}
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary svg {display: none !important;}
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary {width: 100% !important; height: 40px !important; border-radius: 15px 15px 0 0 !important; background-image: none !important; background-color: #238636 !important; color: white !important; display: flex; align-items: center; justify-content: center; animation: none !important; border: none !important; margin: 0 !important;}
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary::after {content: "❌ ZAVŘÍT CHAT"; font-weight: bold; font-size: 0.9rem; color: white;}
    div[data-testid="stExpander"]:has(#floating-bot-anchor) div[data-testid="stExpanderDetails"] {max-height: 400px; overflow-y: auto; background-color: #0d1117; border-bottom-left-radius: 20px; border-bottom-right-radius: 20px; border-top: 1px solid #30363D; padding: 15px;}
    
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
        100% { transform: translateY(0px); }
    }
    @media (max-width: 600px) {
        .ticker-text {font-size: 0.8rem !important;}
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

# --- LOTTIE LOADER ---
@st.cache_data
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200: return None
    return r.json()

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

@st.cache_data(ttl=86400, show_spinner=False, persist="disk")
def _ziskej_info_cached(ticker):
    t = yf.Ticker(str(ticker))
    info = t.info
    
    if not info or len(info) < 5 or "Yahoo API limit" in info.get("longBusinessSummary", ""):
        raise ValueError("Neúplná data z Yahoo API")
    
    required_info = {
        'longName': info.get('longName', ticker),
        'longBusinessSummary': info.get('longBusinessSummary', 'Popis není k dispozici.'),
        'recommendationKey': info.get('recommendationKey', 'N/A'),
        'targetMeanPrice': info.get('targetMeanPrice', 0),
        'trailingPE': info.get('trailingPE', 0),
        'marketCap': info.get('marketCap', 0),
        'currency': info.get('currency', 'USD'),
        'currentPrice': info.get('currentPrice', 0),
        'website': info.get('website', '')
    }
    return required_info

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
    try:
        info = _ziskej_info_cached(ticker)
    except Exception:
        try:
            t = yf.Ticker(str(ticker))
            fi = t.fast_info
            info = {
                "longName": ticker,
                "longBusinessSummary": "MISSING_SUMMARY",
                "recommendationKey": "N/A",
                "targetMeanPrice": 0,
                "trailingPE": fi.trailing_pe,
                "marketCap": fi.market_cap,
                "currency": fi.currency,
                "currentPrice": fi.last_price,
                "website": ""
            }
        except:
            info = {
                "longName": ticker, 
                "currency": "USD", 
                "currentPrice": 0, 
                "longBusinessSummary": "Data nedostupná.",
                "trailingPE": 0,
                "marketCap": 0
            }

    hist = _ziskej_historii_cached(ticker)
    return info, hist

# --- POMOCNÁ FUNKCE PRO TRŽNÍ HODINY ---
def zjisti_stav_trhu(timezone_str, open_hour, close_hour):
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        is_open = False
        # Jednoduchá logika: Pondělí-Pátek (0-4) a čas mezi Open a Close
        if 0 <= now.weekday() <= 4:
            if open_hour <= now.hour < close_hour:
                is_open = True
        return now.strftime("%H:%M"), is_open
    except:
        return "N/A", False

# --- PDF GENERATOR ---
def clean_text(text):
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
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "SOUHRN", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, clean_text(f"Celkove jmeni: {total_czk:,.0f} CZK"), ln=True)
    pdf.cell(0, 10, clean_text(f"Hotovost: {cash_usd:,.0f} USD"), ln=True)
    pdf.cell(0, 10, clean_text(f"Celkovy zisk/ztrata: {profit_czk:,.0f} CZK"), ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(30, 10, "Ticker", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Kusy", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Cena (Avg)", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Hodnota (USD)", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Zisk (USD)", 1, 1, 'C', 1)
    
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
        
        for col in ['Datum', 'Date']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        for col in ['Pocet', 'Cena', 'Castka', 'Kusu', 'Prodejka', 'Zisk', 'TotalUSD', 'Investice', 'Target', 'TargetBuy', 'TargetSell']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        if nazev_souboru == SOUBOR_WATCHLIST:
             if 'Target' in df.columns and 'TargetBuy' not in df.columns:
                 df['TargetBuy'] = df['Target']
             
             if 'TargetBuy' not in df.columns: df['TargetBuy'] = 0.0
             if 'TargetSell' not in df.columns: df['TargetSell'] = 0.0
             
             if 'Target' in df.columns: df = df.drop(columns=['Target'])
             cols = ["Ticker", "TargetBuy", "TargetSell", "Owner"]
        
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

def pridat_do_watchlistu(ticker, target_buy, target_sell, user):
    df_w = st.session_state['df_watch']
    if ticker not in df_w['Ticker'].values:
        new = pd.DataFrame([{"Ticker": ticker, "TargetBuy": float(target_buy), "TargetSell": float(target_sell), "Owner": user}])
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

# --- NOVÁ FUNKCE: PROVEDENÍ NÁKUPU (Refactoring pro CLI) ---
def proved_nakup(ticker, kusy, cena, user):
    df_p = st.session_state['df']
    _, mena, _ = ziskej_info(ticker)
    cost = kusy * cena
    zustatky = get_zustatky(user)
    
    if zustatky.get(mena, 0) >= cost:
        pohyb_penez(-cost, mena, "Nákup", ticker, user)
        d = pd.DataFrame([{"Ticker": ticker, "Pocet": kusy, "Cena": cena, "Datum": datetime.now(), "Owner": user, "Sektor": "Doplnit", "Poznamka": "CLI/Auto"}])
        st.session_state['df'] = pd.concat([df_p, d], ignore_index=True)
        uloz_data_uzivatele(st.session_state['df'], user, SOUBOR_DATA)
        return True, f"✅ Koupeno: {kusy}x {ticker} za {cena} {mena}"
    else:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {zustatky.get(mena, 0):,.2f})"

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
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy.get("CZK", 20.85)
    elif z_meny == "EUR": castka_usd = castka * kurzy.get("EUR", 1.16) 
    
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
    if returns.empty or returns.std() == 0:
        return 0.0
    daily_risk_free_rate = risk_free_rate / periods_per_year
    excess_returns = returns - daily_risk_free_rate
    sharpe_ratio = np.sqrt(periods_per_year) * (excess_returns.mean() / returns.std())
    return sharpe_ratio

# --- POMOCNÁ FUNKCE PRO STÁHNUTÍ GRAFU (PYTHON VERZE - ROBUSTNÍ) ---
# Nahraď původní funkci add_download_button touto novou verzí.
# Vyžaduje instalaci knihovny: pip install kaleido

def add_download_button(fig, filename):
    # Tlačítko se pokusíme vygenerovat, ale pokud chybí systémové knihovny (což je časté na cloudu),
    # zobrazíme jen návod na alternativní stažení, abychom uživatele neděsili chybou.
    try:
        import io
        buffer = io.BytesIO()
        # Pokus o renderování
        fig.write_image(buffer, format="png", width=1200, height=800, scale=2)
        
        st.download_button(
            label=f"⬇️ Stáhnout graf: {filename}",
            data=buffer.getvalue(),
            file_name=f"{filename}.png",
            mime="image/png",
            use_container_width=True
        )
    except Exception:
        # Tichý fallback - pokud to nejde, zobrazíme jen jemný tip místo chyby
        st.caption("💡 Tip: Pro stažení obrázku použij ikonu fotoaparátu 📷, která se objeví v pravém horním rohu grafu po najetí myší.")


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
    if 'chat_expanded' not in st.session_state:
        st.session_state['chat_expanded'] = False
        
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
                        df_u = nacti_uzivatele(); row = df_u[df_u['username'] == u]
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
                        df_u = nacti_uzivatele(); row = df_u[df_u['username'] == ru]
                        if not row.empty and row.iloc[0]['password'] == zasifruj(rk):
                            df_u.at[row.index[0], 'password'] = zasifruj(rnp); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}")
                            st.success("Heslo změněno!")
                        else: st.error("Chyba údajů.")
        return

    # =========================================================================
    # ZDE ZAČÍNÁ APLIKACE PRO PŘIHLÁŠENÉHO UŽIVATELE
    # =========================================================================
    
    USER = st.session_state['user']
    
    # --- BOOT SEQUENCE (POUZE JEDNOU) ---
    if 'boot_completed' not in st.session_state:
        st.session_state['boot_completed'] = False

    if not st.session_state['boot_completed']:
        boot_placeholder = st.empty()
        with boot_placeholder.container():
            st.markdown("""<style>.stApp {background-color: black !important;}</style>""", unsafe_allow_html=True)
            st.markdown("## 🖥️ TERMINAL PRO v4.0", unsafe_allow_html=True)
            
            steps = [
                "Initializing secure connection...",
                "Loading neural network weights...",
                "Accessing global market data...",
                "Decrypting user wallet...",
                "Bypassing firewalls...",
                "ACCESS GRANTED"
            ]
            
            bar = st.progress(0)
            status_text = st.empty()
            
            for i, step in enumerate(steps):
                status_text.markdown(f"```bash\n> {step}\n```")
                bar.progress((i + 1) * (100 // len(steps)))
                time.sleep(0.3) # Rychlost bootování
            
            st.success("SYSTEM ONLINE")
            time.sleep(0.5)
        
        boot_placeholder.empty()
        st.session_state['boot_completed'] = True
    
    # --- DEFINICE CLI CALLBACKU (OPRAVA VYKONÁVÁNÍ PŘÍKAZŮ) ---
    # Tento callback se spustí PŘED tím, než se stránka znovu načte.
    # To zaručuje, že se příkaz provede, vstup se vymaže a nic se necyklí.
    
    if 'cli_msg' not in st.session_state: st.session_state['cli_msg'] = None

    def process_cli_command():
        cmd_raw = st.session_state.cli_cmd
        if not cmd_raw: return
        
        # 1. Okamžitě vymažeme vstup v session state (takže po reloadu bude prázdný)
        st.session_state.cli_cmd = ""
        
        cmd_parts = cmd_raw.strip().split()
        cmd = cmd_parts[0].lower()
        
        msg_text = None
        msg_icon = None

        try:
            if cmd == "/help":
                msg_text = "Příkazy:\n/price [TICKER]\n/buy [TICKER] [KUSY]\n/sell [TICKER] [KUSY]\n/cash"
                msg_icon = "ℹ️"
            
            elif cmd == "/price" and len(cmd_parts) > 1:
                t_cli = cmd_parts[1].upper()
                p_cli, m_cli, z_cli = ziskej_info(t_cli)
                if p_cli: 
                    msg_text = f"💰 {t_cli}: {p_cli:.2f} {m_cli} ({z_cli*100:+.2f}%)"
                    msg_icon = "📈"
                else: 
                    msg_text = f"❌ Ticker {t_cli} nenalezen."
                    msg_icon = "⚠️"
            
            elif cmd == "/cash":
                bals = get_zustatky(USER)
                txt = " | ".join([f"{k}: {v:,.0f}" for k,v in bals.items()])
                msg_text = f"🏦 {txt}"
                msg_icon = "💵"
                
            elif cmd == "/buy" and len(cmd_parts) >= 3:
                t_cli = cmd_parts[1].upper()
                k_cli = float(cmd_parts[2])
                p_cli, m_cli, _ = ziskej_info(t_cli)
                if p_cli:
                    ok, msg = proved_nakup(t_cli, k_cli, p_cli, USER)
                    msg_text = msg
                    msg_icon = "✅" if ok else "❌"
                else: 
                    msg_text = "❌ Chyba ceny"
                    msg_icon = "⚠️"

            elif cmd == "/sell" and len(cmd_parts) >= 3:
                t_cli = cmd_parts[1].upper()
                k_cli = float(cmd_parts[2])
                p_cli, m_cli, _ = ziskej_info(t_cli)
                if p_cli:
                    ok, msg = proved_prodej(t_cli, k_cli, p_cli, USER, m_cli)
                    msg_text = msg
                    msg_icon = "✅" if ok else "❌"
                else:
                    msg_text = "❌ Chyba ceny"
                    msg_icon = "⚠️"
            else:
                msg_text = "❌ Neznámý příkaz nebo formát"
                msg_icon = "❓"
        except Exception as e:
            msg_text = f"❌ Chyba: {str(e)}"
            msg_icon = "⚠️"
            
        # Uložíme zprávu do session state, aby se zobrazila po reloadu
        if msg_text:
            st.session_state['cli_msg'] = (msg_text, msg_icon)

    # -----------------------------------------------------------

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
            tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']
            
            if buy_trg > 0 or sell_trg > 0:
                inf = LIVE_DATA.get(tk, {})
                price = inf.get('price')
                if not price: 
                    price, _, _ = ziskej_info(tk)
                
                if price:
                    if buy_trg > 0 and price <= buy_trg:
                        alerts.append(f"{tk}: KUPNÍ ALERT! Cena {price:.2f} <= {buy_trg:.2f}")
                        st.toast(f"🔔 {tk} je ve slevě! ({price:.2f})", icon="🔥")
                    
                    if sell_trg > 0 and price >= sell_trg:
                        alerts.append(f"{tk}: PRODEJNÍ ALERT! Cena {price:.2f} >= {sell_trg:.2f}")
                        st.toast(f"🔔 {tk} dosáhl cíle! ({price:.2f})", icon="💰")

    # --- VÝPOČET PORTFOLIA + ZÍSKÁNÍ FUNDAMENTŮ ---
    fundament_data = {}
    if not df.empty:
        tickers_in_portfolio = df['Ticker'].unique().tolist()
        for tkr in tickers_in_portfolio:
            info, _ = ziskej_detail_akcie(tkr) 
            fundament_data[tkr] = info

    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        df_g['Cena'] = df_g['Investice'] / df_g['Pocet']
        
        for i, (idx, row) in enumerate(df_g.iterrows()):
            tkr = row['Ticker']
            p, m, d_zmena = ziskej_info(tkr)
            if p is None: p = row['Cena']
            if m is None or m == "N/A": m = "USD"
            
            fundamenty = fundament_data.get(tkr, {})
            pe_ratio = fundamenty.get('trailingPE', 0)
            market_cap = fundamenty.get('marketCap', 0)
            
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
            
            country = "United States" 
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
                if m == "CZK": k = 1.0 / kurzy.get("CZK", 20.85)
                elif m == "EUR": k = kurzy.get("EUR", 1.16)
                else: k = 1.0
            except Exception: k = 1.0
            
            celk_hod_usd += hod*k
            celk_inv_usd += inv*k
            
            viz_data.append({
                "Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m, 
                "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Cena'], "Dan": dan_status, "Investice": inv, "Divi": div_vynos, "Dnes": d_zmena,
                "Země": country,
                "P/E": pe_ratio,
                "Kapitalizace": market_cap / 1e9 if market_cap else 0 # Oprava formátování na Miliardy (B)
            })
    
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
        cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))
    except Exception: cash_usd = 0

    # --- 4. SIDEBAR ---
    with st.sidebar:
        # Lottie Animation Placeholder - Generic tech loop
        lottie_url = "https://lottie.host/02092823-3932-4467-9d7e-976934440263/3q5XJg2Z2W.json" # Public generic tech URL
        lottie_json = load_lottieurl(lottie_url)
        if lottie_json:
            st_lottie(lottie_json, height=150, key="sidebar_anim")
        
        st.header(f"👤 {USER.upper()}")
        
        # --- NOVÉ: SVĚTOVÉ TRHY (HODINY) ---
        with st.expander("🌍 SVĚTOVÉ TRHY", expanded=True):
            ny_time, ny_open = zjisti_stav_trhu("America/New_York", 9, 16) # NYSE: 9:30 - 16:00 (zjednodušeno na hodiny)
            ln_time, ln_open = zjisti_stav_trhu("Europe/London", 8, 16)    # LSE
            jp_time, jp_open = zjisti_stav_trhu("Asia/Tokyo", 9, 15)       # TSE
            
            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇺🇸 New York"); c_m2.markdown(f"**{ny_time}** {'🟢' if ny_open else '🔴'}")
            
            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇬🇧 Londýn"); c_m2.markdown(f"**{ln_time}** {'🟢' if ln_open else '🔴'}")
            
            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇯🇵 Tokio"); c_m2.markdown(f"**{jp_time}** {'🟢' if jp_open else '🔴'}")
        
        st.divider()
        # -----------------------------------

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

        # --- NOVINKA: VELITELSKÁ ŘÁDKA (CLI) - S CALLBACKEM ---
        st.divider()
        st.caption("💻 TERMINÁL (Příkazová řádka)")
        
        # Zobrazení zprávy z callbacku (pokud existuje z minulé akce)
        if st.session_state.get('cli_msg'):
            txt, ic = st.session_state['cli_msg']
            st.toast(txt, icon=ic)
            st.session_state['cli_msg'] = None # Vyčistit po zobrazení, aby se toast neopakoval

        # Input s callbackem - klíčová změna!
        st.text_input(">", key="cli_cmd", placeholder="/help pro nápovědu", on_change=process_cli_command)
        # ---------------------------------------

        st.divider(); st.subheader("NAVIGACE")
        page = st.radio("Jít na:", ["🏠 Přehled", "👀 Sledování", "📈 Analýza", "📰 Zprávy", "💸 Obchod", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení"], label_visibility="collapsed")
        
        st.divider()
        if st.button("📧 ODESLAT RANNÍ REPORT", use_container_width=True):
            msg = f"<h2>Report {USER}</h2><p>Jmění: {celk_hod_czk:,.0f} Kč</p>"
            if odeslat_email(st.secrets["email"]["sender"], "Report", msg) == True: st.success("Odesláno!")
            else: st.error("Chyba")
        
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
        
        # --- NOVÉ: SKOKAN A PROPADÁK DNE ---
        if viz_data:
            # Seřadíme data podle % změny (Dnes)
            sorted_data = sorted(viz_data, key=lambda x: x['Dnes'], reverse=True)
            best = sorted_data[0]
            worst = sorted_data[-1]
            
            st.write("")
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                st.success(f"🚀 SKOKAN DNE: **{best['Ticker']}**")
                st.metric("Změna", f"{best['Dnes']*100:+.2f} %", f"Cena: {best['Cena']:.2f} {best['Měna']}")
            with c_m2:
                st.error(f"💀 PROPADÁK DNE: **{worst['Ticker']}**")
                st.metric("Změna", f"{worst['Dnes']*100:+.2f} %", f"Cena: {worst['Cena']:.2f} {worst['Měna']}")
        # -----------------------------------

        # --- NOVÉ: AI PORTFOLIO AUDITOR ---
        if AI_AVAILABLE and viz_data:
            with st.expander("🧠 AI AUDIT PORTFOLIA (Strategie)", expanded=False):
                st.info("AI zanalyzuje tvé rozložení aktiv, rizikovost a navrhne vylepšení.")
                if st.button("🕵️ SPUSTIT HLOUBKOVÝ AUDIT"):
                    with st.spinner("AI počítá rizikové modely..."):
                        # Příprava dat
                        port_summary = "\n".join([f"- {i['Ticker']} ({i['Sektor']}): {i['HodnotaUSD']:.0f} USD ({i['Zisk']:.0f} USD zisk)" for i in viz_data])
                        cash_info = f"Hotovost: {cash_usd:.0f} USD"
                        total_val = f"Celkové jmění: {celk_hod_usd:.0f} USD"
                        
                        prompt_audit = f"""
                        Jsi profesionální portfolio manažer (Hedge Fund). Udělej tvrdý a upřímný audit tohoto portfolia:
                        
                        {total_val}
                        {cash_info}
                        
                        POZICE:
                        {port_summary}
                        
                        ÚKOL:
                        1. Zhodnoť diverzifikaci (sektory, jednotlivé akcie).
                        2. Identifikuj největší riziko (koncentrace, měna, sektor).
                        3. Navrhni 1 konkrétní krok pro vylepšení (co prodat/koupit/změnit).
                        
                        Odpověz stručně, profesionálně a česky. Používej formátování (body, tučné písmo).
                        """
                        try:
                            audit_res = AI_MODEL.generate_content(prompt_audit)
                            st.markdown("### 📝 VÝSLEDEK AUDITU")
                            st.markdown(audit_res.text)
                        except Exception as e:
                            st.error(f"Chyba auditu: {e}")
        # ----------------------------------

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
                        {'range': [0, 25], 'color': '#FF4136'},
                        {'range': [25, 45], 'color': '#FF851B'},
                        {'range': [45, 55], 'color': '#AAAAAA'},
                        {'range': [55, 75], 'color': '#7FDBFF'},
                        {'range': [75, 100], 'color': '#2ECC40'}
                    ],
                }
            ))
            fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white", 'family': "Roboto Mono"}, height=250, margin=dict(l=20, r=20, t=30, b=20))
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
                fig_area.update_traces(line_color='#00CC96', fillcolor='rgba(0, 204, 150, 0.3)')
                fig_area.update_layout(xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, font_family="Roboto Mono")
                fig_area.update_xaxes(showgrid=False)
                fig_area.update_yaxes(showgrid=True, gridcolor='#30363D')
                st.plotly_chart(fig_area, use_container_width=True, key="fig_vyvoj_maj")
                add_download_button(fig_area, "vyvoj_majetku")
        
        with col_graf2:
            if not vdf.empty:
                st.subheader("🍰 SEKTORY")
                fig_pie = px.pie(vdf, values='HodnotaUSD', names='Sektor', hole=0.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=300, paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
                st.plotly_chart(fig_pie, use_container_width=True, key="fig_sektory")
                add_download_button(fig_pie, "sektorova_analyza")

        # --- NOVINKA: SANKEY DIAGRAM (TOK PENĚZ) ---
        st.divider()
        st.subheader("🌊 TOK KAPITÁLU (Sankey)")
        
        # 1. Příprava dat pro Sankey
        # Zdroje (Odkud peníze přišly)
        total_vklady_czk = 0
        if not df_cash.empty:
            # Sečteme vklady mínus výběry (přibližný přepočet na CZK pro vizualizaci)
            for _, row in df_cash.iterrows():
                cst = row['Castka']
                men = row['Mena']
                val_czk = cst
                if men == "USD": val_czk = cst * kurzy.get("CZK", 20.85)
                elif men == "EUR": val_czk = cst * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                
                if row['Typ'] in ['Vklad', 'Deposit']: total_vklady_czk += val_czk
                elif row['Typ'] in ['Výběr', 'Withdrawal']: total_vklady_czk -= val_czk
        
        total_divi_czk = 0
        if not df_div.empty:
             for _, r in df_div.iterrows():
                amt = r['Castka']; currency = r['Mena']
                if currency == "USD": total_divi_czk += amt * kurzy.get("CZK", 20.85)
                elif currency == "EUR": total_divi_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                else: total_divi_czk += amt

        # Zisky (Nerealizované + Realizované)
        # Pro jednoduchost vezmeme aktuální hodnotu portfolia minus investice
        # A přičteme historické realizované zisky
        total_realized_czk = 0
        if not st.session_state['df_hist'].empty:
             for _, r in st.session_state['df_hist'].iterrows():
                 # Zjednodušený odhad realizovaného zisku v CZK
                 zsk = r['Zisk'] # Předpokládáme, že Zisk je v měně obchodu, ale tady to pro vizualizaci zjednodušíme nebo převedeme
                 men = r['Mena']
                 if men == "USD": total_realized_czk += zsk * kurzy.get("CZK", 20.85)
                 elif men == "EUR": total_realized_czk += zsk * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                 else: total_realized_czk += zsk

        unrealized_profit_czk = (celk_hod_czk - celk_inv_czk)
        total_market_profit_czk = total_divi_czk + total_realized_czk + unrealized_profit_czk
        
        # Pokud je zisk záporný (ztráta), Sankey to neumí dobře zobrazit jako "zdroj", 
        # tak to pro vizualizaci ošetříme (zobrazíme jen kladné toky nebo snížíme hodnotu kapitálu)
        # Zde uděláme verzi: Vklady + Zisk = Majetek. (Pokud ztráta, Majetek < Vklady)
        
        # Cíle (Kde peníze jsou)
        cash_total_czk = cash_usd * kurzy.get("CZK", 20.85)
        stock_total_czk = celk_hod_czk
        
        # Konstrukce uzlů
        label = ["Vklady (Netto)", "Tržní Zisk & Divi", "MŮJ KAPITÁL", "Hotovost"]
        color = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd"]
        
        # Přidáme jednotlivé akcie (Top 5 pro přehlednost)
        top_stocks = []
        if not vdf.empty:
            vdf_sorted = vdf.sort_values('HodnotaUSD', ascending=False).head(5)
            for _, row in vdf_sorted.iterrows():
                stock_label = f"Akcie {row['Ticker']}"
                label.append(stock_label)
                color.append("#e377c2") # Barva pro akcie
                top_stocks.append({'label': stock_label, 'value_czk': row['HodnotaUSD'] * kurzy.get("CZK", 20.85)})
        
        # Jiné akcie (zbytek)
        other_stocks_val_czk = stock_total_czk - sum([s['value_czk'] for s in top_stocks])
        if other_stocks_val_czk > 100: # Jen pokud tam něco zbývá
            label.append("Ostatní Akcie")
            color.append("#7f7f7f")
        
        # Indexy uzlů
        IDX_VKLADY = 0
        IDX_ZISK = 1
        IDX_KAPITAL = 2
        IDX_CASH = 3
        IDX_FIRST_STOCK = 4
        
        source = []
        target = []
        value = []
        
        # Tok 1: Vklady -> Kapitál
        if total_vklady_czk > 0:
            source.append(IDX_VKLADY); target.append(IDX_KAPITAL); value.append(total_vklady_czk)
            
        # Tok 2: Zisk -> Kapitál (jen pokud jsme v plusu celkově)
        if total_market_profit_czk > 0:
            source.append(IDX_ZISK); target.append(IDX_KAPITAL); value.append(total_market_profit_czk)
        
        # Tok 3: Kapitál -> Hotovost
        if cash_total_czk > 100: # Filtrujeme drobné
            source.append(IDX_KAPITAL); target.append(IDX_CASH); value.append(cash_total_czk)
            
        # Tok 4: Kapitál -> Akcie
        current_stock_idx = IDX_FIRST_STOCK
        for s in top_stocks:
            source.append(IDX_KAPITAL); target.append(current_stock_idx); value.append(s['value_czk'])
            current_stock_idx += 1
            
        if other_stocks_val_czk > 100:
            source.append(IDX_KAPITAL); target.append(current_stock_idx); value.append(other_stocks_val_czk)

        # Vykreslení
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
              pad = 15,
              thickness = 20,
              line = dict(color = "black", width = 0.5),
              label = label,
              color = "rgba(0, 204, 150, 0.6)" # Defaultní barva uzlů
            ),
            link = dict(
              source = source,
              target = target,
              value = value,
              color = "rgba(100, 100, 100, 0.3)" # Průhledná šedá pro toky
          ))])

        fig_sankey.update_layout(title_text="Tok peněz v portfoliu (CZK)", font_size=12, height=400, paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
        st.plotly_chart(fig_sankey, use_container_width=True)
        # ----------------------------------------

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

        if 'show_portfolio_live' not in st.session_state:
            st.session_state['show_portfolio_live'] = True
        if 'show_cash_history' not in st.session_state:
            st.session_state['show_cash_history'] = False
            
        col_view1, col_view2, _ = st.columns([1, 1, 3])
        with col_view1:
            st.session_state['show_portfolio_live'] = st.checkbox("Zobrazit Portfolio Tabulku", value=st.session_state['show_portfolio_live'], key="chk_portfolio")
        with col_view2:
             st.session_state['show_cash_history'] = st.checkbox("Zobrazit Historii Hotovosti", value=st.session_state['show_cash_history'], key="chk_cash")
        st.write("")

        if st.session_state['show_portfolio_live']:
            st.subheader("📋 PORTFOLIO LIVE")
            if not vdf.empty:
                # --- PŘÍPRAVA SPARKLINES (MINIGRAFY) ---
                # Hromadné stažení dat pro minigrafy (30 dní)
                tickers_list = vdf['Ticker'].tolist()
                spark_data = {}
                
                if tickers_list:
                    try:
                        # Stáhneme data najednou (rychlejší než cyklus)
                        batch_history = yf.download(tickers_list, period="1mo", interval="1d", group_by='ticker', progress=False)
                        
                        for t in tickers_list:
                            # Získání dat pro konkrétní ticker (ošetření multi-indexu vs single indexu)
                            if len(tickers_list) > 1:
                                if t in batch_history.columns.levels[0]:
                                    closes = batch_history[t]['Close'].dropna().tolist()
                                    spark_data[t] = closes
                                else:
                                    spark_data[t] = []
                            else:
                                # Pokud je v portfoliu jen jedna akcie, struktura DF je jiná
                                closes = batch_history['Close'].dropna().tolist()
                                spark_data[t] = closes
                    except Exception:
                        pass # Pokud selže stahování, grafy prostě nebudou (safe fail)

                vdf['Trend 30d'] = vdf['Ticker'].map(spark_data)
                # ---------------------------------------

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
                        "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f", help="Poměr ceny k ziskům. Nízká hodnota může značit podhodnocení."),
                        "Kapitalizace": st.column_config.NumberColumn("Kapitalizace", format="$%.1fB", help="Tržní kapitalizace ve formátu miliard USD."),
                        "Dan": st.column_config.TextColumn("Daně", help="🟢 > 3 roky (Osvobozeno)\n🔴 < 3 roky (Zdanit)\n🟠 Mix nákupů"),
                        "Země": "Země",
                        "Trend 30d": st.column_config.LineChartColumn(
                            "Trend (30 dní)",
                            width="medium",
                            help="Vývoj ceny za poslední měsíc"
                            # Odstraněno y_min/y_max pro správné auto-škálování
                        )
                    },
                    column_order=["Ticker", "Trend 30d", "Sektor", "Měna", "Země", "Kusy", "Průměr", "Cena", "Dnes", "HodnotaUSD", "Zisk", "Divi", "P/E", "Kapitalizace", "Dan"],
                    use_container_width=True,
                    hide_index=True
                )
            else: st.info("Portfolio je prázdné.")
        
        if st.session_state['show_cash_history']:
            st.divider()
            st.subheader("🏦 HISTORIE HOTOVOSTI")
            if not df_cash.empty:
                 st.dataframe(df_cash.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
            else:
                 st.info("Historie hotovosti je prázdná.")

    elif page == "👀 Sledování":
        st.title("👀 WATCHLIST (Hlídač) – Cenové zóny")
        
        with st.expander("➕ Přidat novou akcii", expanded=False):
            with st.form("add_w", clear_on_submit=True):
                t = st.text_input("Symbol (např. AAPL)").upper()
                c_buy, c_sell = st.columns(2)
                with c_buy: target_buy = st.number_input("Cílová NÁKUPNÍ cena ($)", min_value=0.0, key="tg_buy")
                with c_sell: target_sell = st.number_input("Cílová PRODEJNÍ cena ($)", min_value=0.0, key="tg_sell")
                
                if st.form_submit_button("Sledovat"):
                    if t and (target_buy > 0 or target_sell > 0):
                        pridat_do_watchlistu(t, target_buy, target_sell, USER); st.rerun() 
                    else:
                        st.warning("Zadejte symbol a alespoň jednu cílovou cenu (Buy nebo Sell).")
        
        if not df_watch.empty:
            st.subheader("📡 TAKTICKÝ RADAR")
            st.info("Rychlý přehled technického stavu sledovaných akcií.")
            
            # Příprava dat pro Radar
            w_data = []
            tickers_list = df_watch['Ticker'].unique().tolist()
            
            # Hromadné stažení historie pro RSI (rychlejší než po jednom)
            if tickers_list:
                with st.spinner("Skenuji trh a počítám indikátory..."):
                    try:
                        batch_data = yf.download(tickers_list, period="3mo", group_by='ticker', progress=False)
                    except: batch_data = pd.DataFrame()

            for _, r in df_watch.iterrows():
                tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']
                
                # Získání live ceny a info
                inf = LIVE_DATA.get(tk, {})
                price = inf.get('price')
                cur = inf.get('curr', 'USD')
                
                # Fallback pro měnu
                if tk.upper().endswith(".PR"): cur = "CZK"
                elif tk.upper().endswith(".DE"): cur = "EUR"
                
                if not price: 
                    price, _, _ = ziskej_info(tk)
                
                # Výpočet RSI
                rsi_val = 50 # Default neutral
                try:
                    if len(tickers_list) > 1:
                        # Multi-index
                        if tk in batch_data.columns.levels[0]:
                            hist = batch_data[tk]['Close']
                        else: hist = pd.Series()
                    else:
                        # Single index (pokud je jen jedna akcie ve watchlistu)
                        if 'Close' in batch_data.columns: hist = batch_data['Close']
                        else: hist = pd.Series()

                    if not hist.empty and len(hist) > 14:
                        delta = hist.diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        rsi_series = 100 - (100 / (1 + rs))
                        rsi_val = rsi_series.iloc[-1]
                except: pass

                # 52 Week Range (z fast_info)
                year_low = 0; year_high = 0; range_pos = 0.5
                try:
                    t_obj = yf.Ticker(tk)
                    year_low = t_obj.fast_info.year_low
                    year_high = t_obj.fast_info.year_high
                    if price and year_high > year_low:
                        range_pos = (price - year_low) / (year_high - year_low)
                        range_pos = max(0.0, min(1.0, range_pos)) # Ořezání 0-1
                except: pass

                # Status text
                status_text = "💤 Sleduji"
                dist_to_buy = 0
                if price:
                    if buy_trg > 0:
                        dist = ((price - buy_trg) / price) * 100
                        dist_to_buy = dist
                        if price <= buy_trg: status_text = "🔥 BUY ZONE"
                        else: status_text = f"Wait (-{dist:.1f}%)"
                    
                    if sell_trg > 0 and price >= sell_trg:
                        status_text = "💰 SELL ZONE"
                
                # RSI Interpretace pro tabulku
                rsi_display = f"{rsi_val:.0f}"
                
                w_data.append({
                    "Symbol": tk, 
                    "Cena": price, 
                    "Měna": cur, 
                    "RSI (14)": rsi_val, # Číselná hodnota pro sorting/logiku
                    "52T Range": range_pos,
                    "Cíl Buy": buy_trg,
                    "Status": status_text
                })
            
            wdf = pd.DataFrame(w_data)
            
            if not wdf.empty:
                st.dataframe(
                    wdf, 
                    column_config={
                        "Cena": st.column_config.NumberColumn(format="%.2f"),
                        "Cíl Buy": st.column_config.NumberColumn(format="%.2f"),
                        "RSI (14)": st.column_config.NumberColumn(
                            "RSI Indikátor",
                            help="< 30: Přeprodáno (Levné) | > 70: Překoupeno (Drahé)",
                            format="%.0f",
                        ),
                        "52T Range": st.column_config.ProgressColumn(
                            "Roční Rozsah",
                            help="Poloha ceny mezi ročním minimem (vlevo) a maximem (vpravo)",
                            min_value=0,
                            max_value=1,
                            format="" 
                        )
                    },
                    column_order=["Symbol", "Cena", "Měna", "RSI (14)", "52T Range", "Cíl Buy", "Status"],
                    use_container_width=True, 
                    hide_index=True
                )
                
                # Legenda k RSI
                st.caption("💡 **RSI Legenda:** Hodnoty pod **30** značí přeprodanost (možný odraz nahoru 📈). Hodnoty nad **70** značí překoupenost (možná korekce dolů 📉).")
            
            st.divider()
            c_del1, c_del2 = st.columns([3, 1])
            with c_del2:
                to_del = st.selectbox("Vyber pro smazání:", df_watch['Ticker'].unique())
                if st.button("🗑️ Smazat ze sledování", use_container_width=True): 
                    odebrat_z_watchlistu(to_del, USER); st.rerun()
        else:
            st.info("Zatím nic nesleduješ. Přidej první akcii nahoře.")

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
                    # --- POUŽITÍ NOVÉ FUNKCE proved_nakup ---
                    _, m, _ = ziskej_info(t)
                    # Pokud uživatel nezadal cenu (0), zkusíme ji stáhnout
                    final_c = c if c > 0 else ziskej_info(t)[0]
                    
                    if final_c and final_c > 0:
                        ok, msg = proved_nakup(t, k, final_c, USER)
                        if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error(msg)
                    else:
                        st.error("Nepodařilo se získat cenu. Zadej ji ručně.")
                    # ----------------------------------------
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

    elif page == "💎 Dividendy":
        st.title("💎 DIVIDENDOVÝ KALENDÁŘ")
        
        # --- NOVINKA: PROJEKTOR PASIVNÍHO PŘÍJMU ---
        est_annual_income_czk = 0
        if viz_data:
            for item in viz_data:
                # Výpočet: Hodnota pozice * Dividend Yield
                # viz_data má HodnotaUSD a Divi (v desítkovém tvaru, např. 0.05 pro 5%)
                yield_val = item.get('Divi', 0)
                val_usd = item.get('HodnotaUSD', 0)
                if yield_val > 0 and val_usd > 0:
                    est_annual_income_czk += (val_usd * yield_val) * kurzy.get("CZK", 20.85)
        
        est_monthly_income_czk = est_annual_income_czk / 12
        
        with st.container(border=True):
            st.subheader("🔮 PROJEKTOR PASIVNÍHO PŘÍJMU")
            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("Očekávaný roční příjem", f"{est_annual_income_czk:,.0f} Kč", help="Hrubý odhad na základě aktuálního dividendového výnosu držených akcií.")
            cp2.metric("Měsíční průměr", f"{est_monthly_income_czk:,.0f} Kč", help="Kolik to dělá měsíčně k dobru.")
            
            # Svoboda Levels
            levels = {
                "Netflix (300 Kč)": 300,
                "Internet (600 Kč)": 600,
                "Energie (2 000 Kč)": 2000,
                "Nájem/Hypo (15 000 Kč)": 15000
            }
            
            next_goal = "Rentier"
            next_val = 100000
            progress = 0.0
            
            for name, val in levels.items():
                if est_monthly_income_czk < val:
                    next_goal = name
                    next_val = val
                    progress = min(est_monthly_income_czk / val, 1.0)
                    break
                else:
                    # Pokud splněno, progress je 100% pro tento level
                    pass
            
            if est_monthly_income_czk > 15000:
                next_goal = "Finanční Svoboda 🏖️"
                progress = 1.0

            cp3.caption(f"Cíl: **{next_goal}**")
            cp3.progress(progress)
        
        st.divider()
        # -------------------------------------------

        # 1. Metriky
        total_div_czk = 0
        if not df_div.empty:
            for _, r in df_div.iterrows():
                amt = r['Castka']; currency = r['Mena']
                if currency == "USD": total_div_czk += amt * kurzy.get("CZK", 20.85)
                elif currency == "EUR": total_div_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85)) # approx
                else: total_div_czk += amt
        
        st.metric("CELKEM VYPLACENO (CZK)", f"{total_div_czk:,.0f} Kč")
        
        t_div1, t_div2 = st.tabs(["HISTORIE & GRAF", "PŘIDAT DIVIDENDU"])
        
        with t_div1:
            if not df_div.empty:
                # Graf - OPRAVA VIZUALIZACE
                # Vytvoříme pomocný dataframe jen pro graf
                plot_df = df_div.copy()
                # Převedeme přesný čas jen na datum (string YYYY-MM-DD), aby měly sloupce šířku "1 den" a byly vidět
                plot_df['Datum_Den'] = pd.to_datetime(plot_df['Datum']).dt.strftime('%Y-%m-%d')
                
                # Seskupíme podle dne a tickeru (aby se v jednom dni sloupce sečetly/navrstvily)
                plot_df_grouped = plot_df.groupby(['Datum_Den', 'Ticker'])['Castka'].sum().reset_index()
                plot_df_grouped = plot_df_grouped.sort_values('Datum_Den')

                fig_div = px.bar(plot_df_grouped, x='Datum_Den', y='Castka', color='Ticker', 
                                 title="Historie výplat (po dnech)", 
                                 labels={'Datum_Den': 'Datum', 'Castka': 'Částka'},
                                 template="plotly_dark")
                
                # Vynutíme, aby osa X byla kategorie (text), ne časová osa -> tlusté sloupce
                fig_div.update_xaxes(type='category')
                
                fig_div.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
                st.plotly_chart(fig_div, use_container_width=True)
                
                # Tabulka - tu necháme s původními detailními daty
                st.dataframe(df_div.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Zatím žádné dividendy.")
        
        with t_div2:
            st.caption("Peníze se automaticky připíší do peněženky.")
            with st.form("add_div"):
                dt_ticker = st.selectbox("Ticker", df['Ticker'].unique() if not df.empty else ["Jiny"])
                dt_amount = st.number_input("Částka (Netto)", 0.0, step=0.1)
                dt_curr = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                
                if st.form_submit_button("💰 PŘIPSAT DIVIDENDU"):
                    pridat_dividendu(dt_ticker, dt_amount, dt_curr, USER)
                    st.success(f"Připsáno {dt_amount} {dt_curr} od {dt_ticker}")
                    time.sleep(1)
                    st.rerun()

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
                                # --- 1. VÝPOČTY INDIKÁTORŮ (MUSÍ BÝT PRVNÍ!) ---
                                # Bollinger Bands
                                hist_data['BB_Middle'] = hist_data['Close'].rolling(window=20).mean()
                                hist_data['BB_Std'] = hist_data['Close'].rolling(window=20).std()
                                hist_data['BB_Upper'] = hist_data['BB_Middle'] + (hist_data['BB_Std'] * 2)
                                hist_data['BB_Lower'] = hist_data['BB_Middle'] - (hist_data['BB_Std'] * 2)

                                # RSI
                                delta = hist_data['Close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                                rs = gain / loss
                                hist_data['RSI'] = 100 - (100 / (1 + rs))
                                
                                # SMA
                                hist_data['SMA20'] = hist_data['Close'].rolling(window=20).mean()
                                hist_data['SMA50'] = hist_data['Close'].rolling(window=50).mean()

                                # --- 2. PŘÍPRAVA DAT PRO AI (TEĎ UŽ BEZPEČNÁ) ---
                                # Najdeme poslední řádek, kde JSOU data pro SMA vypočítaná (ne NaN)
                                valid_data = hist_data.dropna(subset=['SMA50'])
                                if not valid_data.empty:
                                    last_row = valid_data.iloc[-1] # Použijeme poslední PLATNÝ řádek
                                else:
                                    last_row = hist_data.iloc[-1] # Fallback

                                current_price_scan = last_row['Close']
                                rsi_scan = last_row['RSI']
                                sma20_scan = last_row['SMA20']
                                sma50_scan = last_row['SMA50']
                                bb_upper_scan = last_row['BB_Upper']
                                bb_lower_scan = last_row['BB_Lower']
                                # ----------------------------------------

                                # --- 3. VYKRESLENÍ GRAFU ---
                                fig_candle = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                                fig_candle.add_trace(go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], name=vybrana_akcie), row=1, col=1)

                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['BB_Upper'], mode='lines', name='BB Upper', line=dict(color='gray', width=1)), row=1, col=1)
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['BB_Lower'], mode='lines', name='BB Lower', line=dict(color='gray', width=1), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.1)'), row=1, col=1)

                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['SMA20'], mode='lines', name='SMA 20 (Trend)', line=dict(color='orange', width=1.5)), row=1, col=1)
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['SMA50'], mode='lines', name='SMA 50 (Dlouhý)', line=dict(color='cyan', width=1.5)), row=1, col=1)
                                fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['RSI'], mode='lines', name='RSI', line=dict(color='#A56CC1', width=2)), row=2, col=1)
                                fig_candle.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1, annotation_text="Překoupené (70)", annotation_position="top right")
                                fig_candle.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1, annotation_text="Přeprodané (30)", annotation_position="bottom right")
                                fig_candle.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=600, margin=dict(l=0, r=0, t=30, b=0), legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0)"), font_family="Roboto Mono")
                                fig_candle.update_yaxes(title_text="Cena", row=1, col=1, showgrid=True, gridcolor='#30363D'); fig_candle.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100], showgrid=True, gridcolor='#30363D')
                                fig_candle.update_xaxes(showgrid=False)
                                st.plotly_chart(fig_candle, use_container_width=True)
                                add_download_button(fig_candle, f"rentgen_{vybrana_akcie}")
                                
                                # --- NOVÁ FUNKCE: AI TECHNICKÁ ANALÝZA ---
                                if AI_AVAILABLE:
                                    st.divider()
                                    if st.button(f"🤖 SPUSTIT AI TECHNICKOU ANALÝZU PRO {vybrana_akcie}", type="secondary"):
                                        with st.spinner(f"AI analyzuje indikátory pro {vybrana_akcie}..."):
                                            prompt_tech = f"""
                                            Jsi expert na technickou analýzu akcií. Analyzuj následující data pro {vybrana_akcie}:
                                            Aktuální Cena: {current_price_scan:.2f}
                                            RSI (14): {rsi_scan:.2f}
                                            SMA 20 (Krátkodobý trend): {sma20_scan:.2f}
                                            SMA 50 (Střednědobý trend): {sma50_scan:.2f}
                                            Bollinger Upper: {bb_upper_scan:.2f}
                                            Bollinger Lower: {bb_lower_scan:.2f}
                                            
                                            Úkol:
                                            1. Urči trend (SMA20 vs SMA50, Cena vs SMA).
                                            2. Zhodnoť RSI (Překoupeno > 70, Přeprodáno < 30).
                                            3. Zkontroluj Bollinger Bands (Je cena u kraje?).
                                            4. Dej finální verdikt: BÝČÍ / MEDVĚDÍ / NEUTRÁLNÍ.
                                            Odpověz stručně v bodech, česky.
                                            """
                                            try:
                                                tech_res = AI_MODEL.generate_content(prompt_tech)
                                                st.success("Analýza dokončena!")
                                                st.markdown(f"""
                                                <div style="background-color: #0D1117; border: 1px solid #30363D; border-radius: 10px; padding: 20px;">
                                                    <h3 style="color: #58A6FF;">🤖 AI VERDIKT: {vybrana_akcie}</h3>
                                                    {tech_res.text}
                                                </div>
                                                """, unsafe_allow_html=True)
                                            except Exception as e:
                                                st.error(f"Chyba AI analýzy: {e}")
                                # -----------------------------------------

                            else: st.warning("Graf historie není k dispozici.")
                        except Exception as e: st.error(f"Chyba zobrazení rentgenu: {e}")
                    else: st.error("Nepodařilo se načíst data o firmě.")

        with tab2:
            st.subheader("⚔️ SROVNÁNÍ VÝKONNOSTI AKCIÍ")
            
            portfolio_tickers = df['Ticker'].unique().tolist() if not df.empty else []
            default_tickers = ['AAPL', 'MSFT', '^GSPC']
            initial_selection = list(set(portfolio_tickers[:5] + ['^GSPC']))
            
            tickers_to_compare = st.multiselect(
                "Vyberte akcie/indexy pro srovnání výkonnosti:", 
                options=list(set(default_tickers + portfolio_tickers)),
                default=initial_selection,
                key="multi_compare"
            )

            if tickers_to_compare:
                try:
                    with st.spinner(f"Stahuji historická data pro {len(tickers_to_compare)} tickerů..."):
                        raw_data = yf.download(tickers_to_compare, period="1y", interval="1d", progress=False)['Close']
                        
                        if raw_data.empty:
                             st.warning("Nepodařilo se načíst historická data pro vybrané tickery.")
                        else:
                            normalized_data = raw_data.apply(lambda x: (x / x.iloc[0] - 1) * 100)

                            fig_multi_comp = px.line(
                                normalized_data, 
                                title='Normalizovaná výkonnost (Změna v %) od počátku',
                                template="plotly_dark"
                            )
                            fig_multi_comp.update_layout(
                                xaxis_title="Datum", 
                                yaxis_title="Změna (%)", 
                                height=500,
                                margin=dict(t=50, b=0, l=0, r=0),
                                font_family="Roboto Mono",
                                plot_bgcolor="rgba(0,0,0,0)", 
                                paper_bgcolor="rgba(0,0,0,0)"
                            )
                            fig_multi_comp.update_xaxes(showgrid=False)
                            fig_multi_comp.update_yaxes(showgrid=True, gridcolor='#30363D')
                            st.plotly_chart(fig_multi_comp, use_container_width=True, key="fig_srovnani")
                            add_download_button(fig_multi_comp, "srovnani_akcii")

                            st.divider()
                            st.subheader("Detailní srovnání metrik")
                            
                            comp_list = []
                            for t in tickers_to_compare[:2]:
                                i, h = ziskej_detail_akcie(t)
                                if i:
                                    mc = i.get('marketCap', 0)
                                    pe = i.get('trailingPE', 0)
                                    dy = i.get('dividendYield', 0)
                                    perf = ((h['Close'].iloc[-1] / h['Close'].iloc[0]) - 1) * 100 if h is not None and not h.empty and h['Close'].iloc[0] != 0 else 0
                                    
                                    comp_list.append({
                                        "Metrika": [f"Kapitalizace {t}", f"P/E Ratio {t}", f"Dividenda {t}", f"Změna 1R {t}"],
                                        "Hodnota": [
                                            f"${mc/1e9:.1f}B", 
                                            f"{pe:.2f}" if pe > 0 else "N/A", 
                                            f"{dy*100:.2f}%" if dy else "0%", 
                                            f"{perf:+.2f}%"
                                        ]
                                    })
                                
                            if len(comp_list) >= 2:
                                comp_data = {
                                    "Metrika": ["Kapitalizace", "P/E Ratio", "Dividenda", "Změna 1R"],
                                    tickers_to_compare[0]: [comp_list[0]['Hodnota'][i] for i in range(4)],
                                    tickers_to_compare[1]: [comp_list[1]['Hodnota'][i] for i in range(4)]
                                }
                                st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)
                            elif tickers_to_compare:
                                st.info(f"Pro detailní srovnávací tabulku (metriky P/E, Kapitalizace) vyberte alespoň 2 akcie.")
                            
                except Exception as e:
                    st.error(f"Chyba při stahování/zpracování dat: Zkuste vybrat jiné tickery. (Detail: {e})")
            else:
                st.info("Vyberte alespoň jeden ticker (akcii nebo index) pro zobrazení srovnávacího grafu.")


        with tab3:
            if not vdf.empty:
                st.subheader("🌍 MAPA IMPÉRIA")
                try:
                    df_map = vdf.groupby('Země')['HodnotaUSD'].sum().reset_index()
                    fig_map = px.scatter_geo(df_map, locations="Země", locationmode="country names", hover_name="Země", size="HodnotaUSD", projection="orthographic", color="Země", template="plotly_dark")
                    fig_map.update_geos(bgcolor="#161B22", showcountries=True, countrycolor="#30363D", showocean=True, oceancolor="#0E1117", showland=True, landcolor="#1c2128")
                    fig_map.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={"color": "white", "family": "Roboto Mono"}, height=500, margin={"r":0,"t":0,"l":0,"b":0})
                    st.plotly_chart(fig_map, use_container_width=True, key="fig_mapa_imperia")
                    add_download_button(fig_map, "mapa_imperia")
                except Exception as e: st.error(f"Chyba mapy: {e}")
                st.divider()
                st.caption("MAPA TRHU (Sektory)")
                try:
                    fig = px.treemap(vdf, path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'], values='HodnotaUSD', color='Zisk', color_continuous_scale=['red', '#161B22', 'green'], color_continuous_midpoint=0)
                    fig.update_layout(font_family="Roboto Mono", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True, key="fig_sektor_map")
                    add_download_button(fig, "mapa_sektoru")
                except Exception: st.error("Chyba mapy.")
            else: st.info("Portfolio je prázdné.")

        with tab4:
            st.subheader("🔮 FINANČNÍ STROJ ČASU")
            st.write("")
            
            tickers_for_ef = df['Ticker'].unique().tolist()
            if len(tickers_for_ef) < 2:
                st.warning("⚠️ Pro simulaci Efektivní hranice potřebujete mít v portfoliu alespoň 2 různé akcie.")
            else:
                st.subheader("📊 Efektivní Hranice (Optimalizace Riziko/Výnos)")
                st.info(f"Proběhne simulace {len(tickers_for_ef)} akcií z tvého portfolia za posledních 5 let.")

                num_portfolios = st.slider("Počet simulací:", 1000, 10000, 5000, step=1000)
                
                if st.button("📈 SPUSTIT OPTIMALIZACI PORTFOLIA", type="primary", key="run_ef"):
                    try:
                        with st.spinner("Počítám tisíce náhodných portfolií..."):
                            end_date = datetime.now()
                            start_date = end_date - timedelta(days=5 * 365)
                            
                            price_data = yf.download(tickers_for_ef, start=start_date, end=end_date, progress=False)['Close']
                            price_data = price_data.dropna()

                            if price_data.empty or len(price_data) < 252:
                                st.error("Nelze provést simulaci: Historická data pro vybrané akcie nejsou dostupná nebo jsou nedostatečná (potřeba min. 1 rok dat).")
                                raise ValueError("Nedostatečná data pro EF")

                            log_returns = np.log(price_data / price_data.shift(1)).dropna()
                            num_assets = len(tickers_for_ef)
                            
                            results = np.zeros((3 + num_assets, num_portfolios))
                            
                            for i in range(num_portfolios):
                                weights = np.random.random(num_assets)
                                weights /= np.sum(weights)

                                portfolio_return = np.sum(log_returns.mean() * weights) * 252
                                
                                portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(log_returns.cov() * 252, weights)))
                                
                                sharpe_ratio = (portfolio_return - RISK_FREE_RATE) / portfolio_volatility

                                results[0,i] = portfolio_volatility
                                results[1,i] = portfolio_return
                                results[2,i] = sharpe_ratio
                                for j in range(num_assets):
                                    results[3+j,i] = weights[j]

                            cols = ['Volatilita', 'Výnos', 'Sharpe'] + tickers_for_ef
                            results_frame = pd.DataFrame(results.T, columns=cols)
                            
                            max_sharpe_portfolio = results_frame.loc[results_frame['Sharpe'].idxmax()]
                            
                            min_vol_portfolio = results_frame.loc[results_frame['Volatilita'].idxmin()]
                            
                            fig_ef = go.Figure()

                            fig_ef.add_trace(go.Scatter(
                                x=results_frame['Volatilita'],
                                y=results_frame['Výnos'],
                                mode='markers',
                                marker=dict(
                                    color=results_frame['Sharpe'],
                                    size=5,
                                    colorscale='Viridis',
                                    showscale=True,
                                    colorbar=dict(title='Sharpe Ratio')
                                ),
                                name='Simulovaná Portfolia'
                            ))
                            
                            fig_ef.add_trace(go.Scatter(
                                x=[min_vol_portfolio['Volatilita']], 
                                y=[min_vol_portfolio['Výnos']], 
                                mode='markers',
                                marker=dict(color='red', size=15, symbol='star'),
                                name='Minimální Riziko'
                            ))
                            
                            fig_ef.add_trace(go.Scatter(
                                x=[max_sharpe_portfolio['Volatilita']], 
                                y=[max_sharpe_portfolio['Výnos']], 
                                mode='markers',
                                marker=dict(color='lightgreen', size=15, symbol='star'),
                                name='Max Sharpe Ratio'
                            ))
                            
                            fig_ef.update_layout(
                                title='Efektivní Hranice',
                                xaxis_title='Volatilita (Riziko)',
                                yaxis_title='Očekávaný Roční Výnos',
                                template="plotly_dark",
                                hovermode='closest',
                                height=550,
                                font_family="Roboto Mono",
                                plot_bgcolor="rgba(0,0,0,0)",
                                paper_bgcolor="rgba(0,0,0,0)"
                            )
                            fig_ef.update_xaxes(showgrid=False)
                            fig_ef.update_yaxes(showgrid=True, gridcolor='#30363D')
                            st.plotly_chart(fig_ef, use_container_width=True, key="fig_ef_frontier")
                            add_download_button(fig_ef, "efektivni_hranice")
                            
                            st.divider()
                            c_ef1, c_ef2 = st.columns(2)
                            
                            with c_ef1:
                                st.success("🟢 OPTIMÁLNÍ SHARPE RATIO PORTFOLIO (Max. výnos k riziku)")
                                st.metric("Sharpe Ratio", f"{max_sharpe_portfolio['Sharpe']:.2f}")
                                st.metric("Roční výnos", f"{max_sharpe_portfolio['Výnos'] * 100:.2f} %")
                                st.metric("Roční riziko (Volatilita)", f"{max_sharpe_portfolio['Volatilita'] * 100:.2f} %")
                                st.markdown("**Doporučené váhy:**")
                                max_sharpe_weights_df = max_sharpe_portfolio[tickers_for_ef].to_frame(name="Váha (%)").T.copy()
                                max_sharpe_weights_df.index = ['Doporučená váha']
                                st.dataframe(
                                    max_sharpe_weights_df.T.style.format({"Váha (%)": "{:.1%}"}), 
                                    use_container_width=True, 
                                    hide_index=False
                                )
                                
                            with c_ef2:
                                st.error("🔴 MINIMÁLNÍ RIZIKO PORTFOLIO (Nejnižší volatilita)")
                                st.metric("Sharpe Ratio", f"{min_vol_portfolio['Sharpe']:.2f}")
                                st.metric("Roční výnos", f"{min_vol_portfolio['Výnos'] * 100:.2f} %")
                                st.metric("Roční riziko (Volatilita)", f"{min_vol_portfolio['Volatilita'] * 100:.2f} %")
                                st.markdown("**Doporučené váhy:**")
                                min_vol_weights_df = min_vol_portfolio[tickers_for_ef].to_frame(name="Váha (%)").T.copy()
                                min_vol_weights_df.index = ['Doporučená váha']
                                st.dataframe(
                                    min_vol_weights_df.T.style.format({"Váha (%)": "{:.1%}"}), 
                                    use_container_width=True, 
                                    hide_index=False
                                )

                    except ValueError:
                        pass 
                    except Exception as e:
                        st.error(f"Při simulaci došlo k neočekávané chybě: {e}")
                        
            st.divider()
            st.subheader("🔮 Složené úročení (Původní funkce)")
            
            col_v1, col_v2 = st.columns([1, 2])
            with col_v1:
                vklad = st.number_input("Měsíční vklad (Kč)", value=5000, step=500, key="vklad_orig")
                roky = st.slider("Počet let", 5, 40, 15, key="roky_orig")
                urok = st.slider("Očekávaný úrok p.a. (%)", 1.0, 15.0, 8.0, key="urok_orig")
            with col_v2:
                data_budoucnost = []; aktualni_hodnota = celk_hod_czk; vlozeno = celk_hod_czk
                for r in range(1, roky + 1):
                    rocni_vklad = vklad * 12; vlozeno += rocni_vklad
                    aktualni_hodnota = (aktualni_hodnota + rocni_vklad) * (1 + urok/100)
                    data_budoucnost.append({"Rok": datetime.now().year + r, "Hodnota": round(aktualni_hodnota), "Vklady": round(vlozeno)})
                st.area_chart(pd.DataFrame(data_budoucnost).set_index("Rok"), color=["#00FF00", "#333333"])
                st.metric(f"Hodnota v roce {datetime.now().year + roky}", f"{aktualni_hodnota:,.0f} Kč", f"Zisk: {aktualni_hodnota - vlozeno:,.0f} Kč")
            
            st.divider()
            st.subheader("🎲 MONTE CARLO: Simulace budoucnosti (Původní funkce)")
            st.info("Simulace 50 možných scénářů vývoje tvého portfolia na základě volatility trhu.")
            c_mc1, c_mc2 = st.columns(2)
            with c_mc1:
                mc_years = st.slider("Délka simulace (roky)", 1, 20, 5, key="mc_years")
                mc_volatility = st.slider("Očekávaná volatilita (%)", 5, 50, 20, key="mc_vol") / 100
            with c_mc2:
                mc_return = st.slider("Očekávaný výnos p.a. (%)", -5, 20, 8, key="mc_ret") / 100
                start_val = celk_hod_czk if celk_hod_czk > 0 else 100000 
            if st.button("🔮 SPUSTIT SIMULACI", key="run_mc", type="primary"):
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
                fig_mc.update_layout(title=f"Monte Carlo: {num_simulations} scénářů na {mc_years} let", xaxis_title="Dny", yaxis_title="Hodnota (CZK)", template="plotly_dark", font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                fig_mc.update_xaxes(showgrid=False)
                fig_mc.update_yaxes(showgrid=True, gridcolor='#30363D')
                st.plotly_chart(fig_mc, use_container_width=True)
                st.success(f"Průměrná hodnota na konci: {sim_data['Average'].iloc[-1]:,.0f} Kč")

            st.divider()
            st.subheader("💥 CRASH TEST")
            with st.container(border=True):
                propad = st.slider("Simulace pádu trhu (%)", 5, 80, 20, step=5, key="crash_slider")
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
                
                my_returns = user_df['TotalUSD'].pct_change().dropna()
                my_sharpe = calculate_sharpe_ratio(my_returns)
                
                try:
                    sp500 = yf.download("^GSPC", start=start_date, progress=False)
                    if not sp500.empty:
                        if isinstance(sp500.columns, pd.MultiIndex): close_col = sp500['Close'].iloc[:, 0]
                        else: close_col = sp500['Close']
                        sp500_start = close_col.iloc[0]
                        sp500_norm = ((close_col / sp500_start) - 1) * 100
                        
                        sp500_returns = close_col.pct_change().dropna()
                        sp500_sharpe = calculate_sharpe_ratio(sp500_returns)
                        
                        fig_bench = go.Figure()
                        fig_bench.add_trace(go.Scatter(x=user_df.index, y=user_df['MyReturn'], mode='lines', name='Moje Portfolio', line=dict(color='#00CC96', width=3)))
                        fig_bench.add_trace(go.Scatter(x=sp500_norm.index, y=sp500_norm, mode='lines', name='S&P 500', line=dict(color='#808080', width=2, dash='dot')))
                        fig_bench.update_layout(title="Výkonnost v % od začátku měření", xaxis_title="", yaxis_title="Změna (%)", template="plotly_dark", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01), font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                        fig_bench.update_xaxes(showgrid=False)
                        fig_bench.update_yaxes(showgrid=True, gridcolor='#30363D')
                        st.plotly_chart(fig_bench, use_container_width=True, key="fig_benchmark")
                        add_download_button(fig_bench, "benchmark_analyza")
                        
                        my_last = user_df['MyReturn'].iloc[-1]; sp_last = sp500_norm.iloc[-1]; diff = my_last - sp_last
                        c_b1, c_b2, c_b3, c_b4 = st.columns(4)
                        
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
                    else: assets_by_curr["USD"] += item['HodnotaUSD'] 
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
            fig_curr.update_layout(barmode='group', template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0), font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            fig_curr.update_xaxes(showgrid=False)
            fig_curr.update_yaxes(showgrid=True, gridcolor='#30363D')
            st.plotly_chart(fig_curr, use_container_width=True)
        
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
                            fig_corr.update_layout(template="plotly_dark", height=600, font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig_corr, use_container_width=True)
                            avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix.values, 1)].mean()
                            st.metric("Průměrná korelace portfolia", f"{avg_corr:.2f}")
                            if avg_corr > 0.7: st.error("⚠️ Vysoká korelace! Tvé akcie se hýbou stejně.")
                            elif avg_corr < 0.3: st.success("✅ Nízká korelace! Dobrá diverzifikace.")
                            else: st.warning("⚖️ Střední korelace. Portfolio je vyvážené.")
                    except Exception as e: st.error(f"Chyba při výpočtu korelace: {e}")
                else: st.warning("Pro výpočet korelace potřebuješ alespoň 2 různé akcie.")
            else: st.info("Portfolio je prázdné.")

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

    with st.expander("🤖 AI ASISTENT", expanded=st.session_state.get('chat_expanded', False)):
        st.markdown('<span id="floating-bot-anchor"></span>', unsafe_allow_html=True)
        
        # --- NOVÉ: Tlačítko pro vymazání paměti ---
        c_clear, _ = st.columns([1, 2])
        with c_clear:
            if st.button("🧹 Nová konverzace", key="clear_chat"):
                st.session_state["chat_messages"] = [{"role": "assistant", "content": "Paměť vymazána. O čem se chceš bavit teď? 🧠"}]
                st.rerun()
        # ------------------------------------------

        if "chat_messages" not in st.session_state: st.session_state["chat_messages"] = [{"role": "assistant", "content": "Ahoj! Jsem tvůj AI průvodce. Co pro tebe mohu udělat?"}]
        for msg in st.session_state["chat_messages"]: st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("Zeptej se..."):
            if not AI_AVAILABLE: st.error("Chybí API klíč.")
            else: st.session_state["chat_messages"].append({"role": "user", "content": prompt}); st.rerun()
        if st.session_state["chat_messages"][-1]["role"] == "user":
            with st.spinner("Přemýšlím..."):
                last_user_msg = st.session_state["chat_messages"][-1]["content"]
                
                # --- VYLEPŠENÝ KONTEXT (Market Awareness) ---
                portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
                if viz_data: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data])
                
                # Přidání tržních dat do promptu (Fear & Greed)
                fg_score, fg_rating = ziskej_fear_greed()
                if fg_score:
                    portfolio_context += f"\nAktuální tržní nálada (Fear & Greed Index): {fg_score} ({fg_rating}). Pokud je strach (pod 40), zmiň příležitost k nákupu. Pokud chamtivost (nad 75), varuj před rizikem."
                
                # Přidání sentimentu zpráv (pokud existuje analýza)
                ai_news = st.session_state.get('ai_news_analysis', {})
                if ai_news:
                    avg_sentiment = sum([v['score'] for v in ai_news.values()]) / len(ai_news) if len(ai_news) > 0 else 50
                    sentiment_str = "Pozitivní" if avg_sentiment > 60 else ("Negativní" if avg_sentiment < 40 else "Neutrální")
                    portfolio_context += f"\nAnalýza posledních zpráv vyznívá: {sentiment_str} (Skóre {avg_sentiment:.0f}/100)."
                # ---------------------------------------------

                full_prompt = f"{APP_MANUAL}\n\nDATA A TRŽNÍ KONTEXT:\n{portfolio_context}\n\nDOTAZ UŽIVATELE: {last_user_msg}"
                try: response = AI_MODEL.generate_content(full_prompt); ai_reply = response.text
                except Exception as e: ai_reply = f"Chyba: {str(e)}"
                st.session_state["chat_messages"].append({"role": "assistant", "content": ai_reply}); st.rerun()

if __name__ == "__main__":
    main()

