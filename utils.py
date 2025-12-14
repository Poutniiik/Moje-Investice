import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import json
import feedparser
import smtplib
from email.mime.text import MIMEText
from fpdf import FPDF
from datetime import datetime
import pytz
import plotly.graph_objects as go
import matplotlib.pyplot as plt
# Importujeme konstantu z data_manageru, abychom ji nemuseli definovat znovu
from data_manager import RISK_FREE_RATE 

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

import json # Přidej nahoru k importům, pokud tam není

# ... (ostatní kód) ...

@st.cache_data(ttl=3600)
def ziskej_ceny_hromadne(tickers):
    """
    Verze TURBO (Opravená): Načte i kurzy měn z JSONu od robota.
    """
    data = {}
    
    # 1. ZKUSÍME NAČÍST DATA OD ROBOTA (z cache souboru)
    try:
        # Použijeme absolutní cestu nebo relativní - záleží kde běží appka, 
        # ale 'market_cache.json' by měl být ve stejné složce.
        with open("market_cache.json", "r") as f:
            cache = json.load(f)
            cached_prices = cache.get("prices", {})
            
            # --- TADY JE TA OPRAVA PRO LIŠTU ---
            # Vytáhneme kurzy, které leží v JSONu mimo složku "prices"
            usd_czk = cache.get("usd_czk")
            if usd_czk:
                data["USD/CZK"] = {"price": usd_czk, "curr": "CZK"}
            
            eur_usd = cache.get("eur_usd")
            if eur_usd:
                data["EUR/USD"] = {"price": eur_usd, "curr": "USD"}
            # -----------------------------------
            
            # Teď načteme klasické akcie
            if tickers:
                for t in tickers:
                    if t in cached_prices:
                        p_info = cached_prices[t]
                        price = p_info.get("price", 0)
                        
                        # Určení měny
                        curr = "USD"
                        if ".PR" in str(t): curr = "CZK"
                        elif ".DE" in str(t): curr = "EUR"
                        
                        if price > 0:
                            data[t] = {"price": price, "curr": curr}
            
            # Pokud máme data (aspoň něco), vracíme je a končíme.
            if len(data) > 0:
                print("🚀 Použita TURBO cache (včetně měn).")
                return data

    except Exception as e:
        print(f"⚠️ Cache cache nenalezena, jedu postaru: {e}")

    # 2. POKUD SOUBOR NENÍ, JEDEME POSTARU (Záloha přes Yahoo)
    # (Tohle se spustí jen když selže načtení JSONu)
    search_list = list(set((tickers if tickers else []) + ["CZK=X", "EURUSD=X"]))
    for t in search_list:
        try:
            stock = yf.Ticker(t)
            price = 0.0
            try: price = float(stock.fast_info.last_price)
            except: pass
            
            if not price:
                try: 
                    hist = stock.history(period="5d", auto_adjust=True)
                    price = float(hist['Close'].iloc[-1])
                except: pass
            
            curr = "USD"
            label = t 
            
            if ".PR" in str(t): curr = "CZK"
            elif ".DE" in str(t): curr = "EUR"
            elif "CZK=X" in str(t): 
                curr = "CZK"
                label = "USD/CZK"
            elif "EURUSD=X" in str(t): 
                curr = "USD"
                label = "EUR/USD"
            
            if price > 0:
                data[label] = {"price": price, "curr": curr}
        except: pass
            
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

# --- FINANČNÍ FUNKCE ---
def calculate_sharpe_ratio(returns, risk_free_rate=RISK_FREE_RATE, periods_per_year=252):
    if returns.empty or returns.std() == 0:
        return 0.0
    daily_risk_free_rate = risk_free_rate / periods_per_year
    excess_returns = returns - daily_risk_free_rate
    sharpe_ratio = np.sqrt(periods_per_year) * (excess_returns.mean() / returns.std())
    return sharpe_ratio

# --- 1. STYLOVÁNÍ PRO PLOTLY (Interaktivní) ---
def make_plotly_cyberpunk(fig):
    """Aplikuje Cyberpunk skin na Plotly graf bezpečně podle typu trace."""
    neon_green = "#00FF99"
    dark_bg = "rgba(0,0,0,0)"
    grid_color = "#30363D"

    # Layout styling (bezpečné, univerzální)
    try:
        fig.update_layout(
            paper_bgcolor=dark_bg,
            plot_bgcolor=dark_bg,
            font=dict(color=neon_green, family="Courier New"),
            xaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color, showline=True, linecolor=grid_color),
            yaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color, showline=True, linecolor=grid_color),
            legend=dict(bgcolor=dark_bg, bordercolor=grid_color, borderwidth=1),
            hovermode="x unified"
        )
    except Exception:
        pass

    # Aplikuj styl selektivně podle typu trace
    try:
        for t in fig.data:
            t_type = getattr(t, "type", None)

            # PIE: obrys se nastavuje přes marker.line
            if t_type == "pie":
                try:
                    current_marker = dict(t.marker) if getattr(t, "marker", None) is not None else {}
                    current_marker["line"] = dict(width=3, color=neon_green)
                    t.marker = current_marker
                except Exception:
                    try:
                        t.marker = {"line": dict(width=3, color=neon_green)}
                    except Exception:
                        pass

            # Trace, které běžně podporují line
            elif t_type in ("scatter", "bar", "line", "ohlc", "candlestick"):
                try:
                    t.line = dict(width=3, color=neon_green)
                except Exception:
                    pass

            # Fallback: pokud má trace marker, pokusíme se nastavit marker.line
            else:
                try:
                    if hasattr(t, "marker"):
                        m = dict(t.marker) if getattr(t, "marker", None) is not None else {}
                        m["line"] = dict(width=3, color=neon_green)
                        t.marker = m
                except Exception:
                    pass
    except Exception:
        pass

    return fig

# --- 2. STYLOVÁNÍ PRO MATPLOTLIB (Statické) ---
def make_matplotlib_cyberpunk(fig, ax):
    """Aplikuje Cyberpunk skin na Matplotlib Figure a Axes."""
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

    for spine in ax.spines.values():
        spine.set_edgecolor(grid_color)

    ax.grid(True, color=grid_color, linestyle='--', linewidth=0.5, alpha=0.5)
    
    return fig
