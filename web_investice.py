import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
from datetime import datetime
import hashlib

# --- KONFIGURACE STRÁNKY (WIDE MODE) ---
st.set_page_config(page_title="Terminal", layout="wide", page_icon="💹")

# --- KONSTANTY ---
REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv"

# --- PROFESIONÁLNÍ "BLOOMBERG" STYLY ---
st.markdown("""
<style>
    /* Styling for the Bloomberg look */
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

# --- SPRÁVA UŽIVATELŮ ---
def nacti_uzivatele():
    try: df = nacti_csv(SOUBOR_UZIVATELE); return df
    except: return pd.DataFrame(columns=["username", "password", "recovery_key"])

# --- UNIVERZÁLNÍ UKLÁDÁNÍ ---
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
        
        if 'Datum' in df.columns: df['Datum'] = pd.to_datetime(df['Datum'], errors='coerce')
        if 'Date' in df.columns: df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        df['Owner'] = df['Owner'].astype(str)
        return df
    except:
        if nazev_souboru == SOUBOR_HISTORIE: return pd.DataFrame(columns=["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"])
        if nazev_souboru == SOUBOR_CASH: return pd.DataFrame(columns=["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"])
        if nazev_souboru == SOUBOR_VYVOJ: return pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
        if nazev_souboru == SOUBOR_UZIVATELE: return pd.DataFrame(columns=["username", "password", "recovery_key"])
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena", "Datum", "Owner"])

def uloz_data_uzivatele(user_df, username, nazev_souboru):
    full_df = nacti_csv(nazev_souboru)
    full_df = full_df[full_df['Owner'] != str(username)]
    if not user_df.empty:
        user_df['Owner'] = str(username)
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    uloz_csv(full_df, nazev_souboru, f"Update {username}")
    st.cache_data.clear()

# --- PENĚŽENKA LOGIKA ---
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

# --- VÝVOJ HODNOTY ---
def aktualizuj_graf_vyvoje(user, aktualni_hodnota_usd):
    try: full_hist = nacti_csv(SOUBOR_VYVOJ)
    except: full_hist = pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    if not full_hist.empty: full_hist['Date'] = pd.to_datetime(full_hist['Date'])
    today = datetime.now().strftime("%Y-%m-%d")
    user_hist = full_hist[full_hist['Owner'] == str(user)].copy()
    dnes_uz_zapsano = False
    if not user_hist.empty:
        last_date = user_hist.iloc[-1]['Date']
        if pd.to_datetime(last_date).strftime("%Y-%m-%d") == today:
            dnes_uz_zapsano = True
            last_idx = user_hist.index[-1]
            full_hist.at[last_idx, 'TotalUSD'] = aktualni_hodnota_usd
    if not dnes_uz_zapsano:
        new_row = pd.DataFrame([{"Date": datetime.now(), "TotalUSD": aktualni_hodnota_usd, "Owner": str(user)}])
        full_hist = pd.concat([full_hist, new_row], ignore_index=True)
    uloz_csv(full_hist, SOUBOR_VYVOJ, "Daily snapshot")
    return full_hist[full_hist['Owner'] == str(user)]

# --- LOGIKA PRODEJE ---
def proved_prodej(ticker, kusy_k_prodeji, prodejni_cena, user, mena_akcie):
    df_port = st.session_state['df'].copy(); df_hist = st.session_state['df_hist'].copy()
    df_ticker = df_port[df_port['Ticker'] == ticker].sort_values('Datum')
    if df_ticker.empty or df_ticker['Pocet'].sum() < kusy_k_prodeji: return False, "Nedostatek kusů."
    zbyva, zisk, trzba = kusy_k_prodeji, 0, kusy_k_prodeji * prodejni_cena 
    for idx, row in df_ticker.iterrows():
        if zbyva <= 0: break
        ukrojeno = min(row['Pocet'], zbyva)
        zisk += (prodejni_cena - row['Cena']) * ukrojeno
        if ukrojeno == row['Pocet']: df_port = df_port.drop(idx)
        else: df_port.at[idx, 'Pocet'] -= ukrojeno
        zbyva -= ukrojeno
    new_hist = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy_k_prodeji, "Prodejka": prodejni_cena, "Zisk": zisk, "Mena": mena_akcie, "Datum": datetime.now(), "Owner": user}])
    df_hist = pd.concat([df_hist, new_hist], ignore_index=True)
    pohyb_penez(trzba, mena_akcie, "Prodej", f"Prodej {ticker}", user)
    st.session_state['df'] = df_port; st.session_state['df_hist'] = df_hist
    uloz_data_uzivatele(df_port, user, SOUBOR_DATA); uloz_data_uzivatele(df_hist, user, SOUBOR_HISTORIE)
    return True, f"Prodáno! +{trzba:,.2f} {mena_akcie}"

# --- EXTERNAL DATA ---
@st.cache_data(ttl=86400)
def ziskej_sektor(ticker):
    try: return yf.Ticker(str(ticker)).info.get('sector', 'Ostatní')
    except: return 'Ostatní'

@st.cache_data(ttl=3600)
def ziskej_kurzy():
    kurzy = {"USD": 1.0}
    try:
        data = yf.download(["CZK=X", "EURUSD=X"], period="1d")['Close'].iloc[-1]
        kurzy["CZK"] = float(data["CZK=X"]); kurzy["EUR"] = float(data["EURUSD=X"])
    except: pass
    return kurzy

def ziskej_info_o_akcii(ticker):
    if not ticker or pd.isna(ticker): return None, "USD"
    try: akcie = yf.Ticker(str(ticker)); return akcie.fast_info.last_price, akcie.fast_info.currency
    except: return None, "USD"

# --- MAIN APP ---
def main():
    if 'prihlasen' not in st.session_state: st.session_state['prihlasen'] = False
    if 'aktualni_uzivatel' not in st.session_state: st.session_state['aktualni_uzivatel'] = ""

    if not st.session_state['prihlasen']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.header("🔒 TERMINAL ACCESS")
            t1, t2 = st.tabs(["LOGIN", "REGISTER"])
            with t1:
                with st.form("log"):
                    u = st.text_input("USER")
                    p = st.text_input("PASS", type="password")
                    if st.form_submit_button(">>> CONNECT", use_container_width=True):
                        users = nacti_uzivatele(); row = users[users['username'] == u] if not users.empty else pd.DataFrame()
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            st.session_state.clear(); st.session_state['prihlasen'] = True; st.session_state['aktualni_uzivatel'] = u; st.rerun()
                        else: st.error("ACCESS DENIED")
            with t2:
                with st.form("reg"):
                    nu = st.text_input("NEW USER"); np = st.text_input("PASS", type="password"); rec = st.text_input("RECOVERY KEY", type="password")
                    if st.form_submit_button(">>> CREATE", use_container_width=True):
                        users = nacti_uzivatele(); if not users.empty and nu in users['username'].values: st.error("USER EXISTS")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(np), "recovery_key": zasifruj(rec)}]); uloz_csv(pd.concat([users, new], ignore_index=True), SOUBOR_UZIVATELE, "New user"); st.success("CREATED")
        return

    # --- PŘIHLÁŠENÝ UŽIVATEL - TERMINÁL ---
    USER = st.session_state['aktualni_uzivatel']
    
    # NAČTENÍ DAT
    if 'df' not in st.session_state:
        with st.spinner("INITIALIZING DATA STREAMS..."):
            fp = nacti_csv(SOUBOR_DATA); st.session_state['df'] = fp[fp['Owner'] == str(USER)].copy()
            fh = nacti_csv(SOUBOR_HISTORIE); st.session_state['df_hist'] = fh[fh['Owner'] == str(USER)].copy()
            fc = nacti_csv(SOUBOR_CASH); st.session_state['df_cash'] = fc[fc['Owner'] == str(USER)].copy()
            st.session_state['hist_vyvoje'] = aktualizuj_graf_vyvoje(USER, 0)

    df = st.session_state['df']; df_hist = st.session_state['df_hist']; df_cash = st.session_state['df_cash']
    zustatky = get_zustatky(USER)

    # --- HORNÍ KPI PÁS (HEADS-UP DISPLAY) ---
    st.title(f"📊 PORTFOLIO TERMINAL: {USER.upper()}")
    st.divider()

    # VÝPOČET DAT
    viz_data = []; celk_hod_usd = 0; celk_inv_usd = 0; stats_meny = {}
    if not df.empty:
        df_grouped = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        kurzy = ziskej_kurzy()
        bar = st.progress(0, "FETCHING LIVE DATA & SECTORS...")
        
        # SÍTO: Filtrace pro zobrazení
        filtered_df = df_grouped # Tady budeme vždy pracovat s AGREG. daty
        
        for i, (idx, row) in enumerate(filtered_df.iterrows()):
            if pd.isna(row['Ticker']) or pd.isna(row['Pocet']): continue
            tkr = str(row['Ticker']); cena_ted, mena = ziskej_info_o_akcii(tkr); sektor = ziskej_sektor(tkr)
            cena_ted = cena_ted if cena_ted else row['Cena']
            hod = row['Pocet'] * cena_ted; inv = row['Pocet'] * row['Cena']; zisk = hod - inv
            konv = 1.0 / kurzy["CZK"] if mena == "CZK" else (kurzy["EUR"] if mena == "EUR" else 1.0)
            celk_hod_usd += hod * konv; celk_inv_usd += inv * konv
            
            # Agregace pro metriky
            if mena not in stats_meny: stats_meny[mena] = {"inv": 0, "zisk": 0}
            stats_meny[mena]["inv"] += inv; stats_meny[mena]["zisk"] += zisk
            
            trend = "▲" if cena_ted > row['Cena'] else ("▼" if cena_ted < row['Cena'] else "■")
            viz_data.append({"Ticker": tkr, "Sektor": sektor, "Kusy": row['Pocet'], "Avg Cena": row['Cena'], "Live Cena": cena_ted, "Trend": trend, "Zisk (Měna)": zisk, "Měna": mena, "HodnotaUSD": hod*konv, "ZiskUSD": zisk*konv})
            bar.progress((i+1)/len(filtered_df))
        bar.empty()

    # Aktualizace historie a výpočet 24h změny
    hist_vyvoje = st.session_state['hist_vyvoje']
    if celk_hod_usd > 0:
         hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
         st.session_state['hist_vyvoje'] = hist_vyvoje

    zmena_24h_usd = 0; zmena_pct = 0
    if len(hist_vyvoje) > 1:
        vcera_usd = hist_vyvoje.iloc[-2]['TotalUSD']
        zmena_24h_usd = celk_hod_usd - vcera_usd
        zmena_pct = (zmena_24h_usd / vcera_usd * 100) if vcera_usd > 0 else 0

    # Oprava NaN u cash
    cash_usd = (zustatky.get('USD', 0) * 1.0) + (zustatky.get('CZK', 0)/kurzy.get('CZK', 25.0)) + (zustatky.get('EUR', 0)*kurzy.get('EUR', 1.0))
    if cash_usd == 0 and not zustatky: cash_usd = 0 # Zajištění, že se nezobrazí $nan

    # Zobrazení KPI karet
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("NET LIQUIDITY (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} P&L")
    kpi2.metric("24H CHANGE (USD)", f"$ {zmena_24h_usd:+,.0f}", f"{zmena_pct:+.2f}%")
    kpi3.metric("AVAILABLE CASH (USD EST)", f"$ {cash_usd:,.0f}", "READY TO DEPLOY")
    
    top_sektor = "N/A"
    if viz_data:
        gf = pd.DataFrame(viz_data)
        top_sektor = gf.groupby('Sektor')['HodnotaUSD'].sum().idxmax()
    kpi4.metric("TOP EXPOSURE", f"{top_sektor}", f"{len(df) if not df.empty else 0} POSITIONS")

    st.divider()

    # --- HLAVNÍ ROZLOŽENÍ (GRID) ---
    col_left, col_right = st.columns([2, 1])

    with col_left:
        t_sum, t_edit = st.tabs(["SUMMARY VIEW", "EDIT DATA"])
        
        # TABULKA VÝPISU
        with t_sum:
             if viz_data:
                gf = pd.DataFrame(viz_data)
                st.dataframe(
                    gf[["Ticker", "Trend", "Live Cena", "Avg Cena", "Kusy", "Měna", "Zisk (Měna)"]]
                    .style
                    .format({"Live Cena": "{:.2f}", "Avg Cena": "{:.2f}", "Kusy": "{:.2f}", "Zisk (Měna)": "{:+,.0f}"})
                    .map(lambda x: 'color: #00FF00;' if x > 0 else 'color: #FF4B4B;', subset=['Zisk (Měna)', 'Trend'])
                    .set_properties(**{'background-color': '#161B22', 'color': '#E6EDF3', 'border-color': '#30363D'}),
                    use_container_width=True, height=400
                )
             else: st.info("NO POSITIONS.")

        # EDITOVATELNÝ DETAIL
        with t_edit:
            st.warning("⚠️ Změny v tabulce MUSÍTE uložit tlačítkem dole!")
            # POZOR: Zde editujeme RAW data (df), ne ta AGREGovaná!
            edited_df = st.data_editor(
                df[["Ticker", "Pocet", "Cena", "Datum"]],
                num_rows="dynamic", use_container_width=True,
                column_config={"Pocet": st.column_config.NumberColumn(format="%.4f"), "Cena": st.column_config.NumberColumn(format="%.2f"), "Datum": st.column_config.DatetimeColumn(format="D.M.YYYY")}
            )
            if not df[["Ticker", "Pocet", "Cena", "Datum"]].reset_index(drop=True).equals(edited_df.reset_index(drop=True)):
                if st.button("💾 SAVE CHANGES TO GITHUB"):
                    st.session_state['df'] = edited_df
                    uloz_data_uzivatele(edited_df, USER, SOUBOR_DATA)
                    st.success("SAVED"); st.rerun()

        # QUICK ACTIONS
        with st.expander("⚡ TRANSACTION ENTRY (BUY/SELL/CASH)"):
             t_buy, t_sell_tab, t_cash_tab = st.tabs(["BUY", "SELL", "CASH MGMT"])
             # KÓD ZŮSTÁVÁ STEJNÝ

    with col_right:
        st.subheader("📈 EQUITY CURVE")
        if not hist_vyvoje.empty:
            fig_line = px.area(hist_vyvoje, x='Date', y='TotalUSD')
            fig_line.update_layout(margin=dict(t=0, l=0, r=0, b=0), showlegend=False, font=dict(family="Roboto Mono", color="#E6EDF3"), paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
                                   xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#30363D'))
            fig_line.update_traces(line_color='#00FF00', fillcolor='rgba(0, 255, 0, 0.1)')
            st.plotly_chart(fig_line, use_container_width=True)
        else: st.info("NO HISTORY.")
        
        st.subheader("🗺️ SECTOR DIVERSIFICATION")
        if viz_data:
            # PROFESIONÁLNÍ TREEMAP
            fig_tree = px.treemap(gf, path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'], values='HodnotaUSD',
                                  color='ZiskUSD', color_continuous_scale=['#FF4B4B', '#161B22', '#00FF00'], 
                                  color_continuous_midpoint=0)
            fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), font=dict(family="Roboto Mono", color="#E6EDF3"), paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
            fig_tree.data[0].textinfo = 'label+text+value'
            st.plotly_chart(fig_tree, use_container_width=True)

    # --- PATIČKA ---
    st.divider()
    with st.expander("⚙️ SYSTEM & DATA MANAGEMENT"):
        t_hist_ed, t_raw = st.tabs(["TRADE LOGS", "RAW DATA"])
        # KÓD ZŮSTÁVÁ STEJNÝ

    if st.sidebar.button(">>> LOGOUT"): st.session_state.clear(); st.rerun()

if __name__ == "__main__":
    main()
