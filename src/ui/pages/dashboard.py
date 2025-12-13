import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.services.portfolio_service import cached_fear_greed
from src.ai_brain import ask_ai_guard
from src.utils import ziskej_historicka_data
import yfinance as yf

def render_ticker_tape(data_dict):
    if not data_dict: return
    content = ""
    for ticker, info in data_dict.items():
        price = info.get('price', 0)
        curr = info.get('curr', '')
        content += f"&nbsp;&nbsp;&nbsp;&nbsp; <b>{ticker}</b>: {price:,.2f} {curr}"

    st.markdown(f"""
        <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 5px; padding: 8px; margin-bottom: 20px; white-space: nowrap; overflow: hidden;">
            <div style="display: inline-block; animation: marquee 20s linear infinite; color: #00CC96; font-family: 'Roboto Mono', monospace; font-weight: bold;" class="ticker-text">
                {content} {content} {content}
            </div>
        </div>
        <style>
            @keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}
        </style>
    """, unsafe_allow_html=True)

def render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA):
    """Vykreslí stránku '🏠 Přehled' (Dashboard) - VERZE 2.2 (Sektory + Měny Tabs)"""

    # --- BEZPEČNÁ INICIALIZACE ---
    if 'show_cash_history' not in st.session_state:
        st.session_state['show_cash_history'] = False
    if 'show_portfolio_live' not in st.session_state:
        st.session_state['show_portfolio_live'] = True

    # 1. HLAVIČKA A HLAVNÍ METRIKY
    st.title(f"🏠 PŘEHLED: {USER.upper()}")

    with st.container(border=True):
        k1, k2, k3, k4 = st.columns(4)
        kurz_czk = kurzy.get('CZK', 20.85)

        k1.metric("💰 JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{(celk_hod_usd-celk_inv_usd)*kurz_czk:+,.0f} Kč Zisk")
        k2.metric("🌎 JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} USD")
        k3.metric("📈 ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        k4.metric("💳 HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné prostředky")

    st.write("")

    # 2. ŘÁDEK: TRŽNÍ NÁLADA + KOMPAS
    c_left, c_right = st.columns([1, 2])

    with c_left:
        with st.container(border=True):
            st.caption("🧠 PSYCHOLOGIE TRHU")
            score, rating = cached_fear_greed()
            if score:
                st.metric("Fear & Greed Index", f"{score}/100", rating)
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score,
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
            viz_data_list = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
            if viz_data_list:
                sorted_data = sorted(viz_data_list, key=lambda x: x.get('Dnes', 0) if x.get('Dnes') is not None else 0, reverse=True)
                best = sorted_data[0]; worst = sorted_data[-1]
                st.write(f"🚀 **{best['Ticker']}**: {best['Dnes']*100:+.2f}%")
                st.write(f"💀 **{worst['Ticker']}**: {worst['Dnes']*100:+.2f}%")

    with c_right:
        with st.container(border=True):
            st.caption("🧭 GLOBÁLNÍ KOMPAS")
            try:
                makro_tickers = {"🇺🇸 S&P 500": "^GSPC", "🥇 Zlato": "GC=F", "₿ Bitcoin": "BTC-USD", "🏦 Úroky 10Y": "^TNX"}
                makro_data = ziskej_historicka_data(list(makro_tickers.values()), period="5d")

                mc1, mc2, mc3, mc4 = st.columns(4)
                cols_list = [mc1, mc2, mc3, mc4]

                for i, (name, ticker) in enumerate(makro_tickers.items()):
                    with cols_list[i]:
                        series = pd.Series()
                        if not makro_data.empty:
                            if isinstance(makro_data, pd.DataFrame) and ticker in makro_data.columns:
                                series = makro_data[ticker].dropna()
                            elif isinstance(makro_data, pd.Series):
                                series = makro_data.dropna()

                        if not series.empty:
                            last = series.iloc[-1]; prev = series.iloc[-2] if len(series) > 1 else last
                            delta = ((last - prev) / prev) * 100
                            st.metric(name, f"{last:,.0f}", f"{delta:+.2f}%")

                            line_color = '#238636' if delta >= 0 else '#da3633'
                            fig_spark = go.Figure(go.Scatter(y=series.values, mode='lines', line=dict(color=line_color, width=2), fill='tozeroy', fillcolor=f"rgba({'35, 134, 54' if delta >= 0 else '218, 54, 51'}, 0.1)"))
                            fig_spark.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=35, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
            except Exception as e: st.error(f"Chyba kompasu: {e}")

        if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
             with st.container(border=True):
                if st.button("🛡️ SPUSTIT RANNÍ AI BRIEFING", use_container_width=True):
                    with st.spinner("Analyzuji rizika..."):
                         top_mover = best.get('Ticker', "N/A") if 'best' in locals() else "N/A"
                         flop_mover = worst.get('Ticker', "N/A") if 'worst' in locals() else "N/A"
                         res = ask_ai_guard(model, pct_24h, cash_usd, top_mover, flop_mover)
                         st.info(f"🤖 **AI:** {res}")

    # 3. ŘÁDEK: GRAFY (VÝVOJ + NOVÝ TABBED BOX)
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

    # --- ZDE JE TA NOVÁ VYCHYTÁVKA (TABS) ---
    with col_graf2:
        with st.container(border=True):
            # Přepínání mezi Sektory a Měnami
            tab_sec, tab_cur = st.tabs(["🏭 SEKTORY", "💱 MĚNY"])

            # --- ZÁLOŽKA 1: SEKTORY ---
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
                        column_order=["Sektor", "Podíl", "HodnotaUSD"], width='stretch', hide_index=True
                    )
                else: st.info("Žádná data")

            # --- ZÁLOŽKA 2: MĚNY (NOVÉ!) ---
            with tab_cur:
                if not vdf.empty:
                    # Agregace podle měny
                    df_curr = vdf.groupby('Měna')['HodnotaUSD'].sum().reset_index()
                    total_val_c = df_curr['HodnotaUSD'].sum()
                    df_curr['Podíl'] = (df_curr['HodnotaUSD'] / total_val_c) * 100

                    # Graf měn (jiná paleta barev - pastelová)
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
                        column_order=["Měna", "Podíl", "HodnotaUSD"], width='stretch', hide_index=True
                    )
                else: st.info("Žádná data")
    # --------------------------------------------------------

    # 4. ŘÁDEK: SANKEY
    st.write("")
    with st.container(border=True):
        st.subheader("🌊 TOK KAPITÁLU (Sankey)")

        total_vklady_czk = 0
        df_cash_temp = st.session_state.get('df_cash', pd.DataFrame())
        if not df_cash_temp.empty:
            for _, row in df_cash_temp.iterrows():
                val_czk = row['Castka']
                if row['Mena'] == "USD": val_czk *= kurzy.get("CZK", 20.85)
                elif row['Mena'] == "EUR": val_czk *= (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                if row['Typ'] in ['Vklad', 'Deposit']: total_vklady_czk += val_czk
                elif row['Typ'] in ['Výběr', 'Withdrawal']: total_vklady_czk -= val_czk

        total_divi_czk = 0
        df_div_temp = st.session_state.get('df_div', pd.DataFrame())
        if not df_div_temp.empty:
             for _, r in df_div_temp.iterrows():
                amt = r['Castka']
                if r['Mena'] == "USD": total_divi_czk += amt * kurzy.get("CZK", 20.85)
                elif r['Mena'] == "EUR": total_divi_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                else: total_divi_czk += amt

        total_realized_czk = 0
        unrealized_profit_czk = (celk_hod_czk - celk_inv_usd * kurzy.get("CZK", 20.85))
        total_market_profit_czk = total_divi_czk + total_realized_czk + unrealized_profit_czk
        cash_total_czk = cash_usd * kurzy.get("CZK", 20.85)

        label = ["Vklady (Netto)", "Tržní Zisk & Divi", "MŮJ KAPITÁL", "Hotovost"]
        top_stocks = []
        if not vdf.empty:
            vdf_sorted = vdf.sort_values('HodnotaUSD', ascending=False).head(5)
            for _, row in vdf_sorted.iterrows():
                stock_label = f"{row['Ticker']}"
                label.append(stock_label)
                top_stocks.append({'label': stock_label, 'value_czk': row['HodnotaUSD'] * kurzy.get("CZK", 20.85)})

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
            node = dict(
                pad = 20, thickness = 20,
                line = dict(color = "black", width = 0.5),
                label = label,
                color = "rgba(0, 204, 150, 0.8)",
            ),
            link = dict(
                source = source, target = target, value = value,
                color = "rgba(100, 100, 100, 0.2)"
            ),
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
                    # PŮVODNÍ: batch = yf.download(tickers_list, period="1mo", interval="1d", group_by='ticker', progress=False, auto_adjust=False)
                    # OPTIMALIZACE:
                    batch_close = ziskej_historicka_data(tickers_list, period="1mo", interval="1d")

                    for t in tickers_list:
                        # Sparkline logic for ziskej_historicka_data result
                        if isinstance(batch_close, pd.DataFrame) and t in batch_close.columns:
                             spark_data[t] = batch_close[t].dropna().tolist()
                        elif isinstance(batch_close, pd.Series) and batch_close.name == t:
                             spark_data[t] = batch_close.dropna().tolist()
                        elif len(tickers_list) == 1 and isinstance(batch_close, pd.Series):
                             spark_data[t] = batch_close.dropna().tolist()
                        elif len(tickers_list) == 1 and isinstance(batch_close, pd.DataFrame) and not batch_close.empty:
                             if t in batch_close.columns:
                                 spark_data[t] = batch_close[t].dropna().tolist()
                             else:
                                 spark_data[t] = batch_close.iloc[:, 0].dropna().tolist()
                        else:
                             spark_data[t] = []
                except: pass

            vdf['Trend 30d'] = vdf['Ticker'].map(spark_data)

            st.dataframe(
                vdf,
                column_config={
                    "Ticker": st.column_config.TextColumn("Symbol", width="small"),
                    "Trend 30d": st.column_config.LineChartColumn("Trend (30d)", width="small", y_min=0, y_max=None),
                    "HodnotaUSD": st.column_config.ProgressColumn("Velikost pozice", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"])),
                    "Dnes": st.column_config.NumberColumn("24h %", format="%.2f%%"),
                    "Zisk": st.column_config.NumberColumn("Zisk ($)", format="%.0f"),
                },
                column_order=["Ticker", "Trend 30d", "HodnotaUSD", "Dnes", "Zisk"],
                width='stretch', hide_index=True
            )

            with st.expander("🔍 Zobrazit detailní tabulku"):
                st.dataframe(
                    vdf,
                    column_config={
                        "Ticker": st.column_config.TextColumn("Symbol"),
                        "Sektor": st.column_config.TextColumn("Sektor"),
                        "HodnotaUSD": st.column_config.ProgressColumn("Velikost", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"])),
                        "Zisk": st.column_config.NumberColumn("Zisk/Ztráta", format="%.2f"),
                        "Dnes": st.column_config.NumberColumn("Dnes %", format="%.2f%%"),
                        "Divi": st.column_config.NumberColumn("Yield", format="%.2f%%"),
                        "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
                        "Trend 30d": st.column_config.LineChartColumn("Trend", width="medium")
                    },
                    column_order=["Ticker", "Trend 30d", "Sektor", "Měna", "Kusy", "Průměr", "Cena", "Dnes", "HodnotaUSD", "Zisk", "Divi", "P/E"],
                    width='stretch',
                    hide_index=True
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
            st.dataframe(df_cash_local.sort_values('Datum', ascending=False), width='stretch', hide_index=True)
        else:
            st.info("Historie hotovosti je prázdná.")
