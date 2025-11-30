import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO
import time

# --- KONFIGURACE ---
st.set_page_config(page_title="Moje Portfolio", layout="wide", page_icon="📈")

# 🛑 ZKONTROLUJ SI NÁZEV REPOZITÁŘE!
REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"

# --- STYLY (CSS) ---
# Trochu mague, aby to vypadalo lépe
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
        return pd.read_csv(StringIO(data))
    except:
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena"])

def uloz_data(df):
    repo = get_repo()
    csv = df.to_csv(index=False)
    try:
        file = repo.get_contents(SOUBOR_DATA)
        repo.update_file(file.path, "Update", csv, file.sha)
    except:
        repo.create_file(SOUBOR_DATA, "Init", csv)
    st.cache_data.clear()

# --- BEZPEČNÉ STAŽENÍ CENY ---
def ziskej_aktualni_cenu(ticker):
    """Pokusí se stáhnout cenu. Když to nejde, vrátí None."""
    try:
        # Ticker object je spolehlivější než hromadný download
        akcie = yf.Ticker(ticker)
        # Získáme historii za poslední 2 dny (pro jistotu)
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

    # 1. LOGIN OBRAZOVKA
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
        st.info("💡 Data se ukládají automaticky na GitHub.")

    st.title("📈 Moje Investiční Portfolio")

    if 'df' not in st.session_state:
        with st.spinner("Nahrávám data z cloudu..."):
            st.session_state['df'] = nacti_data()
    
    df = st.session_state['df']

    # --- VÝPOČTY (TADY SE DĚJE KOUZLO) ---
    if not df.empty:
        viz_data = []
        celkova_hodnota = 0
        celkem_investovano = 0
        
        # Progress bar, aby to vypadalo profi
        progress_text = "Aktualizuji ceny na burze..."
        my_bar = st.progress(0, text=progress_text)
        
        celkem_polozek = len(df)
        
        for index, row in df.iterrows():
            ticker = row['Ticker']
            aktualni_cena = ziskej_aktualni_cenu(ticker)
            
            # 🛡️ ZÁCHRANNÁ SÍŤ: Když se cena nepodaří stáhnout
            if aktualni_cena is None or pd.isna(aktualni_cena):
                # Použijeme nákupní cenu, aby se nerozbily výpočty
                pouzita_cena = row['Cena']
                status = "⚠️ (Offline)"
            else:
                pouzita_cena = aktualni_cena
                status = ""

            hodnota = row['Pocet'] * pouzita_cena
            investice = row['Pocet'] * row['Cena']
            zisk = hodnota - investice
            
            celkova_hodnota += hodnota
            celkem_investovano += investice
            
            viz_data.append({
                "Ticker": f"{ticker} {status}",
                "Kusů": row['Pocet'],
                "Cena nákup": row['Cena'],
                "Cena teď": pouzita_cena,
                "Hodnota": hodnota,
                "Zisk ($)": zisk,
                "Zisk (%)": (zisk / investice * 100) if investice > 0 else 0
            })
            # Aktualizace progress baru
            my_bar.progress((index + 1) / celkem_polozek)
        
        my_bar.empty() # Skrýt bar po dokončení
        
        # --- ZOBRAZENÍ DASHBOARDU ---
        celkovy_zisk = celkova_hodnota - celkem_investovano
        
        # Velké metriky
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Investováno", f"${celkem_investovano:,.0f}")
        col2.metric("📊 Aktuální hodnota", f"${celkova_hodnota:,.0f}")
        col3.metric("🚀 Celkový zisk", f"${celkovy_zisk:+,.0f}", delta_color="normal")
        
        st.divider()
        
        c_graf, c_tabulka = st.columns([1, 2])
        
        df_viz = pd.DataFrame(viz_data)

        with c_graf:
            st.subheader("🍰 Rozložení")
            fig = px.pie(df_viz, values='Hodnota', names='Ticker', hole=0.4)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

        with c_tabulka:
            st.subheader("📋 Detailní přehled")
            
            # Formátování tabulky s barvami
            st.dataframe(
                df_viz.style.format({
                    "Cena nákup": "${:.2f}",
                    "Cena teď": "${:.2f}",
                    "Hodnota": "${:.2f}",
                    "Zisk ($)": "${:+.2f}",
                    "Zisk (%)": "{:+.1f} %"
                }).map(lambda x: 'color: #4CAF50; font-weight: bold' if x > 0 else 'color: #FF5252; font-weight: bold', subset=['Zisk ($)', 'Zisk (%)']),
                use_container_width=True,
                height=400
            )

    else:
        st.info("Zatím žádné investice. Přidej první vlevo dole! 👇")

    st.divider()

    # --- PŘIDÁVÁNÍ NOVÝCH ---
    with st.expander("➕ PŘIDAT / UPRAVIT INVESTICI", expanded=df.empty):
        with st.form("add_form"):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                t = st.text_input("Ticker (např. AAPL, BTC-USD)").upper()
            with col_b:
                p = st.number_input("Počet kusů", min_value=0.0001, format="%.4f")
            with col_c:
                c = st.number_input("Nákupní cena ($)", min_value=0.1)
            
            if st.form_submit_button("💾 Uložit na GitHub", use_container_width=True):
                novy = pd.DataFrame([{"Ticker": t, "Pocet": p, "Cena": c}])
                df = pd.concat([df, novy], ignore_index=True)
                st.session_state['df'] = df
                with st.spinner("Odesílám..."):
                    uloz_data(df)
                st.success("Uloženo!")
                st.rerun()

    # --- TLAČÍTKO SMAZAT ---
    if not df.empty:
        if st.button("🗑️ Smazat celou databázi"):
            empty_df = pd.DataFrame(columns=["Ticker", "Pocet", "Cena"])
            st.session_state['df'] = empty_df
            uloz_data(empty_df)
            st.rerun()

if __name__ == "__main__":
    main()
