import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
from datetime import datetime
import hashlib # Pro šifrování hesel

# --- KONFIGURACE ---
st.set_page_config(page_title="Investiční App", layout="wide", page_icon="📈")

REPO_NAZEV = "Poutniik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv" # Data akcií
SOUBOR_UZIVATELE = "users_db.csv"  # Data uživatelů

# --- STYLY ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 15px; text-align: center;}
    div[data-testid="stMetricValue"] {font-size: 1.8rem;}
</style>
""", unsafe_allow_html=True)

# --- PŘIPOJENÍ KE GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
except:
    st.error("❌ CHYBA: Chybí GitHub Token v Secrets!")
    st.stop()

def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAZEV)

# --- BEZPEČNOST (HASHING) ---
def zasifruj(text):
    """Převede heslo na změť znaků (hash), aby nebylo čitelné."""
    return hashlib.sha256(str(text).encode()).hexdigest()

# --- SPRÁVA UŽIVATELŮ (NA GITHUB) ---
def nacti_uzivatele():
    repo = get_repo()
    try:
        file = repo.get_contents(SOUBOR_UZIVATELE)
        data = file.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(data), dtype=str)
    except:
        # Pokud soubor neexistuje, vytvoříme ho s prvním adminem (z secrets nebo default)
        try:
            def_user = st.secrets["login"]["uzivatel"]
            def_pass = zasifruj(st.secrets["login"]["heslo"])
        except:
            def_user = "admin"
            def_pass = zasifruj("admin123")
            
        df = pd.DataFrame([{
            "username": def_user, 
            "password": def_pass, 
            "recovery_key": zasifruj("tajne") # Default záchranný klíč
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

# --- SPRÁVA DAT PORTFOLIA ---
def nacti_data():
    try:
        repo = get_repo()
        file = repo.get_contents(SOUBOR_DATA)
        data = file.decoded_content.decode("utf-8")
        df = pd.read_csv(StringIO(data))
        if 'Datum' not in df.columns: df['Datum'] = datetime.now()
        df['Datum'] = pd.to_datetime(df['Datum'])
        # Filtrace: Každý vidí jen SVÉ akcie (pokud přidáme sloupec owner)
        # Pro zjednodušení v této verzi sdílí všichni jednu "firemní" databázi, 
        # ale login je oddělený.
        return df
    except:
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena", "Datum"])

def uloz_data(df):
    repo = get_repo()
    df_clean = df.dropna(subset=['Ticker', 'Pocet']) 
    csv = df_clean.to_csv(index=False)
    try:
        file = repo.get_contents(SOUBOR_DATA)
        repo.update_file(file.path, "Update data", csv, file.sha)
    except:
        repo.create_file(SOUBOR_DATA, "Init data", csv)
    st.cache_data.clear()

# --- POMOCNÉ FUNKCE ---
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
    except:
        return None, "USD"

# --- HLAVNÍ APLIKACE ---
def main():
    if 'prihlasen' not in st.session_state: st.session_state['prihlasen'] = False
    if 'aktualni_uzivatel' not in st.session_state: st.session_state['aktualni_uzivatel'] = ""

    # 1. LOGIN / REGISTRACE / OBNOVA
    if not st.session_state['prihlasen']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Investiční Brána")
            
            tab_login, tab_reg, tab_reset = st.tabs(["Přihlášení", "Registrace", "Zapomenuté heslo"])
            
            # --- PŘIHLÁŠENÍ ---
            with tab_login:
                with st.form("login_form"):
                    u = st.text_input("Uživatelské jméno")
                    p = st.text_input("Heslo", type="password")
                    if st.form_submit_button("Vstoupit", use_container_width=True):
                        users_df = nacti_uzivatele()
                        # Hledáme uživatele
                        user_row = users_df[users_df['username'] == u]
                        
                        if not user_row.empty:
                            stored_pass = user_row.iloc[0]['password']
                            if stored_pass == zasifruj(p):
                                st.session_state['prihlasen'] = True
                                st.session_state['aktualni_uzivatel'] = u
                                st.success("Vítej!")
                                st.rerun()
                            else:
                                st.error("Špatné heslo.")
                        else:
                            st.error("Uživatel neexistuje.")

            # --- REGISTRACE ---
            with tab_reg:
                st.info("Vytvoř si nový účet.")
                with st.form("reg_form"):
                    new_u = st.text_input("Nové jméno")
                    new_p = st.text_input("Heslo", type="password")
                    recovery = st.text_input("Záchranný kód (pro obnovu hesla)", type="password", help="Např. jméno psa. Budeš ho potřebovat, když zapomeneš heslo!")
                    
                    if st.form_submit_button("Zaregistrovat", use_container_width=True):
                        users_df = nacti_uzivatele()
                        if new_u in users_df['username'].values:
                            st.error("Toto jméno už je zabrané.")
                        elif len(new_p) < 3:
                            st.error("Heslo je moc krátké.")
                        elif not recovery:
                            st.error("Musíš zadat záchranný kód!")
                        else:
                            # Uložíme nového uživatele
                            new_row = pd.DataFrame([{
                                "username": new_u, 
                                "password": zasifruj(new_p),
                                "recovery_key": zasifruj(recovery)
                            }])
                            updated_users = pd.concat([users_df, new_row], ignore_index=True)
                            uloz_uzivatele(updated_users)
                            st.success("Účet vytvořen! Nyní se můžeš přihlásit.")

            # --- OBNOVA HESLA ---
            with tab_reset:
                st.warning("Změna hesla pomocí záchranného kódu.")
                with st.form("reset_form"):
                    res_u = st.text_input("Tvé jméno")
                    res_key = st.text_input("Tvůj záchranný kód", type="password")
                    new_pass_reset = st.text_input("Nové heslo", type="password")
                    
                    if st.form_submit_button("Změnit heslo", use_container_width=True):
                        users_df = nacti_uzivatele()
                        user_idx = users_df.index[users_df['username'] == res_u].tolist()
                        
                        if user_idx:
                            idx = user_idx[0]
                            stored_recovery = users_df.at[idx, 'recovery_key']
                            
                            if stored_recovery == zasifruj(res_key):
                                users_df.at[idx, 'password'] = zasifruj(new_pass_reset)
                                uloz_uzivatele(users_df)
                                st.success("Heslo úspěšně změněno! Jdi na přihlášení.")
                            else:
                                st.error("Špatný záchranný kód.")
                        else:
                            st.error("Uživatel neexistuje.")
        return

    # 3. APLIKACE PO PŘIHLÁŠENÍ
    with st.sidebar:
        st.write(f"👤 **{st.session_state['aktualni_uzivatel']}**")
        if st.button("Odhlásit"):
            st.session_state['prihlasen'] = False
            st.rerun()

    st.title("🌍 Globální Portfolio")

    if 'df' not in st.session_state:
        with st.spinner("Nahrávám data..."):
            st.session_state['df'] = nacti_data()
    
    df = st.session_state['df']

    # --- TABULKA EDITACE ---
    with st.expander("📝 Správa (Editace)", expanded=False):
        edited_df = st.data_editor(
            df, num_rows="dynamic", use_container_width=True,
            column_config={
                "Pocet": st.column_config.NumberColumn("Kusy", format="%.4f"),
                "Cena": st.column_config.NumberColumn("Cena", format="%.2f"),
                "Datum": st.column_config.DatetimeColumn("Koupeno", format="D.M.YYYY")
            }
        )
        if not df.equals(edited_df):
            if st.button("💾 ULOŽIT ZMĚNY"):
                st.session_state['df'] = edited_df
                uloz_data(edited_df)
                st.success("Uloženo!")
                st.rerun()

    # --- Rychlé přidání ---
    with st.expander("➕ Rychlé přidání", expanded=False):
        with st.form("add"):
            c1, c2, c3 = st.columns(3)
            with c1: t = st.text_input("Ticker").upper()
            with c2: p = st.number_input("Počet", min_value=0.0001)
            with c3: c = st.number_input("Cena", min_value=0.1)
            if st.form_submit_button("Přidat"):
                novy = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now()}])
                updated = pd.concat([edited_df, novy], ignore_index=True)
                st.session_state['df'] = updated
                uloz_data(updated)
                st.rerun()

    st.divider()

    # --- DASHBOARD (ZŮSTAL STEJNÝ) ---
    if not edited_df.empty:
        viz_data = []
        celk_hodnota_usd = 0
        celk_investice_usd = 0
        stats_meny = {}
        kurzy = ziskej_kurzy()
        
        my_bar = st.progress(0, text="Stahuji ceny...")
        
        for index, row in edited_df.iterrows():
            if pd.isna(row['Ticker']) or pd.isna(row['Pocet']) or str(row['Ticker']).strip() == "": continue
            
            ticker = str(row['Ticker'])
            aktualni_cena, mena = ziskej_info_o_akcii(ticker)
            pouzita_cena = row['Cena'] if aktualni_cena is None else aktualni_cena

            hodnota_orig = row['Pocet'] * pouzita_cena
            investice_orig = row['Pocet'] * row['Cena']
            zisk_orig = hodnota_orig - investice_orig

            if mena not in stats_meny: stats_meny[mena] = {"investice": 0.0, "zisk": 0.0}
            stats_meny[mena]["investice"] += investice_orig
            stats_meny[mena]["zisk"] += zisk_orig

            # Přepočet na USD
            konverze = 1.0
            if mena == "CZK": konverze = 1/kurzy["CZK"]
            elif mena == "EUR": konverze = kurzy["EUR"]
            
            celk_hodnota_usd += hodnota_orig * konverze
            celk_investice_usd += investice_orig * konverze

            viz_data.append({
                "Ticker": ticker, "Měna": mena, "Cena teď": pouzita_cena,
                "Hodnota (Orig)": hodnota_orig, "Zisk (Orig)": zisk_orig
            })
            my_bar.progress((index + 1) / len(edited_df))
        
        my_bar.empty()

        # Metriky
        celk_zisk_usd = celk_hodnota_usd - celk_investice_usd
        c1, c2, c3 = st.columns(3)
        c1.metric("Celkem investováno", f"${celk_investice_usd:,.0f}")
        c2.metric("Aktuální hodnota", f"${celk_hodnota_usd:,.0f}")
        c3.metric("Celkový zisk", f"${celk_zisk_usd:+,.0f}", delta_color="normal")

        st.divider()
        st.subheader("💰 Peněženky podle měn")
        cols = st.columns(len(stats_meny))
        for i, mena in enumerate(stats_meny):
            data = stats_meny[mena]
            symbol = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€" if mena == "EUR" else mena)
            with cols[i]:
                st.metric(f"Měna: {mena}", f"Inv: {data['investice']:,.0f} {symbol}", f"{data['zisk']:+,.0f} {symbol}")
        
        st.divider()
        st.dataframe(pd.DataFrame(viz_data).style.map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Zisk (Orig)']), use_container_width=True)

if __name__ == "__main__":
    main()
