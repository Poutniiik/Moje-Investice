import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
from datetime import datetime
import hashlib
import time
import zipfile
import io
import requests
import feedparser # 👈 NOVINKA PRO ZPRÁVY
from streamlit_lottie import st_lottie
import google.generativeai as genai
import plotly.graph_objects as go # 👈 PRO TACHOMETR

# --- KONFIGURACE ---
st.set_page_config(page_title="Terminal Pro", layout="wide", page_icon="💹")

REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv"
SOUBOR_WATCHLIST = "watchlist.csv"
SOUBOR_DIVIDENDY = "dividends.csv"

# --- ZDROJE ZPRÁV (RSS) ---
# Použijeme Google News - je to nejspolehlivější a agreguje to všechno
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
1. '🏠 Přehled': Dashboard, Jmění, Hotovost, Síň slávy.
2. '📈 Analýza': Grafy, Srovnání s S&P 500, Rebalancing, Věštec.
3. '📰 Zprávy': Čtečka novinek z trhu + AI shrnutí sentimentu.
4. '💸 Obchod & Peníze': Nákup/Prodej akcií, Vklady, Směnárna.
5. '💎 Dividendy': Historie a graf dividend.
6. '⚙️ Správa Dat': Zálohy a editace.

POKYNY:
- Buď stručný, přátelský a používej emojis.
- Pokud dostaneš seznam zpráv, shrň náladu na trhu (Bullish/Bearish).
"""

# --- KONFIGURACE CÍLŮ ---
CILOVE_SEKTORY = {
    "Technologie": 30, "Energie": 20, "Spotřební zboží": 15,
    "Finance": 15, "Krypto": 10, "Ostatní": 10
}

# --- AI SETUP ---
try:
    GOOGLE_API_KEY = st.secrets["google"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    AI_MODEL = genai.GenerativeModel('gemini-2.5-flash') 
    AI_AVAILABLE = True
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
try: GITHUB_TOKEN = st.secrets["github"]["token"]
except: st.error("❌ CHYBA: Chybí GitHub Token v Secrets!"); st.stop()

def get_repo(): return Github(GITHUB_TOKEN).get_repo(REPO_NAZEV)
def zasifruj(text): return hashlib.sha256(str(text).encode()).hexdigest()
def load_lottieurl(url):
    try:
        r = requests.get(url)
        if r.status_code != 200: return None
        return r.json()
    except: return None

# --- ZPRAVODAJSTVÍ ---
@st.cache_data(ttl=1800) 
def ziskej_zpravy():
    news = []
    # Jednoduchý User-Agent
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for url in RSS_ZDROJE:
        try:
            # 1. Stažení
            response = requests.get(url, headers=headers, timeout=5)
            
            # 2. Analýza
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                # Pokud feedparser nic nenašel, zkusíme to říct
                if not feed.entries:
                    print(f"Zdroj {url} vrátil prázdný seznam.")
                    continue
                    
                for entry in feed.entries[:5]: 
                    # Zkusíme najít datum, nebo dáme dnešek
                    datum = entry.get('published', datetime.now().strftime("%d.%m.%Y"))
                    
                    news.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": datum,
                        "summary": entry.get('summary', 'Klikni pro více info...')[:200]
                    })
            else:
                print(f"Chyba {response.status_code} pro {url}")
                
        except Exception as e:
            print(f"Kritická chyba u {url}: {e}")
            pass
            
    return news

# --- FEAR & GREED INDEX (PSYCHOLOGIE TRHU) ---
@st.cache_data(ttl=3600) # Uložíme na hodinu
def ziskej_fear_greed():
    # Tajný endpoint CNN (psst!)
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        score = int(data['fear_and_greed']['score'])
        rating = data['fear_and_greed']['rating']
        timestamp = data['fear_and_greed']['timestamp']
        datum = datetime.fromisoformat(timestamp).strftime("%d.%m. %H:%M")
        return score, rating, datum
    except:
        return None, None, None

# --- DATABÁZE ---
def uloz_csv(df, nazev_souboru, zprava):
    repo = get_repo()
    csv = df.to_csv(index=False)
    try:
        file = repo.get_contents(nazev_souboru)
        repo.update_file(file.path, zprava, csv, file.sha)
    except: repo.create_file(nazev_souboru, zprava, csv)

def nacti_csv(nazev_souboru):
    try:
        repo = get_repo()
        file = repo.get_contents(nazev_souboru)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        for col in ['Datum', 'Date']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        for col in ['Pocet', 'Cena', 'Castka', 'Kusu', 'Prodejka', 'Zisk', 'TotalUSD', 'Investice']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        if 'Sektor' not in df.columns and nazev_souboru == SOUBOR_DATA: df['Sektor'] = "Doplnit"
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        df['Owner'] = df['Owner'].astype(str)
        return df
    except:
        cols = ["Ticker", "Pocet", "Cena", "Datum", "Owner", "Sektor"]
        if nazev_souboru == SOUBOR_HISTORIE: cols = ["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_CASH: cols = ["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_VYVOJ: cols = ["Date", "TotalUSD", "Owner"]
        if nazev_souboru == SOUBOR_WATCHLIST: cols = ["Ticker", "Owner"]
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
def pridat_do_watchlistu(ticker, user):
    df_w = st.session_state['df_watch']
    if ticker not in df_w['Ticker'].values:
        new = pd.DataFrame([{"Ticker": ticker, "Owner": user}])
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
        api_curr = t.fast_info.currency
        if api_curr and api_curr != "N/A": mena = api_curr
        return price, mena
    except: return None, mena

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

# --- MAIN ---
def main():
    if 'prihlasen' not in st.session_state: st.session_state['prihlasen'] = False
    if 'user' not in st.session_state: st.session_state['user'] = ""

    if not st.session_state['prihlasen']:
        c1,c2,c3 = st.columns([1, 2, 1])
        with c2:
            st.title("🔐 INVESTIČNÍ TERMINÁL")
            t1, t2 = st.tabs(["PŘIHLÁŠENÍ", "REGISTRACE"])
            with t1:
                with st.form("l"):
                    u=st.text_input("Uživatelské jméno"); p=st.text_input("Heslo", type="password")
                    if st.form_submit_button("VSTOUPIT", use_container_width=True):
                        df_u = nacti_uzivatele()
                        row = df_u[df_u['username'] == u] if not df_u.empty else pd.DataFrame()
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            st.session_state.clear(); st.session_state.update({'prihlasen':True, 'user':u}); st.rerun()
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
        return

    # --- NAČTENÍ DAT ---
    USER = st.session_state['user']
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

    # VÝPOČTY PRO AI KONTEXT
    all_tickers = []; viz_data = []; celk_hod_usd = 0; celk_inv_usd = 0; stats_meny = {}
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    LIVE_DATA = ziskej_ceny_hromadne(list(set(all_tickers)))
    if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]

    # Hlavní smyčka výpočtů
    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        df_g['Cena'] = df_g['Investice'] / df_g['Pocet']
        for i, (idx, row) in enumerate(df_g.iterrows()):
            tkr = row['Ticker']
            inf = LIVE_DATA.get(tkr, {})
            p, m = ziskej_info(tkr)
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

            hod = row['Pocet']*p; inv = row['Investice']; z = hod-inv
            try: k = 1.0 / kurzy.get("CZK", 20.85) if m=="CZK" else (kurzy.get("EUR", 1.16) if m=="EUR" else 1.0)
            except: k = 1.0
            
            celk_hod_usd += hod*k; celk_inv_usd += inv*k
            if m not in stats_meny: stats_meny[m] = {"inv":0, "zisk":0}
            stats_meny[m]["inv"]+=inv; stats_meny[m]["zisk"]+=z
            
            viz_data.append({
                "Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m, 
                "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Cena'], "Dan": dan_status, "Investice": inv
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

    # --- SIDEBAR + CHATBOT ---
    with st.sidebar:
        st.header(f"👤 {USER.upper()}")
        
        # Peněženka
        if zustatky:
            st.caption("Stav peněženky:")
            for mena in ["USD", "CZK", "EUR"]:
                if mena in zustatky and zustatky[mena] > 0.01:
                    castka = zustatky[mena]
                    sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
                    st.info(f"**{castka:,.2f} {sym}**", icon="💰")
        else: st.warning("Peněženka prázdná")
        
        st.divider()
        st.subheader("🧭 NAVIGACE")
        page = st.radio("Menu:", ["🏠 Přehled", "📈 Analýza", "📰 Zprávy", "💸 Obchod & Peníze", "💎 Dividendy", "⚙️ Správa Dat"], label_visibility="collapsed")
        
        # --- 🤖 AI CHATBOT V SIDEBARU ---
        st.divider()
        st.subheader("🤖 AI Průvodce")
        
        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = [{"role": "assistant", "content": "Ahoj! Jsem tvůj AI průvodce. Zeptej se mě na portfolio, zprávy nebo kde co najdeš."}]

        with st.container(border=True, height=300):
            for msg in st.session_state["chat_messages"]:
                st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("Napiš dotaz..."):
            if not AI_AVAILABLE:
                st.error("Chybí API klíč.")
            else:
                st.session_state["chat_messages"].append({"role": "user", "content": prompt})
                st.rerun()

        if st.session_state["chat_messages"][-1]["role"] == "user":
            with st.spinner("Přemýšlím..."):
                last_user_msg = st.session_state["chat_messages"][-1]["content"]
                portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
                if viz_data:
                    portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data])
                
                full_prompt = f"{APP_MANUAL}\n\nDATA UŽIVATELE:\n{portfolio_context}\n\nDOTAZ UŽIVATELE: {last_user_msg}"
                try:
                    response = AI_MODEL.generate_content(full_prompt)
                    ai_reply = response.text
                except Exception as e:
                    ai_reply = f"Omlouvám se, došlo k chybě: {str(e)}"
                
                st.session_state["chat_messages"].append({"role": "assistant", "content": ai_reply})
                st.rerun()

        st.divider()
        st.subheader("👀 WATCHLIST")
        with st.expander("➕ Přidat", expanded=False):
            with st.form("w_add", clear_on_submit=True):
                new_w = st.text_input("Symbol").upper()
                if st.form_submit_button("OK"):
                    if new_w: pridat_do_watchlistu(new_w, USER); st.rerun()
        
        if not df_watch.empty:
            for t in df_watch['Ticker']:
                info = LIVE_DATA.get(t, {})
                price = info.get('price'); curr = info.get('curr', '?')
                if not price:
                    try: p, m = ziskej_info(t); price=p; curr=m
                    except: pass
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(f"**{t}**")
                        if price: st.markdown(f"### {price:,.2f} {curr}")
                        else: st.caption("Offline")
                    with c2:
                        st.write("") 
                        if st.button("❌", key=f"del_{t}"): odebrat_z_watchlistu(t, USER); st.rerun()

        st.divider()
        if st.button("🚪 ODHLÁSIT", use_container_width=True): st.session_state.clear(); st.rerun()

    # --- STRÁNKY ---
    if page == "🏠 Přehled":
        st.title(f"🏠 PŘEHLED: {USER.upper()}")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} Zisk")
        k2.metric("JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{zisk_czk:+,.0f} Kč")
        k3.metric("ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        try: cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*1.16)
        except: cash_usd = 0
        k4.metric("HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné")
        
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
            st.dataframe(vdf[["Ticker", "Měna", "Sektor", "Kusy", "Průměr", "Cena", "Hodnota", "Zisk", "Dan"]].style.format({"Průměr": "{:.2f}", "Cena": "{:.2f}", "Hodnota": "{:,.0f}", "Zisk": "{:+,.0f}"}).background_gradient(cmap="RdYlGn", subset=["Zisk"], vmin=-1000, vmax=1000), use_container_width=True)
        else: st.info("Portfolio je prázdné.")

    elif page == "📈 Analýza":
        st.title("📈 HLOUBKOVÁ ANALÝZA")
        # 👇 TACHOMETR STRACHU A CHAMTIVOSTI 👇
        score, rating, datum_fg = ziskej_fear_greed()
        
        if score is not None:
            st.write("")
            with st.container(border=True):
                st.subheader("😨 PSYCHOLOGIE TRHU (Fear & Greed)")
                
                # Vykreslení tachometru
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = score,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': f"Aktuálně: {rating.upper()}", 'font': {'size': 24}},
                    delta = {'reference': 50, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}}, # Červená když roste chamtivost
                    gauge = {
                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
                        'bar': {'color': "white", 'thickness': 0.2}, # Ručička
                        'bgcolor': "white",
                        'borderwidth': 2,
                        'bordercolor': "gray",
                        'steps': [
                            {'range': [0, 25], 'color': '#FF4B4B'},  # Extrémní strach (Červená)
                            {'range': [25, 45], 'color': '#FFA07A'}, # Strach
                            {'range': [45, 55], 'color': '#FFFF00'}, # Neutrál (Žlutá)
                            {'range': [55, 75], 'color': '#90EE90'}, # Chamtivost
                            {'range': [75, 100], 'color': '#008000'} # Extrémní chamtivost (Zelená)
                        ],
                    }
                ))
                # Nastavení velikosti a průhlednosti
                fig_gauge.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", 
                    font={'color': "white", 'family': "Roboto Mono"},
                    height=250,
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                
                c_g1, c_g2 = st.columns([2, 1])
                with c_g1:
                    st.plotly_chart(fig_gauge, use_container_width=True)
                with c_g2:
                    st.info(
                        f"""
                        **Hodnota: {score}/100**
                        
                        📅 {datum_fg}
                        
                        *Výklad:*
                        - **< 25**: Trh se bojí (Levné nákupy?)
                        - **> 75**: Trh je nenažraný (Riziko pádu?)
                        """
                    )
        # 👆 KONEC TACHOMETRU 👆
        if viz_data:
            vdf = pd.DataFrame(viz_data)
            c1, c2 = st.columns(2)
            with c1:
                st.caption("MAPA TRHU (Sektory)")
                try:
                    fig = px.treemap(vdf, path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'], values='HodnotaUSD', color='Zisk', color_continuous_scale=['red', '#161B22', 'green'], color_continuous_midpoint=0)
                    st.plotly_chart(fig, use_container_width=True)
                except: st.error("Chyba mapy.")
            with c2:
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
            
            st.divider()
            st.subheader("⚖️ REBALANCING")
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

            st.divider()
            st.subheader("🔮 VĚŠTEC: Budoucí bohatství")
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
        else: st.info("Žádná data.")

    # --- SEKCE ZPRÁVY (NOVINKA) ---
    elif page == "📰 Zprávy":
        st.title("📰 BURZOVNÍ ZPRAVODAJSTVÍ")
        news = ziskej_zpravy()
        
        # AI Shrnutí
        if AI_AVAILABLE and news:
            if st.button("🧠 AI: SHRNUTÍ TRHU", type="primary"):
                with st.spinner("Čtu noviny..."):
                    titles = [n['title'] for n in news]
                    prompt = f"Tady jsou titulky zpráv z burzy: {titles}. Jaká je nálada na trhu? Shrň to jednou větou a přidej emoji."
                    try:
                        res = AI_MODEL.generate_content(prompt)
                        st.info(res.text, icon="🤖")
                    except: st.error("AI chyba.")
        
        # Výpis zpráv (Bez ošklivého HTML shrnutí)
        if news:
            for n in news:
                with st.container(border=True):
                    st.subheader(n['title'])
                    st.caption(f"📅 {n['published']}")
                    # Tu řádku s 'summary' jsme vyhodili, protože dělala bordel
                    st.link_button("Číst celý článek", n['link'])
        else:
            st.info("Žádné nové zprávy.")

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
            with st.form("b"):
                t = st.text_input("Symbol").upper(); p = st.number_input("Ks", 0.001); c = st.number_input("Cena", 0.1)
                if st.form_submit_button("KOUPIT"):
                    _, m = ziskej_info(t)
                    cost = p*c; bal = zustatky.get(m, 0)
                    if bal >= cost:
                        pohyb_penez(-cost, m, "Nákup", f"Buy {t}", USER)
                        new = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now(), "Owner": USER, "Sektor": "Doplnit"}])
                        upd = pd.concat([df, new], ignore_index=True)
                        st.session_state['df'] = upd; uloz_data_uzivatele(upd, USER, SOUBOR_DATA); st.toast("OK", icon="🛒"); st.rerun()
                    else: st.toast(f"Nedostatek {m}!", icon="❌")
        with t_sell:
            if not df.empty:
                with st.form("s"):
                    t = st.selectbox("Akcie", df['Ticker'].unique().tolist()); q = st.number_input("Ks", 0.001); pr = st.number_input("Cena", 0.1)
                    if st.form_submit_button("PRODAT"):
                        _, m = ziskej_info(t)
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
            if st.button("💾 ULOŽIT PORTFOLIO"): st.session_state['df'] = ed; uloz_data_uzivatele(ed, USER, SOUBOR_DATA); st.toast("Uloženo", icon="✅"); st.rerun()
        with t2:
            st.session_state['df_hist'] = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True, key="he")
            if st.button("💾 ULOŽIT HISTORII"): uloz_data_uzivatele(st.session_state['df_hist'], USER, SOUBOR_HISTORIE); st.toast("Uloženo", icon="✅"); st.rerun()
        
        st.divider()
        st.subheader("📦 ZÁLOHA")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for n, d in [(SOUBOR_DATA, 'df'), (SOUBOR_HISTORIE, 'df_hist'), (SOUBOR_CASH, 'df_cash'), (SOUBOR_DIVIDENDY, 'df_div'), (SOUBOR_WATCHLIST, 'df_watch')]:
                if d in st.session_state: zip_file.writestr(n, st.session_state[d].to_csv(index=False))
        st.download_button("💾 STÁHNOUT ZÁLOHU (.ZIP)", data=zip_buffer.getvalue(), file_name=f"zaloha_{datetime.now().strftime('%Y%m%d')}.zip", mime="application/zip")

if __name__ == "__main__":
    main()




