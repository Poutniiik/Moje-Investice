import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_lottie import st_lottie
import extra_streamlit_components as stx
import random

# --- IMPORTY NOVÝCH MODULŮ ---
import notification_engine as notify
import bank_engine as bank
from styles import get_css
from ai_brain import init_ai, get_chat_response

# DATA MANAGER: Importujeme přímo z databáze
from data_manager import (
    SOUBOR_DATA, SOUBOR_UZIVATELE, SOUBOR_HISTORIE, SOUBOR_CASH, 
    SOUBOR_WATCHLIST, SOUBOR_DIVIDENDY, nacti_csv, nacti_uzivatele, zasifruj, uloz_csv, uloz_data_uzivatele
)

from utils import ziskej_info, ziskej_fear_greed, cached_ceny_hromadne, cached_kurzy, cached_detail_akcie, zjisti_stav_trhu, vytvor_pdf_report

# LOGIC PORTFOLIO: Importujeme jen logiku, ne data funkce (abychom se vyhnuli zmatkům)
from logic_portfolio import (
    calculate_all_data, send_daily_telegram_report, get_zustatky, 
    pohyb_penez, invalidate_data_core, proved_smenu, aktualizuj_graf_vyvoje
)

from render_engine import (
    render_ticker_tape, render_prehled_page, render_sledovani_page, 
    render_dividendy_page, render_gamifikace_page, render_obchod_page
)

# --- KONFIGURACE ---
st.set_page_config(page_title="Terminal Pro", layout="wide", page_icon="💹", initial_sidebar_state="expanded")

# --- CITÁTY ---
CITATY = ["„Cena je to, co zaplatíš. Hodnota je to, co dostaneš.“ — Warren Buffett", "„Riziko pochází z toho, že nevíte, co děláte.“ — Warren Buffett"]

# --- SETUP STYLU & CACHE ---
if 'ui_theme' not in st.session_state: st.session_state['ui_theme'] = "🕹️ Cyberpunk (Retro)"
st.markdown(f"<style>{get_css(st.session_state['ui_theme'])}</style>", unsafe_allow_html=True)

def get_manager(): return stx.CookieManager(key="cookie_manager_inst")

@st.cache_resource(show_spinner="Připojuji neurální sítě...")
def get_cached_ai_connection():
    return init_ai()

# --- HLAVNÍ FUNKCE ---
def main():
    model, AI_AVAILABLE = get_cached_ai_connection()
    cookie_manager = get_manager()
    time.sleep(0.3)

    # 1. LOGIN
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False
        st.session_state['user'] = ""

    if not st.session_state['prihlasen']:
        cookie_user = cookie_manager.get("invest_user")
        if cookie_user:
            st.session_state['prihlasen'] = True; st.session_state['user'] = cookie_user; st.rerun()

        st.title("🔐 LOGIN")
        u=st.text_input("Uživatelské jméno"); p=st.text_input("Heslo", type="password")
        if st.button("VSTOUPIT"):
             df_u = nacti_uzivatele(); row = df_u[df_u['username'] == u]
             if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                 cookie_manager.set("invest_user", u, expires_at=datetime.now() + timedelta(days=30))
                 st.session_state.update({'prihlasen':True, 'user':u}); st.rerun()
             else: st.error("Chyba")
        return

    # 2. DATA LOAD
    USER = st.session_state['user']
    if 'df' not in st.session_state:
        st.session_state['df'] = nacti_csv(SOUBOR_DATA).query(f"Owner=='{USER}'").copy()
        st.session_state['df_hist'] = nacti_csv(SOUBOR_HISTORIE).query(f"Owner=='{USER}'").copy()
        st.session_state['df_cash'] = nacti_csv(SOUBOR_CASH).query(f"Owner=='{USER}'").copy()
        st.session_state['df_div'] = nacti_csv(SOUBOR_DIVIDENDY).query(f"Owner=='{USER}'").copy()
        st.session_state['df_watch'] = nacti_csv(SOUBOR_WATCHLIST).query(f"Owner=='{USER}'").copy()
        st.session_state['hist_vyvoje'] = aktualizuj_graf_vyvoje(USER, 0)

    # 3. VÝPOČTY (JÁDRO)
    df = st.session_state['df']; df_watch = st.session_state['df_watch']; zustatky = get_zustatky(USER)
    kurzy = cached_kurzy() # Placeholder
    
    if 'data_core' not in st.session_state or (datetime.now() - st.session_state['data_core']['timestamp']) > timedelta(minutes=5):
        data_core = calculate_all_data(USER, df, df_watch, zustatky, kurzy)
    else: data_core = st.session_state['data_core']

    # Rozbalení dat
    vdf = data_core['vdf']; celk_hod_usd = data_core['celk_hod_usd']; celk_inv_usd = data_core['celk_inv_usd']
    hist_vyvoje = data_core['hist_vyvoje']; zmena_24h = data_core['zmena_24h']; pct_24h = data_core['pct_24h']
    cash_usd = data_core['cash_usd']; fundament_data = data_core['fundament_data']; kurzy = data_core['kurzy']
    LIVE_DATA = st.session_state.get('LIVE_DATA', {})
    celk_hod_czk = celk_hod_usd * kurzy.get("CZK", 20.85)
    celk_inv_czk = celk_inv_usd * kurzy.get("CZK", 20.85)

    # 4. SIDEBAR & NAVIGACE
    with st.sidebar:
        st.header(f"👤 {USER.upper()}")
        page = st.radio("Jít na:", ["🏠 Přehled", "👀 Sledování", "💸 Obchod", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení"], label_visibility="collapsed")
        
        level_name = "Novic" if celk_hod_czk < 10000 else "Trader"
        st.caption(f"Úroveň: **{level_name}**"); st.progress(min(celk_hod_czk/100000, 1.0))
        
        if st.button("🚪 ODHLÁSIT"):
            cookie_manager.delete("invest_user"); st.session_state.clear(); st.rerun()

    if page != "🎮 Gamifikace": render_ticker_tape(LIVE_DATA)

    # 5. ROUTING
    if page == "🏠 Přehled":
        render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA)
    elif page == "👀 Sledování":
        render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST)
    elif page == "💸 Obchod":
        render_obchod_page(USER, df, zustatky, LIVE_DATA, kurzy)
    elif page == "💎 Dividendy":
        render_dividendy_page(USER, df, st.session_state['df_div'], kurzy, data_core['viz_data_list'])
    elif page == "🎮 Gamifikace":
        render_gamifikace_page(USER, level_name, 0.5, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, st.session_state['df_div'], vdf, zustatky)
    elif page == "⚙️ Nastavení":
        st.title("⚙️ NASTAVENÍ")
        if st.button("Uložit Portfolio"): uloz_data_uzivatele(st.session_state['df'], USER, SOUBOR_DATA); st.success("Uloženo")
        notify.otestovat_tlacitko()

if __name__ == "__main__":
    main()
