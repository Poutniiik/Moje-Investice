import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
from datetime import datetime
import hashlib

# --- KONFIGURACE ---
st.set_page_config(page_title="Investiční App", layout="wide", page_icon="📈")

REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"
SOUBOR_UZIVATELE = "users_db.csv"
SOUBOR_HISTORIE = "history_data.csv"

# --- STYLY ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 15px; text-align: center;}
    div[data-testid="stMetricValue"] {font-size: 1.6rem;}
</style>
""", unsafe_allow_html=True)

# --- PŘIPOJENÍ ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
except:
    st.error("❌ CHYBA: Chybí GitHub Token v Secrets!")
    st.stop()

def get_repo():
    return Github(GITHUB_TOKEN).get_repo(REPO_NAZEV)

def zasifruj(text):
    return hashlib.sha256(str(text).encode()).hexdigest()

# --- SPRÁVA UŽIVATELŮ ---
def nacti_uzivatele():
    repo = get_repo()
    try:
        file = repo.get_contents(SOUBOR_UZIVATELE)
        return pd.read_csv(StringIO(file.decoded_content.decode("utf-8")), dtype=str)
    except:
        try:
            p = zasifruj(st.secrets["login"]["heslo"])
            def_user = st.secrets["login"]["uzivatel"]
        except:
            p = zasifruj("admin123")
            def_user = "admin"
        df = pd.DataFrame([{"username": def_user, "password": p, "recovery_key": zasifruj("admin")}])
        uloz_csv(df, SOUBOR_UZIVATELE, "Init users")
        return df

# --- UNIVERZÁLNÍ UKLÁDÁNÍ ---
def uloz_csv(df, nazev_souboru, zprava):
    repo = get_repo()
    csv = df.to_csv(index=False)
    try:
        file = repo.get_contents(nazev_souboru)
        repo.update_file(file.path, zprava, csv, file.sha)
    except:
        repo.create_file(nazev_souboru, zprava, csv)

def nacti_csv(nazev_souboru):
    try:
        repo = get_repo()
        file = repo.get_contents(nazev_souboru)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        if 'Datum' in df.columns: df['Datum'] = pd.to_datetime(df['Datum'])
        if 'Owner' not in df.columns: df['Owner'] = "admin"
        df['Owner'] = df['Owner'].astype(str)
        return df
    except:
        if nazev_souboru == SOUBOR_HISTORIE:
            return pd.DataFrame(columns=["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"])
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena", "Datum", "Owner"])

def uloz_data_uzivatele(user_df, username, nazev_souboru):
    full_df = nacti_csv(nazev_souboru)
    full_df = full_df[full_df['Owner'] != str(username)]
    if not user_df.empty:
        user_df['Owner'] = str(username)
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    uloz_csv(full_df, nazev_souboru, f"Update {username}")
    st.cache_data.clear()

# --- LOGIKA PRODEJE ---
def proved_prodej(ticker, kusy_k_prodeji, prodejni_cena, user, mena_akcie):
    df_port = st.session_state['df'].copy()
    df_hist = st.session_state['df_hist'].copy()
    
    df_ticker = df_port[df_port['Ticker'] == ticker].sort_values('Datum')
    
    if df_ticker.empty or df_ticker['Pocet'].sum() < kusy_k_prodeji:
        return False, "Nedostatek kusů."

    zbyva = kusy_k_prodeji
    zisk = 0
    
    for idx, row in df_ticker.iterrows():
        if zbyva <= 0: break
        ukrojeno = min(row['Pocet'], zbyva)
        zisk += (prodejni_cena - row['Cena']) * ukrojeno
        
        if ukrojeno == row['Pocet']:
            df_port = df_port.drop(idx)
        else:
            df_port.at[idx, 'Pocet'] -= ukrojeno
        zbyva -= ukrojeno

    new_hist = pd.DataFrame([{
        "Ticker": ticker, "Kusu": kusy_k_prodeji, "Prodejka": prodejni_cena,
        "Zisk": zisk, "Mena": mena_akcie, "Datum": datetime.now(), "Owner": user
    }])
    
    df_hist = pd.concat([df_hist, new_hist], ignore_index=True)
    
    st.session_state['df'] = df_port
    st.session_state['df_hist'] = df_hist
    uloz_data_uzivatele(df_port, user, SOUBOR_DATA)
    uloz_data_uzivatele(df_hist, user, SOUBOR_HISTORIE)
    
    return True, f"Zisk: {zisk:+.2f} {mena_akcie}"

# --- INFO ---
@st.cache_data(ttl=3600)
def ziskej_kurzy():
    kurzy = {"USD": 1.0}
    try:
        data = yf.download(["CZK=X", "EURUSD=X"], period="1d")['Close'].iloc[-1]
        kurzy["CZK"] = float(data["CZK=X"])
        kurzy["EUR"] = float(data["EURUSD=X"])
    except: pass
    return kurzy

def ziskej_info_o_akcii(ticker):
    if not ticker or pd.isna(ticker): return None, "USD"
    try:
        akcie = yf.Ticker(str(ticker))
        return akcie.fast_info.last_price, akcie.fast_info.currency
    except: return None, "USD"

# --- HLAVNÍ APLIKACE ---
def main():
    if 'prihlasen' not in st.session_state: st.session_state['prihlasen'] = False
    if 'aktualni_uzivatel' not in st.session_state: st.session_state['aktualni_uzivatel'] = ""

    # LOGIN
    if not st.session_state['prihlasen']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Investiční Brána")
            t1, t2, t3 = st.tabs(["Přihlášení", "Registrace", "Obnova"])
            with t1:
                with st.form("log"):
                    u = st.text_input("Jméno")
                    p = st.text_input("Heslo", type="password")
                    if st.form_submit_button("Vstoupit", use_container_width=True):
                        users = nacti_uzivatele()
                        row = users[users['username'] == u]
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            st.session_state.clear()
                            st.session_state['prihlasen'] = True
                            st.session_state['aktualni_uzivatel'] = u
                            st.rerun()
                        else: st.error("Chyba")
            with t2:
                with st.form("reg"):
                    nu = st.text_input("Jméno")
                    np = st.text_input("Heslo", type="password")
                    rec = st.text_input("Kód", type="password")
                    if st.form_submit_button("Registrovat", use_container_width=True):
                        users = nacti_uzivatele()
                        if nu in users['username'].values: st.error("Obsazeno")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(np), "recovery_key": zasifruj(rec)}])
                            uloz_csv(pd.concat([users, new], ignore_index=True), SOUBOR_UZIVATELE, "New user")
                            st.success("Hotovo")
            with t3:
                with st.form("res"):
                    ru = st.text_input("Jméno")
                    rk = st.text_input("Kód", type="password")
                    rnp = st.text_input("Nové heslo", type="password")
                    if st.form_submit_button("Reset", use_container_width=True):
                        users = nacti_uzivatele()
                        idx = users.index[users['username'] == ru].tolist()
                        if idx and users.at[idx[0], 'recovery_key'] == zasifruj(rk):
                            users.at[idx[0], 'password'] = zasifruj(rnp)
                            uloz_csv(users, SOUBOR_UZIVATELE, "Reset")
                            st.success("Změněno")
                        else: st.error("Chyba")
        return

    # APP
    USER = st.session_state['aktualni_uzivatel']
    with st.sidebar:
        st.write(f"👤 **{USER}**")
        if st.button("Odhlásit"):
            st.session_state.clear()
            st.rerun()

    st.title(f"🌍 Portfolio: {USER}")

    if 'df' not in st.session_state:
        with st.spinner("Nahrávám..."):
            fp = nacti_csv(SOUBOR_DATA)
            st.session_state['df'] = fp[fp['Owner'] == str(USER)].copy()
            fh = nacti_csv(SOUBOR_HISTORIE)
            st.session_state['df_hist'] = fh[fh['Owner'] == str(USER)].copy()
    
    df = st.session_state['df']
    df_hist = st.session_state['df_hist']

    t_port, t_sell, t_hist = st.tabs(["📊 Portfolio", "💸 Prodej", "📜 Historie"])

    # --- 1. PORTFOLIO & DASHBOARD ---
    with t_port:
        # PŘIDÁNÍ
        with st.expander("➕ PŘIDAT NÁKUP"):
            with st.form("add"):
                c1, c2, c3 = st.columns(3)
                with c1: t = st.text_input("Ticker").upper()
                with c2: p = st.number_input("Počet", min_value=0.0001)
                with c3: c = st.number_input("Cena", min_value=0.1)
                if st.form_submit_button("Koupit"):
                    novy = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now(), "Owner": USER}])
                    updated = pd.concat([df, novy], ignore_index=True)
                    st.session_state['df'] = updated
                    uloz_data_uzivatele(updated, USER, SOUBOR_DATA)
                    st.success("OK")
                    st.rerun()

        # TABULKA
        st.subheader("Vaše pozice")
        edited_df = st.data_editor(
            df[["Ticker", "Pocet", "Cena", "Datum"]],
            num_rows="dynamic", use_container_width=True,
            column_config={"Pocet": st.column_config.NumberColumn(format="%.4f"), "Cena": st.column_config.NumberColumn(format="%.2f"), "Datum": st.column_config.DatetimeColumn(format="D.M.YYYY")}
        )
        if not df[["Ticker", "Pocet", "Cena", "Datum"]].reset_index(drop=True).equals(edited_df.reset_index(drop=True)):
            if st.button("💾 ULOŽIT ZMĚNY"):
                st.session_state['df'] = edited_df
                uloz_data_uzivatele(edited_df, USER, SOUBOR_DATA)
                st.success("Uloženo")
                st.rerun()

        # --- TADY JE TEN NÁVRAT DASHBOARDU ---
        st.divider()
        if not df.empty:
            viz_data = []
            celk_hod_usd = 0
            celk_inv_usd = 0
            stats_meny = {}
            kurzy = ziskej_kurzy()
            
            bar = st.progress(0, "Počítám...")
            
            for i, (idx, row) in enumerate(df.iterrows()):
                if pd.isna(row['Ticker']) or pd.isna(row['Pocet']): continue
                tkr = str(row['Ticker'])
                cena_ted, mena = ziskej_info_o_akcii(tkr)
                cena_ted = cena_ted if cena_ted else row['Cena']
                
                hod = row['Pocet'] * cena_ted
                inv = row['Pocet'] * row['Cena']
                zisk = hod - inv
                
                if mena not in stats_meny: stats_meny[mena] = {"inv": 0, "zisk": 0}
                stats_meny[mena]["inv"] += inv
                stats_meny[mena]["zisk"] += zisk
                
                konv = 1.0
                if mena == "CZK": konv = 1/kurzy["CZK"]
                elif mena == "EUR": konv = kurzy["EUR"]
                
                celk_hod_usd += hod * konv
                celk_inv_usd += inv * konv
                
                viz_data.append({"Ticker": tkr, "Hodnota": hod, "Zisk": zisk, "Měna": mena, "HodnotaUSD": hod*konv})
                bar.progress((i+1)/len(df))
            bar.empty()

            # HLAVNÍ METRIKY
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkem investováno (USD)", f"${celk_inv_usd:,.0f}")
            c2.metric("Aktuální hodnota (USD)", f"${celk_hod_usd:,.0f}")
            c3.metric("Celkový zisk (USD)", f"${(celk_hod_usd-celk_inv_usd):+,.0f}", delta_color="normal")

            # ROZPAD MĚN
            st.subheader("💰 Peněženky podle měn")
            cols = st.columns(len(stats_meny))
            for i, m in enumerate(stats_meny):
                d = stats_meny[m]
                sym = "$" if m=="USD" else ("Kč" if m=="CZK" else "€")
                cols[i].metric(f"Měna: {m}", f"Inv: {d['inv']:,.0f} {sym}", f"{d['zisk']:+,.0f} {sym}")

            # GRAFY
            st.divider()
            gf = pd.DataFrame(viz_data)
            g1, g2 = st.columns(2)
            with g1:
                st.caption("Rozložení (USD)")
                fig = px.pie(gf, values='HodnotaUSD', names='Ticker', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            with g2:
                st.caption("Ziskovost (Orig. měna)")
                fig = px.bar(gf, x='Ticker', y='Zisk', color='Zisk', color_continuous_scale=['red', 'green'])
                st.plotly_chart(fig, use_container_width=True)

    # --- 2. PRODEJ ---
    with t_sell:
        st.subheader("Realizace zisku")
        if df.empty: st.info("Prázdno.")
        else:
            tickery = df['Ticker'].unique().tolist()
            with st.form("sell"):
                sel_t = st.selectbox("Akcie", tickery)
                ks = df[df['Ticker'] == sel_t]['Pocet'].sum()
                akt_cena, akt_mena = ziskej_info_o_akcii(sel_t)
                st.write(f"Máš: **{ks}** ks. Cena teď: **{akt_cena:.2f} {akt_mena}**")
                
                c1, c2 = st.columns(2)
                q = c1.number_input("Kolik prodat?", 0.0001, float(ks))
                pr = c2.number_input("Prodejní cena", 0.01, float(akt_cena) if akt_cena else 0.0)
                
                if st.form_submit_button("PRODAT"):
                    ok, msg = proved_prodej(sel_t, q, pr, USER, akt_mena)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)

    # --- 3. HISTORIE ---
    with t_hist:
        st.subheader("Deník obchodů")
        if df_hist.empty: st.info("Žádné obchody.")
        else:
            st.dataframe(df_hist.sort_values("Datum", ascending=False), use_container_width=True)
            # Součet realizovaného
            real_czk = df_hist[df_hist['Mena']=='CZK']['Zisk'].sum()
            real_usd = df_hist[df_hist['Mena']=='USD']['Zisk'].sum()
            col1, col2 = st.columns(2)
            col1.metric("Realizováno (CZK)", f"{real_czk:,.0f} Kč")
            col2.metric("Realizováno (USD)", f"${real_usd:,.0f}")

if __name__ == "__main__":
    main()
