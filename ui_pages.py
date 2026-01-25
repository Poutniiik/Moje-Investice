import streamlit as st
import pandas as pd
import numpy as np                 # <--- Nové (pro korelace)
import yfinance as yf              # <--- Nové (pro stahování dat)
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta  # <--- Nové (pro kalendář)
from utils import (
    ziskej_detail_akcie, 
    make_plotly_cyberpunk, 
    ziskej_earnings_datum,  # <--- Nové (pro kalendář)
    ziskej_insider_transakce
)

# ... pod tím už je tvoje funkce render_analýza_rentgen_page ...

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

                    st.write("")
                    st.divider()
                    st.subheader("🕵️‍♂️ INSIDER RADAR")
                    st.caption("Co dělají ředitelé a manažeři se svými akciemi? (Zelená = Nákup, Červená = Prodej)")

                    # 1. Stáhneme data
                    insider_df = ziskej_insider_transakce(vybrana_akcie)

                    # 2. Pokud data máme, zobrazíme je
                    if insider_df is not None and not insider_df.empty:
                        # Spočítáme sentiment
                        pocet_nakupu = insider_df[insider_df['Popis transakce'].str.contains("Purchase", case=False, na=False)].shape[0]
                        pocet_prodeju = insider_df[insider_df['Popis transakce'].str.contains("Sale", case=False, na=False)].shape[0]

                        # Metriky vedle sebe
                        col_in1, col_in2 = st.columns([1, 3])
                        with col_in1:
                            st.metric("Nákupy vedení", pocet_nakupu)
                            st.metric("Prodeje vedení", pocet_prodeju, delta_color="inverse")
                        
                        with col_in2:
                            # Funkce pro barvení řádků
                            def highlight_insider(row):
                                text = str(row['Popis transakce']).lower()
                                if 'purchase' in text: # Nákup = Zelená
                                    return ['background-color: rgba(0, 255, 0, 0.1)'] * len(row)
                                elif 'sale' in text:   # Prodej = Červená
                                    return ['background-color: rgba(255, 0, 0, 0.1)'] * len(row)
                                else:
                                    return [''] * len(row)

                            # Vykreslení tabulky
                            st.dataframe(
                                insider_df.style.apply(highlight_insider, axis=1),
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Hodnota ($)": st.column_config.NumberColumn(format="$%.0f"),
                                    "Počet akcií": st.column_config.NumberColumn(format="%.0f ks")
                                }
                            )
                            
                            # Rychlé shrnutí situace
                            if pocet_nakupu > pocet_prodeju:
                                st.success("✅ **Býčí signál:** Vedení firmy v poslední době více nakupuje. Věří růstu!")
                            elif pocet_prodeju > pocet_nakupu:
                                st.warning("⚠️ **Opatrnost:** Vedení spíše prodává. Sledujte důvody.")
                            else:
                                st.info("⚖️ **Neutrál:** Aktivita vedení je vyrovnaná.")
                    else:
                        st.info(f"Pro ticker {vybrana_akcie} nejsou k dispozici data o insider transakcích (nebo je to ETF).")

                    st.divider()
                    st.subheader(f"📈 PROFESIONÁLNÍ CHART (SMA 50/200)")
                    
                    if hist_data is not None and not hist_data.empty:
                        # --- 1. VÝPOČET INDIKÁTORŮ (Magie) ---
                        # SMA 50 = Průměrná cena za posledních 50 dní (Modrá čára - Rychlá)
                        hist_data['SMA50'] = hist_data['Close'].rolling(window=50).mean()
                        # SMA 200 = Průměrná cena za posledních 200 dní (Oranžová čára - Pomalá)
                        hist_data['SMA200'] = hist_data['Close'].rolling(window=200).mean()

                        # --- 2. VYKRESLENÍ GRAFU ---
                        fig_candle = go.Figure()

                        # A) Svíčky (Cena)
                        fig_candle.add_trace(go.Candlestick(
                            x=hist_data.index,
                            open=hist_data['Open'],
                            high=hist_data['High'],
                            low=hist_data['Low'],
                            close=hist_data['Close'],
                            name='Cena'
                        ))

                        # B) SMA 50 (Trend)
                        fig_candle.add_trace(go.Scatter(
                            x=hist_data.index,
                            y=hist_data['SMA50'],
                            line=dict(color='#00FFFF', width=2), # Azurová
                            name='SMA 50 (Trend)'
                        ))

                        # C) SMA 200 (Dlouhodobý trend)
                        fig_candle.add_trace(go.Scatter(
                            x=hist_data.index,
                            y=hist_data['SMA200'],
                            line=dict(color='#FFA500', width=2), # Oranžová
                            name='SMA 200 (Dlouhodobý)'
                        ))

                        # --- 3. DESIGN (Cyberpunk Style) ---
                        fig_candle.update_layout(
                            template="plotly_dark", 
                            height=500, 
                            xaxis_rangeslider_visible=False, 
                            paper_bgcolor="rgba(0,0,0,0)",
                            legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"), # Legenda nahoře
                            hovermode="x unified" # Ukáže všechny hodnoty najednou při najetí myší
                        )
                        
                        st.plotly_chart(fig_candle, use_container_width=True)
                        
                        # Vysvětlivka pro tebe pod grafem
                        with st.expander("📚 Co znamenají ty čáry? (Nápověda)"):
                            st.markdown("""
                            * **🔵 SMA 50 (Modrá):** Krátkodobý trend. Pokud je cena NAD ní, je to dobré.
                            * **🟠 SMA 200 (Oranžová):** Dlouhodobý trend. To je "podlaha".
                            * **☠️ DEATH CROSS:** Když modrá překříží oranžovou směrem DOLŮ -> **PRODAT!**
                            * **🌟 GOLDEN CROSS:** Když modrá překříží oranžovou směrem NAHORU -> **NAKOUPIT!**
                            """)
                except Exception as e: 
                    st.error(f"Chyba zobrazení rentgenu: {e}")
            
           else:
               st.error("Nepodařilo se načíst data o firmě.")

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

# --- NOVÉ FUNKCE PRO ANALÝZU (Tabulky 6, 7, 8, 9) ---


def render_analýza_korelace_page(df, kurzy):
    """Vykreslí Matice Korelace (Tab8 Analýzy)."""
    st.subheader("📊 MATICE KORELACE (Diversifikace)")
    st.info("Jak moc se tvé akcie hýbou společně? Čím více 'modrá', tím lepší diverzifikace.")
    
    if not df.empty:
        tickers_list = df['Ticker'].unique().tolist()
        if len(tickers_list) > 1:
            try:
                with st.spinner("Počítám korelace..."):
                    hist_data = yf.download(tickers_list, period="1y")['Close']
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
                            color_icon = "🟢"
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

