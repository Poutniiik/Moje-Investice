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
SOUBOR_HISTORIE = "history_data.csv" # Nový soubor pro prodané akcie

# --- STYLY ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 15px; text-align: center;}
    div[data-testid="stMetricValue"] {font-size: 1.8rem;}
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

# --- UNIVERZÁLNÍ FUNKCE PRO UKLÁDÁNÍ ---
def uloz_csv(df, nazev_souboru, zprava):
    repo = get_repo()
    csv = df.to_csv(index=False)
    try:
        file = repo.get_contents(nazev_souboru)
        repo.update_file(file.path, zprava, csv, file.sha)
    except:
        repo.create_file(nazev_souboru, zprava, csv)

# --- SPRÁVA DAT (PORTFOLIO A HISTORIE) ---
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
        # Vrací prázdné DF se správnými sloupci podle typu souboru
        if nazev_souboru == SOUBOR_HISTORIE:
            return pd.DataFrame(columns=["Ticker", "Kusu", "Nakupka", "Prodejka", "Zisk", "Mena", "Datum", "Owner"])
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena", "Datum", "Owner"])

def uloz_data_uzivatele(user_df, username, nazev_souboru):
    full_df = nacti_csv(nazev_souboru)
    full_df = full_df[full_df['Owner'] != str(username)] # Smazat staré uživatelovy
    if not user_df.empty:
        user_df['Owner'] = str(username)
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    uloz_csv(full_df, nazev_souboru, f"Update {username}")
    st.cache_data.clear()

# --- LOGIKA PRODEJE (FIFO) ---
def proved_prodej(ticker, kusy_k_prodeji, prodejni_cena, user, mena_akcie):
    # 1. Načteme portfolio a historii
    df_port = st.session_state['df'].copy() # Aktuální portfolio uživatele
    df_hist = st.session_state['df_hist'].copy() # Historie uživatele
    
    # Seřadíme nákupy od nejstaršího (FIFO metoda)
    df_ticker = df_port[df_port['Ticker'] == ticker].sort_values('Datum')
    
    if df_ticker.empty:
        return False, "Tuto akcii nemáš."
    
    if df_ticker['Pocet'].sum() < kusy_k_prodeji:
        return False, f"Nemáš tolik kusů. Máš jen {df_ticker['Pocet'].sum()}."

    zbyva_prodat = kusy_k_prodeji
    celkovy_zisk = 0
    
    # Procházíme nákupy a "ukrajujeme" z nich
    for idx, row in df_ticker.iterrows():
        if zbyva_prodat <= 0: break
        
        kusy_z_tohoto_radku = min(row['Pocet'], zbyva_prodat)
        
        # Výpočet zisku z této části
        nakupni_cena = row['Cena']
        zisk_obchodu = (prodejni_cena - nakupni_cena) * kusy_z_tohoto_radku
        celkovy_zisk += zisk_obchodu
        
        # Aktualizace portfolia
        if kusy_z_tohoto_radku == row['Pocet']:
            df_port = df_port.drop(idx) # Smazat celý řádek, pokud prodáváme vše
        else:
            df_port.at[idx, 'Pocet'] -= kusy_z_tohoto_radku # Snížit počet
            
        zbyva_prodat -= kusy_z_tohoto_radku

    # Zápis do historie
    novy_zaznam = pd.DataFrame([{
        "Ticker": ticker,
        "Kusu": kusy_k_prodeji,
        "Nakupka": "Průměr", # Pro zjednodušení historie
        "Prodejka": prodejni_cena,
        "Zisk": celkovy_zisk,
        "Mena": mena_akcie,
        "Datum": datetime.now(),
        "Owner": user
    }])
    
    df_hist = pd.concat([df_hist, novy_zaznam], ignore_index=True)
    
    # Uložení změn
    st.session_state['df'] = df_port
    st.session_state['df_hist'] = df_hist
    
    uloz_data_uzivatele(df_port, user, SOUBOR_DATA)
    uloz_data_uzivatele(df_hist, user, SOUBOR_HISTORIE)
    
    return True, f"Prodáno! Realizovaný zisk: {celkovy_zisk:+.2f} {mena_akcie}"

# --- KURZY ---
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
                    nu = st.text_input("Nové jméno")
                    np = st.text_input("Heslo", type="password")
                    rec = st.text_input("Záchranný kód", type="password")
                    if st.form_submit_button("Registrovat", use_container_width=True):
                        users = nacti_uzivatele()
                        if nu in users['username'].values: st.error("Obsazeno.")
                        elif not rec: st.error("Chybí kód.")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(np), "recovery_key": zasifruj(rec)}])
                            uloz_csv(pd.concat([users, new], ignore_index=True), SOUBOR_UZIVATELE, "New user")
                            st.success("Hotovo.")
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
                            uloz_csv(users, SOUBOR_UZIVATELE, "Pass reset")
                            st.success("Změněno.")
                        else: st.error("Chyba.")
        return

    # APLIKACE
    USER = st.session_state['aktualni_uzivatel']
    with st.sidebar:
        st.write(f"👤 **{USER}**")
        if st.button("Odhlásit"):
            st.session_state.clear()
            st.rerun()

    st.title(f"🌍 Portfolio: {USER}")

    # Načtení dat (Portfolio i Historie)
    if 'df' not in st.session_state:
        with st.spinner(f"Nahrávám data..."):
            full_port = nacti_csv(SOUBOR_DATA)
            st.session_state['df'] = full_port[full_port['Owner'] == str(USER)].copy()
            
            full_hist = nacti_csv(SOUBOR_HISTORIE)
            st.session_state['df_hist'] = full_hist[full_hist['Owner'] == str(USER)].copy()
    
    df = st.session_state['df']
    df_hist = st.session_state['df_hist']

    # --- ZÁLOŽKY ---
    tab_portfolio, tab_prodej, tab_historie = st.tabs(["📊 Portfolio & Nákup", "💸 PRODEJ", "📜 Historie Obchodů"])

    # --- 1. PORTFOLIO A NÁKUP ---
    with tab_portfolio:
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
                    st.success(f"Nakoupeno: {t}")
                    st.rerun()

        # EDITACE TABULKY
        st.subheader("Vaše pozice")
        edited_df = st.data_editor(
            df[["Ticker", "Pocet", "Cena", "Datum"]],
            num_rows="dynamic", use_container_width=True,
            column_config={
                "Pocet": st.column_config.NumberColumn("Kusy", format="%.4f"),
                "Cena": st.column_config.NumberColumn("Cena (Orig)", format="%.2f"),
                "Datum": st.column_config.DatetimeColumn("Koupeno", format="D.M.YYYY")
            }
        )
        if not df[["Ticker", "Pocet", "Cena", "Datum"]].reset_index(drop=True).equals(edited_df.reset_index(drop=True)):
            if st.button("💾 ULOŽIT ZMĚNY TABULKY"):
                st.session_state['df'] = edited_df
                uloz_data_uzivatele(edited_df, USER, SOUBOR_DATA)
                st.success("Uloženo!")
                st.rerun()

    # --- 2. PRODEJ ---
    with tab_prodej:
        st.subheader("💰 Realizace zisku / Stop loss")
        if df.empty:
            st.info("Nemáš co prodávat.")
        else:
            # Seznam akcií, které vlastníme
            vlastnene_tickery = df['Ticker'].unique().tolist()
            if not vlastnene_tickery: st.info("Prázdné portfolio."); st.stop()
            
            with st.form("sell_form"):
                sel_ticker = st.selectbox("Vyber akcii k prodeji", vlastnene_tickery)
                
                # Zjistíme, kolik toho má
                celkem_kusu = df[df['Ticker'] == sel_ticker]['Pocet'].sum()
                
                # Zjistíme aktuální cenu pro nápovědu
                cena_napoveda, mena_napoveda = ziskej_info_o_akcii(sel_ticker)
                aktualni_info = f"(Aktuální tržní cena: {cena_napoveda:.2f} {mena_napoveda})" if cena_napoveda else ""
                
                st.write(f"Vlastníš celkem: **{celkem_kusu} ks** {aktualni_info}")
                
                c1, c2 = st.columns(2)
                with c1: sel_qty = st.number_input("Kolik kusů prodat?", min_value=0.0001, max_value=float(celkem_kusu))
                with c2: sel_price = st.number_input(f"Prodejní cena ({mena_napoveda})", min_value=0.01, value=float(cena_napoveda) if cena_napoveda else 0.0)
                
                if st.form_submit_button("💸 PRODAT A ZAPSAT ZISK"):
                    uspech, msg = proved_prodej(sel_ticker, sel_qty, sel_price, USER, mena_napoveda)
                    if uspech:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # --- 3. HISTORIE ---
    with tab_historie:
        st.subheader("📜 Deník obchodů")
        if df_hist.empty:
            st.info("Zatím žádné uzavřené obchody.")
        else:
            st.dataframe(df_hist[["Ticker", "Kusu", "Prodejka", "Zisk", "Mena", "Datum"]].sort_values(by="Datum", ascending=False), use_container_width=True)
            
            # Celkový realizovaný zisk
            # (Jednoduchý součet bez ohledu na měny pro orientaci, nebo by to chtělo kurzový přepočet)
            total_profit_czk = df_hist[df_hist['Mena'] == 'CZK']['Zisk'].sum()
            total_profit_usd = df_hist[df_hist['Mena'] == 'USD']['Zisk'].sum()
            total_profit_eur = df_hist[df_hist['Mena'] == 'EUR']['Zisk'].sum()
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Realizováno (CZK)", f"{total_profit_czk:,.0f} Kč")
            c2.metric("Realizováno (USD)", f"${total_profit_usd:,.0f}")
            c3.metric("Realizováno (EUR)", f"€{total_profit_eur:,.0f}")

    st.divider()

    # --- DASHBOARD (SOUČTY) ---
    # (Zde se nic nemění, jen se počítá zbylé portfolio)
    if not df.empty:
        viz_data = []
        celk_hodnota_usd, celk_inv_usd = 0, 0
        stats_meny = {}
        kurzy = ziskej_kurzy()
        
        # Zrychlení: nenačítat, když jsme v tabu historie nebo prodeje, pokud nechceme
        # Ale pro přehled dole to necháme
        
        for i, (index, row) in enumerate(df.iterrows()):
            if pd.isna(row['Ticker']) or pd.isna(row['Pocet']): continue
            ticker = str(row['Ticker'])
            aktualni_cena, mena = ziskej_info_o_akcii(ticker)
            pouzita_cena = row['Cena'] if aktualni_cena is None else aktualni_cena

            hodnota_orig = row['Pocet'] * pouzita_cena
            investice_orig = row['Pocet'] * row['Cena']
            zisk_orig = hodnota_orig - investice_orig

            if mena not in stats_meny: stats_meny[mena] = {"inv": 0.0, "zisk": 0.0}
            stats_meny[mena]["inv"] += investice_orig
            stats_meny[mena]["zisk"] += zisk_orig

            konverze = 1.0
            if mena == "CZK": konverze = 1/kurzy["CZK"]
            elif mena == "EUR": konverze = kurzy["EUR"]
            
            celk_hodnota_usd += hodnota_orig * konverze
            celk_inv_usd += investice_orig * konverze

            viz_data.append({"Ticker": ticker, "Měna": mena, "Cena teď": pouzita_cena, 
                             "Hodnota (Orig)": hodnota_orig, "Zisk (Orig)": zisk_orig})

        st.subheader("🌐 Stav otevřeného portfolia")
        c1, c2, c3 = st.columns(3)
        c1.metric("Otevřeno (Investice)", f"${celk_inv_usd:,.0f}")
        c2.metric("Otevřeno (Hodnota)", f"${celk_hodnota_usd:,.0f}")
        c3.metric("Nerealizovaný zisk", f"${(celk_hodnota_usd-celk_inv_usd):+,.0f}", delta_color="normal")

if __name__ == "__main__":
    main()
