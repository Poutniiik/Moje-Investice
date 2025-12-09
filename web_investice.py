import streamlit as st
import time
from datetime import datetime, timedelta
import pandas as pd

# Importy z našich nových modulů
import core
import views
from data_manager import nacti_csv, nacti_uzivatele, zasifruj, SOUBOR_DATA, SOUBOR_WATCHLIST, SOUBOR_CASH, SOUBOR_HISTORIE, SOUBOR_DIVIDENDY
from styles import get_css
from streamlit_lottie import st_lottie
import requests
import notification_engine as notify

# --- KONFIGURACE ---
st.set_page_config(page_title="Terminal Pro", layout="wide", page_icon="💹")

# --- INITIAL SETUP ---
if 'ui_theme' not in st.session_state: st.session_state['ui_theme'] = "🕹️ Cyberpunk (Retro)"
st.markdown(f"<style>{get_css(st.session_state['ui_theme'])}</style>", unsafe_allow_html=True)

# --- DATA LOADING (SESSION STATE) ---
if 'df' not in st.session_state:
    # Prvotní načtení do session state
    # (V reálu zde načti data pro konkrétního usera po loginu)
    pass 

# --- LOGIN LOGIKA (Zjednodušeno pro přehlednost, doplň svoji auth logiku) ---
if 'prihlasen' not in st.session_state: st.session_state['prihlasen'] = False

if not st.session_state['prihlasen']:
    st.title("🔐 PŘIHLÁŠENÍ")
    user = st.text_input("Uživatel")
    pw = st.text_input("Heslo", type="password")
    if st.button("Vstoupit"):
        # Tady by byla kontrola hesla proti users_db.csv
        st.session_state['prihlasen'] = True
        st.session_state['user'] = user
        st.rerun()
    st.stop()

USER = st.session_state['user']

# --- NAČTENÍ DAT UŽIVATELE ---
if 'df' not in st.session_state:
    with st.spinner("Startuji jádro..."):
        st.session_state['df'] = nacti_csv(SOUBOR_DATA).query(f"Owner=='{USER}'")
        st.session_state['df_cash'] = nacti_csv(SOUBOR_CASH).query(f"Owner=='{USER}'")
        st.session_state['df_watch'] = nacti_csv(SOUBOR_WATCHLIST).query(f"Owner=='{USER}'")
        st.session_state['df_hist'] = nacti_csv(SOUBOR_HISTORIE).query(f"Owner=='{USER}'")
        st.session_state['df_div'] = nacti_csv(SOUBOR_DIVIDENDY).query(f"Owner=='{USER}'")

# --- CORE VÝPOČTY ---
# Zkontrolujeme, zda musíme přepočítat data (cache timeout 5 min)
if 'data_core' not in st.session_state or (datetime.now() - st.session_state['data_core']['timestamp'] > timedelta(minutes=5)):
    # Získáme zustatky
    zustatky = st.session_state['df_cash'].groupby('Mena')['Castka'].sum().to_dict()
    # Spustíme velký výpočet v CORE
    st.session_state['data_core'] = core.calculate_all_data(
        USER, 
        st.session_state['df'], 
        st.session_state['df_watch'], 
        zustatky, 
        {"USD": 1.0, "CZK": 21.0, "EUR": 1.1} # Default kurzy, core si je zpřesní
    )

data_core = st.session_state['data_core']

# --- AUTOMATICKÝ TELEGRAM REPORT ---
# Toto se spustí při každém kliknutí/načtení.
# Pokud je po 18:00 a report nebyl odeslán, odešle se.
is_sent, status_msg = core.check_and_send_daily_report(USER, data_core)
if is_sent:
    st.toast(f"🤖 {status_msg}", icon="📨")

# --- SIDEBAR NAVIGACE ---
with st.sidebar:
    st.header(f"👤 {USER}")
    page = st.radio("Menu", ["🏠 Přehled", "💸 Obchod", "💎 Dividendy", "📈 Analýza", "⚙️ Nastavení"])
    
    # Indikátor auto-reportu
    if st.session_state.get('last_telegram_report') == datetime.now().strftime("%Y-%m-%d"):
        st.caption("✅ Denní report: ODESLÁN")
    else:
        st.caption("⏳ Denní report: ČEKÁ (18:00+)")
        
    if st.button("Odhlásit"):
        st.session_state.clear()
        st.rerun()

# --- ROUTER STRÁNEK ---
if page == "🏠 Přehled":
    views.render_prehled_page(USER, data_core, False, None)

elif page == "💸 Obchod":
    zustatky = st.session_state['df_cash'].groupby('Mena')['Castka'].sum().to_dict()
    views.render_obchod_page(USER, st.session_state['df'], zustatky, st.session_state.get('LIVE_DATA', {}))

elif page == "💎 Dividendy":
    views.render_dividendy_page(USER, st.session_state['df_div'], data_core['kurzy'])

elif page == "📈 Analýza":
    views.render_analyza_page(data_core, None, False)

elif page == "⚙️ Nastavení":
    st.title("⚙️ Nastavení")
    # Tlačítko pro manuální test Telegramu
    notify.otestovat_tlacitko()
