import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
from datetime import datetime
import hashlib

# --- KONFIGURACE ---
st.set_page_config(page_title="Terminal Pro", layout="wide", page_icon="💹")

REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv"
SOUBOR_WATCHLIST = "watchlist.csv"

# --- STYLY ---
st.markdown("""
<style>
    .stApp {background-color: #0E1117; font-family: 'Roboto Mono', monospace;}
    div[data-testid="stMetric"] {background-color: #161B22; border: 1px solid #30363D; padding: 15px; border-radius: 5px; color: #E6EDF3;}
    div[data-testid="stMetricLabel"] {font-size: 0.9rem; color: #8B949E; font-weight: bold; text-transform: uppercase;}
    div[data-testid="stMetricValue"] {font-size: 1.8rem; color: #E6EDF3; font-weight: bold;}
    h1, h2, h3 {color: #E6EDF3 !important; font-family: 'Roboto Mono', monospace; text-transform: uppercase; letter-spacing: 1px;}
    hr {border-color: #30363D;}
</style>
""", unsafe_allow_html=True)

# --- PŘIPOJENÍ ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
except: st.error("❌ CRITICAL ERROR: Missing GitHub Token!"); st.stop()

def get_repo(): return Github(GITHUB_TOKEN).get_repo(REPO_NAZEV)
def zasifruj(text): return hashlib.sha256(str(text).encode()).hexdigest()

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
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        df['Owner'] = df['Owner'].astype(str)
        return df
    except:
        cols = ["Ticker", "Pocet", "Cena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_HISTORIE: cols = ["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_CASH: cols = ["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"]
        if nazev_souboru == SOUBOR_VYVOJ: cols = ["Date", "TotalUSD", "Owner"]
        if nazev_souboru == SOUBOR_WATCHLIST: cols = ["Ticker", "Owner"]
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

# --- WATCHLIST ---
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

# --- CASH & HISTORY ---
def get_zustatky(user):
    df_cash = st.session_state.get('df_cash', pd.DataFrame())
    if df_cash.empty: return {}
    return df_cash.groupby('Mena')['Castka'].sum().to_dict()

def pohyb_penez(castka, mena, typ, poznamka, user):
    df_cash = st.session_state['df_cash']
    novy = pd.DataFrame([{"Typ": typ, "Castka": castka, "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash = pd.concat([df_cash, novy], ignore_index=True)
    st.session_state['df_cash'] = df_cash
    uloz_data_uzivatele(df_cash, user, SOUBOR_CASH)

def aktualizuj_graf_vyvoje(user, aktualni_hodnota_usd):
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

# --- LIVE DATA ---
@st.cache_data(ttl=86400)
def ziskej_sektor(ticker):
    try: return yf.Ticker(str(ticker)).info.get('sector', 'Ostatní')
    except: return 'Ostatní'

@st.cache_data(ttl=3600)
def ziskej_kurzy():
    kurzy = {"USD": 1.0}
    try:
        d = yf.download(["CZK=X", "EURUSD=X"], period="1d")['Close'].iloc[-1]
        kurzy["CZK"] = float(d["CZK=X"]); kurzy["EUR"] = float(d["EURUSD=X"])
    except: pass
    return kurzy

def ziskej_info(ticker):
    try: t = yf.Ticker(str(ticker)); return t.fast_info.last_price, t.fast_info.currency
    except: return None, "USD"

def get_live_data_batch(tickers):
    data = {}
    for t in tickers:
        p, m = ziskej_info(t)
        if p: data[t] = {"price": p, "curr": m}
    return data

# --- MAIN APP ---
def main():
    if 'prihlasen' not in st.session_state: st.session_state['prihlasen'] = False
    if 'user' not in st.session_state: st.session_state['user'] = ""

    if not st.session_state['prihlasen']:
        c1,c2,c3 = st.columns([1,2,1])
        with c2:
            st.title("🔒 LOGIN")
            t1, t2 = st.tabs(["Vstup", "Registrace"])
            with t1:
                with st.form("l"):
                    u=st.text_input("Jméno"); p=st.text_input("Heslo", type="password")
                    if st.form_submit_button("Vstoupit", use_container_width=True):
                        df_u = nacti_uzivatele()
                        row = df_u[df_u['username'] == u] if not df_u.empty else pd.DataFrame()
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            st.session_state.clear(); st.session_state.update({'prihlasen':True, 'user':u}); st.rerun()
                        else: st.error("Chyba")
            with t2:
                with st.form("r"):
                    nu=st.text_input("Nové jméno"); np=st.text_input("Heslo", type="password"); nr=st.text_input("Kód pro obnovu")
                    if st.form_submit_button("Registrovat", use_container_width=True):
                        df_u = nacti_uzivatele()
                        if not df_u.empty and nu in df_u['username'].values: st.error("Obsazeno")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(np), "recovery_key": zasifruj(nr)}])
                            uloz_csv(pd.concat([df_u, new], ignore_index=True), SOUBOR_UZIVATELE, "New"); st.success("OK")
        return

    # --- DASHBOARD ---
    USER = st.session_state['user']
    if 'df' not in st.session_state:
        with st.spinner("STARTING SYSTEM..."):
            st.session_state['df'] = nacti_csv(SOUBOR_DATA).query(f"Owner=='{USER}'").copy()
            st.session_state['df_hist'] = nacti_csv(SOUBOR_HISTORIE).query(f"Owner=='{USER}'").copy()
            st.session_state['df_cash'] = nacti_csv(SOUBOR_CASH).query(f"Owner=='{USER}'").copy()
            st.session_state['df_watch'] = nacti_csv(SOUBOR_WATCHLIST).query(f"Owner=='{USER}'").copy()
            st.session_state['hist_vyvoje'] = aktualizuj_graf_vyvoje(USER, 0)

    df = st.session_state['df']; df_cash = st.session_state['df_cash']; df_watch = st.session_state['df_watch']
    zustatky = get_zustatky(USER); kurzy = ziskej_kurzy()

    with st.sidebar:
        st.write(f"👤 **{USER.upper()}**")
        if st.button("LOGOUT"): st.session_state.clear(); st.rerun()
        st.divider()
        st.subheader("🔍 WATCHLIST")
        w_new = st.text_input("Ticker", placeholder="NVDA").upper()
        if w_new:
            if pridat_do_watchlistu(w_new, USER): st.rerun()
        if not df_watch.empty:
            wd = get_live_data_batch(df_watch['Ticker'].tolist())
            for t in df_watch['Ticker']:
                info = wd.get(t)
                c1, c2 = st.columns([3, 1])
                c1.metric(t, f"{info['price']:.2f} {info['curr']}" if info else "?")
                if c2.button("✖", key=f"d_{t}"): odebrat_z_watchlistu(t, USER); st.rerun()

    st.title(f"📊 TERMINAL: {USER.upper()}")
    st.divider()

    # VÝPOČTY
    viz_data = []; celk_hod_usd = 0; celk_inv_usd = 0
    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        bar = st.progress(0, "MARKET DATA...")
        for i, (idx, row) in enumerate(df_g.iterrows()):
            tkr = row['Ticker']
            p, m = ziskej_info(tkr); p = p if p else row['Cena']
            sektor = ziskej_sektor(tkr)
            hod = row['Pocet']*p; inv = row['Pocet']*row['Cena']; z = hod-inv
            k = 1/kurzy["CZK"] if m=="CZK" else (kurzy["EUR"] if m=="EUR" else 1)
            celk_hod_usd += hod*k; celk_inv_usd += inv*k
            viz_data.append({"Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m, "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Cena']})
            bar.progress((i+1)/len(df_g))
        bar.empty()

    hist_vyvoje = st.session_state['hist_vyvoje']
    if celk_hod_usd > 0: hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)

    # KPI
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("LIQUIDITY (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f}")
    cash_usd = sum([v/kurzy["CZK"] if k=="CZK" else (v*kurzy["EUR"] if k=="EUR" else v) for k,v in zustatky.items()])
    k2.metric("CASH (USD)", f"$ {cash_usd:,.0f}")
    if not hist_vyvoje.empty and len(hist_vyvoje) > 1:
        diff = celk_hod_usd - hist_vyvoje.iloc[-2]['TotalUSD']
        k3.metric("24H CHANGE", f"{diff:+,.0f} $")
    else: k3.metric("24H CHANGE", "$ 0")
    top_s = pd.DataFrame(viz_data).groupby('Sektor')['HodnotaUSD'].sum().idxmax() if viz_data else "N/A"
    k4.metric("TOP SECTOR", top_s)

    st.divider()

    t1, t2, t3, t4 = st.tabs(["PORTFOLIO", "WALLET", "TRADE", "LOGS"])

    with t1:
        c1, c2 = st.columns([2, 1])
        with c1:
            # PŘEPÍNAČ POHLEDŮ (JE ZPÁTKY!)
            rezim = st.radio("Pohled:", ["Editace (Tabulka)", "Přehled (Grafický)"], horizontal=True)
            
            if rezim == "Editace (Tabulka)":
                st.caption("Zde můžeš upravovat jednotlivé nákupy.")
                edited_df = st.data_editor(df[["Ticker", "Pocet", "Cena", "Datum"]], num_rows="dynamic", use_container_width=True)
                if not df[["Ticker", "Pocet", "Cena", "Datum"]].reset_index(drop=True).equals(edited_df.reset_index(drop=True)):
                    if st.button("💾 SAVE CHANGES"):
                        st.session_state['df'] = edited_df; uloz_data_uzivatele(edited_df, USER, SOUBOR_DATA); st.success("SAVED"); st.rerun()
            else:
                if viz_data:
                    vdf = pd.DataFrame(viz_data)
                    st.dataframe(vdf[["Ticker", "Měna", "Sektor", "Kusy", "Průměr", "Cena", "Hodnota", "Zisk"]].style.format({"Průměr": "{:.2f}", "Cena": "{:.2f}", "Hodnota": "{:,.0f}", "Zisk": "{:+,.0f}"}).map(lambda x: 'color: green' if x>0 else 'color: red', subset=['Zisk']), use_container_width=True)
                else: st.info("No assets.")

        with c2:
            st.subheader("MARKET MAP")
            if viz_data:
                fig = px.treemap(vdf, path=[px.Constant("ALL"), 'Sektor', 'Ticker'], values='HodnotaUSD', color='Zisk', color_continuous_scale=['red', '#161B22', 'green'], color_continuous_midpoint=0)
                st.plotly_chart(fig, use_container_width=True)
                if not hist_vyvoje.empty:
                    st.caption("Equity Curve")
                    st.line_chart(hist_vyvoje.set_index("Date")['TotalUSD'], color="#00FF00")

    with t2:
        c1, c2 = st.columns(2)
        with c1:
            with st.form("d"):
                a = st.number_input("Amount", 1.0); c = st.selectbox("Cur", ["USD", "CZK", "EUR"])
                if st.form_submit_button("DEPOSIT"): pohyb_penez(a, c, "Vklad", "Man", USER); st.success("OK"); st.rerun()
            with st.form("w"):
                a = st.number_input("Amount", 1.0); c = st.selectbox("Cur", ["USD", "CZK", "EUR"])
                if st.form_submit_button("WITHDRAW"): pohyb_penez(-a, c, "Vyber", "Man", USER); st.success("OK"); st.rerun()
        with c2: st.dataframe(df_cash.sort_values("Datum", ascending=False), use_container_width=True)

    with t3:
        if not df.empty:
            with st.form("b"):
                t = st.text_input("BUY Ticker").upper(); p = st.number_input("Qty", 0.001); c = st.number_input("Price", 0.1)
                if st.form_submit_button("BUY
