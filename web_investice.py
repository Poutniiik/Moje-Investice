import streamlit as st
import yfinance as yf
import pandas as pd

# --- NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="Moje Investice", layout="wide")

# --- PAMĚŤ APLIKACE (SESSION STATE) ---
# Tady aplikaci naučíme, aby si pamatovala portfolio, i když klikáme
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = [
        {"symbol": "AAPL", "pocet": 10, "nakupni_cena": 150.00},
        {"symbol": "BTC-USD", "pocet": 0.5, "nakupni_cena": 30000.00},
    ]

# --- FUNKCE PRO PŘIDÁNÍ NOVÉ INVESTICE ---
def pridat_investici(symbol, pocet, cena):
    nova_polozka = {
        "symbol": symbol.upper(), # .upper() změní text na VELKÁ PÍSMENA
        "pocet": float(pocet),
        "nakupni_cena": float(cena)
    }
    st.session_state['portfolio'].append(nova_polozka)
    st.success(f"Přidáno: {symbol}")

# --- HLAVNÍ APLIKACE ---
def ukaz_aplikaci():
    # Rozdělení na dva sloupce: Vlevo ovládání, Vpravo přehled
    col_ovladani, col_prehled = st.columns([1, 3]) 

    with col_ovladani:
        st.header("➕ Přidat nákup")
        with st.form("pridani_form"):
            novy_symbol = st.text_input("Zkratka akcie (např. TSLA)")
            novy_pocet = st.number_input("Počet kusů", min_value=0.01, step=0.1)
            nova_cena = st.number_input("Nákupní cena za kus ($)", min_value=0.1)
            
            # Tlačítko odeslat
            odeslat = st.form_submit_button("Uložit do portfolia")
            
            if odeslat:
                if novy_symbol:
                    pridat_investici(novy_symbol, novy_pocet, nova_cena)
                    st.rerun() # Obnovit stránku, aby se to ukázalo v tabulce
                else:
                    st.error("Vyplň zkratku akcie!")

        st.info("💡 Tip: Pro Bitcoin zadej 'BTC-USD', pro Apple 'AAPL'.")

    with col_prehled:
        st.header("📈 Můj investiční přehled")
        
        celkem_investovano = 0
        celkova_hodnota = 0
        data_pro_tabulku = []

        # Pokud je portfolio prázdné
        if not st.session_state['portfolio']:
            st.warning("Zatím nemáš žádné investice. přidej je vlevo.")
        else:
            with st.spinner('Aktualizuji ceny...'):
                for polozka in st.session_state['portfolio']:
                    ticker = polozka["symbol"]
                    pocet = polozka["pocet"]
                    nakupka = polozka["nakupni_cena"]
                    
                    try:
                        aktualni_cena = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
                    except:
                        aktualni_cena = 0 # Když se nepodaří načíst
                    
                    investovano = pocet * nakupka
                    hodnota_ted = pocet * aktualni_cena
                    zisk = hodnota_ted - investovano
                    
                    if investovano > 0:
                        zisk_procenta = (zisk / investovano) * 100
                    else:
                        zisk_procenta = 0

                    celkem_investovano += investovano
                    celkova_hodnota += hodnota_ted
                    
                    data_pro_tabulku.append({
                        "Akcie": ticker,
                        "Počet": pocet,
                        "Cena nákup": nakupka,
                        "Cena teď": aktualni_cena,
                        "Hodnota": hodnota_ted,
                        "Zisk ($)": zisk,
                        "Zisk (%)": f"{zisk_procenta:.1f} %"
                    })

            # --- ZOBRAZENÍ METRIK (TŘI ČÍSLA NAHOŘE) ---
            celkovy_zisk = celkova_hodnota - celkem_investovano
            m1, m2, m3 = st.columns(3)
            m1.metric("Investováno", f"{celkem_investovano:,.2f} $")
            m2.metric("Hodnota portfolia", f"{celkova_hodnota:,.2f} $")
            m3.metric("Zisk / Ztráta", f"{celkovy_zisk:+,.2f} $", delta_color="normal")

            # --- TABULKA ---
            df = pd.DataFrame(data_pro_tabulku)
            
            # Formátování tabulky (aby čísla vypadala hezky)
            st.dataframe(
                df.style.format({
                    "Cena nákup": "${:.2f}",
                    "Cena teď": "${:.2f}",
                    "Hodnota": "${:.2f}",
                    "Zisk ($)": "${:+.2f}"
                }).map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Zisk ($)']),
                use_container_width=True
            )

# --- LOGIN (ZŮSTAL STEJNÝ) ---
# --- LOGIN SE SEKCE ---
def main():
    st.sidebar.title("🔐 Přihlášení")
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False

    if not st.session_state['prihlasen']:
        uzivatel = st.sidebar.text_input("Uživatelské jméno")
        heslo = st.sidebar.text_input("Heslo", type="password")
        tlacitko = st.sidebar.button("Přihlásit se")

        if tlacitko:
            # --- BEZPEČNOSTNÍ ZMĚNA ---
            try:
                spravne_jmeno = st.secrets["login"]["uzivatel"]
                spravne_heslo = st.secrets["login"]["heslo"]
            except FileNotFoundError:
                st.error("Chybí soubor .streamlit/secrets.toml!")
                return

            if uzivatel == spravne_jmeno and heslo == spravne_heslo:
                st.session_state['prihlasen'] = True
                st.rerun()
            else:
                st.sidebar.error("Chyba přihlášení")
            # --------------------------
            
    else:
        if st.sidebar.button("Odhlásit se"):
            st.session_state['prihlasen'] = False
            st.rerun()
        ukaz_aplikaci()

if __name__ == "__main__":
    main()