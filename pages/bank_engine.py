# =========================================================================
# SOUBOR: pages/bank_page.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "🧪 Banka"
# =========================================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import requests
import io
import zipfile
from datetime import datetime

# Imports z root modulů - klíčové závislosti
from .. import utils
from .. import bank_engine


# --- HLAVNÍ FUNKCE STRÁNKY ---
def bank_page():
    """
    Vykreslí stránku '🧪 Banka' (Původní render_bank_lab_page)
    """
    st.title("🏦 BANKOVNÍ CENTRÁLA (Verze 3.1)")
    st.caption("Automatické propojení s bankovním účtem (Transakce + Zůstatky).")

    # 1. PŘIPOJENÍ (Pokud nemáme token)
    if 'bank_token' not in st.session_state:
        st.info("Zatím není připojena žádná banka.")
        
        if st.button("🔌 PŘIPOJIT BANKU (Sandbox)", type="primary"):
            with st.spinner("Volám bankovní motor..."):
                token = bank_engine.simulace_pripojeni()
                
                if "Chyba" in str(token):
                    st.error(token)
                else:
                    st.session_state['bank_token'] = token
                    st.balloons()
                    st.success("✅ Banka úspěšně připojena! Token uložen.")
                    time.sleep(1)
                    st.rerun()
    
    # 2. PRÁCE S DATY (Když už jsme připojeni)
    else:
        c1, c2 = st.columns([3, 1])
        with c1: st.success("🟢 Spojení aktivní: Test Bank (Sandbox)")
        with c2: 
            if st.button("Odpojit"):
                del st.session_state['bank_token']
                if 'bank_data' in st.session_state: del st.session_state['bank_data']
                if 'bank_balance' in st.session_state: del st.session_state['bank_balance']
                st.rerun()

        st.divider()
        
        # --- OVLÁDACÍ PANEL (Dvě tlačítka vedle sebe) ---
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("💰 ZOBRAZIT ZŮSTATKY", use_container_width=True):
                with st.spinner("Ptám se banky na stav konta..."):
                    df_bal = bank_engine.stahni_zustatky(st.session_state['bank_token'])
                    if df_bal is not None:
                        st.session_state['bank_balance'] = df_bal
                    else:
                        st.error("Chyba při stahování zůstatků.")

        with col_btn2:
            if st.button("📥 STÁHNOUT TRANSAKCE", use_container_width=True):
                with st.spinner("Stahuji výpis..."):
                    df_trans = bank_engine.stahni_data(st.session_state['bank_token'])
                    if df_trans is not None:
                        st.session_state['bank_data'] = df_trans
                    else:
                        st.error("Chyba při stahování transakcí.")

        # --- SEKCE 1: ZŮSTATKY (Nové!) ---
        if 'bank_balance' in st.session_state:
            st.write("")
            st.subheader("💳 Aktuální stav účtů")
            df_b = st.session_state['bank_balance']
            
            # Vykreslíme jako kartičky vedle sebe
            cols = st.columns(len(df_b))
            for index, row in df_b.iterrows():
                col_idx = index % len(cols)
                with cols[col_idx]:
                    st.metric(
                        label=row['Název účtu'], 
                        value=f"{row['Zůstatek']:,.2f} {row['Měna']}", 
                        delta="Aktuální"
                    )
            st.divider()

        # --- SEKCE 2: TRANSAKCE ---
        if 'bank_data' in st.session_state:
            df_t = st.session_state['bank_data']
            
            # Cashflow (Příjmy vs Výdaje za stažené období)
            total_spend = df_t[df_t['Částka'] < 0]['Částka'].sum()
            total_income = df_t[df_t['Částka'] > 0]['Částka'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Příjmy (90 dní)", f"{total_income:,.0f}")
            m2.metric("Výdaje (90 dní)", f"{total_spend:,.0f}")
            m3.metric("Cashflow", f"{total_income + total_spend:,.0f}")
            
            st.subheader("📜 Historie transakcí")
            st.dataframe(
                df_t, 
                column_config={
                    "Částka": st.column_config.NumberColumn("Částka", format="%.2f"),
                    "Kategorie": st.column_config.TextColumn("Druh"),
                },
                use_container_width=True
            )
            
            # Graf výdajů
            st.subheader("📊 Analýza výdajů")
            expenses = df_t[df_t['Částka'] < 0].copy()
            expenses['Částka'] = expenses['Částka'].abs() 
            
            if not expenses.empty:
                fig_exp = px.pie(expenses, values='Částka', names='Kategorie', hole=0.4, template="plotly_dark")
                st.plotly_chart(fig_exp, use_container_width=True)
