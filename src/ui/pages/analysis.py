import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
from src.utils import make_plotly_cyberpunk, ziskej_detail_akcie, ziskej_earnings_datum, calculate_sharpe_ratio, download_stock_history, download_stock_history_from_start
from src.services.portfolio_service import cached_detail_akcie

def add_download_button(fig, filename):
    try:
        import io
        buffer = io.BytesIO()
        fig.write_image(buffer, format="png", width=1200, height=800, scale=2)

        st.download_button(
            label=f"⬇️ Stáhnout graf: {filename}",
            data=buffer.getvalue(),
            file_name=f"{filename}.png",
            mime="image/png",
            use_container_width=True
        )
    except Exception:
        st.caption("💡 Tip: Pro stažení obrázku použij ikonu fotoaparátu 📷, která se objeví v pravém horním rohu grafu po najetí myší.")

def render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE):
    """Vykreslí kartu Rentgen (Tab 1 Analýzy) - FINAL VERZE"""
    st.write("")

    # Výběr akcie
    vybrana_akcie = st.selectbox("Vyber firmu:", df['Ticker'].unique() if not df.empty else [])

    if vybrana_akcie:
        with st.spinner(f"Načítám rentgen pro {vybrana_akcie}..."):
            t_info, hist_data = ziskej_detail_akcie(vybrana_akcie)

            if t_info or (hist_data is not None and not hist_data.empty):
                try:
                    long_name = t_info.get('longName', vybrana_akcie) if t_info else vybrana_akcie
                    summary = t_info.get('longBusinessSummary', '') if t_info else ''
                    recommendation = t_info.get('recommendationKey', 'N/A').upper().replace('_', ' ') if t_info else 'N/A'
                    target_price = t_info.get('targetMeanPrice', 0) if t_info else 0
                    pe_ratio = t_info.get('trailingPE', 0) if t_info else 0
                    currency = t_info.get('currency', '?') if t_info else '?'
                    current_price = t_info.get('currentPrice', 0) if t_info else 0
                    profit_margin = t_info.get('profitMargins', 0)
                    roe = t_info.get('returnOnEquity', 0)
                    rev_growth = t_info.get('revenueGrowth', 0)
                    debt_equity = t_info.get('debtToEquity', 0)
                    insiders = t_info.get('heldPercentInsiders', 0)
                    institutions = t_info.get('heldPercentInstitutions', 0)
                    public = max(0, 1.0 - insiders - institutions)

                    if (not summary or summary == "MISSING_SUMMARY" or "Yahoo" in summary) and AI_AVAILABLE:
                        try:
                            summary = "Popis není k dispozici."
                        except: summary = "Popis není k dispozici."
                    elif not summary or "Yahoo" in summary: summary = "Popis není k dispozici."

                    # --- 1. SEKCE ---
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
                        # ČISTÝ NADPIS (BEZ UPDATE)
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

                        fig_own.update_layout(
                            height=300,
                            margin=dict(l=0, r=0, t=10, b=10),
                            paper_bgcolor="rgba(0,0,0,0)",
                            showlegend=True,
                            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
                            font=dict(size=14)
                        )
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

def render_analýza_rebalancing_page(df, vdf, kurzy):
    """Vykreslí Rebalanční kalkulačku (Tab7 Analýzy)."""
    st.subheader("⚖️ REBALANČNÍ KALKULAČKA")
    if not vdf.empty:
        df_reb = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
        total_val = df_reb['HodnotaUSD'].sum()
        st.write("Nastav cílové váhy pro sektory:")

        # Abychom se vyhnuli problémům s klíči, musíme zajistit, že klíče jsou konzistentní
        targets = {};
        cols = st.columns(3)
        for i, row in df_reb.iterrows():
            current_pct = (row['HodnotaUSD'] / total_val) * 100
            # Využití klíčů Session State pro uchování hodnoty slideru
            key = f"reb_{row['Sektor']}"
            with cols[i % 3]:
                targets[row['Sektor']] = st.number_input(
                    f"{row['Sektor']} (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(round(current_pct, 1)),
                    step=1.0,
                    key=key
                )

        total_target = sum(targets.values())
        if abs(total_target - 100) > 0.1: st.warning(f"⚠️ Součet cílů je {total_target:.1f}%. Měl by být 100%.")

        df_reb['Cíl %'] = df_reb['Sektor'].map(targets)
        df_reb['Cílová Hodnota'] = total_val * (df_reb['Cíl %'] / 100)
        df_reb['Rozdíl'] = df_reb['Cílová Hodnota'] - df_reb['HodnotaUSD']

        st.divider(); st.subheader("🛠️ Návrh akcí")
        for _, r in df_reb.iterrows():
            diff = r['Rozdíl']
            if abs(diff) > 1:
                if diff > 0: st.success(f"🟢 **{r['Sektor']}**: DOKOUPIT za {diff:,.0f} USD")
                else: st.error(f"🔴 **{r['Sektor']}**: PRODAT za {abs(diff):,.0f} USD")

        st.dataframe(df_reb.style.format({"HodnotaUSD": "{:,.0f}", "Cílová Hodnota": "{:,.0f}", "Rozdíl": "{:+,.0f}"}))
    else:
        st.info("Portfolio je prázdné.")

def render_analýza_korelace_page(df, kurzy):
    """Vykreslí Matice Korelace (Tab8 Analýzy)."""
    st.subheader("📊 MATICE KORELACE (Diversifikace)")
    st.info("Jak moc se tvé akcie hýbou společně? Čím více 'modrá', tím lepší diverzifikace.")

    if not df.empty:
        tickers_list = df['Ticker'].unique().tolist()
        if len(tickers_list) > 1:
            try:
                with st.spinner("Počítám korelace..."):
                    hist_data = download_stock_history(tickers_list, period="1y")['Close']
                    returns = hist_data.pct_change().dropna()
                    corr_matrix = returns.corr()

                    fig_corr = px.imshow(corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", origin='lower')
                    fig_corr.update_layout(template="plotly_dark", height=600, font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")

                    fig_corr = make_plotly_cyberpunk(fig_corr)
                    st.plotly_chart(fig_corr, use_container_width=True)

                    avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix.values, 1)].mean()
                    st.metric("Průměrná korelace portfolia", f"{avg_corr:.2f}")

                    if avg_corr > 0.7: st.error("⚠️ Vysoká korelace! Tvé akcie se hýbou stejně.")
                    elif avg_corr < 0.3: st.success("✅ Nízká korelace! Dobrá diverzifikace.")
                    else: st.warning("⚖️ Střední korelace. Portfolio je vyvážené.")
            except Exception as e:
                st.error(f"Chyba při výpočtu korelace: {e}")
        else:
            st.warning("Pro výpočet korelace potřebuješ alespoň 2 různé akcie.")
    else:
        st.info("Portfolio je prázdné.")

def render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd):
    """Vykreslí Měnový simulátor (Tab6 Analýzy)."""
    st.subheader("💱 MĚNOVÝ SIMULÁTOR")
    st.info("Jak změna kurzu koruny ovlivní hodnotu tvého portfolia?")
    assets_by_curr = {"USD": 0, "EUR": 0, "CZK": 0}

    if viz_data_list:
        if isinstance(viz_data_list, pd.DataFrame):
            data_to_use = viz_data_list.to_dict('records')
        else:
            data_to_use = viz_data_list

        for item in data_to_use:
            curr = item['Měna']; val = item['Hodnota']
            if curr in assets_by_curr: assets_by_curr[curr] += val
            else: assets_by_curr["USD"] += item['HodnotaUSD'] # Zajištění, že se používá HodnotaUSD

    kurz_usd_now = kurzy.get("CZK", 20.85)
    kurz_eur_now = kurzy.get("EUR", 1.16) * kurz_usd_now

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        sim_usd = st.slider(f"Kurz USD/CZK (Aktuálně: {kurz_usd_now:.2f})", 15.0, 30.0, float(kurz_usd_now))
    with col_s2:
        sim_eur = st.slider(f"Kurz EUR/CZK (Aktuálně: {kurz_eur_now:.2f})", 15.0, 35.0, float(kurz_eur_now))

    val_now_czk = (assets_by_curr["USD"] * kurz_usd_now) + (assets_by_curr["EUR"] * kurz_eur_now) + assets_by_curr["CZK"]
    val_sim_czk = (assets_by_curr["USD"] * sim_usd) + (assets_by_curr["EUR"] * sim_eur) + assets_by_curr["CZK"]
    diff = val_sim_czk - val_now_czk

    st.divider()
    c_m1, c_m2 = st.columns(2)
    c_m1.metric("Hodnota Portfolia (Simulace)", f"{val_sim_czk:,.0f} Kč", delta=f"{diff:,.0f} Kč")

    impact_data = pd.DataFrame({
        "Měna": ["USD Aktiva", "EUR Aktiva", "CZK Aktiva"],
        "Hodnota CZK (Teď)": [assets_by_curr["USD"] * kurz_usd_now, assets_by_curr["EUR"] * kurz_eur_now, assets_by_curr["CZK"]],
        "Hodnota CZK (Simulace)": [assets_by_curr["USD"] * sim_usd, assets_by_curr["EUR"] * kurz_eur_now, assets_by_curr["CZK"]]
    })

    fig_curr = go.Figure(data=[
        go.Bar(name='Teď', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Teď)"], marker_color='#555555'),
        go.Bar(name='Simulace', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Simulace)"], marker_color='#00CC96')
    ])
    fig_curr.update_layout(barmode='group', template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0), font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig_curr.update_xaxes(showgrid=False)
    fig_curr.update_yaxes(showgrid=True, gridcolor='#30363D')
    fig_curr = make_plotly_cyberpunk(fig_curr)
    st.plotly_chart(fig_curr, use_container_width=True)


def render_analýza_kalendář_page(df, df_watch, LIVE_DATA):
    """Vykreslí Kalendář výsledků (Tab9 Analýzy)."""
    st.subheader("📅 KALENDÁŘ VÝSLEDKŮ (Earnings)")
    st.info("Termíny zveřejňování hospodářských výsledků tvých firem. Očekávej volatilitu!")

    all_my_tickers = []
    if not df.empty:
        all_my_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty:
        all_my_tickers.extend(df_watch['Ticker'].unique().tolist())
    all_my_tickers = list(set(all_my_tickers))

    if all_my_tickers:
        earnings_data = []
        with st.spinner(f"Skenuji kalendáře pro {len(all_my_tickers)} firem..."):
            prog_bar = st.progress(0)
            for i, tk in enumerate(all_my_tickers):
                try:
                    e_date = ziskej_earnings_datum(tk)
                    if e_date:
                        if hasattr(e_date, 'date'):
                            e_date_norm = datetime.combine(e_date, datetime.min.time())
                        else:
                            e_date_norm = pd.to_datetime(e_date).to_pydatetime()

                        days_left = (e_date_norm - datetime.now()).days

                        status = "V budoucnu"
                        color_icon = "⚪️"

                        if 0 <= days_left <= 7:
                            status = f"🔥 POZOR! Za {days_left} dní"
                            color_icon = "🔴"
                            st.toast(f"⚠️ {tk} má výsledky za {days_left} dní!", icon="📢")
                        elif 7 < days_left <= 30:
                            status = f"Blíží se (za {days_left} dní)"
                            color_icon = "🟡"
                        elif days_left < 0:
                            status = "Již proběhlo"
                            color_icon = "✔️"
                        else:
                            status = f"Za {days_left} dní"
                            color_icon = "🟢"

                        if days_left > -7:
                            earnings_data.append({
                                "Symbol": tk,
                                "Datum": e_date_norm.strftime("%d.%m.%Y"),
                                "Dní do akce": days_left,
                                "Status": status,
                                "Ikona": color_icon
                            })
                except Exception:
                    pass
                try:
                    prog_bar.progress((i + 1) / len(all_my_tickers))
                except Exception:
                    pass
            prog_bar.empty()

        if earnings_data:
            df_cal = pd.DataFrame(earnings_data).sort_values('Dní do akce')
            try:
                st.dataframe(
                    df_cal,
                    column_config={
                        "Ikona": st.column_config.TextColumn("Riziko", width="small"),
                        "Dní do akce": st.column_config.NumberColumn("Odpočet (dny)", format="%d")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            except Exception:
                st.dataframe(df_cal, use_container_width=True)

            try:
                df_future = df_cal[df_cal['Dní do akce'] >= 0].copy()
                if not df_future.empty:
                    df_future['Datum_ISO'] = pd.to_datetime(df_future['Datum'], format="%d.%m.%Y")
                    fig_timeline = px.scatter(
                        df_future,
                        x="Datum_ISO",
                        y="Symbol",
                        color="Dní do akce",
                        color_continuous_scale="RdYlGn_r",
                        size=[20] * len(df_future),
                        title="Časová osa výsledkové sezóny",
                        template="plotly_dark"
                    )
                    fig_timeline.update_layout(
                        height=300,
                        xaxis_title="Datum",
                        yaxis_title="",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_family="Roboto Mono"
                    )
                    try:
                        fig_timeline = make_plotly_cyberpunk(fig_timeline)
                    except Exception:
                        pass
                    st.plotly_chart(fig_timeline, use_container_width=True)
            except Exception as e:
                st.error(f"Chyba timeline: {e}")
        else:
            st.info("Žádná data o výsledcích nebyla nalezena (nebo jsou příliš daleko).")
    else:
        st.warning("Nemáš žádné akcie v portfoliu ani ve sledování.")

def render_analýza_page(df, df_watch, vdf, model, AI_AVAILABLE, kurzy, celk_hod_usd, hist_vyvoje, viz_data_list, celk_hod_czk, LIVE_DATA):
    st.title("📈 HLOUBKOVÁ ANALÝZA")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA & SEKTORY", "🔮 VĚŠTEC", "🏆 BENCHMARK", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE", "📅 KALENDÁŘ"])

    with tab1:
        render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE)

    with tab2:
        st.subheader("⚔️ SROVNÁNÍ VÝKONNOSTI AKCIÍ")

        portfolio_tickers = df['Ticker'].unique().tolist() if not df.empty else []
        default_tickers = ['AAPL', 'MSFT', '^GSPC']
        initial_selection = list(set(portfolio_tickers[:5] + ['^GSPC']))

        tickers_to_compare = st.multiselect(
            "Vyberte akcie/indexy pro srovnání výkonnosti:",
            options=list(set(default_tickers + portfolio_tickers)),
            default=initial_selection,
            key="multi_compare"
        )

        if tickers_to_compare:
            try:
                with st.spinner(f"Stahuji historická data pro {len(tickers_to_compare)} tickerů..."):
                    raw_data = download_stock_history(tickers_to_compare, period="1y", interval="1d")['Close']

                if raw_data.empty:
                    st.warning("Nepodařilo se načíst historická data pro vybrané tickery.")
                else:
                    # Normalizace (Start na 0%)
                    normalized_data = raw_data.apply(lambda x: (x / x.iloc[0] - 1) * 100)

                    fig_multi_comp = px.line(
                        normalized_data,
                        title='Normalizovaná výkonnost (Změna v %) od počátku',
                        template="plotly_dark"
                    )

                    # --- VYLEPŠENÍ PRO MOBIL (LEGENDA DOLE) ---
                    fig_multi_comp.update_layout(
                        xaxis_title="Datum",
                        yaxis_title="Změna (%)",
                        height=500,
                        margin=dict(t=50, b=0, l=0, r=0),
                        font_family="Roboto Mono",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        legend=dict(
                            orientation="h",  # Horizontální legenda
                            yanchor="bottom",
                            y=-0.2,           # Posunutá pod graf
                            xanchor="center",
                            x=0.5
                        )
                    )
                    fig_multi_comp.update_xaxes(showgrid=False)
                    fig_multi_comp.update_yaxes(showgrid=True, gridcolor='#30363D')
                    st.plotly_chart(fig_multi_comp, use_container_width=True, key="fig_srovnani")
                    add_download_button(fig_multi_comp, "srovnani_akcii")

                    st.divider()
                    st.subheader("Detailní srovnání metrik")

                    # Tabulka metrik (zůstává stejná, je super)
                    comp_list = []
                    # Omezíme to na max 4 pro přehlednost v tabulce, nebo necháme vše
                    for t in tickers_to_compare[:4]:
                        i, h = cached_detail_akcie(t)
                        if i:
                            mc = i.get('marketCap', 0)
                            pe = i.get('trailingPE', 0)
                            dy = i.get('dividendYield', 0)
                            # Bezpečný výpočet změny
                            perf = 0
                            if h is not None and not h.empty:
                                start_p = h['Close'].iloc[0]
                                end_p = h['Close'].iloc[-1]
                                if start_p != 0:
                                    perf = ((end_p / start_p) - 1) * 100

                            comp_list.append({
                                "Metrika": [f"Kapitalizace", f"P/E Ratio", f"Dividenda", f"Změna 1R"],
                                "Hodnota": [
                                    f"${mc/1e9:.1f}B",
                                    f"{pe:.2f}" if pe > 0 else "N/A",
                                    f"{dy*100:.2f}%" if dy else "0%",
                                    f"{perf:+.2f}%"
                                ],
                                "Ticker": t
                            })

                    if comp_list:
                        # Transpozice pro hezčí tabulku: Sloupce = Tickery, Řádky = Metriky
                        final_data = {"Metrika": comp_list[0]["Metrika"]}
                        for item in comp_list:
                            final_data[item["Ticker"]] = item["Hodnota"]

                        st.dataframe(pd.DataFrame(final_data), use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Chyba při stahování dat: {e}")
        else:
            st.info("Vyberte alespoň jeden ticker.")

    with tab3:
        if not vdf.empty:
            st.subheader("🌍 MAPA IMPÉRIA")
            try:
                df_map = vdf.groupby('Země')['HodnotaUSD'].sum().reset_index()
                fig_map = px.scatter_geo(
                    df_map,
                    locations="Země",
                    locationmode="country names",
                    hover_name="Země",
                    size="HodnotaUSD",
                    projection="orthographic",
                    color="Země",
                    template="plotly_dark"
                )
                fig_map.update_geos(
                    bgcolor="#161B22",
                    showcountries=True,
                    countrycolor="#30363D",
                    showocean=True,
                    oceancolor="#0E1117",
                    showland=True,
                    landcolor="#1c2128"
                )
                fig_map.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    font={"color": "white", "family": "Roboto Mono"},
                    height=500,
                    margin={"r": 0, "t": 0, "l": 0, "b": 0}
                )

                try:
                    fig_map = make_plotly_cyberpunk(fig_map)
                except Exception:
                    pass

                st.plotly_chart(fig_map, use_container_width=True, key="fig_mapa_imperia")
                add_download_button(fig_map, "mapa_imperia")
            except Exception as e:
                st.error(f"Chyba mapy: {e}")

            st.divider()
            st.caption("MAPA TRHU (Sektory)")

            try:
                if vdf.empty:
                    st.info("Portfolio je prázdné.")
                else:
                    treemap_fig = px.treemap(
                        vdf,
                        path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'],
                        values='HodnotaUSD',
                        color='Zisk',
                        color_continuous_scale=['red', '#161B22', 'green'],
                        color_continuous_midpoint=0
                    )
                    treemap_fig.update_layout(
                        font_family="Roboto Mono",
                        paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=30, l=10, r=10, b=10),
                        title="Treemap: rozložení podle sektorů"
                    )

                    try:
                        treemap_fig = make_plotly_cyberpunk(treemap_fig)
                    except Exception:
                        pass

                    st.plotly_chart(treemap_fig, use_container_width=True, key="fig_sektor_map")
                    add_download_button(treemap_fig, "mapa_sektoru")

                    if 'Datum' in df.columns and 'Cena' in df.columns and not df.empty:
                        try:
                            # Toto je zbytečný řádek, pokud už máš treemap výše, ale ponecháno pro zachování původního kódu
                            line_fig = px.line(df.sort_values('Datum'), x='Datum', y='Cena', title='Vývoj ceny', markers=True)
                            line_fig.update_layout(
                                paper_bgcolor="rgba(0,0,0,0)",
                                font_family="Roboto Mono",
                                margin=dict(t=30, l=10, r=10, b=10)
                            )
                            try:
                                line_fig = make_plotly_cyberpunk(line_fig)
                            except Exception:
                                pass

                            st.plotly_chart(line_fig, use_container_width=True, key="fig_vyvoj_ceny")
                            add_download_button(line_fig, "vyvoj_ceny")
                        except Exception:
                            st.warning("Nepodařilo se vykreslit graf vývoje ceny.")
            except Exception:
                st.error("Chyba mapy.")
        else:
            st.info("Portfolio je prázdné.")

    with tab4:
        st.subheader("🔮 FINANČNÍ STROJ ČASU")
        st.caption("Pokročilé simulace budoucnosti a zátěžové testy.")

        # --- 1. AI PREDIKCE ---
        with st.expander("🤖 AI PREDIKCE (Neuro-Věštec)", expanded=False):
            st.info("Experimentální modul využívající model Prophet (Meta) k predikci trendu.")

            c_ai1, c_ai2 = st.columns(2)
            with c_ai1:
                pred_ticker = st.text_input("Ticker pro predikci:", value="BTC-USD").upper()
            with c_ai2:
                pred_days = st.slider("Predikce na (dny):", 7, 90, 30)

            if st.button("🧠 AKTIVOVAT NEURONOVOU SÍŤ", type="primary"):
                try:
                    from prophet import Prophet
                    with st.spinner(f"Trénuji model na datech {pred_ticker}..."):
                        hist_train = download_stock_history(pred_ticker, period="2y")

                        if not hist_train.empty:
                            if isinstance(hist_train.columns, pd.MultiIndex):
                                y_data = hist_train['Close'].iloc[:, 0]
                            else:
                                y_data = hist_train['Close']

                            df_prophet = pd.DataFrame({'ds': y_data.index.tz_localize(None), 'y': y_data.values})
                            m = Prophet(daily_seasonality=True)
                            m.fit(df_prophet)
                            future = m.make_future_dataframe(periods=pred_days)
                            forecast = m.predict(future)

                            st.divider()
                            last_price = df_prophet['y'].iloc[-1]
                            future_price = forecast['yhat'].iloc[-1]
                            pct_pred = ((future_price - last_price) / last_price) * 100

                            c_res1, c_res2 = st.columns(2)
                            c_res1.metric("Cena dnes", f"{last_price:,.2f}")
                            c_res2.metric(f"Predikce (+{pred_days} dní)", f"{future_price:,.2f}", f"{pct_pred:+.2f} %")

                            fig_pred = go.Figure()
                            fig_pred.add_trace(go.Scatter(x=df_prophet['ds'], y=df_prophet['y'], name='Historie', line=dict(color='gray')))
                            future_part = forecast[forecast['ds'] > df_prophet['ds'].iloc[-1]]
                            fig_pred.add_trace(go.Scatter(x=future_part['ds'], y=future_part['yhat'], name='Predikce', line=dict(color='#58A6FF', width=3)))
                            fig_pred.add_trace(go.Scatter(
                                x=pd.concat([future_part['ds'], future_part['ds'][::-1]]),
                                y=pd.concat([future_part['yhat_upper'], future_part['yhat_lower'][::-1]]),
                                fill='toself', fillcolor='rgba(88, 166, 255, 0.2)',
                                line=dict(color='rgba(255,255,255,0)'), name='Rozptyl'
                            ))
                            fig_pred.update_layout(template="plotly_dark", height=400, paper_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig_pred, use_container_width=True)
                        else: st.error("Nedostatek dat.")
                except Exception as e: st.error(f"Chyba Prophet: {e}")

        # --- 2. DCA BACKTESTER ---
        with st.expander("⏳ DCA BACKTESTER (Stroj času)", expanded=False):
            st.info("Kolik bys měl, kdyby jsi pravidelně investoval v minulosti?")
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                dca_ticker = st.text_input("Ticker:", value="BTC-USD", key="dca_t").upper()
                dca_years = st.slider("Délka (roky)", 1, 10, 5, key="dca_y")
            with c_d2:
                dca_amount = st.number_input("Měsíční vklad (Kč)", value=2000, step=500, key="dca_a")

            if st.button("🚀 SPUSTIT SIMULACI", key="btn_dca"):
                with st.spinner("Počítám..."):
                    try:
                        start = datetime.now() - timedelta(days=dca_years*365)
                        start_str = start.strftime('%Y-%m-%d')
                        hist = download_stock_history_from_start(dca_ticker, start_date=start_str, interval="1mo")['Close']
                        if isinstance(hist, pd.DataFrame): hist = hist.iloc[:, 0]
                        hist = hist.dropna()

                        rate = 1.0 if ".PR" in dca_ticker else kurzy.get("CZK", 21)
                        inv_total = 0; shares = 0; evol = []

                        for d, p in hist.items():
                            p_czk = p * rate
                            shares += dca_amount / p_czk
                            inv_total += dca_amount
                            evol.append({"Datum": d, "Hodnota": shares * p_czk, "Vklad": inv_total})

                        df_dca = pd.DataFrame(evol).set_index("Datum")
                        fin_val = df_dca["Hodnota"].iloc[-1]
                        profit = fin_val - inv_total

                        c1, c2 = st.columns(2)
                        c1.metric("Vloženo", f"{inv_total:,.0f} Kč")
                        c2.metric("Hodnota DNES", f"{fin_val:,.0f} Kč", f"{profit:+,.0f} Kč")

                        fig_dca = px.area(df_dca, x=df_dca.index, y=["Hodnota", "Vklad"],
                                          color_discrete_map={"Hodnota": "#00CC96", "Vklad": "#AB63FA"}, template="plotly_dark")
                        fig_dca.update_layout(height=400, paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.2))
                        st.plotly_chart(fig_dca, use_container_width=True)
                    except Exception as e: st.error(f"Chyba: {e}")

        # --- 3. EFEKTIVNÍ HRANICE ---
        with st.expander("📊 EFEKTIVNÍ HRANICE (Optimalizace)", expanded=False):
            tickers_ef = df['Ticker'].unique().tolist()
            if len(tickers_ef) < 2:
                st.warning("Potřebuješ alespoň 2 akcie v portfoliu.")
            else:
                st.write(f"Optimalizace pro: {', '.join(tickers_ef)}")
                if st.button("📈 Vypočítat optimální portfolio"):
                    with st.spinner("Simuluji 5000 portfolií..."):
                        try:
                            data = download_stock_history(tickers_ef, period="2y")['Close']
                            returns = np.log(data / data.shift(1)).dropna()
                            results = np.zeros((3, 5000))
                            for i in range(5000):
                                w = np.random.random(len(tickers_ef)); w /= np.sum(w)
                                ret = np.sum(returns.mean() * w) * 252
                                vol = np.sqrt(np.dot(w.T, np.dot(returns.cov() * 252, w)))
                                results[0,i] = vol; results[1,i] = ret; results[2,i] = (ret - 0.04) / vol

                            max_sharpe_idx = results[2].argmax()
                            sd_p, ret_p = results[0, max_sharpe_idx], results[1, max_sharpe_idx]

                            c1, c2 = st.columns(2)
                            c1.metric("Max Sharpe Výnos", f"{ret_p*100:.1f}%")
                            c2.metric("Riziko (Volatilita)", f"{sd_p*100:.1f}%")

                            fig_ef = go.Figure(go.Scatter(x=results[0], y=results[1], mode='markers', marker=dict(color=results[2], showscale=True)))
                            fig_ef.add_trace(go.Scatter(x=[sd_p], y=[ret_p], marker=dict(color='red', size=15), name='TOP'))
                            fig_ef.update_layout(template="plotly_dark", height=400, xaxis_title="Riziko", yaxis_title="Výnos", paper_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig_ef, use_container_width=True)
                        except: st.error("Chyba výpočtu.")

        # --- 4. SLOŽENÉ ÚROČENÍ ---
        with st.expander("💰 SLOŽENÉ ÚROČENÍ (Kalkulačka)", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                vklad_mes = st.number_input("Měsíčně (Kč)", 500, 100000, 5000, step=500)
                urok_pa = st.slider("Úrok p.a. (%)", 1, 15, 8)
            with c2:
                roky_spo = st.slider("Délka (let)", 5, 40, 20)

            data_urok = []
            total = celk_hod_czk; vlozeno = celk_hod_czk
            for r in range(1, roky_spo + 1):
                vlozeno += vklad_mes * 12
                total = (total + vklad_mes * 12) * (1 + urok_pa/100)
                data_urok.append({"Rok": datetime.now().year + r, "Hodnota": total, "Vklady": vlozeno})

            df_urok = pd.DataFrame(data_urok)
            zisk_final = df_urok.iloc[-1]['Hodnota'] - df_urok.iloc[-1]['Vklady']

            st.metric(f"Za {roky_spo} let budeš mít", f"{df_urok.iloc[-1]['Hodnota']:,.0f} Kč", f"Zisk z úroků: {zisk_final:,.0f} Kč")

            fig_urok = px.area(df_urok, x="Rok", y=["Hodnota", "Vklady"], color_discrete_map={"Hodnota": "#00CC96", "Vklady": "#333333"}, template="plotly_dark")
            fig_urok.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig_urok, use_container_width=True)

        # --- 5. MONTE CARLO ---
        with st.expander("🎲 MONTE CARLO (Simulace)", expanded=False):
            c1, c2 = st.columns(2)
            mc_years = c1.slider("Roky", 1, 20, 5)
            mc_vol = c2.slider("Volatilita %", 10, 50, 20) / 100

            if st.button("🔮 SPUSTIT MONTE CARLO"):
                sims = []
                start = celk_hod_czk if celk_hod_czk > 0 else 100000
                for _ in range(30): # 30 simulací stačí pro mobil
                    path = [start]
                    for _ in range(mc_years):
                        shock = np.random.normal(0.08, mc_vol) # 8% průměrný výnos
                        path.append(path[-1] * (1 + shock))
                    sims.append(path)

                fig_mc = go.Figure()
                for s in sims: fig_mc.add_trace(go.Scatter(y=s, mode='lines', opacity=0.3, showlegend=False))
                avg_end = np.mean([s[-1] for s in sims])
                fig_mc.add_trace(go.Scatter(y=[np.mean([s[i] for s in sims]) for i in range(mc_years+1)], mode='lines', line=dict(color='yellow', width=4), name='Průměr'))

                st.metric("Očekávaný výsledek (Průměr)", f"{avg_end:,.0f} Kč")
                fig_mc.update_layout(template="plotly_dark", height=400, paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_mc, use_container_width=True)

        # --- 6. CRASH TEST ---
        with st.expander("💥 CRASH TEST (Zátěžová zkouška)", expanded=False):
            st.info("Co se stane s portfoliem, když přijde krize?")

            scenarios = {
                "COVID-19 (2020)": {"drop": 34, "desc": "Pandemie (-34%)"},
                "Finanční krize (2008)": {"drop": 57, "desc": "Hypoteční krize (-57%)"},
                "Dot-com bublina (2000)": {"drop": 49, "desc": "Tech bublina (-49%)"},
                "Black Monday (1987)": {"drop": 22, "desc": "Bleskový pád (-22%)"}
            }

            # Výběr scénáře (Selectbox je lepší pro mobil než 4 tlačítka)
            selected_scen = st.selectbox("Vyber historický scénář:", list(scenarios.keys()))
            manual_drop = st.slider("Nebo nastav vlastní propad (%)", 0, 90, scenarios[selected_scen]['drop'])

            ztrata = celk_hod_czk * (manual_drop / 100)
            zbytek = celk_hod_czk - ztrata

            c1, c2 = st.columns(2)
            c1.metric("Ztráta", f"-{ztrata:,.0f} Kč", f"-{manual_drop}%")
            c2.metric("Zůstatek", f"{zbytek:,.0f} Kč")

            fig_crash = px.pie(values=[ztrata, zbytek], names=["Ztráta", "Zůstatek"],
                               color_discrete_sequence=["#da3633", "#238636"], hole=0.5, template="plotly_dark")
            fig_crash.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            # Text doprostřed
            fig_crash.add_annotation(text=f"-{manual_drop}%", showarrow=False, font=dict(size=20, color="white"))
            st.plotly_chart(fig_crash, use_container_width=True)


    with tab5:
        st.subheader("🏆 SROVNÁNÍ S TRHEM (S&P 500)")
        st.caption("Porážíš trh, nebo trh poráží tebe?")

        if not hist_vyvoje.empty and len(hist_vyvoje) > 1:
            user_df = hist_vyvoje.copy()
            user_df['Date'] = pd.to_datetime(user_df['Date']); user_df = user_df.sort_values('Date').set_index('Date')
            start_val = user_df['TotalUSD'].iloc[0]
            if start_val > 0: user_df['MyReturn'] = ((user_df['TotalUSD'] / start_val) - 1) * 100
            else: user_df['MyReturn'] = 0
            start_date = user_df.index[0].strftime('%Y-%m-%d')

            my_returns = user_df['TotalUSD'].pct_change().dropna()
            my_sharpe = calculate_sharpe_ratio(my_returns)

            # --- FIX: Ošetření NaN hodnot ---
            if pd.isna(my_sharpe) or np.isinf(my_sharpe): my_sharpe = 0.0

            try:
                sp500 = download_stock_history_from_start("^GSPC", start_date=start_date)
                if not sp500.empty:
                    if isinstance(sp500.columns, pd.MultiIndex): close_col = sp500['Close'].iloc[:, 0]
                    else: close_col = sp500['Close']
                    sp500_start = close_col.iloc[0]
                    sp500_norm = ((close_col / sp500_start) - 1) * 100
                    sp500_returns = close_col.pct_change().dropna()
                    sp500_sharpe = calculate_sharpe_ratio(sp500_returns)

                    # --- FIX: Ošetření NaN u S&P ---
                    if pd.isna(sp500_sharpe) or np.isinf(sp500_sharpe): sp500_sharpe = 0.0

                    # --- GRAF (Bez nadpisu, legenda dole) ---
                    fig_bench = go.Figure()
                    fig_bench.add_trace(go.Scatter(x=user_df.index, y=user_df['MyReturn'], mode='lines', name='Moje Portfolio', line=dict(color='#00CC96', width=3)))
                    fig_bench.add_trace(go.Scatter(x=sp500_norm.index, y=sp500_norm, mode='lines', name='S&P 500', line=dict(color='#808080', width=2, dash='dot')))
                    fig_bench.update_layout(
                        xaxis_title="", yaxis_title="Změna (%)", template="plotly_dark",
                        font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        height=400,
                        margin=dict(t=10, l=0, r=0, b=0), # Menší okraje nahoře
                        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center") # Legenda dole
                    )
                    fig_bench.update_xaxes(showgrid=False)
                    fig_bench.update_yaxes(showgrid=True, gridcolor='#30363D')
                    st.plotly_chart(fig_bench, use_container_width=True, key="fig_benchmark")

                    # --- METRIKY (GRID 2x2 a bez NaN) ---
                    my_last = user_df['MyReturn'].iloc[-1]; sp_last = sp500_norm.iloc[-1]; diff = my_last - sp_last

                    col_vy1, col_vy2 = st.columns(2)
                    with col_vy1: st.metric("Můj výnos", f"{my_last:+.2f} %")
                    with col_vy2: st.metric("S&P 500 výnos", f"{sp_last:+.2f} %", delta=f"{diff:+.2f} %")

                    st.write("")

                    col_sh1, col_sh2 = st.columns(2)
                    # Tady už se NaN neobjeví, ošetřili jsme to nahoře
                    with col_sh1: st.metric("Můj Sharpe", f"{my_sharpe:+.2f}", help="Riziko/Výnos (Vyšší je lepší)")
                    with col_sh2: st.metric("S&P 500 Sharpe", f"{sp500_sharpe:+.2f}")

                    if diff > 0: st.success("🎉 Gratuluji! Porážíš trh.")
                    else: st.warning("📉 Trh zatím vede.")

                else: st.warning("Nepodařilo se stáhnout data S&P 500.")
            except Exception as e: st.error(f"Chyba benchmarku: {e}")
        else: st.info("Pro srovnání potřebuješ historii alespoň za 2 dny.")


    with tab6:
        # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
        render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd)

    with tab7:
        # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
        render_analýza_rebalancing_page(df, vdf, kurzy)

    with tab8:
        # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
        render_analýza_korelace_page(df, kurzy)


    with tab9:
        # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
        render_analýza_kalendář_page(df, df_watch, LIVE_DATA)
