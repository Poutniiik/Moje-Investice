import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
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
import plotly.graph_objects as go
import smtplib
from email.mime.text import MIMEText
from fpdf import FPDF
import extra_streamlit_components as stx

# --- KONFIGURACE ---
st.set_page_config(page_title="Terminal Pro", layout="wide", page_icon="💹")

# --- KONSTANTY ---
REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv"
SOUBOR_WATCHLIST = "watchlist.csv"
SOUBOR_DIVIDENDY = "dividends.csv"

# --- ZDROJE ZPRÁV ---
RSS_ZDROJE = [
    "https://news.google.com/rss/search?q=akcie+burza+ekonomika&hl=cs&gl=CZ&ceid=CZ:cs",
    "https://servis.idnes.cz/rss.aspx?c=ekonomika", 
    "https://www.investicniweb.cz/rss"
]

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

# --- CÍLE PORTFOLIA ---
CILOVE_SEKTORY = {
    "Technologie": 30, "Energie": 20, "Spotřební zboží": 15,
    "Finance": 15, "Krypto": 10, "Ostatní": 10
}

# --- AI SETUP ---
try:
    if "google" in st.secrets:
        GOOGLE_API_KEY = st.secrets["google"]["api_key"]
        genai.configure(api_key=GOOGLE_API_KEY)
        AI_MODEL = genai.GenerativeModel('gemini-2.5-flash') 
        AI_AVAILABLE = True
    else:
        AI_AVAILABLE = False
except:
    AI_AVAILABLE = False

# --- STYLY ---
st.markdown("""
<style>
    .stApp {background-color: #0E1117; font-family: 'Roboto Mono', monospace;}
    div[data-testid="stMetric"] {background-color: #161B22; border: 1px solid #30363D; padding: 15px; border-radius: 5px; color: #E6EDF3;}
    div[data-testid="stMetricLabel"] {font-size: 0.9rem; color: #8B949E; font-weight: bold; text-transform: uppercase;}
    div[data-testid="stMetricValue"] {font-size: 1.5rem; color: #E6EDF3; font-weight: bold;}
    h1, h2, h3 {color: #E6EDF3 !important; font-family: 'Roboto Mono', monospace; text-transform: uppercase; letter-spacing: 1px;}
    div[data-testid="column"] button {border: 1px solid #FF4B4B; color: #FF4B4B;}
    div[data-testid="stTooltipIcon"] {color: #58A6FF;}
    a {text-decoration: none; color: #58A6FF !important;} 
</style>
""", unsafe_allow_html=True)

# --- PŘIPOJENÍ ---
try: 
    if "github" in st.secrets:
        GITHUB_TOKEN = st.secrets["github"]["token"]
    else:
        st.warning("⚠️ GitHub Token nenalezen v Secrets. Aplikace běží v demo režimu (bez ukládání).")
        GITHUB_TOKEN = ""
except: 
    st.error("❌ CHYBA: Problém s načtením Secrets!"); st.stop()

def get_repo(): 
    if not GITHUB_TOKEN: return None
    return Github(GITHUB_TOKEN).get_repo(REPO_NAZEV)

def zasifruj(text): return hashlib.sha256(str(text).encode()).hexdigest()

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
        datum = datetime.fromisoformat(data['fear_and_greed']['timestamp']).strftime("%d.%m. %H:%M")
        prev_score = int(data['fear_and_greed']['previous_close'])
        return score, rating, datum, prev_score
    except: return None, None, None, None

@st.cache_data(ttl=1800) 
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
        except: pass
    return news

@st.cache_data(ttl=86400)
def ziskej_yield(ticker):
    try:
        t = yf.Ticker(str(ticker))
        d = t.info.get('dividendYield')
        if d and d > 0.30: return d / 100 
        return d if d else 0
    except: return 0

@st.cache_data(ttl=3600)
def ziskej_detail_akcie(ticker):
    try:
        t = yf.Ticker(str(ticker))
        info = t.info
        hist = t.history(period="1y")
        return info, hist
    except: return None, None

# --- GENERÁTOR PDF ---
def vytvor_pdf_report(user, total_czk, cash_usd, data_list):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # Note: FPDF standard fonts usually don't support UTF-8 well without adding a font file.
    # Using simple ASCII for safety here or would need to add .ttf font
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"INVESTICNI REPORT: {user}", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"Celkove jmeni: {total_czk:,.0f} CZK", ln=True)
    pdf.cell(200, 10, txt=f"Hotovost: {cash_usd:,.0f} USD", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "Ticker", 1)
    pdf.cell(40, 10, "Kusy", 1)
    pdf.cell(40, 10, "Cena", 1)
    pdf.cell(40, 10, "Hodnota USD", 1)
    pdf.ln()
    pdf.set_font("Arial", size=10)
    for item in data_list:
        pdf.cell(40, 10, str(item['Ticker']), 1)
        pdf.cell(40, 10, f"{item['Kusy']:.2f}", 1)
        pdf.cell(40, 10, f"{item['Cena']:.2f}", 1)
        pdf.cell(40, 10, f"{item['HodnotaUSD']:.0f}", 1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- DATABÁZE ---
def uloz_csv(df, nazev_souboru, zprava):
    repo = get_repo()
    if not repo: return
    csv = df.to_csv(index=False)
    try:
        file = repo.get_contents(nazev_souboru)
        repo.update_file(file.path, zprava, csv, file.sha)
    except: repo.create_file(nazev_souboru, zprava, csv)

def nacti_csv(nazev_souboru):
    try:
        repo = get_repo()
        if not repo: raise Exception("No repo")
        file = repo.get_contents(nazev_souboru)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        for col in ['Datum', 'Date']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        for col in ['Pocet', 'Cena', 'Castka', 'Kusu', 'Prodejka', 'Zisk', 'TotalUSD', 'Investice', 'Target']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        if 'Sektor' not in df.columns and nazev_souboru == SOUBOR_DATA: df['Sektor'] = "Doplnit"
        if 'Poznamka' not in df.columns and nazev_souboru == SOUBOR_DATA: df['Poznamka'] = ""
        if nazev_souboru == SOUBOR_WATCHLIST and 'Target' not in df.columns: df['Target'] = 0.0
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        df['Owner'] = df['Owner'].astype(str)
        return df
    except:
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

def nacti_uzivatele(): return nacti_csv(SOUBOR_UZIVATELE)
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
    df_p = st.session_state['df'].copy(); df_h = st.session_state['df_hist'].copy()
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')
    if df_t.empty or df_t['Pocet'].sum() < kusy: return False, "Nedostatek kusů."
    zbyva, zisk, trzba = kusy, 0, kusy * cena
    for idx, row in df_t.iterrows():
        if zbyva <= 0: break
        ukrojeno = min(row['Pocet'], zbyva)
        zisk += (cena - row['Cena']) * ukrojeno
        if ukrojeno == row['Pocet']: df_p = df_p.drop(idx)
        else: df_p.at[idx, 'Pocet'] -= ukrojeno
        zbyva -= ukrojeno
    new_h = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_h = pd.concat([df_h, new_h], ignore_index=True)
    pohyb_penez(trzba, mena, "Prodej", f"Prodej {ticker}", user)
    st.session_state['df'] = df_p; st.session_state['df_hist'] = df_h
    uloz_data_uzivatele(df_p, user, SOUBOR_DATA); uloz_data_uzivatele(df_h, user, SOUBOR_HISTORIE)
    return True, f"Prodáno! +{trzba:,.2f}"
def odeslat_email(prijemce, predmet, telo):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        msg = MIMEText(telo, 'html'); msg['Subject'] = predmet; msg['From'] = sender_email; msg['To'] = prijemce
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password); server.sendmail(sender_email, prijemce, msg.as_string())
        return True
    except Exception as e: return f"Chyba: {e}"

@st.cache_data(ttl=900)
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
            except: pass
    except: pass
    return data

@st.cache_data(ttl=3600)
def ziskej_kurzy(): return {"USD": 1.0, "CZK": 20.85, "EUR": 1.16}

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
    except: return None, mena, 0

def proved_smenu(castka, z_meny, do_meny, user):
    kurzy = ziskej_kurzy()
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy["CZK"]
    elif z_meny == "EUR": castka_usd = castka * 1.16
    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurzy["CZK"]
    elif do_meny == "EUR": vysledna = castka_usd / 1.16
    pohyb_penez(-castka, z_meny, "Směna", f"Směna na {do_meny}", user)
    pohyb_penez(vysledna, do_meny, "Směna", f"Směna z {z_meny}", user)
    return True, f"Směněno: {vysledna:,.2f} {do_meny}"

def render_ticker_tape(data_dict):
    if not data_dict: return
    content = ""
    for ticker, info in data_dict.items():
        price = info.get('price', 0); curr = info.get('curr', '')
        content += f"&nbsp;&nbsp;&nbsp;&nbsp; <b>{ticker}</b>: {price:,.2f} {curr}"
    st.markdown(f"""<div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 5px; padding: 8px; margin-bottom: 20px; white-space: nowrap; overflow: hidden;"><div style="display: inline-block; animation: marquee 20s linear infinite; color: #00CC96; font-family: 'Roboto Mono', monospace; font-weight: bold;">{content} {content} {content}</div></div><style>@keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}</style>""", unsafe_allow_html=True)

# --- HLAVNÍ FUNKCE (S OPRAVENÝM LOGINEM) ---
def main():
    # 1. Start Cookie Manager
    cookie_manager = get_manager()
    
    # 2. Inicializace stavu (Session State)
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False
        st.session_state['user'] = ""
    
    # 3. ZPOŽDĚNÍ PRO COOKIES (Nutné pro stx)
    # Dej prohlížeči chvilku (300ms), aby poslal cookies zpět do Pythonu
    time.sleep(0.3)
    
    # 4. LOGIKA PŘIHLÁŠENÍ (Gatekeeper)
    # Pokud nejsme přihlášeni v paměti (session), zkusíme cookie
    if not st.session_state['prihlasen']:
        cookie_user = cookie_manager.get("invest_user")
        if cookie_user:
            st.session_state['prihlasen'] = True
            st.session_state['user'] = cookie_user
            st.rerun() # Refresh, aby se načetl zbytek appky jako přihlášený

    # --- ZOBRAZENÍ LOGIN FORMULÁŘE POKUD STÁLE NEJSME PŘIHLÁŠENI ---
    if not st.session_state['prihlasen']:
        c1,c2,c3 = st.columns([1, 2, 1])
        with c2:
            st.title("🔐 INVESTIČNÍ TERMINÁL")
            t1, t2, t3 = st.tabs(["PŘIHLÁŠENÍ", "REGISTRACE", "OBNOVA HESLA"])
            with t1:
                with st.form("l"):
                    u=st.text_input("Uživatelské jméno"); p=st.text_input("Heslo", type="password")
                    if st.form_submit_button("VSTOUPIT", use_container_width=True):
                        df_u = nacti_uzivatele()
                        row = df_u[df_u['username'] == u] if not df_u.empty else pd.DataFrame()
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            # ZÁPIS COOKIE S DELŠÍ ŽIVOTNOSTÍ
                            cookie_manager.set("invest_user", u, expires_at=datetime.now() + timedelta(days=30))
                            st.session_state.update({'prihlasen':True, 'user':u})
                            st.toast("Přihlašování...", icon="⏳")
                            time.sleep(1) # Čekáme na zápis cookie
                            st.rerun()
                        else: st.toast("Chyba přihlášení", icon="❌")
            with t2:
                with st.form("r"):
                    nu=st.text_input("Nové jméno"); np=st.text_input("Nové heslo", type="password"); 
                    nr=st.text_input("Záchranný kód", help="Slouží pro obnovu zapomenutého hesla.")
                    if st.form_submit_button("VYTVOŘIT ÚČET", use_container_width=True):
                        df_u = nacti_uzivatele()
                        if not df_u.empty and nu in df_u['username'].values: st.toast("Jméno již existuje.", icon="⚠️")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(np), "recovery_key": zasifruj(nr)}])
                            uloz_csv(pd.concat([df_u, new], ignore_index=True), SOUBOR_UZIVATELE, "New user"); st.toast("Účet vytvořen!", icon="✅")
            with t3:
                st.caption("Zapomněl jsi heslo?")
                with st.form("recovery"):
                    ru = st.text_input("Jméno"); rk = st.text_input("Záchranný kód"); rnp = st.text_input("Nové heslo", type="password")
                    if st.form_submit_button("OBNOVIT"):
                        df_u = nacti_uzivatele(); user_row = df_u[df_u['username'] == ru]
                        if not user_row.empty and user_row.iloc[0]['recovery_key'] == zasifruj(rk):
                            df_u.at[user_row.index[0], 'password'] = zasifruj(rnp)
                            uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}"); st.success("Heslo změněno!")
                        else: st.error("Chyba údajů.")
        return # UKONČÍME FUNKCI, ABY SE NENAČETL ZBYTEK APPKY

    # =========================================================================
    # ZDE ZAČÍNÁ APLIKACE PRO PŘIHLÁŠENÉHO UŽIVATELE
    # =========================================================================
    
    USER = st.session_state['user']
    
    # --- 2. NAČTENÍ DAT (VŽDY A HNED!) ---
    if 'df' not in st.session_state:
        with st.spinner("NAČÍTÁM DATA..."):
            st.session_state['df'] = nacti_csv(SOUBOR_DATA).query(f"Owner=='{USER}'").copy()
            st.session_state['df_hist'] = nacti_csv(SOUBOR_HISTORIE).query(f"Owner=='{USER}'").copy()
            st.session_state['df_cash'] = nacti_csv(SOUBOR_CASH).query(f"Owner=='{USER}'").copy()
            st.session_state['df_div'] = nacti_csv(SOUBOR_DIVIDENDY).query(f"Owner=='{USER}'").copy()
            st.session_state['df_watch'] = nacti_csv(SOUBOR_WATCHLIST).query(f"Owner=='{USER}'").copy()
            st.session_state['hist_vyvoje'] = aktualizuj_graf_vyvoje(USER, 0)

    df = st.session_state['df']; df_cash = st.session_state['df_cash']; df_div = st.session_state['df_div']; df_watch = st.session_state['df_watch']
    zustatky = get_zustatky(USER); kurzy = ziskej_kurzy()

    # --- 3. VÝPOČTY (HODNOTY PRO ROBOTA I STRÁNKY) ---
    all_tickers = []; viz_data = []; celk_hod_usd = 0; celk_inv_usd = 0; stats_meny = {}
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    LIVE_DATA = ziskej_ceny_hromadne(list(set(all_tickers)))
    if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
    if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]

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
            except: sektor = "Doplnit"
            
            nakupy_data = df[df['Ticker'] == tkr]['Datum']
            dnes = datetime.now(); limit_dni = 1095 
            vsechny_ok = True; vsechny_fail = True
            for d in nakupy_data:
                if (dnes - d).days < limit_dni: vsechny_ok = False 
                else: vsechny_fail = False 
            if vsechny_ok: dan_status = "🟢 Free"      
            elif vsechny_fail: dan_status = "🔴 Zdanit" 
            else: dan_status = "🟠 Mix" 
            
            div_vynos = ziskej_yield(tkr)
            hod = row['Pocet']*p; inv = row['Investice']; z = hod-inv
            try: k = 1.0 / kurzy.get("CZK", 20.85) if m=="CZK" else (kurzy.get("EUR", 1.16) if m=="EUR" else 1.0)
            except: k = 1.0
            
            celk_hod_usd += hod*k; celk_inv_usd += inv*k
            viz_data.append({
                "Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m, 
                "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Cena'], "Dan": dan_status, "Investice": inv, "Divi": div_vynos, "Dnes": d_zmena
            })

    hist_vyvoje = st.session_state['hist_vyvoje']
    if celk_hod_usd > 0 and pd.notnull(celk_hod_usd): hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    
    kurz_czk = kurzy.get("CZK", 20.85)
    celk_hod_czk = celk_hod_usd * kurz_czk
    celk_inv_czk = celk_inv_usd * kurz_czk
    zisk_czk = celk_hod_czk - celk_inv_czk
    zmena_24h = 0; pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if pd.notnull(vcera) and vcera > 0: zmena_24h = celk_hod_usd - vcera; pct_24h = (zmena_24h / vcera * 100)
    
    try: cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*1.16)
    except: cash_usd = 0

    # --- 4. SIDEBAR + CHATBOT ---
    with st.sidebar:
        st.header(f"👤 {USER.upper()}")
        if zustatky:
            st.caption("Stav peněženky:")
            for mena in ["USD", "CZK", "EUR"]:
                if mena in zustatky and zustatky[mena] > 0.01:
                    castka = zustatky[mena]
                    sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
                    st.info(f"**{castka:,.2f} {sym}**", icon="💰")
        else: st.warning("Peněženka prázdná")
        
        st.divider(); st.subheader("🧭 NAVIGACE")
        page = st.radio("Menu:", ["🏠 Přehled", "📈 Analýza", "📰 Zprávy", "💸 Obchod & Peníze", "💎 Dividendy", "⚙️ Správa Dat"], label_visibility="collapsed")
        
        # CHAT
        st.divider(); st.subheader("🤖 AI Průvodce")
        if "chat_messages" not in st.session_state: st.session_state["chat_messages"] = [{"role": "assistant", "content": "Ahoj! Jsem tvůj AI průvodce."}]
        with st.container(border=True, height=300):
            for msg in st.session_state["chat_messages"]: st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("Napiš dotaz..."):
            if not AI_AVAILABLE: st.error("Chybí API klíč.")
            else:
                st.session_state["chat_messages"].append({"role": "user", "content": prompt}); st.rerun()
        
        # Zpracování odpovědi
        if st.session_state["chat_messages"][-1]["role"] == "user":
            with st.spinner("..."):
                last_user_msg = st.session_state["chat_messages"][-1]["content"]
                portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
                if viz_data: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data])
                full_prompt = f"{APP_MANUAL}\n\nDATA:\n{portfolio_context}\n\nDOTAZ: {last_user_msg}"
                try:
                    response = AI_MODEL.generate_content(full_prompt)
                    ai_reply = response.text
                except Exception as e: ai_reply = f"Chyba: {str(e)}"
                st.session_state["chat_messages"].append({"role": "assistant", "content": ai_reply}); st.rerun()
        
        st.divider(); st.subheader("📧 RANNÍ REPORT")
        if st.button("Odeslat přehled na e-mail"):
            with st.spinner("Sepisuji zprávu..."):
                html_content = f"<h2>📈 Ranní přehled investora {USER}</h2><p>Jmění: {celk_hod_czk:,.0f} Kč<br>Zisk: {zisk_czk:+,.0f} Kč</p>"
                if viz_data:
                    df_s = pd.DataFrame(viz_data).sort_values(by="Dnes", ascending=False)
                    html_content += f"<p>🚀 <b>{df_s.iloc[0]['Ticker']}</b>: {df_s.iloc[0]['Dnes']:+.2%}</p>"
                score, _, _, _ = ziskej_fear_greed()
                if score: html_content += f"<p>😨 Nálada: {score}/100</p>"
                res = odeslat_email(st.secrets["email"]["sender"], "📈 Denní Report", html_content)
                if res == True: st.success("Odesláno! 📩"); st.balloons()
                else: st.error(f"Chyba: {res}")

        st.divider(); st.subheader("👀 WATCHLIST (Hlídač)")
        with st.expander("➕ Přidat hlídače", expanded=False):
            with st.form("w_add", clear_on_submit=True):
                new_w = st.text_input("Symbol").upper()
                target_w = st.number_input("Cílová cena", min_value=0.0, step=1.0)
                if st.form_submit_button("Sledovat"):
                    if new_w: pridat_do_watchlistu(new_w, target_w, USER); st.rerun()
        if not df_watch.empty:
            if 'Target' not in df_watch.columns: df_watch['Target'] = 0.0
            for idx, row in df_watch.iterrows():
                t = row['Ticker']; cilek = row['Target']
                info = LIVE_DATA.get(t, {})
                price = info.get('price'); curr = info.get('curr', '?')
                if not price:
                    try: p, m, _ = ziskej_info(t); price=p; curr=m
                    except: pass
                alert_icon = "🔥 SLEVA!" if price and cilek > 0 and price <= cilek else ""
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1: 
                        st.markdown(f"**{t}** {alert_icon}")
                        if price: 
                            st.markdown(f"### {price:,.2f} {curr}")
                            if cilek > 0: diff = ((price / cilek) - 1) * 100; st.caption(f"Cíl: {cilek:.0f} ({diff:+.1f}%)")
                        else: st.caption("Offline")
                    with c2: st.write(""); 
                    if st.button("❌", key=f"del_{t}"): odebrat_z_watchlistu(t, USER); st.rerun()
        
        st.divider()
        with st.expander("⚙️ Nastavení účtu"):
            with st.form("pass_change"):
                old = st.text_input("Staré", type="password"); new = st.text_input("Nové", type="password"); conf = st.text_input("Potvrdit", type="password")
                if st.form_submit_button("Změnit"):
                    df_u = nacti_uzivatele(); row = df_u[df_u['username'] == USER]
                    if not row.empty and row.iloc[0]['password'] == zasifruj(old):
                        if new == conf and len(new) > 0:
                            df_u.at[row.index[0], 'password'] = zasifruj(new); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Pass change {USER}"); st.success("Hotovo!")
                        else: st.error("Chyba v novém hesle.")
                    else: st.error("Staré heslo nesedí.")
        st.divider()
        if st.button("🚪 ODHLÁSIT", use_container_width=True): 
            # SMAZÁNÍ COOKIE A RESET
            cookie_manager.delete("invest_user")
            st.session_state.clear()
            st.rerun()

    # BĚŽÍCÍ PÁS
    if page == "🏠 Přehled" or page == "📈 Analýza":
        render_ticker_tape(LIVE_DATA)

    # --- 5. STRÁNKY ---
    if page == "🏠 Přehled":
        st.title(f"🏠 PŘEHLED: {USER.upper()}")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} Zisk")
        k2.metric("JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{zisk_czk:+,.0f} Kč")
        k3.metric("ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        k4.metric("HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné")
        
        st.write(""); 
        if viz_data:
            df_sort = pd.DataFrame(viz_data).sort_values(by="Dnes", ascending=False)
            best = df_sort.iloc[0]; worst = df_sort.iloc[-1]
            s1, s2 = st.columns(2)
            s1.success(f"🚀 TAHY DNE: **{best['Ticker']}** ({best['Dnes']:+.2%})")
            if worst['Dnes'] < 0: s2.error(f"🥀 ZÁTĚŽ DNE: **{worst['Ticker']}** ({worst['Dnes']:+.2%})")
            else: s2.info(f"🐢 NEJPOMALEJŠÍ: **{worst['Ticker']}** ({worst['Dnes']:+.2%})")

        st.write(""); st.subheader("🏆 SÍŇ SLÁVY")
        total_divi_czk = 0
        if not df_div.empty:
            for _, r in df_div.iterrows():
                m = r['Mena']; c = r['Castka']
                k = 20.85 if m == "USD" else (24.20 if m == "EUR" else 1.0)
                total_divi_czk += c * k
        o1, o2, o3, o4 = st.columns(4)
        if not df.empty: o1.success("🥉 **ZAČÁTEČNÍK**\n\nPrvní investice")
        else: o1.caption("🔒 Zamčeno\n\n(Kup první akcii)")
        pf = len(df['Ticker'].unique()) if not df.empty else 0
        if pf >= 3: o2.info(f"🥈 **STRATÉG**\n\n{pf} firem")
        else: o2.caption(f"🔒 Zamčeno\n\n({pf}/3 firem)")
        if celk_hod_czk > 100000: o3.warning("🥇 **BOHÁČ**\n\nJmění > 100k")
        else: o3.caption(f"🔒 Zamčeno\n\n({celk_hod_czk/1000:.0f}k / 100k)")
        if total_divi_czk > 500: o4.error("💎 **RENTIÉR**\n\nDivi > 500 Kč")
        else: o4.caption(f"🔒 Zamčeno\n\n({total_divi_czk:.0f} / 500 Kč)")

        st.divider()
        if viz_data:
            inv_usd = 0; inv_eur = 0; inv_czk = 0
            for item in viz_data:
                item_inv = item['Investice']
                if item['Měna'] == "USD": inv_usd += item_inv
                elif item['Měna'] == "EUR": inv_eur += item_inv
                elif item['Měna'] == "CZK": inv_czk += item_inv
            st.subheader("💰 INVESTOVANÝ KAPITÁL (Dle měny)")
            m1, m2, m3 = st.columns(3)
            m1.metric("Investováno USD", f"$ {inv_usd:,.0f}"); m2.metric("Investováno EUR", f"€ {inv_eur:,.0f}"); m3.metric("Investováno CZK", f"{inv_czk:,.0f} Kč")
        st.divider()
        st.subheader("📋 Detailní pozice")
        if viz_data:
            vdf = pd.DataFrame(viz_data)
            vdf_clean = vdf[vdf['HodnotaUSD'] > 0] 
            st.dataframe(vdf[["Ticker", "Měna", "Sektor", "Kusy", "Průměr", "Cena", "Dnes", "Hodnota", "Zisk", "Divi", "Dan"]].style.format({"Průměr": "{:.2f}", "Cena": "{:.2f}", "Hodnota": "{:,.0f}", "Zisk": "{:+,.0f}", "Divi": "{:.2%}", "Dnes": "{:+.2%}"}).background_gradient(cmap="RdYlGn", subset=["Zisk", "Dnes"], vmin=-0.05, vmax=0.05), use_container_width=True)
            
            st.divider()
            pdf_val = vytvor_pdf_report(USER, celk_hod_czk, cash_usd, viz_data)
            st.download_button("📄 STÁHNOUT PDF REPORT", data=pdf_val, file_name="report.pdf", mime="application/pdf")
            
        else: st.info("Portfolio je prázdné.")

    elif page == "📈 Analýza":
        st.title("📈 HLOUBKOVÁ ANALÝZA")
        if not df.empty:
            st.write("")
            with st.expander("🔍 RENTGEN AKCIE (Detail + Graf)", expanded=False):
                vybrana_akcie = st.selectbox("Vyber firmu:", df['Ticker'].unique())
                if vybrana_akcie:
                    with st.spinner(f"Načítám data pro {vybrana_akcie}..."):
                        t_info, hist_data = ziskej_detail_akcie(vybrana_akcie)
                        if t_info:
                            try:
                                long_name = t_info.get('longName', vybrana_akcie)
                                summary = t_info.get('longBusinessSummary', 'Popis nedostupný.')
                                recommendation = t_info.get('recommendationKey', 'Neznámé').upper().replace('_', ' ')
                                target_price = t_info.get('targetMeanPrice', 0)
                                pe_ratio = t_info.get('trailingPE', 0)
                                currency = t_info.get('currency', '?')
                                current_price = t_info.get('currentPrice', 0)
                                year_high = t_info.get('fiftyTwoWeekHigh', 0)
                                year_low = t_info.get('fiftyTwoWeekLow', 0)
                                c_d1, c_d2 = st.columns([1, 3])
                                with c_d1:
                                    barva_rec = "green" if "BUY" in recommendation else ("red" if "SELL" in recommendation else "orange")
                                    st.markdown(f"### :{barva_rec}[{recommendation}]"); st.caption("Názor analytiků")
                                    st.metric("Cílová cena", f"{target_price} {currency}"); st.metric("P/E Ratio", f"{pe_ratio:.2f}")
                                with c_d2:
                                    st.subheader(long_name); st.info(summary[:400] + "...")
                                    if t_info.get('website'): st.link_button("🌍 Web firmy", t_info.get('website'))
                                    
                                    st.write(""); st.caption("📝 Můj Investiční Deník")
                                    akt_poznamka = ""
                                    row_idx = df[df['Ticker'] == vybrana_akcie].index
                                    if not row_idx.empty:
                                        raw_note = df.at[row_idx[0], 'Poznamka']
                                        if pd.notnull(raw_note): akt_poznamka = str(raw_note)
                                    new_note = st.text_area("Proč to držím?", value=akt_poznamka, key=f"note_{vybrana_akcie}")
                                    if new_note != akt_poznamka:
                                        df.at[row_idx[0], 'Poznamka'] = new_note
                                        st.session_state['df'] = df; uloz_data_uzivatele(df, USER, SOUBOR_DATA); st.toast("Poznámka uložena! 💾")

                                st.subheader(f"📈 Cenový vývoj: {vybrana_akcie}")
                                if hist_data is not None and not hist_data.empty:
                                    fig_candle = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], name=vybrana_akcie)])
                                    moje_nakupka = 0
                                    for item in viz_data:
                                        if item['Ticker'] == vybrana_akcie: moje_nakupka = item['Průměr']; break
                                    if moje_nakupka > 0: fig_candle.add_hline(y=moje_nakupka, line_dash="dash", line_color="cyan", annotation_text=f"Moje nákupka: {moje_nakupka:.2f}")
                                    fig_candle.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=400, margin=dict(l=0, r=0, t=30, b=0))
                                    st.plotly_chart(fig_candle, use_container_width=True)
                                else: st.warning("Graf se nepodařilo načíst.")
                            except Exception as e: st.error(f"Chyba rentgenu: {e}")
                        else: st.warning("Yahoo neodpovídá, zkus to později.")
        st.divider()
        st.subheader("⚔️ SOUBOJ AKCIÍ")
        c_f1, c_f2 = st.columns(2)
        with c_f1: t1 = st.text_input("Bojovník 1", "AAPL").upper()
        with c_f2: t2 = st.text_input("Bojovník 2", "MSFT").upper()
        
        if st.button("SROVNAT"):
            if t1 and t2:
                with st.spinner("Probíhá analýza..."):
                    i1, h1 = ziskej_detail_akcie(t1)
                    i2, h2 = ziskej_detail_akcie(t2)
                    
                    if i1 and i2:
                        # Metriky
                        mc1 = i1.get('marketCap', 0); mc2 = i2.get('marketCap', 0)
                        pe1 = i1.get('trailingPE', 0); pe2 = i2.get('trailingPE', 0)
                        dy1 = i1.get('dividendYield', 0); dy2 = i2.get('dividendYield', 0)
                        perf1 = ((h1['Close'].iloc[-1] / h1['Close'].iloc[0]) - 1) * 100 if not h1.empty else 0
                        perf2 = ((h2['Close'].iloc[-1] / h2['Close'].iloc[0]) - 1) * 100 if not h2.empty else 0
                        
                        cc1, cc2, cc3, cc4 = st.columns(4)
                        # Market Cap Logic (Win highlight)
                        cc1.metric(f"Kapitalizace {t1}", f"${mc1/1e9:.1f}B", delta_color="normal")
                        cc1.metric(f"Kapitalizace {t2}", f"${mc2/1e9:.1f}B", delta=f"{(mc2-mc1)/1e9:.1f}B")

                        # Simple table is better
                        comp_data = {
                            "Metrika": ["Cena", "P/E Ratio", "Dividenda", "Změna 1R"],
                            t1: [f"{i1.get('currentPrice')} {i1.get('currency')}", f"{pe1:.2f}", f"{dy1*100:.2f}%" if dy1 else "0%", f"{perf1:+.2f}%"],
                            t2: [f"{i2.get('currentPrice')} {i2.get('currency')}", f"{pe2:.2f}", f"{dy2*100:.2f}%" if dy2 else "0%", f"{perf2:+.2f}%"]
                        }
                        st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)
                        
                        # Chart
                        df_norm = pd.DataFrame()
                        if not h1.empty and not h2.empty:
                            # Normalize
                            h1['Norm'] = (h1['Close'] / h1['Close'].iloc[0] - 1) * 100
                            h2['Norm'] = (h2['Close'] / h2['Close'].iloc[0] - 1) * 100
                            st.line_chart(pd.concat([h1['Norm'].rename(t1), h2['Norm'].rename(t2)], axis=1))
                    else: st.error("Chyba načítání dat.")
        st.divider()
        score, rating, datum_fg, prev_score = ziskej_fear_greed()
        if score is not None:
            st.write(""); st.subheader("😨 PSYCHOLOGIE TRHU (Fear & Greed)")
            with st.container(border=True):
                ref = prev_score if prev_score else 50
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number+delta", value = score,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': f"Aktuálně: {rating.upper()}", 'font': {'size': 24}},
                    delta = {'reference': ref, 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}},
                    gauge = {'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"}, 'bar': {'color': "white", 'thickness': 0.2}, 'bgcolor': "white", 'borderwidth': 2, 'bordercolor': "gray", 'steps': [{'range': [0, 25], 'color': '#FF4B4B'}, {'range': [25, 45], 'color': '#FFA07A'}, {'range': [45, 55], 'color': '#FFFF00'}, {'range': [55, 75], 'color': '#90EE90'}, {'range': [75, 100], 'color': '#008000'}]}
                ))
                fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white", 'family': "Roboto Mono"}, height=250, margin=dict(l=20, r=20, t=50, b=20))
                c_g1, c_g2 = st.columns([2, 1])
                with c_g1: st.plotly_chart(fig_gauge, use_container_width=True)
                with c_g2: st.info(f"**Hodnota: {score}/100**\n\n📅 {datum_fg}\n\n*< 25: Strach | > 75: Chamtivost*")
        
        st.divider()
        if viz_data:
            vdf = pd.DataFrame(viz_data)
            vdf_charts = vdf[vdf['HodnotaUSD'] > 0]
            c1, c2 = st.columns(2)
            with c1:
                st.caption("MAPA TRHU (Sektory)")
                try:
                    fig = px.treemap(vdf_charts, path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'], values='HodnotaUSD', color='Zisk', color_continuous_scale=['red', '#161B22', 'green'], color_continuous_midpoint=0)
                    st.plotly_chart(fig, use_container_width=True)
                except: st.error("Chyba mapy.")
            with c2:
                st.caption("MĚNOVÉ RIZIKO (Expozice)")
                try:
                    df_mena = vdf_charts.groupby("Měna")["HodnotaUSD"].sum().reset_index()
                    fig_pie = px.pie(df_mena, values='HodnotaUSD', names='Měna', hole=0.4, color='Měna', color_discrete_map={'USD':'#00CC96', 'CZK':'#636EFA', 'EUR':'#EF553B'})
                    st.plotly_chart(fig_pie, use_container_width=True)
                except: st.error("Chyba koláče.")
            
            # 👇 MĚSÍČNÍ HEATMAPA 👇
            st.divider()
            st.caption("📊 MĚSÍČNÍ VYSVĚDČENÍ (Zisk/Ztráta %)")
            if not hist_vyvoje.empty and len(hist_vyvoje) > 30:
                try:
                    df_h = hist_vyvoje.copy()
                    df_h['Date'] = pd.to_datetime(df_h['Date'])
                    df_h = df_h.set_index('Date').resample('M').last()
                    df_h['Pct_Change'] = df_h['TotalUSD'].pct_change() * 100
                    df_h = df_h.dropna()
                    if not df_h.empty:
                        df_h['Year'] = df_h.index.year
                        df_h['Month'] = df_h.index.month_name()
                        pivot_table = df_h.pivot(index='Year', columns='Month', values='Pct_Change')
                        months_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
                        pivot_table = pivot_table.reindex(columns=months_order)
                        fig_heat = px.imshow(pivot_table, labels=dict(x="Měsíc", y="Rok", color="Změna %"), x=pivot_table.columns, y=pivot_table.index, color_continuous_scale=['red', '#161B22', 'green'], color_continuous_midpoint=0, text_auto='.1f')
                        fig_heat.update_layout(height=300)
                        st.plotly_chart(fig_heat, use_container_width=True)
                    else: st.info("Zatím nemám dost dat.")
                except: st.info("Málo dat pro heatmapu.")
            else: st.info("Měsíční mapa se ukáže, až budeš mít historii delší než 1 měsíc.")

            st.divider()
            st.caption("🥊 SOUBOJ S TRHEM (S&P 500)")
            if not hist_vyvoje.empty and len(hist_vyvoje) > 1:
                my_data = hist_vyvoje.copy(); my_data['Date'] = pd.to_datetime(my_data['Date']); my_data = my_data.sort_values('Date')
                start_date = my_data['Date'].iloc[0].strftime('%Y-%m-%d')
                try:
                    sp500 = yf.download("^GSPC", start=start_date, progress=False)['Close']
                    start_val = my_data['TotalUSD'].iloc[0]
                    my_data['Můj Vývoj'] = ((my_data['TotalUSD'] / start_val) - 1) * 100 if start_val > 0 else 0
                    if not sp500.empty:
                        if isinstance(sp500, pd.DataFrame): sp500 = sp500.iloc[:, 0]
                        sp_norm = ((sp500 / sp500.iloc[0]) - 1) * 100
                        my_data['DateOnly'] = my_data['Date'].dt.date
                        sp500_df = sp_norm.reset_index(); sp500_df.columns = ['DateOnly', 'S&P 500']; sp500_df['DateOnly'] = pd.to_datetime(sp500_df['DateOnly']).dt.date
                        final_chart = pd.merge(my_data, sp500_df, on='DateOnly', how='left').fillna(method='ffill')
                        st.line_chart(final_chart.set_index('Date')[['Můj Vývoj', 'S&P 500']])
                    else: st.line_chart(hist_vyvoje.set_index("Date")['TotalUSD'])
                except: st.line_chart(hist_vyvoje.set_index("Date")['TotalUSD'])
            elif not hist_vyvoje.empty: st.info("Srovnání vyžaduje data ze 2 dnů.")
            else: st.info("Žádná historie.")
            
            st.divider(); st.subheader("⚖️ REBALANCING")
            total_assets = vdf['HodnotaUSD'].sum()
            r1, r2, r3 = st.columns(3); col_iter = [r1, r2, r3]
            for i, (sektor_nazev, cil_pct) in enumerate(CILOVE_SEKTORY.items()):
                aktualni_col = col_iter[i % 3]
                row = vdf[vdf['Sektor'] == sektor_nazev]
                realita_pct = (row['HodnotaUSD'].sum() / total_assets * 100) if total_assets > 0 else 0
                rozdil = realita_pct - cil_pct
                with aktualni_col:
                    st.write(f"**{sektor_nazev}**")
                    st.progress(min(realita_pct / 100, 1.0))
                    st.caption(f"Cíl: {cil_pct}% | Máš: {realita_pct:.1f}%")
                    if rozdil > 2: st.warning(f"📉 PRODEJ ({rozdil:+.1f}%)")
                    elif rozdil < -2: st.success(f"🛒 DOKUP ({abs(rozdil):.1f}%)")
                    else: st.info("✅ OK")

            st.divider(); st.subheader("🔮 VĚŠTEC"); 
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
            
            st.divider(); st.subheader("💥 CRASH TEST")
            with st.container(border=True):
                propad = st.slider("Simulace pádu trhu (%)", 5, 80, 20, step=5)
                ztrata_czk = (celk_hod_usd * (propad / 100)) * kurz_czk
                zbytek_czk = (celk_hod_usd * (1 - propad / 100)) * kurz_czk
                c_cr1, c_cr2 = st.columns(2)
                with c_cr1: st.error(f"📉 ZTRÁTA: -{ztrata_czk:,.0f} Kč"); st.warning(f"💰 ZBYDE TI: {zbytek_czk:,.0f} Kč")
                with c_cr2: st.progress(1.0 - (propad / 100))
        else: st.info("Žádná data.")

    elif page == "📰 Zprávy":
        st.title("📰 BURZOVNÍ ZPRAVODAJSTVÍ")
        news = ziskej_zpravy()
        if AI_AVAILABLE and news:
            if st.button("🧠 AI: SHRNUTÍ TRHU", type="primary"):
                with st.spinner("Čtu noviny..."):
                    titles = [n['title'] for n in news]
                    prompt = f"Tady jsou titulky zpráv: {titles}. Jaká je nálada na trhu? Shrň to jednou větou."
                    try: res = AI_MODEL.generate_content(prompt); st.info(res.text, icon="🤖")
                    except: st.error("AI chyba.")
        if news:
            for n in news:
                with st.container(border=True):
                    st.subheader(n['title']); st.caption(f"📅 {n['published']}"); st.link_button("Číst celý článek", n['link'])
        else: st.info("Žádné nové zprávy.")

    elif page == "💸 Obchod & Peníze":
        st.title("💸 BANKA A OBCHODOVÁNÍ")
        t_bank, t_ex, t_buy, t_sell = st.tabs(["🏦 PENĚŽENKA", "💱 SMĚNÁRNA", "🛒 NÁKUP", "📉 PRODEJ"])
        with t_bank:
            c1, c2 = st.columns(2)
            with c1:
                with st.form("d"):
                    a = st.number_input("Částka", 1.0); c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                    if st.form_submit_button("💰 VLOŽIT"): pohyb_penez(a, c, "Vklad", "Man", USER); st.toast("Vloženo", icon="✅"); st.rerun()
                with st.form("w"):
                    a = st.number_input("Částka", 1.0); c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                    if st.form_submit_button("💸 VYBRAT"): pohyb_penez(-a, c, "Vyber", "Man", USER); st.toast("Vybráno", icon="✅"); st.rerun()
            with c2: st.dataframe(df_cash.sort_values("Datum", ascending=False), use_container_width=True)
        with t_ex:
            st.info(f"Kurzy: 1 USD = {kurzy.get('CZK'):.2f} CZK | 1 EUR = 1.16 USD")
            with st.form("ex"):
                c1, c2, c3 = st.columns(3)
                with c1: ce = st.number_input("Částka", 1.0)
                with c2: zm = st.selectbox("Z", ["USD", "CZK", "EUR"])
                with c3: dm = st.selectbox("Do", ["CZK", "USD", "EUR"])
                if st.form_submit_button("💱 SMĚNIT"):
                    if zustatky.get(zm, 0) >= ce: ok, msg = proved_smenu(ce, zm, dm, USER); st.toast(msg, icon="✅"); st.rerun()
                    else: st.toast(f"Nedostatek {zm}", icon="❌")
        with t_buy:
            st.subheader("Nákup akcií")
            with st.form("b"):
                c1, c2 = st.columns(2)
                with c1:
                    t = st.text_input("Symbol", placeholder="NAPŘ. AAPL", help="Zadej ticker akcie (zkratku). Např. AAPL pro Apple, CEZ.PR pro ČEZ.").upper()
                with c2:
                    p = st.number_input("Počet kusů", min_value=0.001, step=1.0, help="Kolik akcií chceš koupit? Můžeš i zlomky (např. 0.5).")
                c = st.number_input("Nákupní cena (za 1 kus)", min_value=0.1, help="Za kolik jsi to koupil? Pokud nevíš, podívej se do své banky.")
                if st.form_submit_button("KOUPIT AKCIE", use_container_width=True):
                    _, m, _ = ziskej_info(t)
                    cost = p*c; bal = zustatky.get(m, 0)
                    if bal >= cost:
                        pohyb_penez(-cost, m, "Nákup", f"Buy {t}", USER)
                        new = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now(), "Owner": USER, "Sektor": "Doplnit", "Poznamka": ""}])
                        upd = pd.concat([df, new], ignore_index=True)
                        st.session_state['df'] = upd; uloz_data_uzivatele(upd, USER, SOUBOR_DATA); st.toast("OK", icon="🛒"); st.rerun()
                    else: st.toast(f"Nedostatek {m}! Jdi do směnárny.", icon="❌")
        with t_sell:
            if not df.empty:
                with st.form("s"):
                    t = st.selectbox("Akcie", df['Ticker'].unique().tolist()); q = st.number_input("Ks", 0.001); pr = st.number_input("Cena", 0.1)
                    if st.form_submit_button("PRODAT"):
                        _, m, _ = ziskej_info(t) 
                        ok, msg = proved_prodej(t, q, pr, USER, m)
                        if ok: st.toast("Prodáno", icon="✅"); st.rerun()
                        else: st.toast(msg, icon="⚠️")

    elif page == "💎 Dividendy":
        st.title("💎 DIVIDENDY")
        if not df_div.empty:
            df_div['Datum'] = pd.to_datetime(df_div['Datum']); df_div['Mesic'] = df_div['Datum'].dt.strftime('%Y-%m')
            df_div['CastkaCZK'] = df_div.apply(lambda r: r['Castka'] * (20.85 if r['Mena'] == 'USD' else (24.20 if r['Mena'] == 'EUR' else 1)), axis=1)
            monthly_data = df_div.groupby('Mesic')['CastkaCZK'].sum()
            k1, k2 = st.columns([2, 1])
            with k1: st.subheader("📅 Pasivní příjem (CZK)"); st.bar_chart(monthly_data, color="#00FF00")
            with k2: st.metric("CELKEM VYPLACENO", f"{df_div['CastkaCZK'].sum():,.0f} Kč"); st.dataframe(monthly_data.sort_index(ascending=False).head(3), use_container_width=True)
            st.divider()
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.form("div"):
                t = st.text_input("Ticker").upper(); a = st.number_input("Částka", 0.01); c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                if st.form_submit_button("PŘIPSAT"):
                    pridat_dividendu(t, a, c, USER); st.toast("Připsáno", icon="💎"); st.balloons(); time.sleep(2); st.rerun()
        with c2:
            if not df_div.empty:
                st.dataframe(df_div[["Datum", "Ticker", "Castka", "Mena", "CastkaCZK"]].sort_values("Datum", ascending=False).style.format({"Castka": "{:,.2f}", "CastkaCZK": "{:,.0f} Kč", "Datum": "{:%d.%m.%Y}"}), use_container_width=True, hide_index=True)

    elif page == "⚙️ Správa Dat":
        st.title("⚙️ EDITACE")
        t1, t2 = st.tabs(["Portfolio", "Historie"])
        with t1:
            ed = st.data_editor(df[["Ticker", "Pocet", "Cena", "Datum", "Sektor"]], num_rows="dynamic", use_container_width=True)
            if st.button("💾 ULOŽIT PORTFOLIO"): 
                st.session_state['df'] = ed
                uloz_data_uzivatele(ed, USER, SOUBOR_DATA)
                st.toast("Uloženo", icon="✅"); st.rerun()
        with t2:
            st.session_state['df_hist'] = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True, key="he")
            if st.button("💾 ULOŽIT HISTORII"): 
                uloz_data_uzivatele(st.session_state['df_hist'], USER, SOUBOR_HISTORIE)
                st.toast("Uloženo", icon="✅"); st.rerun()
        
        st.divider()
        st.subheader("📦 ZÁLOHA")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for n, d in [(SOUBOR_DATA, 'df'), (SOUBOR_HISTORIE, 'df_hist'), (SOUBOR_CASH, 'df_cash'), (SOUBOR_DIVIDENDY, 'df_div'), (SOUBOR_WATCHLIST, 'df_watch')]:
                if d in st.session_state: zip_file.writestr(n, st.session_state[d].to_csv(index=False))
        st.download_button("💾 STÁHNOUT ZÁLOHU (.ZIP)", data=zip_buffer.getvalue(), file_name=f"zaloha_{datetime.now().strftime('%Y%m%d')}.zip", mime="application/zip")

if __name__ == "__main__":
    main()
