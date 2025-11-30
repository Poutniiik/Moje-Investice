import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from github import Github
from io import StringIO

st.set_page_config(page_title="Moje Online Investice", layout="wide")

# --- 1. NASTAVENÍ (Změň si název repozitáře!) ---
REPO_NAZEV = "Poutniiik/Moje-Investice" 
SOUBOR_DATA = "portfolio_data.csv"

# --- 2. PŘIHLÁŠENÍ A TOKENY ---
try:
    ADMIN_USER = st.secrets["login"]["uzivatel"]
    ADMIN_PASS = st.secrets["login"]["heslo"]
    GITHUB_TOKEN = st.secrets["github"]["token"]
except:
    st.error("❌ CHYBA: Nejsou nastaveny Secrets! (chybí login nebo github token)")
    st.stop()

# --- 3. FUNKCE PRO GITHUB (Mozek aplikace) ---
def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAZEV)

def nacti_data():
    try:
        repo = get_repo()
        # Zkusíme najít soubor s daty
        file_content = repo.get_contents(SOUBOR_DATA)
        # Dekódujeme data z GitHubu
        csv_data = file_content.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(csv_data))
    except:
        # Když soubor neexistuje (první spuštění), vrátíme prázdnou tabulku
        return pd.DataFrame(columns=["Ticker", "Pocet", "Cena"])

def uloz_data(df):
    repo = get_repo()
    csv_content = df.to_csv(index=False)
    
    try:
        # Zkusíme soubor aktualizovat
        file = repo.get_contents(SOUBOR_DATA)
        repo.update_file(file.path, "Aktualizace portfolia", csv_content, file.sha)
    except:
        # Pokud neexistuje, vytvoříme nový
        repo.create_file(SOUBOR_DATA, "Vytvoření portfolia", csv_content)
    
    st.cache_data.clear()

# --- 4. HLAVNÍ APLIKACE ---
def main():
    # Login obrazovka
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False

    if not st.session_state['prihlasen']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Přihlášení")
            with st.form("login"):
                u = st.text_input("Jméno")
                p = st.text_input("Heslo", type="password")
                if st.form_submit_button("Vstoupit"):
                    if u == ADMIN_USER and p == ADMIN_PASS:
                        st.session_state['prihlasen'] = True
                        st.rerun()
                    else:
                        st.error("Špatné heslo")
        return

    # Aplikace po přihlášení
    with st.sidebar:
        st.success(f"Uživatel: {ADMIN_USER}")
        if st.button("Odhlásit"):
            st.session_state['prihlasen'] = False
            st.rerun()

    st.title("📈 Moje Portfolio (GitHub Cloud)")

    # Načtení dat při startu
    if 'df' not in st.session_state:
        with st.spinner("Stahuji data z GitHubu..."):
            st.session_state['df'] = nacti_data()

    df = st.session_state['df']

    col1, col2 = st.columns([1, 2])

    # Formulář
    with col1:
        st.subheader("➕ Přidat investici")
        with st.form("add"):
            tick = st.text_input("Zkratka (např. AAPL)").upper()
            kusy = st.number_input("Počet kusů", min_value=0.001, format="%.3f")
            cena = st.number_input("Nákupní cena ($)", min_value=0.1)
            
            if st.form_submit_button("💾 ULOŽIT NAVŽDY"):
                novy_radek = pd.DataFrame([{"Ticker": tick, "Pocet": kusy, "Cena": cena}])
                df = pd.concat([df, novy_radek], ignore_index=True)
                st.session_state['df'] = df # Uložit do paměti aplikace
                
                with st.spinner("Odesílám na GitHub..."):
                    uloz_data(df) # Odeslat na server
                
                st.success("✅ Uloženo! Data jsou v bezpečí.")
                st.rerun()
        
        if st.button("🗑️ Smazat všechna data"):
            prazdny = pd.DataFrame(columns=["Ticker", "Pocet", "Cena"])
            st.session_state['df'] = prazdny
            uloz_data(prazdny)
            st.rerun()

    # Přehled
    with col2:
        if not df.empty:
            # Rychlý výpočet hodnoty
            celkem_hodnota = 0
            viz_data = []
            
            # Abychom nečekali věčnost, stáhneme ceny hromadně
            tickers = df['Ticker'].unique().tolist()
            ceny_burza = {}
            if tickers:
                try:
                    data = yf.download(tickers, period="1d")['Close'].iloc[-1]
                    # Ošetření, když je jen jedna akcie (yfinance vrací číslo, ne seznam)
                    if len(tickers) == 1:
                        ceny_burza[tickers[0]] = float(data)
                    else:
                        for t in tickers:
                            ceny_burza[t] = float(data[t])
                except:
                    pass

            for index, row in df.iterrows():
                t = row['Ticker']
                c_ted = ceny_burza.get(t, row['Cena']) # Když nenačte cenu, použije nákupní
                hodnota = row['Pocet'] * c_ted
                zisk = hodnota - (row['Pocet'] * row['Cena'])
                celkem_hodnota += hodnota
                
                viz_data.append({
                    "Ticker": t,
                    "Kusů": row['Pocet'],
                    "Cena nákup": row['Cena'],
                    "Hodnota": hodnota,
                    "Zisk": zisk
                })
            
            st.metric("Celková hodnota", f"${celkem_hodnota:,.2f}")
            
            df_viz = pd.DataFrame(viz_data)
            
            tab1, tab2 = st.tabs(["Graf", "Tabulka"])
            with tab1:
                fig = px.pie(df_viz, values='Hodnota', names='Ticker', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            with tab2:
                st.dataframe(df_viz.style.format({"Hodnota": "${:.2f}", "Zisk": "${:+.2f}"}), use_container_width=True)
        else:
            st.info("Zatím žádná data.")

if __name__ == "__main__":
    main()


