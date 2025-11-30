import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# --- NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="Moje Investice", layout="wide")

# --- NAČTENÍ HESLA Z TREZORU (BEZPEČNĚ) ---
try:
    # Načteme si to do proměnných hned na začátku
    ADMIN_USER = st.secrets["login"]["uzivatel"]
    ADMIN_PASS = st.secrets["login"]["heslo"]
except Exception:
    # Pokud to selže, aplikace se zastaví a řekne proč
    st.error("🚨 CHYBA: Nejsou nastaveny 'Secrets' v Streamlit Cloudu!")
    st.info("Jdi do Settings -> Secrets a vlož tam přihlašovací údaje.")
    st.stop() # Zastaví zbytek aplikace

# --- PAMĚŤ APLIKACE ---
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []
if 'prihlasen' not in st.session_state:
    st.session_state['prihlasen'] = False

# --- FUNKCE PRO PŘIDÁNÍ ---
def pridat_investici(symbol, pocet, cena):
    nova_polozka = {
        "symbol": symbol.upper(),
        "pocet": float(pocet),
        "nakupni_cena": float(cena)
    }
    st.session_state['portfolio'].append(nova_polozka)
    st.success(f"Přidáno: {symbol}")

# --- HLAVNÍ APLIKACE (DASHBOARD) ---
def ukaz_aplikaci():
    # Tlačítko odhlášení v bočním panelu
    with st.sidebar:
        st.write(f"👤 Uživatel: **{ADMIN_USER}**")
        if st.button("Odhlásit se"):
            st.session_state['prihlasen'] = False
            st.rerun()

    st.title("💰 Můj Investiční Dashboard")
    
    col_ovladani, col_prehled = st.columns([1, 3]) 

    # --- LEVÝ PANEL (PŘIDÁVÁNÍ) ---
    with col_ovladani:
        st.subheader("➕ Nový nákup")
        with st.form("pridani_form"):
            novy_symbol = st.text_input("Ticker (např. AAPL, BTC-USD)")
            novy_pocet = st.number_input("Počet kusů", min_value=0.0001, format="%.4f")
            nova_cena = st.number_input("Nákupní cena za kus ($)", min_value=0.1)
            
            odeslat = st.form_submit_button("Uložit")
            if odeslat:
                if novy_symbol:
                    pridat_investici(novy_symbol, novy_pocet, nova_cena)
                    st.rerun()
                else:
                    st.warning("Musíš vyplnit název akcie!")

        if st.button("🗑️ Vymazat portfolio"):
            st.session_state['portfolio'] = []
            st.rerun()

    # --- PRAVÝ PANEL (DATA A GRAFY) ---
    with col_prehled:
        if not st.session_state['portfolio']:
            st.info("Zatím žádné investice. Přidej něco vlevo! 👈")
        else:
            data_pro_tabulku = []
            celkem_investovano = 0
            celkova_hodnota = 0

            with st.spinner('Aktualizuji tržní data...'):
                for polozka in st.session_state['portfolio']:
                    ticker = polozka["symbol"]
                    pocet = polozka["pocet"]
                    nakupka = polozka["nakupni_cena"]
                    
                    try:
                        aktualni_cena = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                    except:
                        aktualni_cena = 0 
                    
                    investovano = pocet * nakupka
                    hodnota_ted = pocet * aktualni_cena
                    zisk = hodnota_ted - investovano
                    zisk_proc = (zisk / investovano * 100) if investovano > 0 else 0

                    celkem_investovano += investovano
                    celkova_hodnota += hodnota_ted
                    
                    data_pro_tabulku.append({
                        "Ticker": ticker,
                        "Počet": pocet,
                        "Cena nákup": nakupka,
                        "Cena teď": aktualni_cena,
                        "Hodnota ($)": hodnota_ted,
                        "Zisk ($)": zisk,
                        "Zisk (%)": zisk_proc
                    })

            # METRIKY
            celkovy_zisk = celkova_hodnota - celkem_investovano
            c1, c2, c3 = st.columns(3)
            c1.metric("Investováno", f"{celkem_investovano:,.0f} $")
            c2.metric("Hodnota portfolia", f"{celkova_hodnota:,.0f} $")
            c3.metric("Celkový zisk", f"{celkovy_zisk:+,.0f} $", delta_color="normal")
            
            st.divider()

            # GRAFY
            df = pd.DataFrame(data_pro_tabulku)
            g1, g2 = st.columns(2)
            
            with g1:
                st.subheader("🍰 Rozložení")
                fig_pie = px.pie(df, values='Hodnota ($)', names='Ticker', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with g2:
                st.subheader("📊 Ziskovost")
                fig_bar = px.bar(df, x='Ticker', y='Zisk ($)', color='Zisk ($)',
                                color_continuous_scale=['red', 'green'])
                st.plotly_chart(fig_bar, use_container_width=True)

            # TABULKA
            st.subheader("📋 Detailní výpis")
            st.dataframe(
                df.style.format({
                    "Cena nákup": "${:.2f}",
                    "Cena teď": "${:.2f}",
                    "Hodnota ($)": "${:.2f}",
                    "Zisk ($)": "${:+.2f}",
                    "Zisk (%)": "{:+.1f} %"
                }).map(lambda x: 'color: #4CAF50' if x > 0 else 'color: #FF5252', subset=['Zisk ($)', 'Zisk (%)']),
                use_container_width=True
            )

# --- HLAVNÍ FUNKCE (LOGIN) ---
def main():
    # Pokud není uživatel přihlášen, ukážeme jen login formulář
    if not st.session_state['prihlasen']:
        # Zarovnání na střed pomocí prázdných sloupců
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("<h1 style='text-align: center;'>🔐 Přihlášení</h1>", unsafe_allow_html=True)
            with st.form("login_form"):
                uzivatel = st.text_input("Uživatelské jméno")
                heslo = st.text_input("Heslo", type="password")
                submit = st.form_submit_button("Vstoupit do aplikace", use_container_width=True)
                
                if submit:
                    # Porovnáváme s načtenými proměnnými z začátku
                    if uzivatel == ADMIN_USER and heslo == ADMIN_PASS:
                        st.session_state['prihlasen'] = True
                        st.rerun()
                    else:
                        st.error("❌ Špatné jméno nebo heslo")
    
    # Pokud je přihlášen, ukážeme aplikaci
    else:
        ukaz_aplikaci()

if __name__ == "__main__":
    main()
