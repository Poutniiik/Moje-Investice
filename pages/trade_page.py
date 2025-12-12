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
    """
    Vykreslí stránku "💸 Obchodní Pult"
    """
    st.title("💸 OBCHODNÍ PULT")
    
    # --- 1. HLAVNÍ OBCHODNÍ KARTA ---
    with st.container(border=True):
        # Generujeme unikátní suffix pro klíče na základě délky portfolia.
        # Jakmile se provede obchod (změní se počet řádků df), klíče se změní a widgety se resetují.
        # To zabrání "zaseknutí" stavu tlačítek.
        state_id = len(df) if not df.empty else 0
        
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, label_visibility="collapsed", key=f"trade_mode_radio_{state_id}")
        st.divider()
        
        c1, c2 = st.columns([1, 1])
        with c1:
            if mode == "🔴 PRODEJ" and not df.empty:
                ticker_input = st.selectbox("Ticker", df['Ticker'].unique(), key=f"ticker_select_sell_{state_id}")
            else:
                # Použijeme state_id v klíči, aby se input "vyčistil" nebo refreshnul po transakci
                ticker_input = st.text_input("Ticker", placeholder="např. AAPL, CEZ.PR", key=f"ticker_input_buy_{state_id}").upper()
        
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
        
        # Klíč závislý na tickeru a stavu portfolia
        widget_key_suffix = f"{ticker_input}_{mode}_{state_id}"
        
        with col_qty:
            qty = st.number_input("Počet kusů", min_value=0.0, step=1.0, format="%.2f", key=f"qty_{widget_key_suffix}")
        with col_price:
            limit_price = st.number_input("Cena za kus", min_value=0.0, value=float(current_price) if current_price else 0.0, step=0.1, key=f"price_{widget_key_suffix}")

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
                    
                    if st.button(f"KOUPIT {qty}x {ticker_input}", type="primary", use_container_width=True, key=f"btn_buy_{widget_key_suffix}"):
                        with st.spinner("⏳ Provádím nákup a ukládám na GitHub..."):
                            res = proved_nakup_fn(ticker_input, qty, limit_price, USER)
                            # Pokud funkce vrátí výsledek (místo rerunu), zpracujeme ho
                            if res and isinstance(res, tuple):
                                ok, msg = res
                                if not ok: st.error(msg)
                else:
                    c_info2.error(f"Chybí: {total_est - zustatek:,.2f} {menu}")
                    st.button("🚫 Nedostatek prostředků", disabled=True, use_container_width=True, key=f"btn_no_funds_{state_id}")
            else:
                st.button("Zadej množství", disabled=True, use_container_width=True, key=f"btn_enter_qty_{state_id}")

        else: # PRODEJ
            if total_est > 0:
                curr_qty = df[df['Ticker'] == ticker_input]['Pocet'].sum() if not df.empty else 0
                c_info1, c_info2 = st.columns(2)
                c_info1.info(f"Příjem: **{total_est:,.2f} {menu}**")
                
                if curr_qty >= qty:
                    c_info2.success(f"Máš: {curr_qty} ks")
                    if st.button(f"PRODAT {qty}x {ticker_input}", type="primary", use_container_width=True, key=f"btn_sell_{widget_key_suffix}"):
                        with st.spinner("⏳ Provádím prodej a ukládám na GitHub..."):
                            res = proved_prodej_fn(ticker_input, qty, limit_price, USER, menu)
                            if res and isinstance(res, tuple):
                                ok, msg = res
                                if not ok: st.error(msg)
                else:
                    c_info2.error(f"Máš jen: {curr_qty} ks")
                    st.button("🚫 Nedostatek akcií", disabled=True, use_container_width=True, key=f"btn_no_stock_{state_id}")
            else:
                st.button("Zadej množství", disabled=True, use_container_width=True, key=f"btn_enter_qty_sell_{state_id}")

    # --- 2. SEKCE PRO SPRÁVU PENĚZ ---
    st.write("")
    c_ex1, c_ex2 = st.columns(2)
    
    # SMĚNÁRNA 
    with c_ex1:
        with st.expander("💱 SMĚNÁRNA", expanded=False):
            am = st.number_input("Částka", 0.0, step=100.0, key=f"exchange_amount_{state_id}")
            fr = st.selectbox("Z", ["CZK", "USD", "EUR"], key=f"s_z_{state_id}")
            to = st.selectbox("Do", ["USD", "CZK", "EUR"], key=f"s_do_{state_id}")
            
            if st.button("💱 Směnit", use_container_width=True, key=f"btn_exchange_{state_id}"):
                if zustatky.get(fr, 0) >= am and am > 0:
                    with st.spinner("💱 Provádím směnu..."):
                        res = proved_smenu_fn(am, fr, to, USER)
                        if res and isinstance(res, tuple):
                            ok, msg = res
                            if not ok: st.error(msg)
                elif am <= 0:
                    st.warning("Zadej částku.")
                else:
                    st.error("Chybí prostředky")

    # MANUÁLNÍ VKLAD (Zůstává zde, protože nepoužívá global funkci)
    with c_ex2:
        with st.expander("💰 VKLAD & VÝBĚR (Peněženka)", expanded=False):
            st.info("Zde si můžeš ručně dobít nebo vybrat virtuální hotovost.")
            op = st.radio("Akce", ["Vklad", "Výběr"], horizontal=True, label_visibility="collapsed", key=f"manual_op_{state_id}")
            v_a = st.number_input("Částka", 0.0, step=500.0, key=f"manual_amount_{state_id}")
            v_m = st.selectbox("Měna", ["CZK", "USD", "EUR"], key=f"manual_currency_{state_id}")
            
            if st.button(f"Provést {op}", use_container_width=True, key=f"btn_manual_exec_{state_id}"):
                sign = 1 if op == "Vklad" else -1
                if op == "Výběr" and zustatky.get(v_m, 0) < v_a:
                    st.error("Nedostatek prostředků")
                elif v_a <= 0:
                    st.warning("Zadej částku vyšší než 0")
                else:
                    # Zde používáme "optimistickou aktualizaci" lokálně
                    with st.spinner("💾 Ukládám transakci..."):
                        df_cash_new = pohyb_penez_fn(v_a * sign, v_m, op, "Manual", USER, df_cash)
                        
                        # 1. Aktualizace paměti
                        st.session_state['df_cash'] = df_cash_new
                        invalidate_data_core_fn()
                        
                        # 2. Uložení (importujeme lokálně, aby to nebylo závislé na vnějšku)
                        from data_manager import SOUBOR_CASH, uloz_data_uzivatele
                        uloz_data_uzivatele(df_cash_new, USER, SOUBOR_CASH)
                        
                        # 3. Restart
                        st.success("Hotovo")
                        time.sleep(1)
                        st.rerun()
