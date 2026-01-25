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
import unicodedata  # Důležité pro odstranění háčků v PDF

# Importujeme konstantu z data_manageru
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

# --- INSIDER TRADING (ŠPIONÁŽ) ---
@st.cache_data(ttl=3600*12) # Stačí aktualizovat 1x za 12 hodin
def ziskej_insider_transakce(ticker):
    """
    Stáhne seznam transakcí, které provedli manažeři firmy (Insiders).
    """
    try:
        t = yf.Ticker(ticker)
        insiders = t.insider_transactions
        
        if insiders is None or insiders.empty:
            return None
            
        # 1. Seřadíme od nejnovějších
        insiders = insiders.sort_values(by='Start Date', ascending=False)
        
        # 2. Vybereme jen to důležité (Datum, Kdo, Pozice, Akce, Počet, Hodnota)
        # yfinance vrací sloupce anglicky, přejmenujeme je pro hezký vzhled
        df_clean = insiders[['Start Date', 'Insider', 'Position', 'Shares', 'Value', 'Text']].copy()
        
        # Ošetření, aby to nepadalo na chybějících datech
        df_clean['Shares'] = df_clean['Shares'].fillna(0).astype(int)
        df_clean['Value'] = df_clean['Value'].fillna(0).astype(float)
        
        # Přejmenování sloupců do češtiny
        df_clean.columns = ['Datum', 'Jméno', 'Pozice', 'Počet akcií', 'Hodnota ($)', 'Popis transakce']
        
        # Ořízneme datum jen na den (bez času)
        df_clean['Datum'] = df_clean['Datum'].dt.strftime('%d.%m.%Y')
        
        return df_clean.head(15) # Vrátíme posledních 15 pohybů
    except Exception as e:
        # print(f"Chyba insider: {e}")
        return None

# ==========================================
# 📄 NOVÝ GENERÁTOR PROFI PDF (EXECUTIVE)
# ==========================================
def clean_text(text):
    """Odstraní diakritiku, aby PDF nepadalo."""
    if not isinstance(text, str): text = str(text)
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

class PDF(FPDF):
    def header(self):
        # Černé záhlaví
        self.set_fill_color(20, 20, 20) 
        self.rect(0, 0, 210, 40, 'F')
        # Nadpis
        self.set_font('Arial', 'B', 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 25, 'INVESTICNI REPORT', 0, 1, 'C')
        # Podnadpis
        self.set_font('Arial', '', 10)
        self.set_text_color(150, 150, 150)
        self.cell(0, -10, f'Terminal PRO | Uzivatel: {clean_text(self.user_name)}', 0, 1, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Strana {self.page_no()}', 0, 0, 'C')

def vygeneruj_profi_pdf(user, df, total_val, cash, profit):
    """
    Funkce, která vytvoří luxusní PDF report s AGREGACÍ pozic.
    """
    # --- 1. ZDE JE TA MAGIE (AGREGÁTOR) ---
    # Než začneme tisknout, sloučíme řádky se stejným Tickerem
    if not df.empty:
        # Převedeme sloupce na čísla, aby to matematika pobrala
        df['Pocet'] = pd.to_numeric(df['Pocet'])
        df['Cena'] = pd.to_numeric(df['Cena'])
        
        # Vypočítáme celkovou investici pro každý řádek (Kusy * Cena)
        df['Celkem_Investice'] = df['Pocet'] * df['Cena']
        
        # Seskupíme podle Tickeru
        df_agreg = df.groupby('Ticker').agg({
            'Pocet': 'sum',             # Kusy sečteme (1 + 1 + 1 = 3)
            'Celkem_Investice': 'sum'   # Peníze sečteme
        }).reset_index()
        
        # Dopočítáme průměrnou nákupní cenu (Celkem peníze / Celkem kusy)
        df_agreg['Cena'] = df_agreg['Celkem_Investice'] / df_agreg['Pocet']
        
        # Použijeme tato nová, čistá data pro tisk!
        data_pro_tisk = df_agreg
    else:
        data_pro_tisk = df

    # --- 2. ZBYTEK JE TVŮJ PŮVODNÍ KÓD (JEN MÍSTO 'df' POUŽÍVÁM 'data_pro_tisk') ---
    
    pdf = PDF()
    pdf.user_name = user
    pdf.add_page()

    # 1. VELKÁ ČÍSLA (DASHBOARD)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, 'FINANCNI SOUHRN', 0, 1, 'L')
    pdf.line(10, 55, 200, 55)
    pdf.ln(5)

    # Hodnota portfolia
    pdf.set_font('Arial', '', 10)
    pdf.cell(50, 10, "CELKOVA HODNOTA:", 0, 0)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(50, 10, f"{total_val:,.0f} CZK", 0, 1)

    # Hotovost
    pdf.set_font('Arial', '', 10)
    pdf.cell(50, 10, "VOLNA HOTOVOST:", 0, 0)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(50, 10, f"{cash:,.0f} USD", 0, 1)

    # Zisk (Barevně)
    pdf.set_font('Arial', '', 10)
    pdf.cell(50, 10, "CELKOVY ZISK:", 0, 0)
    pdf.set_font('Arial', 'B', 14)
    
    if profit >= 0:
        pdf.set_text_color(0, 150, 0) # Zelená
        prefix = "+"
    else:
        pdf.set_text_color(200, 0, 0) # Červená
        prefix = ""
    
    pdf.cell(50, 10, f"{prefix}{profit:,.0f} CZK", 0, 1)
    pdf.set_text_color(0, 0, 0) # Zpět na černou
    pdf.ln(10)

    # 2. TABULKA POZIC
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'DETAIL PORTFOLIA', 0, 1, 'L')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # Hlavička tabulky
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(40, 10, 'Ticker', 1, 0, 'C', fill=True)
    pdf.cell(40, 10, 'Kusy', 1, 0, 'C', fill=True)
    pdf.cell(40, 10, 'Nakup ($)', 1, 0, 'C', fill=True)
    pdf.cell(50, 10, 'Hodnota ($)', 1, 1, 'C', fill=True)

    # Data tabulky - TADY JE ZMĚNA: Iterujeme přes 'data_pro_tisk'
    pdf.set_font('Arial', '', 10)
    for _, row in data_pro_tisk.iterrows():
        if row['Pocet'] > 0:
            try:
                nakup_cena = float(row['Cena'])
                aktualni_hodnota = nakup_cena * float(row['Pocet']) 
            except:
                nakup_cena = 0; aktualni_hodnota = 0

            pdf.cell(40, 10, str(row['Ticker']), 1, 0, 'C')
            pdf.cell(40, 10, f"{row['Pocet']:.1f}", 1, 0, 'C') # Formátování kusů
            pdf.cell(40, 10, f"{nakup_cena:.2f}", 1, 0, 'R')
            pdf.cell(50, 10, f"{aktualni_hodnota:.2f}", 1, 1, 'R')

    return pdf.output(dest='S').encode('latin-1', errors='replace')


# --- EMAIL ---
def odeslat_email(prijemce, predmet, telo):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        msg = MIMEText(telo, 'html')
        msg['Subject'] = predmet
        msg['From'] = sender_email
        msg['To'] = prijemce
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            login = server.login(sender_email, sender_password)
            server.sendmail(sender_email, prijemce, msg.as_string())
        return True
    except Exception as e: return f"Chyba: {e}"

@st.cache_data(ttl=3600)
def ziskej_ceny_hromadne(tickers):
    """
    Verze TURBO HYBRID:
    1. Zkusí načíst ceny z 'market_cache.json' (vygenerovaný botem).
    2. Cokoliv nenajde v cache, stáhne živě z Yahoo.
    """
    data = {}
    missing_tickers = []
    
    # 1. ZKUSÍME NAČÍST CACHE
    try:
        with open("market_cache.json", "r") as f:
            cache = json.load(f)
            cached_prices = cache.get("prices", {})
            
            # Kurzy měn z cache
            usd_czk = cache.get("usd_czk")
            if usd_czk: data["USD/CZK"] = {"price": usd_czk, "curr": "CZK"}
            
            eur_usd = cache.get("eur_usd")
            if eur_usd: data["EUR/USD"] = {"price": eur_usd, "curr": "USD"}
            
            # Akcie z cache
            if tickers:
                for t in tickers:
                    if t in cached_prices:
                        p_info = cached_prices[t]
                        price = p_info.get("price", 0)
                        
                        # Měna
                        curr = "USD"
                        if ".PR" in str(t): curr = "CZK"
                        elif ".DE" in str(t): curr = "EUR"
                        
                        if price > 0:
                            data[t] = {"price": price, "curr": curr}
                    else:
                        missing_tickers.append(t)
            
            # Pokud cache pokryla vše, super!
            if not missing_tickers:
                return data

    except Exception:
        # Cache selhala nebo neexistuje -> musíme stáhnout vše
        missing_tickers = tickers if tickers else []

    # 2. DOSTÁHNOUT CHYBĚJÍCÍ (nebo vše, pokud cache nebyla)
    if "USD/CZK" not in data: missing_tickers.append("CZK=X")
    if "EUR/USD" not in data: missing_tickers.append("EURUSD=X")
    
    missing_tickers = list(set(missing_tickers))
    if not missing_tickers: return data

    try:
        batch = yf.download(missing_tickers, period="5d", group_by='ticker', progress=False)
        for t in missing_tickers:
            price = 0.0
            try:
                if len(missing_tickers) > 1:
                    if t in batch.columns.levels[0]:
                        series = batch[t]['Close'].dropna()
                        if not series.empty: price = float(series.iloc[-1])
                else:
                    series = batch['Close'].dropna()
                    if not series.empty: price = float(series.iloc[-1])
            except: pass
            
            if price == 0:
                try:
                    s = yf.Ticker(t)
                    price = float(s.fast_info.last_price)
                except: pass

            if price > 0:
                curr = "USD"
                label = t
                if ".PR" in str(t): curr = "CZK"
                elif ".DE" in str(t): curr = "EUR"
                elif "CZK=X" in str(t): curr = "CZK"; label = "USD/CZK"
                elif "EURUSD=X" in str(t): curr = "USD"; label = "EUR/USD"
                data[label] = {"price": price, "curr": curr}
                
    except Exception as e:
        print(f"Chyba při dotahování cen: {e}")
        
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

    try:
        for t in fig.data:
            t_type = getattr(t, "type", None)
            if t_type == "pie":
                try:
                    current_marker = dict(t.marker) if getattr(t, "marker", None) is not None else {}
                    current_marker["line"] = dict(width=3, color=neon_green)
                    t.marker = current_marker
                except Exception:
                    pass
            elif t_type in ("scatter", "bar", "line", "ohlc", "candlestick"):
                try:
                    t.line = dict(width=3, color=neon_green)
                except Exception:
                    pass
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

# --- POMOCNÁ FUNKCE SEKTORY ---
def ziskej_sektor_tickeru(ticker):
    """
    Zjistí, do jakého sektoru akcie patří.
    """
    try:
        if ticker.endswith(".PR"): return "Energy/Utilities (CZ)"
        
        t = yf.Ticker(ticker)
        sektor = t.info.get('sector', 'Neznámý')
        
        preklad = {
            "Technology": "Technologie",
            "Financial Services": "Finance",
            "Energy": "Energie",
            "Healthcare": "Zdravotnictví",
            "Consumer Cyclical": "Zbytné spotřební",
            "Industrials": "Průmysl",
            "Communication Services": "Komunikace"
        }
        return preklad.get(sektor, sektor)
    except:
        return "Neznámý"
