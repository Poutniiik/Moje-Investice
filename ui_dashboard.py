import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from ai_brain import get_portfolio_health_score, get_voice_briefing_text, ask_ai_guard
from voice_engine import VoiceAssistant

@st.cache_data(ttl=3600)  # Pamatuje si skóre 1 hodinu
def get_cached_health_score(USER, _model, vdf_json, cash_usd, sentiment):
    vdf = pd.read_json(vdf_json)
    return get_portfolio_health_score(_model, vdf, cash_usd, sentiment)

@st.cache_data(ttl=3600)  # Pamatuje si text pozdravu 1 hodinu
def get_cached_briefing_text(USER, _model, score, sentiment):
    return get_voice_briefing_text(_model, USER, score, sentiment)

@st.cache_data(ttl=600)  # Pamatuje si tržní data 10 minut
def get_macro_data(tickers_tuple):
    return yf.download(list(tickers_tuple), period="5d", progress=False)['Close']

def render_dashboard(USER, vdf, cash_usd, model, AI_AVAILABLE, cached_fear_greed, 
                     kurzy, celk_hod_czk, celk_hod_usd, celk_inv_usd, zmena_24h, pct_24h):
    """
    Vykresluje horní část Dashboardu: Metriky, AI Diagnostiku, Sentiment a Kompas.
    Tato funkce byla vyčleněna z hlavního souboru pro lepší přehlednost.
    """
    
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
            
            # Získání Fear & Greed pro kontext AI
            score_fg, rating_fg = cached_fear_greed()
            sentiment_context = f"{rating_fg} ({score_fg}/100)" if score_fg else "Neutrální"
            
            try:
                # Výpočet skóre
                health = get_portfolio_health_score(model, vdf, cash_usd, sentiment_context)
                h_score = health.get('score', 50)

                # Automatický hlasový briefing (pouze 1x)
                if 'briefing_played' not in st.session_state:
                    with st.spinner("Attis AI připravuje hlášení..."):
                        briefing_text = get_voice_briefing_text(model, USER, h_score, sentiment_context)
                        audio_html = VoiceAssistant.speak(briefing_text)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                            st.session_state['briefing_played'] = True

                # UI Progress Bar
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
    
    # Příprava dat pro Best/Worst performery
    viz_data_list = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
    best = {"Ticker": "N/A", "Dnes": 0}
    worst = {"Ticker": "N/A", "Dnes": 0}
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
                makro_tickers = {"🇺🇸 S&P 500": "^GSPC", "🥇 Zlato": "GC=F", "₿ Bitcoin": "BTC-USD", "🏦 Úroky 10Y": "^TNX"}
                makro_data = yf.download(list(makro_tickers.values()), period="5d", progress=False)['Close']
                
                mc_cols = st.columns(4)
                for i, (name, ticker) in enumerate(makro_tickers.items()):
                    with mc_cols[i]:
                        series = makro_data[ticker].dropna()
                        if not series.empty:
                            last = series.iloc[-1]; prev = series.iloc[-2] if len(series) > 1 else last
                            delta = ((last - prev) / prev) * 100
                            st.metric(name, f"{last:,.0f}", f"{delta:+.2f}%")
            except Exception: 
                st.error("Chyba kompasu")
        
            # Ranní Briefing Button
            if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
                with st.container(border=True):
                    if st.button("🛡️ SPUSTIT RANNÍ AI BRIEFING", use_container_width=True):
                        with st.spinner("Analyzuji rizika..."):
                            res = ask_ai_guard(model, pct_24h, cash_usd, best.get('Ticker'), worst.get('Ticker'))
                            st.info(f"🤖 **AI:** {res}")
                            audio_html = VoiceAssistant.speak(res)
                            if audio_html:
                                st.components.v1.html(audio_html, height=0)
