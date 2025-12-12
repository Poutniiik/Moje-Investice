# =========================================================================
# SOUBOR: pages/trade_page.py
# =========================================================================
import streamlit as st
import pandas as pd
import time
import numpy as np
import utils

def trade_page(USER, df, df_cash, zustatky, LIVE_DATA, kurzy, 
               proved_nakup_fn, proved_prodej_fn, proved_smenu_fn, 
               pohyb_penez_fn, invalidate_data_core_fn):
    
    st.title("💸 OBCHODNÍ PULT")
    
    # 1. Získání ID transakce (Pokud neexistuje, založíme ho)
    if 'tx_counter' not in st.session_state:
        st.session_state['tx_counter'] = 0
        
    tx_id = st.session_state['tx_counter']
    
    with st.container(border=True):
        # Používáme tx_id v klíči, aby se při nové transakci resetoval i výběr režimu, 
        # nebo můžeme nechat statický klíč, pokud chceme zachovat volbu. 
        # Zde nechávám statický pro plynulost, dynamické jsou inputy dole.
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, label_visibility="collapsed", key="mode_selection")
        st.divider()
        
        c1, c2 = st.columns([1, 1])
        with c1:
            # Dynamické klíče (f"..._{tx_id}") zajistí vyčištění pole po transakci
            if mode == "🔴 PRODEJ" and not df.empty:
                ticker_input = st.selectbox("Ticker", df['Ticker'].unique(), key=f"sel_{tx_id}")
            else:
                ticker_input = st.text_input("Ticker", placeholder="např. AAPL", key=f"inp_{tx_id}").upper()
        
        # Live Cena
        price, curr = 0, "USD"
        if ticker_input:
            info = LIVE_DATA.get(ticker_input, {})
            price = info.get('price', 0)
            curr = info.get('curr', 'USD')
            if price == 0:
                p, m, _ = utils.ziskej_info(ticker_input)
                if p: price, curr = p, m
        
        if price > 0:
            with c2: st.markdown(f"**Cena:** {price:,.2f} {curr}")
        
        c_q, c_p = st.columns(2)
        with c_q: 
            qty = st.number_input("Kusy", min_value=0.0, step=1.0, key=f"qty_{tx_id}")
        with c_p: 
            limit = st.number_input("Cena/ks", value=float(price), key=f"lim_{tx_id}")
        
        total = qty * limit
        balance = zustatky.get(curr, 0)
        
        st.info(f"Celkem: {total:,.2f} {curr} | Máš: {balance:,.2f} {curr}")
        
        # --- LOGIKA TLAČÍTEK S FIXEM PRO REFRESH ---
        if mode == "🟢 NÁKUP":
            if total > 0 and balance >= total:
                if st.button(f"KOUPIT {ticker_input}", type="primary", use_container_width=True, key=f"btn_buy_{tx_id}"):
                    # 1. Volání funkce (předpokládáme, že funkce vrátí výsledek a neudělá hned rerun)
                    proved_nakup_fn(ticker_input, qty, limit, USER)
                    
                    # 2. Inkrementace counteru = RESET FORMULÁŘE
                    st.session_state['tx_counter'] += 1
                    
                    # 3. Invalidace dat (načtení nových zůstatků)
                    if invalidate_data_core_fn:
                        invalidate_data_core_fn()
                        
                    # 4. Rerun pro update UI
                    st.success(f"Koupeno {qty} ks {ticker_input}")
                    time.sleep(0.5) # Malá pauza pro efekt
                    st.rerun()
                    
            elif total > 0:
                st.error("Nedostatek prostředků")
                
        else: # PRODEJ
            held = df[df['Ticker']==ticker_input]['Pocet'].sum() if not df.empty else 0
            st.caption(f"Držíš: {held} ks")
            if total > 0 and held >= qty:
                if st.button(f"PRODAT {ticker_input}", type="primary", use_container_width=True, key=f"btn_sell_{tx_id}"):
                    proved_prodej_fn(ticker_input, qty, limit, USER, curr)
                    
                    # STEJNÁ LOGIKA JAKO U NÁKUPU
                    st.session_state['tx_counter'] += 1
                    
                    if invalidate_data_core_fn:
                        invalidate_data_core_fn()
                        
                    st.success(f"Prodáno {qty} ks {ticker_input}")
                    time.sleep(0.5)
                    st.rerun()
                    
            elif total > 0:
                st.error("Nedostatek akcií")
            else:
                st.button("Zadej množství", disabled=True, use_container_width=True, key="btn_disabled_qty_sell")

    # --- 2. SEKCE PRO SPRÁVU PENĚZ ---
    st.write("")
    c_ex1, c_ex2 = st.columns(2)
    
    # SMĚNÁRNA 
    with c_ex1:
        with st.expander("💱 SMĚNÁRNA", expanded=False):
            # I zde přidáme tx_id pro jistotu, aby se inputy čistily
            am = st.number_input("Částka", 0.0, step=100.0, key=f"exch_amt_{tx_id}")
            fr = st.selectbox("Z", ["CZK", "USD", "EUR"], key=f"exch_fr_{tx_id}")
            to = st.selectbox("Do", ["USD", "CZK", "EUR"], key=f"exch_to_{tx_id}")
            
            if st.button("💱 Směnit", use_container_width=True, key=f"btn_exch_{tx_id}"):
                if zustatky.get(fr, 0) >= am and am > 0:
                    res = proved_smenu_fn(am, fr, to, USER)
                    # Ošetření návratové hodnoty
                    if res and isinstance(res, tuple):
                        ok, msg = res
                    else:
                        ok, msg = True, "Provedeno" # Fallback
                        
                    if ok:
                        st.session_state['tx_counter'] += 1
                        if invalidate_data_core_fn: invalidate_data_core_fn()
                        st.success("Směna OK")
                        st.rerun()
                    else:
                        st.error(msg)
                elif am <= 0:
                    st.warning("Zadej částku.")
                else:
                    st.error("Chybí prostředky")

    # MANUÁLNÍ VKLAD
    with st.expander("💰 PENĚŽENKA (Vklad/Výběr)"):
        m_op = st.radio("Akce", ["Vklad", "Výběr"], horizontal=True, key=f"m_op_{tx_id}")
        m_amt = st.number_input("Částka", 0.0, step=500.0, key=f"m_amt_{tx_id}")
        m_cur = st.selectbox("Měna", ["CZK", "USD", "EUR"], key=f"m_cur_{tx_id}")
        
        if st.button("Provést", key=f"m_btn_{tx_id}"):
            sign = 1 if m_op == "Vklad" else -1
            df_new = pohyb_penez_fn(m_amt * sign, m_cur, m_op, "Manual", USER, df_cash)
            
            # Manuální update
            st.session_state['df_cash'] = df_new
            from data_manager import SOUBOR_CASH, uloz_data_uzivatele
            uloz_data_uzivatele(df_new, USER, SOUBOR_CASH)
            
            # Inkrementace counteru a rerun
            st.session_state['tx_counter'] += 1
            if invalidate_data_core_fn: invalidate_data_core_fn()
            st.rerun()
