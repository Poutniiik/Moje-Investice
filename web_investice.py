import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
from datetime import datetime

# --- KONFIGURACE ---
st.set_page_config(page_title="Moje Portfolio: Multiměna", layout="wide", page_icon="🌍")

REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"

# --- STYLY ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 15px; text-align: center;}
    div[data-testid="stMetricValue"] {font-size: 2.5rem;}
</style>
""", unsafe_allow_html=True)

# --- PŘIHLÁŠENÍ ---
try:
    ADMIN_USER = st.secrets["login"]["uzivatel"]
    ADMIN_PASS = st.secrets["login"]["heslo"]
    GITHUB_TOKEN = st.secrets["github"]["token"]
except:
    st.error("❌ CHYBA: Chybí nastavení Secrets!")
    st.stop()

# --- GITHUB FUNKCE ---
def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAZEV)

def nacti_data():
    try:
        repo = get_repo()
        file = repo.get_contents(SOUBOR_DATA)
        data = file.decoded_content.decode("utf-8")
        df = pd.read_csv(StringIO(data))
        if 'Datum' not in df.columns: df['Datum'] = datetime.now()
        df['Datum'] = pd.to_datetime(df['Datum'])
        return df
    except:
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena", "Datum"])

def uloz_data(df):
    repo = get_repo()
    df_clean = df.dropna(subset=['Ticker', 'Pocet']) 
    csv = df_clean.to_csv(index=False)
    try:
        file = repo.get_contents(SOUBOR_DATA)
        repo.update_file(file.path, "Update portfolia", csv, file.sha)
    except:
        repo.create_file(SOUBOR_DATA, "Init portfolia", csv)
    st.cache_data.clear()

# --- 🧠 MOZEK NA MĚNY A KURZY ---
@st.cache_data(ttl=3600) # Uložíme do paměti na hodinu, ať to nezdržuje
def ziskej_kurzy():
    """Stáhne aktuální kurzy měn vůči USD."""
    kurzy = {"USD": 1.0}
    tickers = ["CZK=X", "EURUSD=X"] # CZK=X (kolik CZK za USD), EURUSD=X (kolik USD za EUR)
    try:
        data = yf.download(tickers, period="1d")['Close'].iloc[-1]
        kurzy["CZK"] = float(data["CZK=X"])   # Např. 23.50
        kurzy["EUR"] = float(data["EURUSD=X"]) # Např. 1.08
    except:
        pass
    return kurzy

def ziskej_info_o_akcii(ticker):
    """Zjistí aktuální cenu A TAKÉ měnu akcie."""
    if not ticker or pd.isna(ticker): return None, "USD"
    try:
        akcie = yf.Ticker(str(ticker))
        # Zkusíme fast_info (je rychlejší)
        cena = akcie.fast_info.last_price
        mena = akcie.fast_info.currency
        return cena, mena
    except:
        # Fallback (když fast_info selže)
        try:
            hist = akcie.history(period="2d")
            return hist['Close'].iloc[-1], "USD" # Defaultně USD
        except:
            return None, "USD"

# --- HLAVNÍ LOGIKA ---
def main():
    if 'prihlasen' not in st.session_state: st.session_state['prihlasen'] = False

    # 1. LOGIN
    if not st.session_state['prihlasen']:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.title("🔐 Vstup")
            with st.form("login"):
                u = st.text_input("Uživatel")
                p = st.text_input("Heslo", type="password")
                if st.form_submit_button("Start"):
                    if u == ADMIN_USER and p == ADMIN_PASS:
                        st.session_state['prihlasen'] = True
                        st.rerun()
                    else:
                        st.error("Chyba")
        return

    # 2. APLIKACE
    with st.sidebar:
        st.write(f"👤 **{ADMIN_USER}**")
        if st.button("Odhlásit"):
            st.session_state['prihlasen'] = False
            st.rerun()

    st.title("🌍 Globální Portfolio (USD Base)")

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
                "Cena": st.column_config.NumberColumn("Nákupní cena (Orig. měna)", format="%.2f"),
                "Datum": st.column_config.DatetimeColumn("Koupeno", format="D.M.YYYY")
            }
        )
        if not df.equals(edited_df):
            if st.button("💾 ULOŽIT ZMĚNY"):
                st.session_state['df'] = edited_df
                uloz_data(edited_df)
                st.success("Uloženo!")
                st.rerun()

    # --- PŘIDÁNÍ FORMULÁŘEM ---
    with st.expander("➕ Rychlé přidání", expanded=False):
        with st.form("add"):
            c1, c2, c3 = st.columns(3)
            with c1: t = st.text_input("Ticker (např. CEZ.PR)").upper()
            with c2: p = st.number_input("Počet", min_value=0.0001)
            with c3: c = st.number_input("Cena (v měně akcie!)", min_value=0.1)
            if st.form_submit_button("Přidat"):
                novy = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c, "Datum": datetime.now()}])
                updated = pd.concat([edited_df, novy], ignore_index=True)
                st.session_state['df'] = updated
                uloz_data(updated)
                st.rerun()

    st.divider()

    # --- VÝPOČTY MĚN ---
    if not edited_df.empty:
        viz_data = []
        celk_hodnota_usd = 0
        celk_investice_usd = 0
        
        # Stáhneme kurzy měn
        kurzy = ziskej_kurzy()
        
        my_bar = st.progress(0, text="Stahuji ceny a přepočítávám měny...")
        
        for index, row in edited_df.iterrows():
            if pd.isna(row['Ticker']) or pd.isna(row['Pocet']) or str(row['Ticker']).strip() == "": continue
            
            ticker = str(row['Ticker'])
            
            # 1. Zjistíme cenu a měnu akcie
            aktualni_cena, mena = ziskej_info_o_akcii(ticker)
            
            if aktualni_cena is None: 
                pouzita_cena = row['Cena']
                mena = "N/A"
            else:
                pouzita_cena = aktualni_cena

            # 2. Výpočet v originální měně
            hodnota_orig = row['Pocet'] * pouzita_cena
            investice_orig = row['Pocet'] * row['Cena']
            zisk_orig = hodnota_orig - investice_orig

            # 3. PŘEPOČET NA DOLARY (USD) PRO CELKOVÝ SOUČET
            # Pokud je to CZK: dělíme kurzem (např. 1000 CZK / 23 = 43 USD)
            # Pokud je to EUR: násobíme kurzem (např. 100 EUR * 1.08 = 108 USD)
            
            hodnota_usd = 0
            investice_usd = 0

            if mena == "USD":
                hodnota_usd = hodnota_orig
                investice_usd = investice_orig
            elif mena == "CZK":
                hodnota_usd = hodnota_orig / kurzy["CZK"]
                investice_usd = investice_orig / kurzy["CZK"]
            elif mena == "EUR":
                hodnota_usd = hodnota_orig * kurzy["EUR"]
                investice_usd = investice_orig * kurzy["EUR"]
            else:
                # Neznámá měna - bereme jako 1:1 (nouzovka)
                hodnota_usd = hodnota_orig
                investice_usd = investice_orig

            celk_hodnota_usd += hodnota_usd
            celk_investice_usd += investice_usd

            viz_data.append({
                "Ticker": ticker,
                "Měna": mena,
                "Cena teď": pouzita_cena,
                "Hodnota (Orig)": hodnota_orig,
                "Hodnota (USD)": hodnota_usd,
                "Zisk (Orig)": zisk_orig
            })
            my_bar.progress((index + 1) / len(edited_df))
        
        my_bar.empty()

        # --- DASHBOARD ---
        celk_zisk_usd = celk_hodnota_usd - celk_investice_usd
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Celkem investováno (USD)", f"${celk_investice_usd:,.0f}")
        c2.metric("Aktuální hodnota (USD)", f"${celk_hodnota_usd:,.0f}")
        c3.metric("Celkový zisk (USD)", f"${celk_zisk_usd:+,.0f}", delta_color="normal")

        # Tabulka s detaily
        st.subheader("📊 Detailní rozpis")
        df_viz = pd.DataFrame(viz_data)
        
        # Formátování, aby to bylo hezké
        st.dataframe(
            df_viz.style.format({
                "Cena teď": "{:.2f}",
                "Hodnota (Orig)": "{:,.2f}",
                "Hodnota (USD)": "${:,.2f}",
                "Zisk (Orig)": "{:+,.2f}"
            }).map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Zisk (Orig)']),
            use_container_width=True
        )

        # Graf (koláč podle USD hodnoty)
        fig = px.pie(df_viz, values='Hodnota (USD)', names='Ticker', title='Rozložení portfolia (přepočteno na USD)')
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Prázdno.")

if __name__ == "__main__":
    main()

