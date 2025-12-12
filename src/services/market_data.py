# Market data service
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import feedparser
from datetime import datetime
import pytz

# --- ZDROJE ZPRÁV ---
RSS_ZDROJE = [
    "https://news.google.com/rss/search?q=akcie+burza+ekonomika&hl=cs&gl=CZ&ceid=CZ:cs",
    "https://servis.idnes.cz/rss.aspx?c=ekonomika", 
    "https://www.investicniweb.cz/rss"
]

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
