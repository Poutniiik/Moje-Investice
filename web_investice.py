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
SOUBOR_CASH = "cash_data.csv"
SOUBOR_VYVOJ = "value_history.csv" # 🆕 Soubor pro graf vývoje

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
    try:
        df = nacti_csv(SOUBOR_UZIVATELE)
        if df.empty: return pd.DataFrame(columns=["username", "password", "recovery_key"])
        return df
    except:
        return pd.DataFrame(columns=["username", "password", "recovery_key"])

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
        # Definice sloupců
        if nazev_souboru == SOUBOR_HISTORIE:
            return pd.DataFrame(columns=["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum", "Owner"])
        if nazev_souboru == SOUBOR_CASH:
            return pd.DataFrame(columns=["Typ", "Castka", "Mena", "Poznamka", "Datum", "Owner"])
        if nazev_souboru == SOUBOR_VYVOJ:
            return pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
        if nazev_souboru == SOUBOR_UZIVATELE:
             return pd.DataFrame(columns=["username", "password", "recovery_key"])
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
    novy = pd.DataFrame([{
        "Typ": typ, "Castka": castka, "Mena": mena, 
        "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user
    }])
    df_cash = pd.concat([df_cash, novy], ignore_index=True)
    st.session_state['df_cash'] = df_cash
    uloz_data_uzivatele(df_cash, user, SOUBOR_CASH)

# --- VÝVOJ HODNOTY (Snapshot) ---
def aktualizuj_graf_vyvoje(user, aktualni_hodnota_usd):
    """Zapíše dnešní hodnotu do historie, pokud tam ještě není."""
    # Načteme celou historii vývoje
    try:
        full_hist = nacti_csv(SOUBOR_VYVOJ)
    except:
        full_hist = pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Vyfiltrujeme záznamy uživatele
    user_hist = full_hist[full_hist['Owner'] == str(user)].copy()
    
    # Zkontrolujeme, jestli už dnes máme záznam
    if not user_hist.empty and user_hist.iloc[-1]['Date'].strftime("%Y-%m-%d") == today:
        # Už máme dnešek -> aktualizujeme hodnotu (přepisujeme)
        # Najdeme index v hlavním DF
        last_idx = user_hist.index[-1]
        full_hist.at[last_idx, 'TotalUSD'] = aktualni_hodnota_usd
    else:
        # Dnešek chybí -> přidáme nový řádek
        new_row = pd.DataFrame([{
            "Date": datetime.now(),
            "TotalUSD": aktualni_hodnota_usd,
            "Owner": str(user)
        }])
        full_hist = pd.concat([full_hist, new_row], ignore_index=True)
    
    # Uložíme jen pokud se něco změnilo (tady ukládáme vždy pro jistotu, ale je to OK)
    uloz_csv(full_hist, SOUBOR_VYVOJ, "Daily snapshot")
    return full_hist[full_hist['Owner'] == str(user)]

# --- LOGIKA PRODEJE ---
def proved_prodej(ticker, kusy_k_prodeji, prodejni_cena, user, mena_akcie):
    df_port = st.session_state['df'].copy()
    df_hist = st.session_state['df_hist'].copy()
    df_ticker = df_port[df_port['Ticker'] == ticker].sort_values('Datum')
    
    if df_ticker.empty or df_ticker['Pocet'].sum() < kusy_k_prodeji:
        return False, "Nedostatek kusů."

    zbyva = kusy_k_prodeji
    zisk = 0
    trzba = kusy_k_prodeji * prodejni_cena 
    
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
    st.session_state['df'] = df_port
    st.session_state['df_hist'] = df_hist
    uloz_data_uzivatele(df_port, user, SOUBOR_DATA)
    uloz_data_uzivatele(df_hist, user, SOUBOR_HISTORIE)
    return True, f"Prodáno! +{trzba:,.2f} {mena_akcie}"

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
                        row = users[users['username'] == u] if not users.empty else pd.DataFrame()
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            st.session_state.clear()
                            st.session_state['prihlasen'] = True
                            st.session_state['aktualni_uzivatel'] = u
                            st.rerun()
                        else: st.error("Chyba")
            with t2:
                with st.form("reg"):
                    nu = st.text_input("Nové jméno")
                    np = st.text_input("Heslo", type="password")
                    rec = st.text_input("Kód", type="password")
                    if st.form_submit_button("Registrovat", use_container_width=True):
                        users = nacti_uzivatele()
                        if not users.empty and nu in users['username'].values: st.error("Obsazeno")
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
                        idx = users.index[users['username'] == ru].tolist() if not users.empty else []
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
        st.divider()
        st.subheader("💰 Peněženka")
        
        if 'df_cash' not in st.session_state:
            with st.spinner("Nahrávám finance..."):
                fc = nacti_csv(SOUBOR_CASH)
                st.session_state['df_cash'] = fc[fc['Owner'] == str(USER)].copy()
        
        zustatky = get_zustatky(USER)
        if not zustatky: st.warning("0.00")
        else:
            for mena, castka in zustatky.items():
                sym = "Kč" if mena == "CZK" else ("$" if mena == "USD" else mena)
                st.metric(mena, f"{castka:,.2f} {sym}")

        if st.button("Odhlásit"):
            st.session_state.clear()
            st.rerun()

    st.title(f"🌍 Portfolio: {USER}")

    if 'df' not in st.session_state:
        with st.spinner("Nahrávám data..."):
            fp = nacti_csv(SOUBOR_DATA)
            st.session_state['df'] = fp[fp['Owner'] == str(USER)].copy()
            fh = nacti_csv(SOUBOR_HISTORIE)
            st.session_state['df_hist'] = fh[fh['Owner'] == str(USER)].copy()
    
    df = st.session_state['df']
    df_hist = st.session_state['df_hist']
    df_cash = st.session_state['df_cash']

    t_port, t_wallet, t_sell, t_hist = st.tabs(["📊 Portfolio", "💰 Peněženka", "💸 Prodej", "📜 Historie"])

    # --- 1. PORTFOLIO & DASHBOARD ---
    with t_port:
        with st.expander("➕ PŘIDAT NÁKUP"):
            with st.form("add"):
                c1, c2, c3 = st.columns(3)
                with c1: t = st.text_input("Ticker").upper()
                with c2: p = st.number_input("Počet", min_value=0.0001)
                with c3: c = st.number_input("Cena", min_value=0.1)
                if st.form_submit_button("Koupit"):
                    _, mena_akcie = ziskej_info_o_akcii(t)
                    if mena_akcie == "N/A": mena_akcie = "USD"
                    cena_celkem = p * c
                    aktualni_hotovost = zustatky.get(mena_akcie, 0)
                    
                    if aktualni_hotovost >= cena_celkem:
                        pohyb_penez(-cena_celkem, mena_akcie, "Nákup", f"Nákup {t}", USER)
                        novy = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now(), "Owner": USER}])
                        updated = pd.concat([df, novy], ignore_index=True)
                        st.session_state['df'] = updated
                        uloz_data_uzivatele(updated, USER, SOUBOR_DATA)
                        st.success("OK")
                        st.rerun()
                    else: st.error(f"Chybí ti {cena_celkem - aktualni_hotovost:.2f} {mena_akcie}")

        rezim = st.radio("Pohled:", ["Detailní (Editace)", "Souhrnný (Přehled)"], horizontal=True)

        if rezim == "Detailní (Editace)":
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
            data_pro_vypocet = df
        else:
            if not df.empty:
                df_temp = df.copy()
                df_temp['Investice'] = df_temp['Pocet'] * df_temp['Cena']
                grouped = df_temp.groupby('Ticker').agg({'Pocet': 'sum', 'Investice': 'sum'}).reset_index()
                grouped['Cena'] = grouped['Investice'] / grouped['Pocet']
                data_pro_vypocet = grouped
            else: data_pro_vypocet = pd.DataFrame()

        st.divider()
        viz_data = []
        celk_hod_usd = 0
        celk_inv_usd = 0
        stats_meny = {}
        
        # VÝPOČET DAT PRO DASHBOARD
        if not data_pro_vypocet.empty:
            kurzy = ziskej_kurzy()
            bar = st.progress(0, "Počítám...")
            for i, (idx, row) in enumerate(data_pro_vypocet.iterrows()):
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
                
                viz_data.append({"Ticker": tkr, "Kusy": row['Pocet'], "Průměrná nákupka": row['Cena'], 
                                 "Hodnota": hod, "Zisk": zisk, "Měna": mena, "HodnotaUSD": hod*konv})
                bar.progress((i+1)/len(data_pro_vypocet))
            bar.empty()

        # ULOŽENÍ SNÍMKU DO HISTORIE VÝVOJE (Jen jednou denně)
        if celk_hod_usd > 0:
            hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
        else:
            hist_vyvoje = pd.DataFrame()

        # HLAVNÍ METRIKY
        c1, c2, c3 = st.columns(3)
        c1.metric("Celkem investováno (USD)", f"${celk_inv_usd:,.0f}")
        c2.metric("Aktuální hodnota (USD)", f"${celk_hod_usd:,.0f}")
        c3.metric("Celkový zisk (USD)", f"${(celk_hod_usd-celk_inv_usd):+,.0f}", delta_color="normal")

        # GRAF VÝVOJE (NOVINKA!)
        if not hist_vyvoje.empty:
            st.caption("📈 Vývoj hodnoty portfolia v čase")
            fig_line = px.area(hist_vyvoje, x='Date', y='TotalUSD', title=None)
            st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("💰 Peněženky podle měn")
        cols = st.columns(len(stats_meny)) if stats_meny else [st.container()]
        for i, m in enumerate(stats_meny):
            d = stats_meny[m]
            sym = "$" if m=="USD" else ("Kč" if m=="CZK" else "€")
            cols[i].metric(f"{m}", f"Inv: {d['inv']:,.0f} {sym}", f"{d['zisk']:+,.0f} {sym}")

        st.divider()
        if viz_data:
            gf = pd.DataFrame(viz_data)
            st.dataframe(gf[["Ticker", "Měna", "Kusy", "Průměrná nákupka", "Hodnota", "Zisk"]]
                         .style.format({"Průměrná nákupka": "{:.2f}", "Hodnota": "{:,.2f}", "Zisk": "{:+,.2f}"})
                         .map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Zisk']), use_container_width=True)
            
            st.divider()
            g1, g2 = st.columns(2)
            with g1:
                st.caption("Rozložení (USD)")
                fig = px.pie(gf, values='HodnotaUSD', names='Ticker', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            with g2:
                st.caption("Ziskovost (Orig. měna)")
                fig = px.bar(gf, x='Ticker', y='Zisk', color='Zisk', color_continuous_scale=['red', 'green'])
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Žádné aktivní investice.")

    with t_wallet:
        st.subheader("🏦 Správa hotovosti")
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.form("deposit"):
                vklad_castka = st.number_input("Částka", min_value=1.0, step=100.0)
                vklad_mena = st.selectbox("Měna", ["USD", "CZK", "EUR"])
                if st.form_submit_button("💰 VLOŽIT"):
                    pohyb_penez(vklad_castka, vklad_mena, "Vklad", "Vklad", USER)
                    st.success("OK")
                    st.rerun()
            with st.form("withdraw"):
                vyber_castka = st.number_input("Částka výběru", min_value=1.0, step=100.0)
                vyber_mena = st.selectbox("Měna výběru", ["USD", "CZK", "EUR"])
                if st.form_submit_button("💸 VYBRAT"):
                    pohyb_penez(-vyber_castka, vyber_mena, "Výběr", "Výběr", USER)
                    st.success("OK")
                    st.rerun()
        with c2:
            if not df_cash.empty:
                st.dataframe(df_cash.sort_values("Datum", ascending=False), use_container_width=True)

    with t_sell:
        st.subheader("Realizace zisku")
        if df.empty: st.info("Prázdno.")
        else:
            tickery = df['Ticker'].unique().tolist()
            with st.form("sell"):
                sel_t = st.selectbox("Akcie", tickery)
                ks = df[df['Ticker'] == sel_t]['Pocet'].sum()
                akt_cena, akt_mena = ziskej_info_o_akcii(sel_t)
                st.write(f"Máš: **{ks}** ks. Cena: **{akt_cena:.2f} {akt_mena}**")
                c1, c2 = st.columns(2)
                q = c1.number_input("Kolik prodat?", 0.0001, float(ks))
                pr = c2.number_input("Prodejní cena", 0.01, float(akt_cena) if akt_cena else 0.0)
                if st.form_submit_button("PRODAT"):
                    ok, msg = proved_prodej(sel_t, q, pr, USER, akt_mena)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)

    with t_hist:
        st.subheader("Deník obchodů (Editace)")
        if df_hist.empty: st.info("Žádné obchody.")
        else:
            st.caption("Pro smazání označ řádek a stiskni Delete.")
            edited_hist = st.data_editor(
                df_hist,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Kusu": st.column_config.NumberColumn(format="%.4f"),
                    "Prodejka": st.column_config.NumberColumn(format="%.2f"),
                    "Zisk": st.column_config.NumberColumn(format="%.2f"),
                    "Datum": st.column_config.DatetimeColumn(format="D.M.YYYY HH:mm")
                },
                key="hist_editor"
            )
            if not df_hist.equals(edited_hist):
                if st.button("💾 ULOŽIT OPRAVY HISTORIE"):
                    st.session_state['df_hist'] = edited_hist
                    uloz_data_uzivatele(edited_hist, USER, SOUBOR_HISTORIE)
                    st.success("Uloženo")
                    st.rerun()
            st.divider()
            real_czk = edited_hist[edited_hist['Mena']=='CZK']['Zisk'].sum()
            real_usd = edited_hist[edited_hist['Mena']=='USD']['Zisk'].sum()
            col1, col2 = st.columns(2)
            col1.metric("Realizováno (CZK)", f"{real_czk:,.0f} Kč")
            col2.metric("Realizováno (USD)", f"${real_usd:,.0f}")

if __name__ == "__main__":
    main()
