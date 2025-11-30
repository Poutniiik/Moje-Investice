import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
from datetime import datetime

# --- KONFIGURACE ---
st.set_page_config(page_title="Moje Portfolio Pro", layout="wide", page_icon="🚀")

# 🛑 ZKONTROLUJ SI NÁZEV REPOZITÁŘE!
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
        
        if 'Datum' not in df.columns:
            df['Datum'] = datetime.now()
        
        df['Datum'] = pd.to_datetime(df['Datum'])
        return df
    except:
        return pd.DataFrame({
            "Ticker": pd.Series(dtype='str'),
            "Pocet": pd.Series(dtype='float'),
            "Cena": pd.Series(dtype='float'),
            "Datum": pd.Series(dtype='datetime64[ns]')
        })

def uloz_data(df):
    repo = get_repo()
    # Před uložením odstraníme prázdné řádky, aby se neukládalo smetí
    df_clean = df.dropna(subset=['Ticker', 'Pocet']) 
    csv = df_clean.to_csv(index=False)
    try:
        file = repo.get_contents(SOUBOR_DATA)
        repo.update_file(file.path, "Update portfolia", csv, file.sha)
    except:
        repo.create_file(SOUBOR_DATA, "Init portfolia", csv)
    st.cache_data.clear()

# --- CENA AKCIE ---
def ziskej_aktualni_cenu(ticker):
    if not ticker or pd.isna(ticker): return None
    try:
        akcie = yf.Ticker(str(ticker))
        hist = akcie.history(period="2d")
        if not hist.empty:
            return hist['Close'].iloc[-1]
    except:
        pass
    return None

# --- HLAVNÍ LOGIKA ---
def main():
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False

    # 1. LOGIN
    if not st.session_state['prihlasen']:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.title("🔐 Vstup do portfolia")
            with st.form("login"):
                u = st.text_input("Uživatel")
                p = st.text_input("Heslo", type="password")
                if st.form_submit_button("Přihlásit se", use_container_width=True):
                    if u == ADMIN_USER and p == ADMIN_PASS:
                        st.session_state['prihlasen'] = True
                        st.rerun()
                    else:
                        st.error("Neplatné údaje")
        return

    # 2. APLIKACE
    with st.sidebar:
        st.write(f"👤 **{ADMIN_USER}**")
        if st.button("Odhlásit", use_container_width=True):
            st.session_state['prihlasen'] = False
            st.rerun()
        st.divider()
        st.info("💡 Tip: Řádky můžeš přidávat i tlačítkem '+' v tabulce.")

    st.title("🚀 Moje Portfolio: Edice Pro")

    if 'df' not in st.session_state:
        with st.spinner("Nahrávám data z cloudu..."):
            st.session_state['df'] = nacti_data()
    
    df = st.session_state['df']

    # --- SEKCE 1: EDITACE DAT (TABULKA) ---
    with st.expander("📝 SPRÁVA DAT (Editace, Mazání, Historie)", expanded=True):
        st.caption("Můžeš editovat přímo v tabulce. Nový řádek přidáš kliknutím na + dole.")
        
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Pocet": st.column_config.NumberColumn("Počet kusů", format="%.4f"),
                "Cena": st.column_config.NumberColumn("Nákupní cena ($)", format="$%.2f"),
                "Datum": st.column_config.DatetimeColumn("Datum nákupu", format="D.M.YYYY HH:mm")
            }
        )

        if not df.equals(edited_df):
            st.warning("⚠️ Máš neuložené změny!")
            if st.button("💾 ULOŽIT ZMĚNY NA GITHUB", type="primary"):
                st.session_state['df'] = edited_df
                with st.spinner("Odesílám změny..."):
                    uloz_data(edited_df)
                st.success("Uloženo!")
                st.rerun()

    st.divider()

    # --- SEKCE 2: DASHBOARD ---
    if not edited_df.empty:
        viz_data = []
        celkova_hodnota = 0
        celkem_investovano = 0
        
        my_bar = st.progress(0, text="Počítám zisky...")
        total_rows = len(edited_df)
        
        for index, row in edited_df.iterrows():
            # --- ZÁCHRANNÁ BRZDA (Oprava chyby) ---
            # Pokud je řádek prázdný (právě jsi klikl na +), přeskočíme výpočty
            if pd.isna(row['Ticker']) or pd.isna(row['Pocet']) or row['Ticker'] == "":
                continue # Jdeme na další řádek a tento ignorujeme
            
            # Převedeme na čísla, kdyby náhodou
            try:
                r_pocet = float(row['Pocet']) if pd.notnull(row['Pocet']) else 0.0
                r_cena_nakup = float(row['Cena']) if pd.notnull(row['Cena']) else 0.0
            except:
                r_pocet = 0
                r_cena_nakup = 0

            ticker = str(row['Ticker'])
            aktualni_cena = ziskej_aktualni_cenu(ticker)
            
            if aktualni_cena is None or pd.isna(aktualni_cena):
                pouzita_cena = r_cena_nakup
            else:
                pouzita_cena = aktualni_cena

            hodnota = r_pocet * pouzita_cena
            investice = r_pocet * r_cena_nakup
            zisk = hodnota - investice
            
            celkova_hodnota += hodnota
            celkem_investovano += investice
            
            viz_data.append({
                "Ticker": ticker,
                "Hodnota": hodnota,
                "Zisk": zisk,
                "Datum": row.get('Datum', '-')
            })
            if total_rows > 0:
                my_bar.progress((index + 1) / total_rows)
        
        my_bar.empty()
        
        # Zobrazíme dashboard jen pokud máme nějaká platná data
        if viz_data:
            celkovy_zisk = celkova_hodnota - celkem_investovano
            c1, c2, c3 = st.columns(3)
            c1.metric("Investováno", f"${celkem_investovano:,.0f}")
            c2.metric("Hodnota", f"${celkova_hodnota:,.0f}")
            c3.metric("Zisk", f"${celkovy_zisk:+,.0f}", delta_color="normal")
            
            df_viz = pd.DataFrame(viz_data)
            g1, g2 = st.columns(2)
            with g1:
                fig = px.pie(df_viz, values='Hodnota', names='Ticker', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            with g2:
                fig = px.bar(df_viz, x='Ticker', y='Zisk', color='Zisk', color_continuous_scale=['red', 'green'])
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Doplň údaje do tabulky nahoře.")

    else:
        st.info("Portfolio je prázdné.")

if __name__ == "__main__":
    main()
