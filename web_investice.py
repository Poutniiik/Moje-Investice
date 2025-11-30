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
        # První spuštění - vytvoříme admina
        try:
            p = zasifruj(st.secrets["login"]["heslo"])
            def_user = st.secrets["login"]["uzivatel"]
        except:
            p = zasifruj("admin123")
            def_user = "admin"
            
        df = pd.DataFrame([{
            "username": def_user, "password": p, "recovery_key": zasifruj("admin")
        }])
        uloz_uzivatele(df)
        return df

def uloz_uzivatele(df):
    repo = get_repo()
    csv = df.to_csv(index=False)
    try:
        file = repo.get_contents(SOUBOR_UZIVATELE)
        repo.update_file(file.path, "Update users", csv, file.sha)
    except:
        repo.create_file(SOUBOR_UZIVATELE, "Init users", csv)

# --- SPRÁVA PORTFOLIA ---
def nacti_celou_databazi():
    """Stáhne všechna data, ale zatím je nefiltruje."""
    try:
        repo = get_repo()
        file = repo.get_contents(SOUBOR_DATA)
        df = pd.read_csv(StringIO(file.decoded_content.decode("utf-8")))
        
        # Oprava sloupců
        if 'Datum' not in df.columns: df['Datum'] = datetime.now()
        df['Datum'] = pd.to_datetime(df['Datum'])
        
        # 🛠️ DŮLEŽITÉ: Pokud stará data nemají vlastníka, dáme je adminovi
        if 'Owner' not in df.columns: 
            df['Owner'] = "admin" 
            
        # Převedeme Owner na string, aby fungovalo porovnávání
        df['Owner'] = df['Owner'].astype(str)
        return df
    except:
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena", "Datum", "Owner"])

def uloz_zmeny_uzivatele(user_df, username):
    """Uloží změny jen pro daného uživatele, ostatní data nechá být."""
    repo = get_repo()
    full_df = nacti_celou_databazi()
    
    # 1. Vymažeme staré záznamy TOHOTO uživatele z hlavní databáze
    # (Ostatní uživatele tam necháme)
    full_df = full_df[full_df['Owner'] != str(username)]
    
    # 2. Přidáme tam jeho nové záznamy
    if not user_df.empty:
        user_df['Owner'] = str(username) # Pojistka: Vtiskneme tam jeho jméno
        full_df = pd.concat([full_df, user_df], ignore_index=True)
    
    # 3. Uložíme celek
    csv = full_df.to_csv(index=False)
    try:
        file = repo.get_contents(SOUBOR_DATA)
        repo.update_file(file.path, f"Update data: {username}", csv, file.sha)
    except:
        repo.create_file(SOUBOR_DATA, "Init data", csv)
    st.cache_data.clear()

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

    # 1. LOGIN / REGISTRACE
    if not st.session_state['prihlasen']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Investiční Brána")
            tab1, tab2, tab3 = st.tabs(["Přihlášení", "Registrace", "Obnova hesla"])
            
            with tab1:
                # UNIKÁTNÍ KLÍČ FORMULÁŘE (oprava chyby)
                with st.form("unique_login_form"):
                    u = st.text_input("Jméno")
                    p = st.text_input("Heslo", type="password")
                    if st.form_submit_button("Vstoupit", use_container_width=True):
                        users = nacti_uzivatele()
                        row = users[users['username'] == u]
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            st.session_state['prihlasen'] = True
                            st.session_state['aktualni_uzivatel'] = u
                            st.rerun()
                        else: st.error("Chyba přihlášení")

            with tab2:
                with st.form("unique_reg_form"):
                    nu = st.text_input("Nové jméno")
                    np = st.text_input("Heslo", type="password")
                    rec = st.text_input("Záchranný kód", type="password")
                    if st.form_submit_button("Registrovat", use_container_width=True):
                        users = nacti_uzivatele()
                        if nu in users['username'].values: st.error("Obsazeno.")
                        elif not rec: st.error("Chybí kód.")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(np), "recovery_key": zasifruj(rec)}])
                            uloz_uzivatele(pd.concat([users, new], ignore_index=True))
                            st.success("Hotovo.")

            with tab3:
                with st.form("unique_reset_form"):
                    ru = st.text_input("Jméno")
                    rk = st.text_input("Kód", type="password")
                    rnp = st.text_input("Nové heslo", type="password")
                    if st.form_submit_button("Reset", use_container_width=True):
                        users = nacti_uzivatele()
                        idx = users.index[users['username'] == ru].tolist()
                        if idx and users.at[idx[0], 'recovery_key'] == zasifruj(rk):
                            users.at[idx[0], 'password'] = zasifruj(rnp)
                            uloz_uzivatele(users)
                            st.success("Změněno.")
                        else: st.error("Chyba.")
        return

    # 2. APLIKACE PO PŘIHLÁŠENÍ
    USER = st.session_state['aktualni_uzivatel']
    
    with st.sidebar:
        st.write(f"👤 **{USER}**")
        if st.button("Odhlásit"):
            st.session_state['prihlasen'] = False
            st.rerun()

    st.title(f"🌍 Portfolio: {USER}")

    # --- NAČTENÍ DAT A FILTRACE ---
    if 'df' not in st.session_state:
        with st.spinner(f"Nahrávám trezor uživatele {USER}..."):
            full_df = nacti_celou_databazi()
            
            # 🔐 TADY SE DĚJE TO KOUZLO FILTROVÁNÍ
            # Vybereme jen řádky, kde se sloupec Owner shoduje s přihlášeným uživatelem
            my_df = full_df[full_df['Owner'] == str(USER)].copy()
            
            st.session_state['df'] = my_df
    
    df = st.session_state['df']

    # --- EDITACE ---
    with st.expander("📝 Správa (Editace)", expanded=False):
        edited_df = st.data_editor(
            df[["Ticker", "Pocet", "Cena", "Datum"]],
            num_rows="dynamic", use_container_width=True,
            column_config={
                "Pocet": st.column_config.NumberColumn("Kusy", format="%.4f"),
                "Cena": st.column_config.NumberColumn("Cena (Orig)", format="%.2f"),
                "Datum": st.column_config.DatetimeColumn("Koupeno", format="D.M.YYYY")
            }
        )
        # Porovnání změn (ignorujeme index)
        if not df[["Ticker", "Pocet", "Cena", "Datum"]].reset_index(drop=True).equals(edited_df.reset_index(drop=True)):
            if st.button("💾 ULOŽIT ZMĚNY"):
                st.session_state['df'] = edited_df
                uloz_zmeny_uzivatele(edited_df, USER)
                st.success("Uloženo!")
                st.rerun()

    # --- PŘIDÁNÍ ---
    with st.expander("➕ Rychlé přidání", expanded=False):
        with st.form("unique_add_form"):
            c1, c2, c3 = st.columns(3)
            with c1: t = st.text_input("Ticker").upper()
            with c2: p = st.number_input("Počet", min_value=0.0001)
            with c3: c = st.number_input("Cena", min_value=0.1)
            if st.form_submit_button("Přidat"):
                # Tady explicitně přidáváme Ownera = USER
                novy = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now(), "Owner": USER}])
                updated = pd.concat([st.session_state['df'], novy], ignore_index=True)
                st.session_state['df'] = updated
                uloz_zmeny_uzivatele(updated, USER)
                st.rerun()

    st.divider()

    # --- DASHBOARD ---
    if not df.empty:
        viz_data = []
        celk_hodnota_usd, celk_inv_usd = 0, 0
        stats_meny = {}
        kurzy = ziskej_kurzy()
        
        my_bar = st.progress(0, text="Počítám...")
        
        for index, row in df.iterrows():
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
            my_bar.progress((index + 1) / len(df))
        my_bar.empty()

        c1, c2, c3 = st.columns(3)
        c1.metric("Celkem investováno", f"${celk_inv_usd:,.0f}")
        c2.metric("Hodnota portfolia", f"${celk_hodnota_usd:,.0f}")
        c3.metric("Celkový zisk", f"${(celk_hodnota_usd-celk_inv_usd):+,.0f}", delta_color="normal")

        st.divider()
        cols = st.columns(len(stats_meny))
        for i, m in enumerate(stats_meny):
            d = stats_meny[m]
            sym = "$" if m=="USD" else ("Kč" if m=="CZK" else "€" if m=="EUR" else m)
            cols[i].metric(f"Měna: {m}", f"{d['inv']:,.0f} {sym}", f"{d['zisk']:+,.0f} {sym}")
        
        st.divider()
        df_viz = pd.DataFrame(viz_data)
        st.dataframe(df_viz.style.format({"Cena teď": "{:.2f}", "Hodnota (Orig)": "{:,.2f}", "Zisk (Orig)": "{:+,.2f}"})
                     .map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Zisk (Orig)']), use_container_width=True)
        
        fig = px.pie(df_viz, values='Hodnota (Orig)', names='Ticker', title='Rozložení (podle velikosti)')
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info(f"Ahoj {USER}, tvůj seznam je prázdný. Cizí data jsou skrytá.")

if __name__ == "__main__":
    main()

