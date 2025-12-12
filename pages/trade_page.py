# =========================================================================
# SOUBOR: pages/trade_page.py
# =========================================================================
import streamlit as st
import pandas as pd
import time
import numpy as np
import utils

def trade_page(USER, df_arg, df_cash_arg, zustatky_arg, LIVE_DATA, kurzy, 
               proved_nakup_fn, proved_prodej_fn, proved_smenu_fn, 
               pohyb_penez_fn, invalidate_data_core_fn):
    """
    Vykreslí stránku "💸 Obchodní Pult"
    """
    st.title("💸 OBCHODNÍ PULT")

    # --- 0. POJISTKA PROTI STARÝM DATŮM (F5 FIX) ---
    # Načteme data přímo ze session_state, pokud tam jsou, abychom měli jistotu, že jsou čerstvá.
    # Argumenty funkce (df_arg, atd.) mohou být z doby před refreshí.
    df = st.session_state.get('df', df_arg)
    df_cash = st.session_state.get('df_cash', df_cash_arg)
    # Zůstatky raději přepočítáme z čerstvých dat, pokud je to možné
    if not df_cash.empty:
        zustatky = df_cash.groupby('Mena')['Castka'].sum().to_dict()
    else:
        zustatky = zustatky_arg
    
    # --- 1. HLAVNÍ OBCHODNÍ KARTA ---
    with st.container(border=True):
        # Jednoduchý klíč pro rádio, aby nemizelo
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, label_visibility="collapsed", key="mode_radio_main")
        st.divider()
        
        c1, c2 = st.columns([1, 1])
        with c1:
            if mode == "🔴 PRODEJ" and not df.empty:
                # Selectbox pro prodej
                ticker_input = st.selectbox("Ticker", df['Ticker'].unique(), key="sell_ticker_select")
            else:
                # Text input pro nákup
                ticker_input = st.text_input("Ticker", placeholder="např. AAPL, CEZ.PR", key="buy_ticker_input").upper()
        
        # Live Data
        current_price, menu, denni_zmena = 0, "USD", 0
        if ticker_input:
            info = LIVE_DATA.get(ticker_input)
            if info:
                current_price = info.get('price', 0)
                menu = info.get('curr', 'USD')
            else:
                p, m, z = utils.ziskej_info(ticker_input)
                if p: current_price, menu, denni_zmena = p, m, z

            if current_price > 0:
                with c2:
                    color_price = "green" if denni_zmena >= 0 else "red"
                    st.markdown(f"**Cena:** :{color_price}[{current_price:,.2f} {menu}]")
                    st.caption(f"Změna: {denni_zmena*100:+.2f}%")
            else:
                with c2: st.warning("Cena nedostupná")

        st.write("")
        col_qty, col_price = st.columns(2)
        
        # Používáme klíče závislé na tickeru, aby se hodnoty resetovaly při změně akcie,
        # ale NE na stavu portfolia, aby to neblblo při překreslení.
        key_suffix = f"{ticker_input}_{mode}"
        
        with col_qty:
            qty = st.number_input("Počet kusů", min_value=0.0, step=1.0, format="%.2f", key=f"q_{key_suffix}")
        with col_price:
            limit_price = st.number_input("Cena za kus", min_value=0.0, value=float(current_price) if current_price else 0.0, step=0.1, key=f"p_{key_suffix}")

        total_est = qty * limit_price
        zustatek = zustatky.get(menu, 0)
        st.write("") 
        
        # --- LOGIKA TLAČÍTKA ---
        if mode == "🟢 NÁKUP":
            if total_est > 0:
                c_info1, c_info2 = st.columns(2)
                c_info1.info(f"Celkem: **{total_est:,.2f} {menu}**")
                
                if zustatek >= total_est:
                    c_info2.success(f"Na účtu: {zustatek:,.2f} {menu}")
                    
                    # TLAČÍTKO NÁKUPU
                    if st.button(f"KOUPIT {qty}x {ticker_input}", type="primary", use_container_width=True, key=f"btn_buy_{key_suffix}"):
                        # 1. Zavoláme funkci nákupu
                        # Očekáváme, že funkce vrátí (True, msg) NEBO rovnou provede rerun a nic nevrátí.
                        res = proved_nakup_fn(ticker_input, qty, limit_price, USER)
                        
                        # 2. Pokud se kód dostane sem, znamená to, že funkce nerestartovala aplikaci.
                        # Musíme zpracovat výsledek a restartovat my.
                        if res and isinstance(res, tuple):
                            ok, msg = res
                            if ok:
                                st.success(msg)
                                st.rerun() # VYNUCENÝ RERUN OKAMŽITĚ
                            else:
                                st.error(msg)
                else:
                    c_info2.error(f"Chybí: {total_est - zustatek:,.2f} {menu}")
                    st.button("🚫 Nedostatek prostředků", disabled=True, use_container_width=True, key="btn_disabled_funds")
            else:
                st.button("Zadej množství", disabled=True, use_container_width=True, key="btn_disabled_qty")

        else: # PRODEJ
            if total_est > 0:
                curr_qty = df[df['Ticker'] == ticker_input]['Pocet'].sum() if not df.empty else 0
                c_info1, c_info2 = st.columns(2)
                c_info1.info(f"Příjem: **{total_est:,.2f} {menu}**")
                
                if curr_qty >= qty:
                    c_info2.success(f"Máš: {curr_qty} ks")
                    
                    # TLAČÍTKO PRODEJE
                    if st.button(f"PRODAT {qty}x {ticker_input}", type="primary", use_container_width=True, key=f"btn_sell_{key_suffix}"):
                        res = proved_prodej_fn(ticker_input, qty, limit_price, USER, menu)
                        
                        # Zpracování výsledku a restart
                        if res and isinstance(res, tuple):
                            ok, msg = res
                            if ok:
                                st.success(msg)
                                st.rerun() # VYNUCENÝ RERUN
                            else:
                                st.error(msg)
                else:
                    c_info2.error(f"Máš jen: {curr_qty} ks")
                    st.button("🚫 Nedostatek akcií", disabled=True, use_container_width=True, key="btn_disabled_stock")
            else:
                st.button("Zadej množství", disabled=True, use_container_width=True, key="btn_disabled_qty_sell")

    # --- 2. SEKCE PRO SPRÁVU PENĚZ ---
    st.write("")
    c_ex1, c_ex2 = st.columns(2)
    
    # SMĚNÁRNA 
    with c_ex1:
        with st.expander("💱 SMĚNÁRNA", expanded=False):
            am = st.number_input("Částka", 0.0, step=100.0, key="exch_amt")
            fr = st.selectbox("Z", ["CZK", "USD", "EUR"], key="exch_fr")
            to = st.selectbox("Do", ["USD", "CZK", "EUR"], key="exch_to")
            
            if st.button("💱 Směnit", use_container_width=True, key="btn_exch"):
                if zustatky.get(fr, 0) >= am and am > 0:
                    res = proved_smenu_fn(am, fr, to, USER)
                    if res and isinstance(res, tuple):
                        ok, msg = res
                        if ok:
                            st.success("Směna OK")
                            st.rerun()
                        else:
                            st.error(msg)
                elif am <= 0:
                    st.warning("Zadej částku.")
                else:
                    st.error("Chybí prostředky")

    # MANUÁLNÍ VKLAD
    with c_ex2:
        with st.expander("💰 VKLAD & VÝBĚR (Peněženka)", expanded=False):
            st.info("Manuální úprava hotovosti.")
            op = st.radio("Akce", ["Vklad", "Výběr"], horizontal=True, label_visibility="collapsed", key="man_op")
            v_a = st.number_input("Částka", 0.0, step=500.0, key="man_amt")
            v_m = st.selectbox("Měna", ["CZK", "USD", "EUR"], key="man_curr")
            
            if st.button(f"Provést {op}", use_container_width=True, key="btn_man_exec"):
                sign = 1 if op == "Vklad" else -1
                if op == "Výběr" and zustatky.get(v_m, 0) < v_a:
                    st.error("Nedostatek prostředků")
                elif v_a <= 0:
                    st.warning("Zadej částku vyšší než 0")
                else:
                    # Lokální aktualizace
                    df_cash_new = pohyb_penez_fn(v_a * sign, v_m, op, "Manual", USER, df_cash)
                    st.session_state['df_cash'] = df_cash_new
                    invalidate_data_core_fn()
                    
                    # Uložení
                    from data_manager import SOUBOR_CASH, uloz_data_uzivatele
                    uloz_data_uzivatele(df_cash_new, USER, SOUBOR_CASH)
                    
                    st.success("Hotovo")
                    st.rerun()
