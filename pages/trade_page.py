# =========================================================================
# SOUBOR: pages/trade_page.py (Verze: Callback Stable Fix)
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
    
    # 1. Inicializace počítadla transakcí (State)
    if 'tx_counter' not in st.session_state:
        st.session_state['tx_counter'] = 0
        
    tx_id = st.session_state['tx_counter']

    # --- CALLBACK FUNKCE (Spouští se PŘED překreslením stránky) ---
    # Tyto funkce se zavolají, když uživatel klikne na tlačítko.
    # Zajistí provedení obchodu a OKAMŽITOU inkrementaci počítadla.

    def callback_nakup(ticker, qty, limit):
        # 1. Volání logiky obchodu
        ok, msg = proved_nakup_fn(ticker, qty, limit, USER)
        if ok:
            # 2. Inkrementace = Reset formuláře pro příště
            st.session_state['tx_counter'] += 1
            # 3. Invalidace dat
            if invalidate_data_core_fn: invalidate_data_core_fn()
        else:
            # Pokud chyba, uložíme si zprávu do session state, abychom ji zobrazili
            st.session_state['trade_error'] = msg

    def callback_prodej(ticker, qty, limit, curr):
        ok, msg = proved_prodej_fn(ticker, qty, limit, USER, curr)
        if ok:
            st.session_state['tx_counter'] += 1
            if invalidate_data_core_fn: invalidate_data_core_fn()
        else:
            st.session_state['trade_error'] = msg

    def callback_smena(amt, fr, to):
        res = proved_smenu_fn(amt, fr, to, USER)
        # Ošetření návratu (funkce vrací tuple nebo bool?)
        if isinstance(res, tuple): ok, msg = res
        else: ok, msg = res, "Info"
        
        if ok:
            st.session_state['tx_counter'] += 1
            if invalidate_data_core_fn: invalidate_data_core_fn()
        else:
            st.session_state['trade_error'] = msg

    def callback_vklad(amt, cur, op):
        sign = 1 if op == "Vklad" else -1
        # Tady musíme volat přímo, funkce vklad/vyber vrací DF
        # Ale pozor: nemůžeme měnit df_cash přímo v callbacku bez vrácení
        # Proto zde uděláme logiku přímo v callbacku
        
        # Toto je trochu hack, protože pohyb_penez_fn vrací nový DF.
        # Pro čistotu to uděláme v hlavním těle, ale reset counteru zde.
        pass # Vklad necháme postaru, ten fungoval, nebo ho přepíšeme níže


    # --- ZOBRAZENÍ CHYB Z CALLBACKU ---
    if 'trade_error' in st.session_state and st.session_state['trade_error']:
        st.error(st.session_state['trade_error'])
        st.session_state['trade_error'] = None # Vymazat po zobrazení


    # --- UI ---
    with st.container(border=True):
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, label_visibility="collapsed", key="mode_selection")
        st.divider()
        
        c1, c2 = st.columns([1, 1])
        with c1:
            # Používáme statický klíč pro výběr (aby se neměnil při psaní),
            # ale hodnotu můžeme resetovat v session_state, pokud chceme.
            # Zde necháme inputy, ať si žijí, resetuje je až tx_counter v jejich klíči.
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
            # Klíče obsahují tx_id -> po změně counteru se vytvoří nové inputy (čisté)
            qty = st.number_input("Kusy", min_value=0.0, step=1.0, key=f"qty_{tx_id}")
        with c_p: 
            limit = st.number_input("Cena/ks", value=float(price), key=f"lim_{tx_id}")
        
        total = qty * limit
        balance = zustatky.get(curr, 0)
        
        st.info(f"Celkem: {total:,.2f} {curr} | Máš: {balance:,.2f} {curr}")
        
        # --- TLAČÍTKA (S POUŽITÍM CALLBACKŮ) ---
        if mode == "🟢 NÁKUP":
            btn_disabled = False
            if total <= 0: btn_disabled = True
            
            # Tlačítko nyní volá 'on_click' místo aby vracelo True/False
            st.button(
                f"KOUPIT {ticker_input}", 
                type="primary", 
                use_container_width=True, 
                key=f"btn_buy_{tx_id}",
                disabled=btn_disabled,
                on_click=callback_nakup,
                args=(ticker_input, qty, limit) # Předáme aktuální hodnoty do callbacku
            )
            
            if total > 0 and balance < total:
                st.warning(f"⚠️ Pozor: Nedostatek prostředků (Chybí {total-balance:,.2f})")

        else: # PRODEJ
            held = df[df['Ticker']==ticker_input]['Pocet'].sum() if not df.empty else 0
            st.caption(f"Držíš: {held} ks")
            
            btn_sell_disabled = False
            if total <= 0 or held < qty: btn_sell_disabled = True
            
            st.button(
                f"PRODAT {ticker_input}", 
                type="primary", 
                use_container_width=True, 
                key=f"btn_sell_{tx_id}",
                disabled=btn_sell_disabled,
                on_click=callback_prodej,
                args=(ticker_input, qty, limit, curr)
            )

    # --- 2. SEKCE PRO SPRÁVU PENĚZ ---
    st.write("")
    c_ex1, c_ex2 = st.columns(2)
    
    # SMĚNÁRNA 
    with c_ex1:
        with st.expander("💱 SMĚNÁRNA", expanded=False):
            am = st.number_input("Částka", 0.0, step=100.0, key=f"exch_amt_{tx_id}")
            fr = st.selectbox("Z", ["CZK", "USD", "EUR"], key=f"exch_fr_{tx_id}")
            to = st.selectbox("Do", ["USD", "CZK", "EUR"], key=f"exch_to_{tx_id}")
            
            st.button(
                "💱 Směnit", 
                use_container_width=True, 
                key=f"btn_exch_{tx_id}",
                on_click=callback_smena,
                args=(am, fr, to)
            )

    # MANUÁLNÍ VKLAD (Zde necháme starší logiku, pokud fungovala, nebo mírně upravíme)
    with st.expander("💰 PENĚŽENKA (Vklad/Výběr)"):
        m_op = st.radio("Akce", ["Vklad", "Výběr"], horizontal=True, key=f"m_op_{tx_id}")
        m_amt = st.number_input("Částka", 0.0, step=500.0, key=f"m_amt_{tx_id}")
        m_cur = st.selectbox("Měna", ["CZK", "USD", "EUR"], key=f"m_cur_{tx_id}")
        
        # Zde použijeme přímou logiku, protože funkce 'pohyb_penez_fn' vrací DataFrame
        # a to se hůře cpe do callbacku bez přístupu ke globálním proměnným.
        if st.button("Provést", key=f"m_btn_{tx_id}"):
            sign = 1 if m_op == "Vklad" else -1
            df_new = pohyb_penez_fn(m_amt * sign, m_cur, m_op, "Manual", USER, df_cash)
            
            # Manuální update Session State
            st.session_state['df_cash'] = df_new
            # Uložení (musíme importovat konstanty, pokud nejsou v kontextu, 
            # ale 'uloz_data_uzivatele' není v args... moment, data_manager import)
            
            # Hack: uložíme to přes session state a rerun to vyřeší v main() nebo zde
            from data_manager import SOUBOR_CASH, uloz_data_uzivatele
            uloz_data_uzivatele(df_new, USER, SOUBOR_CASH)
            
            st.session_state['tx_counter'] += 1
            if invalidate_data_core_fn: invalidate_data_core_fn()
            st.success("Hotovo")
            st.rerun()
