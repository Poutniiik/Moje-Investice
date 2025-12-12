# =========================================================================
# SOUBOR: pages/dashboard.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "🏠 Přehled"
# =========================================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
import random
import numpy as np

import utils 
import ai_brain 

def dashboard_page(USER, celk_hod_czk, celk_hod_usd, celk_inv_usd, cash_usd, zustatky, vdf, df_hist, kurzy, LIVE_DATA, hist_vyvoje):
    """
    Hlavní dashboard stránka.
    Přijímá 'hist_vyvoje' jako argument pro okamžité vykreslení grafu.
    """
    st.title(f"🏠 PŘEHLED KAPITÁNA: {USER}")

    # --- 1. HLAVNÍ METRIKY (KPIs) ---
    # Výpočet celkového zisku
    total_invested_czk = celk_inv_usd * kurzy.get("CZK", 24.50)
    total_profit_czk = celk_hod_czk - total_invested_czk
    total_profit_pct = (total_profit_czk / total_invested_czk * 100) if total_invested_czk > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Celkové jmění (CZK)", f"{celk_hod_czk:,.0f} Kč", delta=f"{total_profit_czk:,.0f} Kč")
    with col2:
        st.metric("Hodnota v USD", f"${celk_hod_usd:,.2f}", delta=f"{total_profit_pct:+.2f} %")
    with col3:
        st.metric("Hotovost (USD)", f"${cash_usd:,.2f}")
    with col4:
        # Fear & Greed (Cached)
        fg_score, fg_rating = utils.cached_fear_greed()
        st.metric("Nálada trhu", f"{fg_score}/100" if fg_score else "N/A", fg_rating)

    st.markdown("---")

    # --- 2. GRAF VÝVOJE MAJETKU (Použití hist_vyvoje) ---
    c_chart, c_pie = st.columns([2, 1])
    
    with c_chart:
        st.subheader("📈 Vývoj hodnoty portfolia")
        if hist_vyvoje is not None and not hist_vyvoje.empty:
            # Konverze data
            hist_plot = hist_vyvoje.copy()
            hist_plot['Date'] = pd.to_datetime(hist_plot['Date'])
            hist_plot = hist_plot.sort_values('Date')
            
            # Vytvoření grafu
            fig_evol = px.area(hist_plot, x='Date', y='TotalUSD', 
                               title="Historie hodnoty (USD)", 
                               line_shape='spline')
            
            # Cyberpunk stylizace
            fig_evol.update_traces(line_color='#00FF99', fillcolor='rgba(0, 255, 153, 0.1)')
            fig_evol = utils.make_plotly_cyberpunk(fig_evol)
            st.plotly_chart(fig_evol, use_container_width=True)
        else:
            st.info("Zatím není dostatek dat pro graf historie.")

    # --- 3. ROZLOŽENÍ AKTIV (Pie Chart) ---
    with c_pie:
        st.subheader("🍰 Rozložení")
        if not vdf.empty:
            # Sloučíme malé pozice do "Ostatní" pro hezčí graf
            df_pie = vdf.copy()
            # Pokud máme Cash, přidáme ho do grafu (volitelné, zde jen akcie)
            
            fig_pie = px.pie(df_pie, values='HodnotaUSD', names='Ticker', hole=0.4)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Portfolio je prázdné.")

    # --- 4. HOTOVOSTNÍ POZICE ---
    # Zobrazíme jako progress bary pro jednotlivé měny
    if zustatky:
        st.markdown("### 💰 Stav hotovosti")
        cols_cash = st.columns(len(zustatky))
        for i, (mena, castka) in enumerate(zustatky.items()):
            with cols_cash[i]:
                st.metric(mena, f"{castka:,.2f}")

    st.markdown("---")

    # --- 5. DETAILNÍ TABULKA (Live Data) ---
    st.subheader("📋 Detailní přehled aktiv")
    
    if LIVE_DATA:
        # Přeformátování pro zobrazení
        vdf_display = vdf.copy()
        
        # Nastavení barev pro zisk/ztrátu
        def color_profit(val):
            color = '#00FF99' if val >= 0 else '#FF3366'
            return f'color: {color}'

        # Zobrazení přes st.dataframe s formátováním (nové Streamlit API)
        st.dataframe(
            vdf_display,
            column_config={
                "Ticker": st.column_config.TextColumn("Symbol", help="Ticker akcie"),
                "Sektor": st.column_config.TextColumn("Sektor"),
                "HodnotaUSD": st.column_config.ProgressColumn("Velikost pozice", format="$%.2f", min_value=0, max_value=float(vdf_display['HodnotaUSD'].max())),
                "Zisk": st.column_config.NumberColumn("Zisk/Ztráta ($)", format="$%.2f"),
                "Dnes": st.column_config.NumberColumn("Změna 24h", format="%.2f %%"),
                "Divi": st.column_config.NumberColumn("Yield", format="%.2f %%"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Žádná aktivní aktiva v portfoliu.")

    # --- 6. POSLEDNÍ TRANSAKCE ---
    if not df_hist.empty:
        with st.expander("📜 Historie obchodů"):
            st.dataframe(df_hist.sort_values("Datum", ascending=False).head(10), use_container_width=True, hide_index=True)
