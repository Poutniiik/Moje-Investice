# =========================================================================
# SOUBOR: pages/analysis_page.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "📈 Analýza"
# =========================================================================
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Importujeme všechny potřebné externí a utilitní funkce
import utils
import ai_brain

# --- 1. RENTGEN ---
def render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE, LIVE_DATA):
    """Vykreslí kartu Rentgen (Tab 1 Analýzy)"""
    st.header("🔍 RENTGEN AKCIE")
    
    # Sloučení tickerů z portfolia a watchlistu
    tickers = df['Ticker'].unique().tolist() if not df.empty else []
    if not df_watch.empty:
        tickers += [t for t in df_watch['Ticker'].unique().tolist() if t not in tickers]
    
    vybrana_akcie = st.selectbox("Vyber firmu k analýze:", tickers)
    
    if vybrana_akcie:
        with st.spinner(f"Načítám rentgen pro {vybrana_akcie}..."):
            t_info, hist_data = utils.cached_detail_akcie(vybrana_akcie)
            
            if t_info:
                # Základní info
                c1, c2, c3 = st.columns(3)
                c1.metric("Cena", f"${t_info.get('currentPrice', 'N/A')}")
                c2.metric("Target (Analytici)", f"${t_info.get('targetMeanPrice', 'N/A')}")
                c3.metric("P/E Ratio", f"{t_info.get('trailingPE', 'N/A')}")
                
                # Popis
                with st.expander("📝 Popis firmy", expanded=True):
                    st.write(t_info.get('longBusinessSummary', 'Popis nedostupný.'))
                
                # AI Analýza (pokud je dostupná)
                if AI_AVAILABLE and model:
                    if st.button("🤖 AI Analýza Akcie"):
                        with st.spinner("AI čte rozvahu..."):
                            prompt = f"Analyzuj akcii {vybrana_akcie}. Fundamental data: P/E {t_info.get('trailingPE')}, Sector: {t_info.get('sector')}. Řekni 3 pro a 3 proti."
                            try:
                                response = model.generate_content(prompt).text
                                st.info(response)
                            except Exception as e:
                                st.error(f"AI chyba: {e}")
            else:
                st.error("Nepodařilo se načíst data o akcii.")

# --- 2. SOUBOJ ---
def render_souboj_page(df, kurzy, calculate_sharpe_ratio=None):
    st.header("⚔️ SOUBOJ TITANŮ")
    st.info("Tato sekce umožní srovnání dvou akcií vedle sebe (Ve vývoji).")

# --- 3. MAPA TRHU ---
def render_mapa_trhu_page(vdf):
    st.header("🗺️ MAPA PORTFOLIA (Treemap)")
    if not vdf.empty:
        fig = px.treemap(vdf, path=['Sektor', 'Ticker'], values='HodnotaUSD',
                         color='Zisk', color_continuous_scale='RdYlGn',
                         title="Rozložení dle sektorů a velikosti")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Prázdné portfolio.")

# --- 4. VĚŠTEC ---
def render_vestec_page(df, model):
    st.header("🔮 VĚŠTEC (Predikce)")
    st.info("AI predikce vývoje trhu na základě historických dat (Beta).")

# --- 5. VS TRH ---
def render_vs_trh_page(df_hist, celk_hod_usd):
    st.header("🏆 TY vs. S&P 500")
    st.info("Srovnání výkonnosti tvého portfolia s indexem S&P 500.")

# --- 6. MĚNY (ZDE BYLA CHYBA) ---
def render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd, get_zustatky):
    st.header("💱 MĚNOVÉ RIZIKO")
    
    # Agregace měnové expozice z aktiv
    exposure = {}
    
    if viz_data_list:
        for item in viz_data_list:
            # --- ZDE JE OPRAVA (KeyError Fix) ---
            # Použijeme .get() s defaultní hodnotou 'USD', pokud klíč chybí
            curr = item.get('Měna', 'USD') 
            val = item.get('HodnotaUSD', 0)
            
            if curr not in exposure: exposure[curr] = 0
            exposure[curr] += val
            
    # Zobrazení dat
    if exposure:
        df_exp = pd.DataFrame(list(exposure.items()), columns=['Měna', 'Hodnota v USD'])
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.dataframe(df_exp, hide_index=True)
        
        with c2:
            fig = px.pie(df_exp, values='Hodnota v USD', names='Měna', title="Expozice dle měny aktiv", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Žádná aktiva k analýze.")

# --- 7. REBALANCING ---
def render_rebalancing_page(vdf):
    st.header("⚖️ REBALANCING")
    st.info("Nástroj pro vyvážení portfolia.")

# --- 8. KORELACE ---
def render_korelace_page(df):
    st.header("📊 KORELAČNÍ MATICE")
    st.info("Analýza, jak se akcie pohybují společně.")

# --- 9. KALENDÁŘ ---
def render_kalendar_page(df):
    st.header("📅 KALENDÁŘ VÝSLEDKŮ (Earnings)")
    
    tickers = df['Ticker'].unique().tolist() if not df.empty else []
    
    if tickers:
        if st.button("Načíst data o výsledcích"):
            earnings_data = []
            progress_bar = st.progress(0)
            
            for i, ticker in enumerate(tickers):
                try:
                    t = yf.Ticker(ticker)
                    cal = t.calendar
                    if cal is not None and not cal.empty:
                        # Zkusíme najít Earnings Date
                        # Struktura yfinance calendar se mění, zkusíme robustní přístup
                        date = cal.iloc[0, 0] if not cal.empty else "N/A"
                        earnings_data.append({"Ticker": ticker, "Earnings Date": str(date)})
                except Exception:
                    pass
                progress_bar.progress((i + 1) / len(tickers))
            
            if earnings_data:
                st.dataframe(pd.DataFrame(earnings_data))
            else:
                st.info("Žádná data o výsledcích nenalezena.")
    else:
        st.warning("Portfolio je prázdné.")


# --- HLAVNÍ FUNKCE STRÁNKY ---
def analysis_page(df, df_watch, vdf, model, AI_AVAILABLE, kurzy, viz_data_list, celk_hod_usd, get_zustatky, LIVE_DATA, calculate_sharpe_ratio):
    """
    Vykreslí celou stránku "📈 Analýza" pomocí tabů.
    """
    st.title("📈 HLOUBKOVÁ ANALÝZA")
        
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA", "🔮 VĚŠTEC", 
        "🏆 VS TRH", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE", "📅 KALENDÁŘ"
    ])

    with tab1: render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE, LIVE_DATA)
    with tab2: render_souboj_page(df, kurzy, calculate_sharpe_ratio)
    with tab3: render_mapa_trhu_page(vdf)
    with tab4: render_vestec_page(df, model)
    with tab5: render_vs_trh_page(None, celk_hod_usd)
    with tab6: render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd, get_zustatky)
    with tab7: render_rebalancing_page(vdf)
    with tab8: render_korelace_page(df)
    with tab9: render_kalendar_page(df)
