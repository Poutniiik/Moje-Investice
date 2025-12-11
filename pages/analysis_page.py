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
from datetime import datetime
import matplotlib.pyplot as plt

# Importujeme všechny potřebné externí a utilitní funkce
import utils
import ai_brain

# --- 1. RENTGEN ---
def render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE, LIVE_DATA):
    """Vykreslí kartu Rentgen (Tab 1 Analýzy)"""
    st.write("")
    vybrana_akcie = st.selectbox("Vyber firmu:", df['Ticker'].unique() if not df.empty else [])
    
    if vybrana_akcie:
        with st.spinner(f"Načítám rentgen pro {vybrana_akcie}..."):
            t_info, hist_data = utils.cached_detail_akcie(vybrana_akcie)
            
            if t_info or (hist_data is not None and not hist_data.empty):
                try:
                    long_name = t_info.get('longName', vybrana_akcie)
                    summary = t_info.get('longBusinessSummary', 'Popis není k dispozici.')
                    recommendation = t_info.get('recommendationKey', 'N/A').upper().replace('_', ' ')
                    target_price = t_info.get('targetMeanPrice', 0)
                    pe_ratio = t_info.get('trailingPE', 0)
                    currency = t_info.get('currency', '?')
                    current_price = t_info.get('currentPrice', 0)
                    profit_margin = t_info.get('profitMargins', 0)
                    roe = t_info.get('returnOnEquity', 0)
                    rev_growth = t_info.get('revenueGrowth', 0)
                    debt_equity = t_info.get('debtToEquity', 0)
                    insiders = t_info.get('heldPercentInsiders', 0)
                    institutions = t_info.get('heldPercentInstitutions', 0)
                    public = max(0, 1.0 - insiders - institutions)

                    c_d1, c_d2 = st.columns([1, 2])
                    
                    with c_d1:
                        with st.container(border=True):
                            if recommendation != "N/A":
                                barva_rec = "green" if "BUY" in recommendation else ("red" if "SELL" in recommendation else "orange")
                                st.markdown(f"### :{barva_rec}[{recommendation}]")
                                st.caption("Názor analytiků")
                            else:
                                st.markdown("### 🤷‍♂️ Neznámé"); st.caption("Bez doporučení")
                            
                            st.divider()
                            if target_price > 0: st.metric("Cílová cena", f"{target_price:,.2f}", help=f"Průměrný cíl analytiků ({currency})")
                            else: st.metric("Cílová cena", "---")

                            if pe_ratio > 0: st.metric("P/E Ratio", f"{pe_ratio:.2f}")
                            else: st.metric("P/E Ratio", "---")

                    with c_d2:
                        st.subheader(f"{long_name}")
                        st.caption(f"Cena: {current_price:,.2f} {currency}")
                        
                        if len(summary) > 200:
                            with st.expander("📝 Popis společnosti (Rozbalit)", expanded=False):
                                st.info(summary)
                                if t_info and t_info.get('website'): st.link_button("🌍 Web firmy", t_info.get('website'))
                        else:
                            st.info(summary)
                            if t_info and t_info.get('website'): st.link_button("🌍 Web firmy", t_info.get('website'))

                    st.divider()
                    st.subheader("🧬 FUNDAMENTÁLNÍ RENTGEN (Zdraví firmy)")
                    fc1, fc2, fc3, fc4 = st.columns(4)
                    fc1.metric("Zisková marže", f"{profit_margin*100:.1f} %")
                    fc2.metric("ROE (Efektivita)", f"{roe*100:.1f} %")
                    fc3.metric("Růst tržeb", f"{rev_growth*100:.1f} %")
                    fc4.metric("Dluh / Jmění", f"{debt_equity:.2f}")

                    st.write("")
                    st.subheader("🐳 VELRYBÍ RADAR (Vlastnická struktura)")

                    own_col1, own_col2 = st.columns([1, 2])
                    with own_col1:
                        with st.container(border=True):
                            st.metric("🏦 Instituce", f"{institutions*100:.1f} %")
                            st.divider()
                            st.metric("👔 Insideři", f"{insiders*100:.1f} %")

                    with own_col2:
                        own_df = pd.DataFrame({
                            "Kdo": ["Instituce 🏦", "Insideři 👔", "Veřejnost 👥"],
                            "Podíl": [institutions, insiders, public]
                        })
                        
                        fig_own = px.pie(own_df, values='Podíl', names='Kdo', hole=0.6,
                                         color='Kdo',
                                         color_discrete_map={"Instituce 🏦": "#58A6FF", "Insideři 👔": "#238636", "Veřejnost 👥": "#8B949E"},
                                         template="plotly_dark")
                        
                        fig_own.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", showlegend=True, legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
                        fig_own.update_traces(textinfo='percent', textposition='outside')
                        st.plotly_chart(fig_own, use_container_width=True)

                    st.divider()
                    st.subheader(f"📈 PROFESIONÁLNÍ CHART")
                    if hist_data is not None and not hist_data.empty:
                        fig_candle = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'])])
                        fig_candle.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_candle, use_container_width=True)

                    if AI_AVAILABLE and st.button(f"🤖 SPUSTIT AI ANALÝZU", type="primary"):
                         st.info("AI funkce připravena.")

                except Exception as e: st.error(f"Chyba zobrazení rentgenu: {e}")
            else: st.error("Nepodařilo se načíst data o firmě.")

# --- 2. SOUBOJ ---
def render_souboj_page(df, kurzy, calculate_sharpe_ratio):
    """Vykreslí Srovnání výkonnosti (Tab 2 Analýzy)."""
    st.subheader("⚔️ SROVNÁNÍ VÝKONNOSTI AKCIÍ")

    # 1. Příprava seznamů tickerů
    portfolio_tickers = df['Ticker'].unique().tolist() if not df.empty else []
    default_tickers = ['AAPL', 'MSFT', '^GSPC', 'BTC-USD', 'GC=F']
    initial_selection = list(set(portfolio_tickers[:5] + ['^GSPC']))

    # 2. Výběr v multiselectu
    tickers_to_compare = st.multiselect(
        "Vyberte akcie/indexy pro srovnání výkonnosti:",
        options=list(set(default_tickers + portfolio_tickers)),
        default=initial_selection,
        key="multi_compare"
    )

    # 3. Pokud je něco vybráno, jdeme stahovat
    if tickers_to_compare:
        try:
            with st.spinner(f"Stahuji historická data pro {len(tickers_to_compare)} tickerů..."):
                raw_data = yf.download(tickers_to_compare, period="1y", interval="1d", progress=False, auto_adjust=True)['Close']

            if raw_data.empty:
                st.warning("Nepodařilo se načíst historická data pro vybrané tickery.")
            else:
                # Normalizace (Start na 0%)
                normalized_data = raw_data.apply(lambda x: (x / x.iloc[0] - 1) * 100)

                # Vykreslení grafu
                fig_multi_comp = px.line(
                    normalized_data,
                    title='Normalizovaná výkonnost (Změna v %) od počátku',
                    template="plotly_dark"
                )
                
                fig_multi_comp.update_layout(
                    xaxis_title="Datum", yaxis_title="Změna (%)", height=500,
                    margin=dict(t=50, b=0, l=0, r=0), font_family="Roboto Mono",
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
                try: fig_multi_comp = utils.make_plotly_cyberpunk(fig_multi_comp)
                except: pass

                st.plotly_chart(fig_multi_comp, use_container_width=True, key="fig_srovnani")
                
                st.divider()
                st.subheader("Detailní srovnání metrik")

                comp_list = []
                for t in tickers_to_compare[:5]: 
                    i, h = utils.cached_detail_akcie(t)
                    if i:
                        mc = i.get('marketCap', 0)
                        pe = i.get('trailingPE', 0)
                        dy = i.get('dividendYield', 0)
                        perf = 0
                        if h is not None and not h.empty:
                            start_p = h['Close'].iloc[0]
                            end_p = h['Close'].iloc[-1]
                            if start_p != 0: perf = ((end_p / start_p) - 1) * 100

                        comp_list.append({
                            "Metrika": [f"Kapitalizace", f"P/E Ratio", f"Dividenda", f"Změna 1R"],
                            "Hodnota": [f"${mc/1e9:.1f}B", f"{pe:.2f}" if pe > 0 else "N/A", f"{dy*100:.2f}%" if dy else "0%", f"{perf:+.2f}%"],
                            "Ticker": t
                        })

                if comp_list:
                    final_data = {"Metrika": comp_list[0]["Metrika"]}
                    for item in comp_list:
                        final_data[item["Ticker"]] = item["Hodnota"]
                    st.dataframe(pd.DataFrame(final_data), use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Chyba při stahování dat: {e}")
    else:
        st.info("Vyberte alespoň jeden ticker.")

# --- 3. MAPA TRHU ---
def render_mapa_sektory_page(df, vdf):
    """Vykreslí Mapu trhu a Sektory (Tab 3 Analýzy)."""
    st.subheader("🗺️ MAPA IMPÉRIA (Treemap)")
    if not vdf.empty:
        tree_df = vdf.copy()
        tree_df['ColorScale'] = tree_df['Dnes'] * 100 
        fig_tree = px.treemap(
            tree_df, path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'], values='HodnotaUSD',
            color='ColorScale', color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
            hover_data={'HodnotaUSD': ':,.0f', 'Dnes': ':.2%'}, template="plotly_dark"
        )
        fig_tree.update_layout(margin=dict(t=30, l=10, r=10, b=10), font_family="Roboto Mono", height=500)
        st.plotly_chart(fig_tree, use_container_width=True)
        st.caption("🟥 Červená = Dnes klesá | 🟩 Zelená = Dnes roste | Velikost = Hodnota v USD")
    else:
        st.info("Nemáš žádné pozice pro zobrazení mapy.")

# --- 4. VĚŠTEC ---
def render_vestec_page(df, kurzy, celk_hod_usd):
    """Vykreslí Stroj času (Tab 4 Analýzy)."""
    st.subheader("🔮 VĚŠTEC: Složené úročení")
    start_czk = celk_hod_usd * kurzy.get("CZK", 20.85)
    
    c1, c2, c3 = st.columns(3)
    with c1: years = st.number_input("Počet let", 1, 40, 10)
    with c2: monthly = st.number_input("Měsíční vklad (Kč)", 0, 100000, 5000, step=500)
    with c3: rate = st.number_input("Očekávaný úrok (%)", 1.0, 20.0, 8.0, step=0.5) / 100
    
    future_vals = []; total_invested = []
    current = start_czk; invested = start_czk
    
    for i in range(years + 1):
        future_vals.append(current)
        total_invested.append(invested)
        current = current * (1 + rate) + (monthly * 12)
        invested += (monthly * 12)
        
    df_proj = pd.DataFrame({"Rok": range(datetime.now().year, datetime.now().year + years + 1), "Hodnota portfolia": future_vals, "Vložené peníze": total_invested})
    
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(x=df_proj["Rok"], y=df_proj["Hodnota portfolia"], fill='tozeroy', name="Hodnota s úroky", line=dict(color="#00CC96")))
    fig_proj.add_trace(go.Scatter(x=df_proj["Rok"], y=df_proj["Vložené peníze"], fill='tonexty', name="Jen vklady", line=dict(color="#AB63FA")))
    
    fig_proj.update_layout(title=f"Za {years} let budeš mít: {future_vals[-1]:,.0f} Kč", template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig_proj = utils.make_plotly_cyberpunk(fig_proj)
    st.plotly_chart(fig_proj, use_container_width=True)
    
    st.metric("Celkový zisk z úroků", f"{future_vals[-1] - total_invested[-1]:,.0f} Kč")

# --- 5. BENCHMARK ---
def render_benchmark_page(df, kurzy, calculate_sharpe_ratio):
    """Vykreslí Srovnání s S&P 500 (Tab 5 Analýzy)."""
    st.subheader("🏆 VS. S&P 500")
    if not df.empty:
        my_top = df.groupby('Ticker')['Cena'].sum().sort_values(ascending=False).index[:1].tolist()
        if not my_top: my_top = ["AAPL"]
        tickers = my_top + ["^GSPC"]
        
        try:
            data = yf.download(tickers, period="1y", progress=False, auto_adjust=True)['Close']
            norm_data = (data / data.iloc[0]) * 100
            
            fig = px.line(norm_data, x=norm_data.index, y=norm_data.columns, title="Tvá TOP akcie vs Trh (1 rok)", template="plotly_dark")
            fig.update_layout(yaxis_title="Výkonnost (start=100)", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            fig = utils.make_plotly_cyberpunk(fig)
            st.plotly_chart(fig, use_container_width=True)
            
            returns = data.pct_change().dropna()
            sharpe_spy = calculate_sharpe_ratio(returns["^GSPC"]) if "^GSPC" in returns else 0
            my_ticker_col = my_top[0]
            if my_ticker_col in returns:
                sharpe_me = calculate_sharpe_ratio(returns[my_ticker_col])
                c1, c2 = st.columns(2)
                c1.metric(f"Sharpe Ratio ({my_ticker_col})", f"{sharpe_me:.2f}")
                c2.metric("Sharpe Ratio (S&P 500)", f"{sharpe_spy:.2f}")
        except Exception as e: st.error(f"Data nedostupná: {e}")
    else: st.info("Portfolio je prázdné.")

# --- 6. MĚNY ---
def render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd, get_zustatky):
    st.subheader("💱 MĚNOVÝ SIMULÁTOR")
    st.info("Jak změna kurzu koruny ovlivní hodnotu tvého portfolia?")
    assets_by_curr = {"USD": 0, "EUR": 0, "CZK": 0}
    
    data_to_use = viz_data_list.to_dict('records') if isinstance(viz_data_list, pd.DataFrame) else viz_data_list
    for item in data_to_use:
        curr = item['Měna']; val = item['Hodnota']
        if curr in assets_by_curr: assets_by_curr[curr] += val
        else: assets_by_curr["USD"] += item['HodnotaUSD']

    kurz_usd_now = kurzy.get("CZK", 20.85)
    kurz_eur_now = kurzy.get("EUR", 1.16) * kurz_usd_now
    cash_in_curr = get_zustatky(st.session_state['user'])
    assets_by_curr['USD'] -= cash_in_curr.get('USD', 0)
    assets_by_curr['CZK'] -= cash_in_curr.get('CZK', 0)
    assets_by_curr['EUR'] -= cash_in_curr.get('EUR', 0)

    col_s1, col_s2 = st.columns(2)
    with col_s1: sim_usd = st.slider(f"Kurz USD/CZK (Aktuálně: {kurz_usd_now:.2f})", 15.0, 30.0, float(kurz_usd_now))
    with col_s2: sim_eur = st.slider(f"Kurz EUR/CZK (Aktuálně: {kurz_eur_now:.2f})", 15.0, 35.0, float(kurz_eur_now))
        
    val_now_czk = (assets_by_curr["USD"] * kurz_usd_now) + (assets_by_curr["EUR"] * kurz_eur_now) + assets_by_curr["CZK"]
    val_sim_czk = (assets_by_curr["USD"] * sim_usd) + (assets_by_curr["EUR"] * sim_eur) + assets_by_curr["CZK"]
    
    st.divider()
    st.metric("Hodnota Akcií (Simulace)", f"{val_sim_czk:,.0f} Kč", delta=f"{val_sim_czk - val_now_czk:,.0f} Kč")

# --- 7. REBALANCING ---
def render_analýza_rebalancing_page(df, vdf, kurzy):
    st.subheader("⚖️ REBALANČNÍ KALKULAČKA")
    if not vdf.empty:
        df_reb = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
        total_val = df_reb['HodnotaUSD'].sum()
        targets = {}; cols = st.columns(3)
        for i, row in df_reb.iterrows():
            with cols[i % 3]:
                targets[row['Sektor']] = st.number_input(f"{row['Sektor']} (%)", min_value=0.0, max_value=100.0, value=float(round((row['HodnotaUSD']/total_val)*100, 1)), step=1.0, key=f"reb_{row['Sektor']}")
        
        df_reb['Cíl %'] = df_reb['Sektor'].map(targets)
        df_reb['Rozdíl'] = (total_val * (df_reb['Cíl %'] / 100)) - df_reb['HodnotaUSD']
        
        st.divider(); st.subheader("🛠️ Návrh akcí")
        for _, r in df_reb.iterrows():
            if abs(r['Rozdíl']) > 1:
                if r['Rozdíl'] > 0: st.success(f"🟢 **{r['Sektor']}**: DOKOUPIT za {r['Rozdíl']:,.0f} USD")
                else: st.error(f"🔴 **{r['Sektor']}**: PRODAT za {abs(r['Rozdíl']):,.0f} USD")
    else: st.info("Portfolio je prázdné.")

# --- 8. KORELACE ---
def render_analýza_korelace_page(df, kurzy):
    st.subheader("📊 MATICE KORELACE")
    if not df.empty and len(df['Ticker'].unique()) > 1:
        try:
            with st.spinner("Počítám korelace..."):
                hist_data = yf.download(df['Ticker'].unique().tolist(), period="1y", auto_adjust=True)['Close']
                corr_matrix = hist_data.pct_change().dropna().corr()
                fig_corr = px.imshow(corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", origin='lower')
                fig_corr.update_layout(template="plotly_dark", height=600, plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(utils.make_plotly_cyberpunk(fig_corr), use_container_width=True)
        except Exception as e: st.error(f"Chyba: {e}")
    else: st.warning("Potřebuješ alespoň 2 různé akcie.")

# --- 9. KALENDÁŘ ---
def render_analýza_kalendář_page(df, df_watch, LIVE_DATA):
    st.subheader("📅 KALENDÁŘ VÝSLEDKŮ")
    all_tickers = list(set(df['Ticker'].unique().tolist() + df_watch['Ticker'].unique().tolist())) if not df.empty or not df_watch.empty else []
    
    if all_tickers:
        earnings = []
        for tk in all_tickers:
            try:
                e_date = utils.ziskej_earnings_datum(tk)
                if e_date:
                    ed = pd.to_datetime(e_date).to_pydatetime()
                    days = (ed - datetime.now()).days
                    if days > -7: earnings.append({"Symbol": tk, "Datum": ed.strftime("%d.%m.%Y"), "Dní": days})
            except: pass
        
        if earnings:
            st.dataframe(pd.DataFrame(earnings).sort_values('Dní'), use_container_width=True)
        else: st.info("Žádné blízké termíny.")
    else: st.warning("Žádné akcie.")

# --- HLAVNÍ FUNKCE STRÁNKY ---
def analysis_page(df, df_watch, vdf, model, AI_AVAILABLE, kurzy, viz_data_list, celk_hod_usd, get_zustatky, LIVE_DATA, calculate_sharpe_ratio):
    """
    Vykreslí celou stránku "📈 Analýza" pomocí tabů.
    """
    st.title("📈 HLOUBKOVÁ ANALÝZA")
        
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA", "🔮 VĚŠTEC", "🏆 VS TRH", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE", "📅 KALENDÁŘ"])

    with tab1: render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE, LIVE_DATA)
    with tab2: render_souboj_page(df, kurzy, calculate_sharpe_ratio)
    with tab3: render_mapa_sektory_page(df, vdf)
    with tab4: render_vestec_page(df, kurzy, celk_hod_usd)
    with tab5: render_benchmark_page(df, kurzy, calculate_sharpe_ratio)
    with tab6: render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd, get_zustatky)
    with tab7: render_analýza_rebalancing_page(df, vdf, kurzy)
    with tab8: render_analýza_korelace_page(df, kurzy)
    with tab9: render_analýza_kalendář_page(df, df_watch, LIVE_DATA)
