import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import make_plotly_cyberpunk, ziskej_earnings_datum, ziskej_detail_akcie, cached_fear_greed, make_matplotlib_cyberpunk
from core import proved_nakup, proved_prodej, proved_pohyb_penez, pridat_dividendu
import time
import bank_engine

# --- DASHBOARD ---
def render_prehled_page(USER, core, AI_AVAILABLE, model):
    """Dashboard stránka."""
    vdf = core['vdf']
    kurzy = core['kurzy']
    celk_hod_usd = core['celk_hod_usd']
    
    st.title(f"🏠 PŘEHLED: {USER.upper()}")
    
    # Metriky
    k1, k2, k3, k4 = st.columns(4)
    czk_val = celk_hod_usd * kurzy.get('CZK', 21)
    k1.metric("💰 JMĚNÍ (CZK)", f"{czk_val:,.0f} Kč")
    k2.metric("🌎 JMĚNÍ (USD)", f"${celk_hod_usd:,.0f}")
    k3.metric("📈 ZMĚNA 24H", f"{core['pct_24h']:+.2f}%")
    k4.metric("💳 HOTOVOST", f"${core['cash_usd']:,.0f}")
    
    # Grafy (Sektory a Vývoj)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("🌊 VÝVOJ")
        hist = core['hist_vyvoje']
        if not hist.empty:
            fig = px.area(hist, x='Date', y='TotalUSD', template="plotly_dark")
            fig = make_plotly_cyberpunk(fig)
            st.plotly_chart(fig, use_container_width=True)
            
    with c2:
        st.subheader("🏭 SEKTORY")
        if not vdf.empty:
            fig_pie = px.pie(vdf, values='HodnotaUSD', names='Sektor', hole=0.6, template="plotly_dark")
            fig_pie = make_plotly_cyberpunk(fig_pie)
            st.plotly_chart(fig_pie, use_container_width=True)

# --- OBCHODNÍ PULT ---
def render_obchod_page(USER, df, zustatky, LIVE_DATA):
    st.title("💸 OBCHODNÍ PULT")
    
    # 1. Nákup / Prodej
    with st.container(border=True):
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True)
        t = st.text_input("Ticker", "AAPL").upper()
        qty = st.number_input("Počet", 1.0)
        
        price = 0
        if t in LIVE_DATA: price = LIVE_DATA[t]['price']
        
        st.metric("Aktuální cena", f"${price:,.2f}" if price else "N/A")
        
        if st.button("PROVÉST PŘÍKAZ", type="primary"):
            if mode == "🟢 NÁKUP":
                ok, msg = proved_nakup(t, qty, price, USER) # Volání funkce z CORE
            else:
                ok, msg = proved_prodej(t, qty, price, USER, "USD")
                
            if ok: st.success(msg); time.sleep(1); st.rerun()
            else: st.error(msg)
            
    # 2. Banka
    st.divider()
    if st.button("🏦 Zobrazit bankovní data"):
        st.info("Připojuji bankovní API...")
        # Zde volat bank_engine funkce

# --- DIVIDENDY ---
def render_dividendy_page(USER, df_div, kurzy):
    st.title("💎 DIVIDENDY")
    total = df_div['Castka'].sum() if not df_div.empty else 0
    st.metric("Celkem vyplaceno", f"${total:,.2f}")
    
    if not df_div.empty:
        st.dataframe(df_div, use_container_width=True)
        fig = px.bar(df_div, x='Datum', y='Castka', color='Ticker', template='plotly_dark')
        st.plotly_chart(fig, use_container_width=True)

# --- ANALÝZA ---
def render_analyza_page(core, model, AI_AVAILABLE):
    st.title("📈 HLOUBKOVÁ ANALÝZA")
    t1, t2, t3 = st.tabs(["RENTGEN", "SROVNÁNÍ", "KALENDÁŘ"])
    
    with t1:
        st.info("Vyber akcii pro detailní analýzu.")
        # Zde zkopírovat logiku pro Rentgen z původního souboru
        
    with t3:
        st.subheader("📅 Kalendář výsledků")
        # Zde logika pro earnings
