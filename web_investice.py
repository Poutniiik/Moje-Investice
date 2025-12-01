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

REPO_NAZEV = "Poutniik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv"
SOUBOR_WATCHLIST = "watchlist.csv"
SOUBOR_DIVIDENDY = "dividends.csv"

# --- STYLY ---
st.markdown("""
<style>
    .stApp {background-color: #0E1117; font-family: 'Roboto Mono', monospace;}
    div[data-testid="stMetric"] {background-color: #161B22; border: 1px solid #30363D; padding: 15px; border-radius: 5px; color: #E6EDF3;}
    div[data-testid="stMetricLabel"] {font-size: 0.9rem; color: #8B949E; font-weight: bold; text-transform: uppercase;}
    div[data-testid="stMetricValue"] {font-size: 1.5rem; color: #E6EDF3; font-weight: bold;}
    h1, h2, h3 {color: #E6EDF3 !important; font-family: 'Roboto Mono', monospace; text-transform: uppercase; letter-spacing: 1px;}
    hr {border-color: #30363D;}
    div[data-testid="column"] button {border: 1px solid #FF4B4B; color: #FF4B4B;}
    div[data-testid="stTooltipIcon"] {color: #58A6FF;}
</style>
""", unsafe_allow_html=True)

# --- PŘIPOJENÍ ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
except: st.error("❌ CHYBA: Chybí GitHub Token v Secrets!"); st.stop()

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

# --- CASH & HISTORY & DIVI ---
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

def pridat_dividendu(ticker, castka, mena, user):
    df_div = st.session_state['df_div']
    novy = pd.DataFrame([{"Ticker": ticker, "Castka": castka, "Mena": mena, "Datum": datetime.now(), "Owner": user}])
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

# --- INFO & TURBO MODE (CACHE) ---
@st.cache_data(ttl=900)
def ziskej_ceny_hromadne(tickers):
    data = {}
    if not tickers: return data
    try:
        ts = list(set(tickers + ["CZK=X", "EURUSD=X"]))
        df_y = yf.download(ts, period="1d", group_by='ticker', progress=False)
        for t in ts:
            try:
                price = df_y[t]['Close'].iloc[-1] if len(ts) > 1 else df_y['Close'].iloc[-1]
                # 🛠️ FIX MĚNY NATVRDO
                curr = "USD"
                if ".PR" in t: curr = "CZK"
                elif ".DE" in t: curr = "EUR"
                
                if pd.notnull(price): data[t] = {"price": float(price), "curr": curr}
            except: pass
    except: pass
    return data

@st.cache_data(ttl=86400)
def ziskej_sektor(ticker):
    try: return yf.Ticker(str(ticker)).info.get('sector', 'Ostatní')
    except: return 'Ostatní'

@st.cache_data(ttl=3600)
def ziskej_kurzy():
    kurzy = {"USD": 1.0, "CZK": 24.5, "EUR": 1.05}
    try:
        d = yf.download(["CZK=X", "EURUSD=X"], period="1d", progress=False)['Close'].iloc[-1]
        if pd.notnull(d["CZK=X"]): kurzy["CZK"] = float(d["CZK=X"])
        if pd.notnull(d["EURUSD=X"]): kurzy["EUR"] = float(d["EURUSD=X"])
    except: pass
    return kurzy

def ziskej_info(ticker):
    # 🛠️ FIX MĚNY NATVRDO
    mena = "USD"
    if ".PR" in str(ticker): mena = "CZK"
    elif ".DE" in str(ticker): mena = "EUR"
    
    try: 
        t = yf.Ticker(str(ticker))
        price = t.fast_info.last_price
        # Ponecháme naši měnu, pokud Yahoo nepošle nic
        return price, mena
    except: return None, mena

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

    # LOGIN SCREEN
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
                    nr=st.text_input("Záchranný kód", help="Slouží pro obnovu zapomenutého hesla. Dobře si ho zapamatuj!")
                    if st.form_submit_button("VYTVOŘIT ÚČET", use_container_width=True):
                        df_u = nacti_uzivatele()
                        if not df_u.empty and nu in df_u['username'].values: st.toast("Jméno již existuje.", icon="⚠️")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(np), "recovery_key": zasifruj(nr)}])
                            uloz_csv(pd.concat([df_u, new], ignore_index=True), SOUBOR_UZIVATELE, "New user"); st.toast("Účet vytvořen!", icon="✅")
        return

    # --- DASHBOARD INIT ---
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

    # 🏎️ TURBO FETCHING
    all_tickers = []
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    LIVE_DATA = ziskej_ceny_hromadne(list(set(all_tickers)))
    
    if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
    if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]

    # --- SIDEBAR ---
    with st.sidebar:
        st.write(f"👤 **{USER.upper()}**")
        if zustatky:
            st.caption("Stav peněženky:")
            for mena, castka in zustatky.items():
                if castka > 0.01 or castka < -0.01:
                    sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
                    st.write(f"💵 **{castka:,.2f} {sym}**")
        st.divider()
        page = st.radio("MENU", ["🏠 Přehled", "📈 Analýza", "💸 Obchod & Peníze", "💎 Dividendy", "⚙️ Správa Dat"])
        st.divider()
        
        st.subheader("🔍 SLEDOVANÉ")
        with st.form("w_add", clear_on_submit=True):
            new_w = st.text_input("Symbol", placeholder="NVDA").upper()
            if st.form_submit_button("Přidat"):
                if new_w: pridat_do_watchlistu(new_w, USER); st.rerun()
            
        if not df_watch.empty:
            for t in df_watch['Ticker']:
                info = LIVE_DATA.get(t, {})
                price = info.get('price'); curr = info.get('curr', '?')
                c1, c2 = st.columns([3, 1])
                c1.metric(t, f"{price:.2f} {curr}" if price else "?")
                c2.write(""); c2.write("")
                if c2.button("🗑️", key=f"del_{t}", on_click=odebrat_z_watchlistu, args=(t, USER)): pass
        else:
            st.caption("Seznam je prázdný.")
        st.divider()
        if st.button("ODHLÁSIT SE"): st.session_state.clear(); st.rerun()

    # VÝPOČTY
    viz_data = []; celk_hod_usd = 0; celk_inv_usd = 0; stats_meny = {}
    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        df_g['Cena'] = df_g['Investice'] / df_g['Pocet']

        for i, (idx, row) in enumerate(df_g.iterrows()):
            tkr = row['Ticker']
            inf = LIVE_DATA.get(tkr, {})
            p = inf.get('price', row['Cena'])
            
            # 🛠️ FIX MĚNY PŘI ZOBRAZENÍ
            m = "USD"
            if ".PR" in tkr: m = "CZK"
            elif ".DE" in tkr: m = "EUR"
            
            sektor = ziskej_sektor(tkr)
            
            hod = row['Pocet']*p; inv = row['Investice']; z = hod-inv
            try: k = 1.0 / kurzy.get("CZK", 24.5) if m=="CZK" else (kurzy.get("EUR", 1.05) if m=="EUR" else 1.0)
            except: k = 1.0
            celk_hod_usd += hod*k; celk_inv_usd += inv*k
            if m not in stats_meny: stats_meny[m] = {"inv":0, "zisk":0}
            stats_meny[m]["inv"]+=inv; stats_meny[m]["zisk"]+=z
            viz_data.append({"Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m, "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Cena']})

    hist_vyvoje = st.session_state['hist_vyvoje']
    if celk_hod_usd > 0 and pd.notnull(celk_hod_usd): hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    
    zmena_24h = 0; pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if pd.notnull(vcera) and vcera > 0:
            zmena_24h = celk_hod_usd - vcera
            pct_24h = (zmena_24h / vcera * 100)

    # --- STRÁNKY ---
    if page == "🏠 Přehled":
        st.title(f"🏠 PŘEHLED: {USER.upper()}")
        k1, k2, k3 = st.columns(3)
        k1.metric("ČISTÉ JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} Zisk")
        k2.metric("ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        try: cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 24.5)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.05))
        except: cash_usd = 0
        k3.metric("HOTOVOST (USD EST)", f"${cash_usd:,.0f}", "Připraveno")
        
        st.divider()
        st.subheader("💰 Peněženky (Investováno vs Zisk)")
        cols = st.columns(len(stats_meny)) if stats_meny else [st.container()]
        for i, m in enumerate(stats_meny):
            d = stats_meny[m]
            sym = "$" if m=="USD" else ("Kč" if m=="CZK" else "€")
            cols[i].metric(f"{m}", f"Inv: {d['inv']:,.0f} {sym}", f"{d['zisk']:+,.0f} {sym}")
        
        st.divider()
        if viz_data:
            vdf = pd.DataFrame(viz_data)
            st.dataframe(vdf[["Ticker", "Měna", "Sektor", "Kusy", "Průměr", "Cena", "Hodnota", "Zisk"]].style.format({"Průměr": "{:.2f}", "Cena": "{:.2f}", "Hodnota": "{:,.0f}", "Zisk": "{:+,.0f}"}).background_gradient(cmap="RdYlGn", subset=["Zisk"], vmin=-1000, vmax=1000), use_container_width=True)
        else: st.info("Portfolio je prázdné. Jdi do sekce Obchod.")

    elif page == "📈 Analýza":
        st.title("📈 HLOUBKOVÁ ANALÝZA")
        if viz_data:
            vdf = pd.DataFrame(viz_data)
            c1, c2 = st.columns(2)
            with c1:
                st.caption("MAPA TRHU (Sektory)")
                fig = px.treemap(vdf, path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'], values='HodnotaUSD', color='Zisk', color_continuous_scale=['red', '#161B22', 'green'], color_continuous_midpoint=0)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.caption("VÝVOJ HODNOTY (Časová osa)")
                if not hist_vyvoje.empty: st.line_chart(hist_vyvoje.set_index("Date")['TotalUSD'])
            st.divider()
            c3, c4 = st.columns(2)
            with c3:
                st.caption("DIVERZIFIKACE (USD)")
                fig2 = px.pie(vdf, values='HodnotaUSD', names='Ticker', hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)
            with c4:
                st.caption("EFEKTIVITA (Zisk)")
                fig3 = px.bar(vdf, x='Ticker', y='Zisk', color='Zisk', color_continuous_scale=['red', 'green'])
                st.plotly_chart(fig3, use_container_width=True)
        else: st.info("Žádná data.")

    elif page == "💸 Obchod & Peníze":
        st.title("💸 BANKA A OBCHODOVÁNÍ")
        t_bank, t_ex, t_buy, t_sell = st.tabs(["🏦 PENĚŽENKA", "💱 SMĚNÁRNA", "🛒 NÁKUP", "📉 PRODEJ"])
        
        with t_bank:
            c1, c2 = st.columns(2)
            with c1:
                with st.form("d"):
                    a = st.number_input("Částka", 1.0); c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                    if st.form_submit_button("💰 VLOŽIT PENÍZE"): pohyb_penez(a, c, "Vklad", "Man", USER); st.toast("Vloženo", icon="✅"); st.rerun()
                with st.form("w"):
                    a = st.number_input("Částka", 1.0); c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                    if st.form_submit_button("💸 VYBRAT PENÍZE"): pohyb_penez(-a, c, "Vyber", "Man", USER); st.toast("Vybráno", icon="✅"); st.rerun()
            with c2:
                st.write("Historie transakcí:"); st.dataframe(df_cash.sort_values("Datum", ascending=False), use_container_width=True)
        
        with t_ex:
            st.subheader("Směna měn")
            st.info(f"Kurzy: 1 USD = {kurzy.get('CZK', 24):.2f} CZK | 1 EUR = {kurzy.get('EUR', 1.05):.2f} USD")
            with st.form("exchange"):
                c1, c2, c3 = st.columns(3)
                with c1: castka_ex = st.number_input("Směnit částku", 1.0)
                with c2: z_meny = st.selectbox("Z měny", ["USD", "CZK", "EUR"])
                with c3: do_meny = st.selectbox("Do měny", ["CZK", "USD", "EUR"])
                if st.form_submit_button("💱 PROVÉST SMĚNU"):
                    dispo = zustatky.get(z_meny, 0)
                    if dispo >= castka_ex:
                        ok, msg = proved_smenu(castka_ex, z_meny, do_meny, USER); st.toast(msg, icon="✅"); st.rerun()
                    else: st.toast(f"Chybí ti {z_meny}", icon="❌")

        with t_buy:
            st.subheader("Nákup akcií")
            with st.form("b"):
                t = st.text_input("Symbol").upper(); p = st.number_input("Ks", 0.001); c = st.number_input("Cena", 0.1)
                if st.form_submit_button("KOUPIT"):
                    _, m = ziskej_info(t)
                    # Vynutit měnu pro nákup
                    if ".PR" in t: m = "CZK"
                    elif ".DE" in t: m = "EUR"
                    else: m = "USD"
                    
                    cost = p*c; bal = zustatky.get(m, 0)
                    if bal >= cost:
                        pohyb_penez(-cost, m, "Nákup", f"Buy {t}", USER)
                        new = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now(), "Owner": USER}])
                        upd = pd.concat([df, new], ignore_index=True)
                        st.session_state['df'] = upd; uloz_data_uzivatele(upd, USER, SOUBOR_DATA); st.toast("OK", icon="🛒"); st.rerun()
                    else: st.toast(f"Nedostatek {m}! Jdi do směnárny.", icon="❌")
        
        with t_sell:
            st.subheader("Prodej akcií")
            if not df.empty:
                tickery = df['Ticker'].unique().tolist()
                with st.form("s"):
                    t = st.selectbox("Vyber akcii", tickery); q = st.number_input("Ks", 0.001); pr = st.number_input("Cena", 0.1)
                    if st.form_submit_button("PRODAT"):
                        _, m = ziskej_info(t)
                        if ".PR" in t: m = "CZK"
                        elif ".DE" in t: m = "EUR"
                        else: m = "USD"
                        
                        ok, msg = proved_prodej(t, q, pr, USER, m)
                        if ok: st.toast("Prodáno", icon="✅"); st.rerun()
                        else: st.toast(msg, icon="⚠️")
        
    elif page == "💎 Dividendy":
        st.title("💎 DIVIDENDY")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Připsat dividendu")
            with st.form("div"):
                t = st.text_input("Ticker").upper(); a = st.number_input("Částka", 0.01); c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                if st.form_submit_button("PŘIPSAT"): pridat_dividendu(t, a, c, USER); st.toast("Připsáno", icon="💎"); st.rerun()
        with c2:
            if not df_div.empty:
                st.dataframe(df_div.sort_values("Datum", ascending=False), use_container_width=True)
                meny_divi = df_div['Mena'].unique().tolist()
                if meny_divi:
                    st.divider()
                    cols = st.columns(len(meny_divi))
                    for i, m in enumerate(meny_divi):
                        suma = df_div[df_div['Mena'] == m]['Castka'].sum()
                        sym = "$" if m=="USD" else ("Kč" if m=="CZK" else "€" if m=="EUR" else m)
                        cols[i].metric(f"Celkem ({m})", f"{suma:,.2f} {sym}")

    elif page == "⚙️ Správa Dat":
        st.title("⚙️ EDITACE")
        t1, t2 = st.tabs(["Portfolio", "Historie"])
        with t1:
            ed = st.data_editor(df[["Ticker", "Pocet", "Cena", "Datum"]], num_rows="dynamic", use_container_width=True)
            if not df[["Ticker", "Pocet", "Cena", "Datum"]].reset_index(drop=True).equals(ed.reset_index(drop=True)):
                if st.button("💾 ULOŽIT PORTFOLIO"): st.session_state['df'] = ed; uloz_data_uzivatele(ed, USER, SOUBOR_DATA); st.toast("Uloženo", icon="✅"); st.rerun()
        with t2:
            st.session_state['df_hist'] = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True, key="he")
            if st.button("💾 ULOŽIT HISTORII"): uloz_data_uzivatele(st.session_state['df_hist'], USER, SOUBOR_HISTORIE); st.toast("Uloženo", icon="✅"); st.rerun()

if __name__ == "__main__":
    main()
