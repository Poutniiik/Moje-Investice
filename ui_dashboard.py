import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import requests
from ai_brain import get_portfolio_health_score, get_voice_briefing_text, ask_ai_guard
from voice_engine import VoiceAssistant

# --- CACHE FUNKCE (Zrychlení aplikace) ---

@st.cache_data(ttl=3600)
def get_cached_health_score(USER, _model, vdf_json, cash_usd, sentiment):
    vdf = pd.read_json(vdf_json)
    return get_portfolio_health_score(_model, vdf, cash_usd, sentiment)

@st.cache_data(ttl=3600)
def get_cached_briefing_text(USER, _model, score, sentiment):
    return get_voice_briefing_text(_model, USER, score, sentiment)

@st.cache_data(ttl=600)
def get_macro_data(tickers_tuple):
    return yf.download(list(tickers_tuple), period="5d", progress=False)['Close']

def cached_fear_greed():
    """Získání Fear & Greed indexu"""
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = r.json()['data'][0]
        return int(data['value']), data['value_classification']
    except: return None, None

# --- HLAVNÍ RENDER FUNKCE ---

def render_dashboard(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, 
                     zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, LIVE_DATA):
    """
    Kompletní render stránky Dashboard (Přehled).
    Obsahuje: Metriky, AI Diagnostiku, Tržní Sentiment, Kompas, Vývoj majetku, 
    Sektory/Měny Tabs, Sankey diagram a Portfolio Live s Sparklines.
    """
    
    # 0. INICIALIZACE STAVU
    if 'show_cash_history' not in st.session_state: st.session_state['show_cash_history'] = False 
    if 'show_portfolio_live' not in st.session_state: st.session_state['show_portfolio_live'] = True
    
    # 1. HLAVNÍ METRIKY
    with st.container(border=True):
        k1, k2, k3, k4 = st.columns(4)
        kurz_czk = kurzy.get('CZK', 20.85)
        
        k1.metric("💰 JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{(celk_hod_usd-celk_inv_usd)*kurz_czk:+,.0f} Kč Zisk")
        k2.metric("🌎 JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} USD")
        k3.metric("📈 ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        k4.metric("💳 HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné prostředky")

    st.write("") 

    # 1.5 AI DIAGNOSTIKA ZDRAVÍ
    audio_html = None
    if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
        with st.container(border=True):
            st.caption("🩺 AI DIAGNOSTIKA PORTFOLIA")
            score_fg, rating_fg = cached_fear_greed()
            sentiment_context = f"{rating_fg} ({score_fg}/100)" if score_fg else "Neutrální"
            
            try:
                vdf_json = vdf.to_json()
                health = get_cached_health_score(USER, model, vdf_json, cash_usd, sentiment_context)
                h_score = health.get('score', 50)

                if 'briefing_played' not in st.session_state:
                    with st.spinner("Attis AI připravuje hlášení..."):
                        briefing_text = get_cached_briefing_text(USER, model, h_score, sentiment_context)
                        audio_html = VoiceAssistant.speak(briefing_text)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                            st.session_state['briefing_played'] = True

                h_col1, h_col2 = st.columns([1, 3])
                with h_col1:
                    h_color = "red" if h_score < 40 else ("orange" if h_score < 70 else "#00FF99")
                    st.markdown(f"<h2 style='text-align: center; color: {h_color}; margin-top: 0;'>{h_score}%</h2>", unsafe_allow_html=True)
                    st.progress(h_score / 100)
                with h_col2:
                    st.markdown(f"**Verdikt:** {health.get('comment', 'Diagnostika dokončena.')}")
                    st.caption("💡 Tip: AI hodnotí diverzifikaci sektorů a tvůj 'cash buffer'.")
            except Exception as e:
                st.error(f"Chyba v diagnostice: {e}")

    # 2. ŘÁDEK: TRŽNÍ NÁLADA + KOMPAS
    c_left, c_right = st.columns([1, 2])
    viz_data_list = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
    best = {"Ticker": "N/A", "Dnes": 0}; worst = {"Ticker": "N/A", "Dnes": 0}
    if viz_data_list:
        sorted_data = sorted(viz_data_list, key=lambda x: x.get('Dnes', 0) or 0, reverse=True)
        best = sorted_data[0]; worst = sorted_data[-1]

    with c_left:
        with st.container(border=True):
            st.caption("🧠 PSYCHOLOGIE TRHU")
            score_f, rating_f = cached_fear_greed()
            if score_f:
                st.metric("Fear & Greed Index", f"{score_f}/100", rating_f)
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score_f,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    gauge = {
                        'axis': {'range': [0, 100], 'tickwidth': 0},
                        'bar': {'color': "white"}, 'bgcolor': "black",
                        'steps': [{'range': [0, 25], 'color': '#FF4136'}, {'range': [75, 100], 'color': '#2ECC40'}],
                    }
                ))
                fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=120, margin=dict(l=20, r=20, t=20, b=20), font={'color': "white"})
                st.plotly_chart(fig_gauge, use_container_width=True)
            
            st.divider()
            st.write(f"🚀 **{best['Ticker']}**: {best.get('Dnes', 0)*100:+.2f}%")
            st.write(f"💀 **{worst['Ticker']}**: {worst.get('Dnes', 0)*100:+.2f}%")

    with c_right:
        with st.container(border=True):
            st.caption("🧭 GLOBÁLNÍ KOMPAS")
            try:
                makro_tickers = ("^GSPC", "GC=F", "BTC-USD", "^TNX")
                makro_names = ["🇺🇸 S&P 500", "🥇 Zlato", "₿ Bitcoin", "🏦 Úroky 10Y"]
                makro_data = get_macro_data(makro_tickers)
                mc_cols = st.columns(4)
                for i, ticker in enumerate(makro_tickers):
                    with mc_cols[i]:
                        series = makro_data[ticker].dropna()
                        if not series.empty:
                            last = series.iloc[-1]; prev = series.iloc[-2] if len(series) > 1 else last
                            delta = ((last - prev) / prev) * 100
                            st.metric(makro_names[i], f"{last:,.0f}", f"{delta:+.2f}%")
                            
                            line_color = '#238636' if delta >= 0 else '#da3633'
                            fig_spark = go.Figure(go.Scatter(y=series.values, mode='lines', line=dict(color=line_color, width=2), fill='tozeroy', fillcolor=f"rgba({'35, 134, 54' if delta >= 0 else '218, 54, 51'}, 0.1)"))
                            fig_spark.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=35, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
            except Exception: st.error("Chyba kompasu")
        
            if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
                if st.button("🛡️ SPUSTIT RANNÍ AI BRIEFING", use_container_width=True):
                    with st.spinner("Analyzuji rizika..."):
                        res = ask_ai_guard(model, pct_24h, cash_usd, best.get('Ticker'), worst.get('Ticker'))
                        st.info(f"🤖 **AI:** {res}")
                        audio_html = VoiceAssistant.speak(res)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)

    # 3. ŘÁDEK: GRAFY
    col_graf1, col_graf2 = st.columns([2, 1])
    with col_graf1:
        with st.container(border=True):
            st.subheader("🌊 VÝVOJ MAJETKU")
            if not hist_vyvoje.empty:
                chart_data = hist_vyvoje.copy()
                chart_data['TotalCZK'] = chart_data['TotalUSD'] * kurzy.get("CZK", 20.85)
                fig_area = px.area(chart_data, x='Date', y='TotalCZK', template="plotly_dark")
                fig_area.update_traces(line_color='#00CC96', fillcolor='rgba(0, 204, 150, 0.2)')
                fig_area.update_layout(xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                fig_area.update_xaxes(showgrid=False)
                fig_area.update_yaxes(showgrid=True, gridcolor='#30363D', tickprefix="Kč ")
                st.plotly_chart(fig_area, use_container_width=True)

    with col_graf2:
        with st.container(border=True):
            tab_sec, tab_cur = st.tabs(["🏭 SEKTORY", "💱 MĚNY"])
            with tab_sec:
                if not vdf.empty:
                    df_sector = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
                    total_val = df_sector['HodnotaUSD'].sum()
                    df_sector['Podíl'] = (df_sector['HodnotaUSD'] / total_val) * 100
                    fig_pie = px.pie(df_sector, values='HodnotaUSD', names='Sektor', hole=0.7, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Bold)
                    fig_pie.update_traces(textinfo='none', hoverinfo='label+percent+value') 
                    fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=150, paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_pie, use_container_width=True)
                    st.dataframe(
                        df_sector.sort_values('Podíl', ascending=False),
                        column_config={
                            "Sektor": st.column_config.TextColumn("Sektor"),
                            "Podíl": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100),
                            "HodnotaUSD": st.column_config.NumberColumn("$ USD", format="$%.0f")
                        },
                        column_order=["Sektor", "Podíl", "HodnotaUSD"], use_container_width=True, hide_index=True
                    )
            with tab_cur:
                if not vdf.empty:
                    df_curr = vdf.groupby('Měna')['HodnotaUSD'].sum().reset_index()
                    total_val_c = df_curr['HodnotaUSD'].sum()
                    df_curr['Podíl'] = (df_curr['HodnotaUSD'] / total_val_c) * 100
                    fig_cur = px.pie(df_curr, values='HodnotaUSD', names='Měna', hole=0.7, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_cur.update_traces(textinfo='none', hoverinfo='label+percent+value')
                    fig_cur.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=150, paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_cur, use_container_width=True)
                    st.dataframe(
                        df_curr.sort_values('Podíl', ascending=False),
                        column_config={
                            "Měna": st.column_config.TextColumn("Měna"),
                            "Podíl": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100),
                            "HodnotaUSD": st.column_config.NumberColumn("Hodnota (v USD)", format="$%.0f")
                        },
                        column_order=["Měna", "Podíl", "HodnotaUSD"], use_container_width=True, hide_index=True
                    )

    # 4. ŘÁDEK: SANKEY
    st.write("")
    with st.container(border=True):
        st.subheader("🌊 TOK KAPITÁLU (Sankey)")
        total_vklady_czk = 0
        df_cash_temp = st.session_state.get('df_cash', pd.DataFrame())
        if not df_cash_temp.empty:
            for _, row in df_cash_temp.iterrows():
                val_czk = row['Castka']
                if row['Mena'] == "USD": val_czk *= kurz_czk
                elif row['Mena'] == "EUR": val_czk *= (kurzy.get("EUR", 1.16) * kurz_czk)
                if row['Typ'] in ['Vklad', 'Deposit']: total_vklady_czk += val_czk
                elif row['Typ'] in ['Výběr', 'Withdrawal']: total_vklady_czk -= val_czk

        total_divi_czk = 0
        df_div_temp = st.session_state.get('df_div', pd.DataFrame())
        if not df_div_temp.empty:
             for _, r in df_div_temp.iterrows():
                amt = r['Castka']
                if r['Mena'] == "USD": total_divi_czk += amt * kurz_czk
                elif r['Mena'] == "EUR": total_divi_czk += amt * (kurzy.get("EUR", 1.16) * kurz_czk)
                else: total_divi_czk += amt
        
        total_realized_czk = 0 
        unrealized_profit_czk = (celk_hod_czk - celk_inv_usd * kurz_czk)
        total_market_profit_czk = total_divi_czk + total_realized_czk + unrealized_profit_czk
        cash_total_czk = cash_usd * kurz_czk
        
        label = ["Vklady (Netto)", "Tržní Zisk & Divi", "MŮJ KAPITÁL", "Hotovost"]
        top_stocks = []
        if not vdf.empty:
            vdf_sorted = vdf.sort_values('HodnotaUSD', ascending=False).head(5)
            for _, row in vdf_sorted.iterrows():
                stock_label = f"{row['Ticker']}"
                label.append(stock_label)
                top_stocks.append({'label': stock_label, 'value_czk': row['HodnotaUSD'] * kurz_czk})
        
        stock_total_czk = celk_hod_czk
        other_stocks_val_czk = stock_total_czk - sum([s['value_czk'] for s in top_stocks])
        if other_stocks_val_czk > 100: label.append("Ostatní")

        IDX_VKLADY = 0; IDX_ZISK = 1; IDX_KAPITAL = 2; IDX_CASH = 3; IDX_FIRST_STOCK = 4
        source = []; target = []; value = []
        if total_vklady_czk > 0: source.append(IDX_VKLADY); target.append(IDX_KAPITAL); value.append(total_vklady_czk)
        if total_market_profit_czk > 0: source.append(IDX_ZISK); target.append(IDX_KAPITAL); value.append(total_market_profit_czk)
        if cash_total_czk > 100: source.append(IDX_KAPITAL); target.append(IDX_CASH); value.append(cash_total_czk)
        curr_idx = IDX_FIRST_STOCK
        for s in top_stocks:
            source.append(IDX_KAPITAL); target.append(curr_idx); value.append(s['value_czk'])
            curr_idx += 1
        if other_stocks_val_czk > 100:
             source.append(IDX_KAPITAL); target.append(curr_idx); value.append(other_stocks_val_czk)

        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(pad = 20, thickness = 20, line = dict(color = "black", width = 0.5), label = label, color = "rgba(0, 204, 150, 0.8)"),
            link = dict(source = source, target = target, value = value, color = "rgba(100, 100, 100, 0.2)"),
            textfont = dict(size=14, color="white", family="Roboto Mono")
        )])
        fig_sankey.update_layout(height=500, margin=dict(l=10, r=10, t=30, b=30), paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
        st.plotly_chart(fig_sankey, use_container_width=True)

    # 5. ŘÁDEK: PORTFOLIO LIVE
    st.write("")
    with st.container(border=True):
        c_head, c_check = st.columns([4, 1])
        c_head.subheader("📋 PORTFOLIO LIVE")
        st.session_state['show_portfolio_live'] = c_check.checkbox("Zobrazit", value=st.session_state['show_portfolio_live'])
        
        if st.session_state['show_portfolio_live'] and not vdf.empty:
            tickers_list = vdf['Ticker'].tolist()
            spark_data = {}
            if tickers_list:
                try:
                    batch = yf.download(tickers_list, period="1mo", interval="1d", group_by='ticker', progress=False)
                    for t in tickers_list:
                         if len(tickers_list) > 1 and t in batch.columns.levels[0]: spark_data[t] = batch[t]['Close'].dropna().tolist()
                         elif len(tickers_list) == 1: spark_data[t] = batch['Close'].dropna().tolist()
                         else: spark_data[t] = []
                except: pass
            
            vdf['Trend 30d'] = vdf['Ticker'].map(spark_data)
            
            st.dataframe(
                vdf,
                column_config={
                    "Ticker": st.column_config.TextColumn("Symbol", width="small"),
                    "Trend 30d": st.column_config.LineChartColumn("Trend (30d)", width="small", y_min=0, y_max=None),
                    "HodnotaUSD": st.column_config.ProgressColumn("Velikost pozice", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"]) if not vdf.empty else 1),
                    "Dnes": st.column_config.NumberColumn("24h %", format="%.2f%%"),
                    "Zisk": st.column_config.NumberColumn("Zisk ($)", format="%.0f"),
                },
                column_order=["Ticker", "Trend 30d", "HodnotaUSD", "Dnes", "Zisk"],
                use_container_width=True, hide_index=True
            )
            
            with st.expander("🔍 Zobrazit detailní tabulku"):
                st.dataframe(
                    vdf,
                    column_config={
                        "Ticker": st.column_config.TextColumn("Symbol"),
                        "Sektor": st.column_config.TextColumn("Sektor"),
                        "HodnotaUSD": st.column_config.ProgressColumn("Velikost", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"]) if not vdf.empty else 1),
                        "Zisk": st.column_config.NumberColumn("Zisk/Ztráta", format="%.2f"),
                        "Dnes": st.column_config.NumberColumn("Dnes %", format="%.2f%%"),
                        "Divi": st.column_config.NumberColumn("Yield", format="%.2f%%"),
                        "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
                        "Trend 30d": st.column_config.LineChartColumn("Trend", width="medium")
                    },
                    column_order=["Ticker", "Trend 30d", "Sektor", "Měna", "Kusy", "Průměr", "Cena", "Dnes", "HodnotaUSD", "Zisk", "Divi", "P/E"],
                    use_container_width=True, hide_index=True
                )
        elif vdf.empty:
             st.info("Portfolio je prázdné.")

    # 6. HISTORIE HOTOVOSTI
    st.write("")
    st.session_state['show_cash_history'] = st.checkbox("📜 Zobrazit historii hotovosti", value=st.session_state['show_cash_history'])

    if st.session_state['show_cash_history']:
        st.divider()
        st.subheader("🏦 HISTORIE HOTOVOSTI")
        df_cash_local = st.session_state.get('df_cash', pd.DataFrame())
        if not df_cash_local.empty:
            st.dataframe(df_cash_local.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Historie hotovosti je prázdná.")
