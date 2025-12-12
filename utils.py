import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import feedparser
import smtplib
from email.mime.text import MIMEText
from fpdf import FPDF
from datetime import datetime
import pytz
import plotly.graph_objects as go
import matplotlib.pyplot as plt

# --- ODSTRANĚN IMPORT Z DATA_MANAGER (Abychom předešli kruhové chybě) ---
# RISK_FREE_RATE si načteme lokálně uvnitř funkce, která ho potřebuje.

# --- ZDROJE ZPRÁV ---
RSS_ZDROJE = [
    "https://news.google.com/rss/search?q=akcie+burza+ekonomika&hl=cs&gl=CZ&ceid=CZ:cs",
    "https://servis.idnes.cz/rss.aspx?c=ekonomika", 
    "https://www.investicniweb.cz/rss"
]

# --- EXTERNÍ DATA (ZÁKLADNÍ FUNKCE) ---

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

@st.cache_data(ttl=86400)
def ziskej_earnings_datum(ticker):
    try:
        t = yf.Ticker(str(ticker))
        cal = t.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if dates:
                return dates[0]
    except Exception:
        pass
    return None

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
        'website': info.get('website', ''),
        'profitMargins': info.get('profitMargins', 0),
        'returnOnEquity': info.get('returnOnEquity', 0),
        'revenueGrowth': info.get('revenueGrowth', 0),
        'debtToEquity': info.get('debtToEquity', 0),
        'quickRatio': info.get('quickRatio', 0),
        'numberOfAnalystOpinions': info.get('numberOfAnalystOpinions', 0),
        'heldPercentInsiders': info.get('heldPercentInsiders', 0),
        'heldPercentInstitutions': info.get('heldPercentInstitutions', 0)
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
                "website": "",
                "profitMargins": 0, "returnOnEquity": 0, "revenueGrowth": 0, "debtToEquity": 0, "quickRatio": 0, "numberOfAnalystOpinions": 0,
                "heldPercentInsiders": 0, "heldPercentInstitutions": 0
            }
        except:
            info = {
                "longName": ticker, 
                "currency": "USD", 
                "currentPrice": 0, 
                "longBusinessSummary": "Data nedostupná.",
                "trailingPE": 0,
                "marketCap": 0,
                "profitMargins": 0, "returnOnEquity": 0, "revenueGrowth": 0, "debtToEquity": 0, "quickRatio": 0, "numberOfAnalystOpinions": 0,
                "heldPercentInsiders": 0, "heldPercentInstitutions": 0
            }

    hist = _ziskej_historii_cached(ticker)
    return info, hist

# --- POMOCNÁ FUNKCE PRO TRŽNÍ HODINY ---
def zjisti_stav_trhu(timezone_str, open_hour, close_hour):
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        is_open = False
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

@st.cache_data(ttl=300) # 5 minut cache pro live ceny
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

# --- FINANČNÍ FUNKCE (Zde jsme upravili import) ---
def calculate_sharpe_ratio(returns, risk_free_rate=None, periods_per_year=252):
    # Bezpečný import uvnitř funkce, aby se soubory nehádaly na začátku
    if risk_free_rate is None:
        try:
            from data_manager import RISK_FREE_RATE
            risk_free_rate = RISK_FREE_RATE
        except ImportError:
            risk_free_rate = 0.04 # Fallback, kdyby import selhal
            
    if returns.empty or returns.std() == 0:
        return 0.0
    daily_risk_free_rate = risk_free_rate / periods_per_year
    excess_returns = returns - daily_risk_free_rate
    sharpe_ratio = np.sqrt(periods_per_year) * (excess_returns.mean() / returns.std())
    return sharpe_ratio

# --- 1. STYLOVÁNÍ PRO PLOTLY ---
def make_plotly_cyberpunk(fig):
    neon_green = "#00FF99"
    dark_bg = "rgba(0,0,0,0)"
    grid_color = "#30363D"
    try:
        fig.update_layout(
            paper_bgcolor=dark_bg, plot_bgcolor=dark_bg, font=dict(color=neon_green, family="Courier New"),
            xaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color, showline=True, linecolor=grid_color),
            yaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color, showline=True, linecolor=grid_color),
            legend=dict(bgcolor=dark_bg, bordercolor=grid_color, borderwidth=1), hovermode="x unified"
        )
    except Exception: pass
    return fig

# --- 2. STYLOVÁNÍ PRO MATPLOTLIB ---
def make_matplotlib_cyberpunk(fig, ax):
    neon_green = "#00FF99"
    dark_bg = "#0E1117"
    text_color = "#00FF99"
    grid_color = "#30363D"
    fig.patch.set_facecolor(dark_bg)
    ax.set_facecolor(dark_bg)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)
    ax.title.set_color(text_color)
    ax.tick_params(axis='x', colors=text_color)
    ax.tick_params(axis='y', colors=text_color)
    for spine in ax.spines.values(): spine.set_edgecolor(grid_color)
    ax.grid(True, color=grid_color, linestyle='--', linewidth=0.5, alpha=0.5)
    return fig

# =========================================================
# 👇 BRIDGE (MŮSTEK) - ZAJIŠTĚNÍ FUNKČNOSTI 👇
# =========================================================
cached_ceny_hromadne = ziskej_ceny_hromadne
cached_kurzy = ziskej_kurzy
cached_fear_greed = ziskej_fear_greed
cached_zpravy = ziskej_zpravy

@st.cache_data(ttl=3600)
def cached_detail_akcie(ticker):
    return ziskej_detail_akcie(ticker)
