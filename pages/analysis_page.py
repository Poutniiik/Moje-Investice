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
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import random
import matplotlib.pyplot as plt
from fpdf import FPDF

# Importujeme všechny potřebné externí a utilitní funkce
import utils
import ai_brain

# --- FINANČNÍ FUNKCE KTERÉ BYLY V PŮVODNÍM web_investice.py ---
# Kód musí používat utilitní funkce s cache, které jsou nyní v utils.py
# Např. utils.cached_detail_akcie namísto ziskej_detail_akcie

def render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE, LIVE_DATA):
    """Vykreslí kartu Rentgen (Tab 1 Analýzy)"""
    st.write("")
    vybrana_akcie = st.selectbox("Vyber firmu:", df['Ticker'].unique() if not df.empty else [])
    
    if vybrana_akcie:
        with st.spinner(f"Načítám rentgen pro {vybrana_akcie}..."):
            # POUŽITÍ CACHE WRAPPERU Z utils.py
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
        
        targets = {}; 
        cols = st.columns(3)
        for i, row in df_reb.iterrows():
            current_pct = (row['HodnotaUSD'] / total_val) * 100
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
                    # Přidáno auto_adjust=True pro potlačení FutureWarning
                    hist_data = yf.download(tickers_list, period="1y", auto_adjust=True)['Close']
                    returns = hist_data.pct_change().dropna()
                    corr_matrix = returns.corr()
                    
                    fig_corr = px.imshow(corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", origin='lower')
                    fig_corr.update_layout(template="plotly_dark", height=600, font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    
                    fig_corr = utils.make_plotly_cyberpunk(fig_corr)
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

def render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd, get_zustatky):
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
            curr = item['Měna'] 
            # Používáme Hodnota, ne HodnotaUSD pro přesnou simulaci
            val = item['Hodnota'] 
            
            if curr in assets_by_curr: assets_by_curr[curr] += val
            else: assets_by_curr["USD"] += item['HodnotaUSD'] # Pokud neznámá měna, přidáme do USD ekv.

    kurz_usd_now = kurzy.get("CZK", 20.85)
    # Přepočet EUR/CZK: EURUSD * USDCZK (Kurz EUR je v kurzy dict jako EUR/USD)
    kurz_eur_now = kurzy.get("EUR", 1.16) * kurz_usd_now 
    
    # Odebereme Hotovost ze zůstatku Portfolia, aby se simulace počítala jen pro AKCIE
    # Musíme zavolat get_zustatky předané z web_investice.py
    cash_in_curr = get_zustatky(st.session_state['user'])
    assets_by_curr['USD'] -= cash_in_curr.get('USD', 0)
    assets_by_curr['CZK'] -= cash_in_curr.get('CZK', 0)
    assets_by_curr['EUR'] -= cash_in_curr.get('EUR', 0)


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
    c_m1.metric("Hodnota Akcií (Simulace)", f"{val_sim_czk:,.0f} Kč", delta=f"{diff:,.0f} Kč")
    
    impact_data = pd.DataFrame({
        "Měna": ["USD Aktiva", "EUR Aktiva", "CZK Aktiva"],
        "Hodnota CZK (Teď)": [assets_by_curr["USD"] * kurz_usd_now, assets_by_curr["EUR"] * kurz_eur_now, assets_by_curr["CZK"]],
        "Hodnota CZK (Simulace)": [assets_by_curr["USD"] * sim_usd, assets_by_curr["EUR"] * sim_eur, assets_by_curr["CZK"]]
    })
    
    fig_curr = go.Figure(data=[
        go.Bar(name='Teď', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Teď)"], marker_color='#555555'),
        go.Bar(name='Simulace', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Simulace)"], marker_color='#00CC96')
    ])
    fig_curr.update_layout(barmode='group', template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0), font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig_curr.update_xaxes(showgrid=False)
    fig_curr.update_yaxes(showgrid=True, gridcolor='#30363D')
    fig_curr = utils.make_plotly_cyberpunk(fig_curr)
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
                    e_date = utils.ziskej_earnings_datum(tk)
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
                        fig_timeline = utils.make_plotly_cyberpunk(fig_timeline)
                    except Exception:
                        pass
                    st.plotly_chart(fig_timeline, use_container_width=True)
            except Exception as e:
                st.error(f"Chyba timeline: {e}")
        else:
            st.info("Žádná data o výsledcích nebyla nalezena (nebo jsou příliš daleko).")
    else:
        st.warning("Nemáš žádné akcie v portfoliu ani ve sledování.")

def render_souboj_page(df, kurzy, calculate_sharpe_ratio):
    """Vykreslí Srovnání výkonnosti (Tab 2 Analýzy)."""
    st.subheader("⚔️ SROVNÁNÍ VÝKONNOSTI AKCIÍ")

    # 1. Příprava seznamů tickerů
    portfolio_tickers = df['Ticker'].unique().tolist() if not df.empty else []
    default_tickers = ['AAPL', 'MSFT', '^GSPC', 'BTC-USD', 'GC=F']
    
    # Výchozí výběr: vezmeme max 5 tvých akcií a přidáme S&P 500 (^GSPC)
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
                # Přidáno auto_adjust=True pro potlačení varování
                raw_data = yf.download(tickers_to_compare, period="1y", interval="1d", progress=False, auto_adjust=True)['Close']

            if raw_data.empty:
                st.warning("Nepodařilo se načíst historická data pro vybrané tickery.")
            else:
                # Normalizace (Start na 0%) - aby všechny čáry začínaly ve stejném bodě
                normalized_data = raw_data.apply(lambda x: (x / x.iloc[0] - 1) * 100)

                # Vykreslení grafu
                fig_multi_comp = px.line(
                    normalized_data,
                    title='Normalizovaná výkonnost (Změna v %) od počátku',
                    template="plotly_dark"
                )
                
                # Stylování grafu (Cyberpunk + Legenda)
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
                
                # Aplikace neonového efektu (pokud je importovaný)
                try:
                    fig_multi_comp = utils.make_plotly_cyberpunk(fig_multi_comp)
                except: pass

                st.plotly_chart(fig_multi_comp, use_container_width=True, key="fig_srovnani")
                
                st.divider()
                st.subheader("Detailní srovnání metrik")

                # Tabulka metrik
                comp_list = []
                # Omezíme to na max 5 pro přehlednost v tabulce
                for t in tickers_to_compare[:5]: 
                    # Zde voláme cachovanou funkci z utils
                    i, h = utils.cached_detail_akcie(t)
                    if i:
                        mc = i.get('marketCap', 0)
                        pe = i.get('trailingPE', 0)
                        dy = i.get('dividendYield', 0)
                        
                        # Bezpečný výpočet změny za 1 rok
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
        st.info("Vyberte alespoň jeden ticker."))

def render_mapa_sektory_page(df, vdf):
    """Vykreslí Mapu trhu a Sektory (Tab 3 Analýzy)."""
    st.subheader("🗺️ MAPA IMPÉRIA (Treemap)")
    
    if not vdf.empty:
        # Příprava dat pro Treemap
        tree_df = vdf.copy()
        # Pro barvu použijeme 'Dnes' (denní změna) nebo 'Zisk' (celkový)
        tree_df['ColorScale'] = tree_df['Dnes'] * 100 # v procentech
        
        fig_tree = px.treemap(
            tree_df,
            path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'],
            values='HodnotaUSD',
            color='ColorScale',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=0,
            hover_data={'HodnotaUSD': ':,.0f', 'Dnes': ':.2%'},
            template="plotly_dark"
        )
        
        fig_tree.update_layout(margin=dict(t=30, l=10, r=10, b=10), font_family="Roboto Mono", height=500)
        st.plotly_chart(fig_tree, use_container_width=True)
        
        st.caption("🟥 Červená = Dnes klesá | 🟩 Zelená = Dnes roste | Velikost = Hodnota v USD")
    else:
        st.info("Nemáš žádné pozice pro zobrazení mapy.")

def render_vestec_page(df, kurzy, celk_hod_usd):
    """Vykreslí Stroj času (Tab 4 Analýzy)."""
    st.subheader("🔮 VĚŠTEC: Složené úročení")
    
    # Přepočet na CZK pro lepší představu
    start_czk = celk_hod_usd * kurzy.get("CZK", 20.85)
    
    c1, c2, c3 = st.columns(3)
    with c1: years = st.number_input("Počet let", 1, 40, 10)
    with c2: monthly = st.number_input("Měsíční vklad (Kč)", 0, 100000, 5000, step=500)
    with c3: rate = st.number_input("Očekávaný úrok (%)", 1.0, 20.0, 8.0, step=0.5) / 100
    
    # Výpočet
    future_vals = []
    total_invested = []
    current = start_czk
    invested = start_czk
    
    for i in range(years + 1):
        future_vals.append(current)
        total_invested.append(invested)
        current = current * (1 + rate) + (monthly * 12)
        invested += (monthly * 12)
        
    # Graf
    df_proj = pd.DataFrame({
        "Rok": range(datetime.now().year, datetime.now().year + years + 1),
        "Hodnota portfolia": future_vals,
        "Vložené peníze": total_invested
    })
    
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(x=df_proj["Rok"], y=df_proj["Hodnota portfolia"], fill='tozeroy', name="Hodnota s úroky", line=dict(color="#00CC96")))
    fig_proj.add_trace(go.Scatter(x=df_proj["Rok"], y=df_proj["Vložené peníze"], fill='tonexty', name="Jen vklady", line=dict(color="#AB63FA")))
    
    fig_proj.update_layout(title=f"Za {years} let budeš mít: {future_vals[-1]:,.0f} Kč", template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig_proj = utils.make_plotly_cyberpunk(fig_proj)
    st.plotly_chart(fig_proj, use_container_width=True)
    
    zisk_celkem = future_vals[-1] - total_invested[-1]
    st.metric("Celkový zisk z úroků", f"{zisk_celkem:,.0f} Kč")

def render_benchmark_page(df, kurzy, calculate_sharpe_ratio):
    """Vykreslí Srovnání s S&P 500 (Tab 5 Analýzy)."""
    st.subheader("🏆 VS. S&P 500")
    
    if not df.empty:
        my_top = df.groupby('Ticker')['Cena'].sum().sort_values(ascending=False).index[:1].tolist()
        if not my_top: my_top = ["AAPL"] # Fallback
        
        tickers = my_top + ["^GSPC"] # ^GSPC je S&P 500
        
        try:
            # Přidáno auto_adjust=True pro potlačení FutureWarning
            data = yf.download(tickers, period="1y", progress=False, auto_adjust=True)['Close']
            # Normalizace
            norm_data = (data / data.iloc[0]) * 100
            
            fig = px.line(norm_data, x=norm_data.index, y=norm_data.columns, title="Tvá TOP akcie vs Trh (1 rok)", template="plotly_dark")
            fig.update_layout(yaxis_title="Výkonnost (start=100)", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            fig = utils.make_plotly_cyberpunk(fig)
            st.plotly_chart(fig, use_container_width=True)
            
            # Sharpe Ratio (Jednoduchý odhad)
            returns = data.pct_change().dropna()
            sharpe_spy = calculate_sharpe_ratio(returns["^GSPC"]) if "^GSPC" in returns else 0
            
            # Bezpečné získání Sharpe pro mou akcii
            my_ticker_col = my_top[0]
            if my_ticker_col in returns:
                sharpe_me = calculate_sharpe_ratio(returns[my_ticker_col])
                
                c1, c2 = st.columns(2)
                c1.metric(f"Sharpe Ratio ({my_ticker_col})", f"{sharpe_me:.2f}")
                c2.metric("Sharpe Ratio (S&P 500)", f"{sharpe_spy:.2f}")
                
                if sharpe_me > sharpe_spy: st.success("🎉 Tvá hlavní akcie má lepší rizikově očištěný výnos než trh!")
                else: st.warning("⚠️ Trh má lepší poměr riziko/zisk.")
                
        except Exception as e:
            st.error(f"Data nedostupná: {e}")
    else:
        st.info("Portfolio je prázdné.")

def analysis_page(df, df_watch, vdf, model, AI_AVAILABLE, kurzy, viz_data_list, celk_hod_usd, get_zustatky, LIVE_DATA, calculate_sharpe_ratio):
    """
    Vykreslí celou stránku "📈 Analýza" pomocí tabů.
    """
    st.title("📈 HLOUBKOVÁ ANALÝZA")
        
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA & SEKTORY", "🔮 VĚŠTEC", "🏆 BENCHMARK", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE", "📅 KALENDÁŘ"])

    with tab1:
        render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE, LIVE_DATA)

    with tab2:
        render_souboj_page(df, kurzy, calculate_sharpe_ratio)

    with tab3:
        render_mapa_sektory_page(df, vdf)

    with tab4:
        render_vestec_page(df, kurzy, celk_hod_usd)

    with tab5:
        render_benchmark_page(df, kurzy, calculate_sharpe_ratio)
    
    with tab6:
        render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd, get_zustatky)

    with tab7:
        render_analýza_rebalancing_page(df, vdf, kurzy)

    with tab8:
        render_analýza_korelace_page(df, kurzy)

    with tab9:
        render_analýza_kalendář_page(df, df_watch, LIVE_DATA)

# --- ZDE JE NUTNÉ DEFINOVAT VŠECHNY OSTATNÍ ANALYTICKÉ FUNKCE ---

def render_vestec_page(df, kurzy, celk_hod_usd):
    """Vykreslí Stroj času (Tab 4 Analýzy)."""
    st.subheader("🔮 VĚŠTEC: Složené úročení")
    
    # Přepočet na CZK pro lepší představu
    start_czk = celk_hod_usd * kurzy.get("CZK", 20.85)
    
    c1, c2, c3 = st.columns(3)
    with c1: years = st.number_input("Počet let", 1, 40, 10)
    with c2: monthly = st.number_input("Měsíční vklad (Kč)", 0, 100000, 5000, step=500)
    with c3: rate = st.number_input("Očekávaný úrok (%)", 1.0, 20.0, 8.0, step=0.5) / 100
    
    # Výpočet
    future_vals = []
    total_invested = []
    current = start_czk
    invested = start_czk
    
    for i in range(years + 1):
        future_vals.append(current)
        total_invested.append(invested)
        current = current * (1 + rate) + (monthly * 12)
        invested += (monthly * 12)
        
    # Graf
    df_proj = pd.DataFrame({
        "Rok": range(datetime.now().year, datetime.now().year + years + 1),
        "Hodnota portfolia": future_vals,
        "Vložené peníze": total_invested
    })
    
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(x=df_proj["Rok"], y=df_proj["Hodnota portfolia"], fill='tozeroy', name="Hodnota s úroky", line=dict(color="#00CC96")))
    fig_proj.add_trace(go.Scatter(x=df_proj["Rok"], y=df_proj["Vložené peníze"], fill='tonexty', name="Jen vklady", line=dict(color="#AB63FA")))
    
    fig_proj.update_layout(title=f"Za {years} let budeš mít: {future_vals[-1]:,.0f} Kč", template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig_proj = utils.make_plotly_cyberpunk(fig_proj)
    st.plotly_chart(fig_proj, use_container_width=True)
    
    zisk_celkem = future_vals[-1] - total_invested[-1]
    st.metric("Celkový zisk z úroků", f"{zisk_celkem:,.0f} Kč")
    # Implementace logiky (zde by byla zkopírovaná logika z web_investice.py)

def render_benchmark_page(df, kurzy, calculate_sharpe_ratio):
    """Vykreslí Srovnání s S&P 500 (Tab 5 Analýzy)."""
    st.subheader("🏆 VS. S&P 500")
    
    if not df.empty:
        my_top = df.groupby('Ticker')['Cena'].sum().sort_values(ascending=False).index[:1].tolist()
        if not my_top: my_top = ["AAPL"] # Fallback
        
        tickers = my_top + ["^GSPC"] # ^GSPC je S&P 500
        
        try:
            # Přidáno auto_adjust=True pro potlačení FutureWarning
            data = yf.download(tickers, period="1y", progress=False, auto_adjust=True)['Close']
            # Normalizace
            norm_data = (data / data.iloc[0]) * 100
            
            fig = px.line(norm_data, x=norm_data.index, y=norm_data.columns, title="Tvá TOP akcie vs Trh (1 rok)", template="plotly_dark")
            fig.update_layout(yaxis_title="Výkonnost (start=100)", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            fig = utils.make_plotly_cyberpunk(fig)
            st.plotly_chart(fig, use_container_width=True)
            
            # Sharpe Ratio (Jednoduchý odhad)
            returns = data.pct_change().dropna()
            sharpe_spy = calculate_sharpe_ratio(returns["^GSPC"]) if "^GSPC" in returns else 0
            
            # Bezpečné získání Sharpe pro mou akcii
            my_ticker_col = my_top[0]
            if my_ticker_col in returns:
                sharpe_me = calculate_sharpe_ratio(returns[my_ticker_col])
                
                c1, c2 = st.columns(2)
                c1.metric(f"Sharpe Ratio ({my_ticker_col})", f"{sharpe_me:.2f}")
                c2.metric("Sharpe Ratio (S&P 500)", f"{sharpe_spy:.2f}")
                
                if sharpe_me > sharpe_spy: st.success("🎉 Tvá hlavní akcie má lepší rizikově očištěný výnos než trh!")
                else: st.warning("⚠️ Trh má lepší poměr riziko/zisk.")
                
        except Exception as e:
            st.error(f"Data nedostupná: {e}")
    else:
        st.info("Portfolio je prázdné.")
