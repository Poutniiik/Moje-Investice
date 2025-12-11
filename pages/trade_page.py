# =========================================================================
# SOUBOR: pages/trade_page.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "💸 Obchod"
# OPRAVA: Fix cesty pro import bank_engine
# =========================================================================
import streamlit as st
import pandas as pd
import time
import numpy as np

# --- BEZPEČNOSTNÍ FIX PRO NAČTENÍ SOUBORŮ Z KOŘENOVÉ SLOŽKY ---
import sys
import os
# Přidáme kořenovou složku do cesty, aby Python našel bank_engine.py
# Toto je nutné, protože Streamlit v podsložkách nevidí kořenové soubory.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 
# --- KONEC FIXU ---

# Imports z root modulů
from .. import utils 
from .. import bank_engine
# ... zbytek souboru


# --- HLAVNÍ FUNKCE STRÁNKY ---
def trade_page(USER, df, df_cash, zustatky, LIVE_DATA, kurzy, 
               proved_nakup_fn, proved_prodej_fn, proved_smenu_fn, 
               pohyb_penez_fn, invalidate_data_core_fn):
    """
    Vykreslí stránku "💸 Obchodní Pult"
    """
    st.title("💸 OBCHODNÍ PULT")
    
    # --- 1. HLAVNÍ OBCHODNÍ KARTA (VELÍN) ---
    with st.container(border=True):
        # Přepínač režimu
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, label_visibility="collapsed")
        
        st.divider()
        
        # Vstupy pro Ticker a Live Cenu
        c1, c2 = st.columns([1, 1])
        with c1:
            # Ticker selector logic
            if mode == "🔴 PRODEJ" and not df.empty:
                ticker_input = st.selectbox("Ticker", df['Ticker'].unique())
            else:
                ticker_input = st.text_input("Ticker", placeholder="např. AAPL, CEZ.PR").upper()
        
        # Live Data Fetch
        current_price, menu, denni_zmena = 0, "USD", 0
        if ticker_input:
            info = LIVE_DATA.get(ticker_input)
            if info:
                current_price = info.get('price', 0)
                menu = info.get('curr', 'USD')
            else:
                # Voláme utilitní funkci, která není cachována a vrací live data
                p, m, z = utils.ziskej_info(ticker_input)
                if p: current_price, menu, denni_zmena = p, m, z

            if current_price > 0:
                with c2:
                    color_price = "green" if denni_zmena >= 0 else "red"
                    st.markdown(f"**Cena:** :{color_price}[{current_price:,.2f} {menu}]")
                    st.caption(f"Změna: {denni_zmena*100:+.2f}%")
            else:
                with c2: st.warning("Cena nedostupná")

        # Množství a Limitní Cena
        st.write("")
        col_qty, col_price = st.columns(2)
        with col_qty:
            qty = st.number_input("Počet kusů", min_value=0.0, step=1.0, format="%.2f")
        with col_price:
            limit_price = st.number_input("Cena za kus", min_value=0.0, value=float(current_price) if current_price else 0.0, step=0.1)

        # Kalkulace celkem
        total_est = qty * limit_price
        zustatek = zustatky.get(menu, 0)
        
        st.write("") 
        
        # --- LOGIKA TLAČÍTKA A VALIDACE ---
        if mode == "🟢 NÁKUP":
            if total_est > 0:
                c_info1, c_info2 = st.columns(2)
                c_info1.info(f"Celkem: **{total_est:,.2f} {menu}**")
                
                if zustatek >= total_est:
                    c_info2.success(f"Na účtu: {zustatek:,.2f} {menu}")
                    if st.button(f"KOUPIT {qty}x {ticker_input}", type="primary", use_container_width=True):
                        # VOLÁNÍ PŘEDANÉ FUNKCE
                        ok, msg = proved_nakup_fn(ticker_input, qty, limit_price, USER)
                        if ok: st.balloons(); st.success(msg); time.sleep(2); st.rerun()
                        else: st.error(msg)
                else:
                    c_info2.error(f"Chybí: {total_est - zustatek:,.2f} {menu}")
                    st.button("🚫 Nedostatek prostředků", disabled=True, use_container_width=True)
            else:
                st.button("Zadej množství", disabled=True, use_container_width=True)

        else: # PRODEJ
            if total_est > 0:
                curr_qty = df[df['Ticker'] == ticker_input]['Pocet'].sum() if not df.empty else 0
                
                c_info1, c_info2 = st.columns(2)
                c_info1.info(f"Příjem: **{total_est:,.2f} {menu}**")
                
                if curr_qty >= qty:
                    c_info2.success(f"Máš: {curr_qty} ks")
                    if st.button(f"PRODAT {qty}x {ticker_input}", type="primary", use_container_width=True):
                        # VOLÁNÍ PŘEDANÉ FUNKCE
                        ok, msg = proved_prodej_fn(ticker_input, qty, limit_price, USER, menu)
                        if ok: st.success(msg); time.sleep(2); st.rerun()
                        else: st.error(msg)
                else:
                    c_info2.error(f"Máš jen: {curr_qty} ks")
                    st.button("🚫 Nedostatek akcií", disabled=True, use_container_width=True)
            else:
                st.button("Zadej množství", disabled=True, use_container_width=True)

    # --- 2. SEKCE PRO SPRÁVU PENĚZ ---
    st.write("")
    c_ex1, c_ex2 = st.columns(2)
    
    # LEVÝ SLOUPEC: SMĚNÁRNA 
    with c_ex1:
        with st.expander("💱 SMĚNÁRNA", expanded=False):
            am = st.number_input("Částka", 0.0, step=100.0)
            fr = st.selectbox("Z", ["CZK", "USD", "EUR"], key="s_z")
            to = st.selectbox("Do", ["USD", "CZK", "EUR"], key="s_do")
            
            if st.button("💱 Směnit", use_container_width=True):
                if zustatky.get(fr, 0) >= am:
                    # VOLÁNÍ PŘEDANÉ FUNKCE
                    ok, msg = proved_smenu_fn(am, fr, to, USER)
                    if ok:
                        st.success("Hotovo"); time.sleep(1); st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Chybí prostředky")

    # PRAVÝ SLOUPEC: BANKA + MANUÁLNÍ VKLAD 
    with c_ex2:
        with st.expander("🏧 BANKA & BANKOMAT", expanded=False):
            
            # A) BANKOVNÍ PROPOJENÍ
            st.caption("🌐 Moje Banka (Plaid API)")
            if st.button("🔄 Synchronizovat zůstatky", key="sync_bank", use_container_width=True):
                with st.spinner("Šifrované spojení..."):
                    # bank_engine je importován a volán přímo
                    t_msg = bank_engine.simulace_pripojeni() 
                    if "Chyba" in t_msg: st.error(t_msg)
                    else:
                        df_b = bank_engine.stahni_zustatky(t_msg)
                        if df_b is not None:
                            st.session_state['bank_data'] = df_b
                            st.toast("Data z banky stažena!", icon="✅")
                        else: st.warning("Žádná data.")
            
            # Zobrazení dat z banky, pokud jsou načtena
            if 'bank_data' in st.session_state:
                st.dataframe(st.session_state['bank_data'], use_container_width=True, hide_index=True)
                celkem_banka = st.session_state['bank_data']['Zůstatek'].sum()
                mena_banka = st.session_state['bank_data'].iloc[0]['Měna']
                st.caption(f"Disponibilní v bance: **{celkem_banka:,.2f} {mena_banka}**")

            st.divider()

            # B) MANUÁLNÍ VKLAD/VÝBĚR 
            st.caption("📝 Manuální operace")
            op = st.radio("Akce", ["Vklad", "Výběr"], horizontal=True, label_visibility="collapsed")
            v_a = st.number_input("Částka", 0.0, step=500.0, key="v_a")
            v_m = st.selectbox("Měna", ["CZK", "USD", "EUR"], key="v_m")
            
            if st.button(f"Provést {op}", use_container_width=True):
                    sign = 1 if op == "Vklad" else -1
                    if op == "Výběr" and zustatky.get(v_m, 0) < v_a:
                        st.error("Nedostatek prostředků")
                    else:
                        # 1. Lokální úprava DF
                        df_cash_new = pohyb_penez_fn(v_a * sign, v_m, op, "Manual", USER, df_cash.copy())
                        
                        # 2. Uložení (Tato logika patří do main, ale musíme ji provést)
                        # Budeme simulovat uložení přímo zde pro jednoduchost (je nutné importovat data_manager)
                        import data_manager # Přidej tento import do pages/trade_page.py nahoře!
                        data_manager.uloz_data_uzivatele(df_cash_new, USER, data_manager.SOUBOR_CASH)

                        # 3. Aktualizace stavu a rerunu
                        st.session_state['df_cash'] = df_cash_new
                        invalidate_data_core_fn()
                        st.success("Hotovo"); time.sleep(1); st.rerun()

    # Historie transakcí
    if not df_cash.empty:
        st.divider()
        st.caption("Poslední pohyby na účtu")
        st.dataframe(df_cash.sort_values('Datum', ascending=False).head(3), use_container_width=True, hide_index=True)
