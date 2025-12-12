# =========================================================================
# SOUBOR: pages/trade_page.py
# =========================================================================
import streamlit as st
import pandas as pd
import time
import utils
from data_manager import SOUBOR_HISTORIE, uloz_data_uzivatele

def trade_page(USER, df, df_cash, zustatky, LIVE_DATA, kurzy, 
               proved_nakup_fn, proved_prodej_fn, proved_smenu_fn, 
               pohyb_penez_fn, invalidate_data_core_fn):
    
    st.title("💸 OBCHODNÍ PULT")

    # 1. Čítač transakcí
    if 'tx_counter' not in st.session_state:
        st.session_state['tx_counter'] = 0
    
    form_key = f"trade_form_{st.session_state['tx_counter']}"

    # --- HORNÍ ČÁST ---
    with st.container(border=True):
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, key="main_mode")
        st.divider()
        
        c1, c2 = st.columns([1, 1])
        with c1:
            ticker_input = st.text_input("Ticker (např. AAPL)", key="t_input").upper().strip()
        with c2:
            current_price = 0.0
            if ticker_input:
                with st.spinner("Hledám cenu..."):
                    info, _ = utils.cached_detail_akcie(ticker_input)
                    if info:
                        current_price = info.get('currentPrice', 0)
                        st.metric("Aktuální cena", f"${current_price}")
                    else:
                        st.warning("Nenalezeno")

    # --- FORMULÁŘ OBCHODU ---
    with st.form(key=form_key):
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            qty = st.number_input("Počet kusů", min_value=0.01, step=1.0)
        with c_f2:
            manual_price = st.number_input("Cena za kus (USD)", value=float(current_price), min_value=0.0)
        
        note = st.text_input("Poznámka / Strategie")
        sector = st.selectbox("Sektor", ["Tech", "Finance", "Energy", "Health", "Cons. Disc", "Cons. Stap", "Real Estate", "Utility", "Materials", "Industrial", "Comms", "ETF/Index", "Crypto", "Jiny"])

        submit = st.form_submit_button("✅ POTVRDIT OBCHOD")

        if submit:
            cost = qty * manual_price
            
            if mode == "🟢 NÁKUP":
                # Kontrola zůstatku
                dostupne_usd = zustatky.get("USD", 0) + (zustatky.get("CZK", 0) / kurzy["CZK"])
                if cost > dostupne_usd:
                    st.error(f"❌ Nedostatek prostředků! Potřebuješ ${cost:.2f}, máš ${dostupne_usd:.2f}")
                else:
                    # 1. STRHNOUT PENÍZE (Optimistic)
                    # Vytvoříme řádek pro cash
                    cash_row = {
                        "Typ": "Nákup",
                        "Castka": -float(cost),
                        "Mena": "USD",
                        "Poznamka": f"{ticker_input}",
                        "Datum": str(pd.Timestamp.now()),
                        "Owner": USER
                    }
                    # Voláme callback pro změnu peněz
                    if proved_smenu_fn:
                        proved_smenu_fn(cash_row, USER)
                    
                    # 2. PŘIDAT AKCII (Optimistic)
                    stock_row = {
                        "Ticker": ticker_input,
                        "Pocet": float(qty),
                        "Cena": float(manual_price),
                        "Datum": str(pd.Timestamp.now()),
                        "Owner": USER,
                        "Sektor": sector,
                        "Poznamka": note
                    }
                    
                    st.session_state['tx_counter'] += 1
                    
                    # Voláme callback pro nákup (ten provede update a rerun)
                    if proved_nakup_fn:
                        proved_nakup_fn(stock_row, USER)

            else: # PRODEJ
                st.info("Prodej je zatím ve vývoji pro novou architekturu.")
                # Zde by byla logika prodeje, která je složitější na update session_state,
                # protože se musí modifikovat existující řádky.

    # --- MANUÁLNÍ VKLAD (Formulář) ---
    with st.expander("💰 PENĚŽENKA (Vklad/Výběr)"):
        with st.form(key=f"wallet_form_{st.session_state['tx_counter']}"):
            m_op = st.radio("Typ operace", ["Vklad", "Výběr"], horizontal=True)
            c_w1, c_w2 = st.columns(2)
            with c_w1: m_amt = st.number_input("Částka", 0.0, step=500.0)
            with c_w2: m_cur = st.selectbox("Měna", ["CZK", "USD", "EUR"])
            
            w_submit = st.form_submit_button("Provést operaci")
            
            if w_submit:
                sign = 1 if m_op == "Vklad" else -1
                
                cash_row = {
                    "Typ": m_op,
                    "Castka": float(m_amt * sign),
                    "Mena": m_cur,
                    "Poznamka": "Manual",
                    "Datum": str(pd.Timestamp.now()),
                    "Owner": USER
                }
                
                st.session_state['tx_counter'] += 1
                if proved_smenu_fn:
                    proved_smenu_fn(cash_row, USER)
