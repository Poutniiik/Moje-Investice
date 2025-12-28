import streamlit as st
from ai_brain import get_portfolio_health_score, get_voice_briefing_text
from voice_engine import VoiceAssistant

def render_dashboard(USER, vdf, cash_usd, model, AI_AVAILABLE, cached_fear_greed):
    """
    Tato funkce přebírá veškerou logiku hlavní stránky.
    Původně byla v web_investice.py, teď má vlastní domov.
    """
    # Inicializace audio proměnné (tvůj oblíbený zásadní řádek)
    audio_html = None
    
    if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
        with st.container(border=True):
            st.caption("🩺 AI DIAGNOSTIKA PORTFOLIA")
            
            score_fg, rating_fg = cached_fear_greed()
            sentiment_context = f"{rating_fg} ({score_fg}/100)" if score_fg else "Neutrální"
            
            try:
                # Výpočet skóre
                health = get_portfolio_health_score(model, vdf, cash_usd, sentiment_context)
                h_score = health.get('score', 50)

                # Automatický hlasový briefing
                if 'briefing_played' not in st.session_state:
                    with st.spinner("Attis AI připravuje hlášení..."):
                        briefing_text = get_voice_briefing_text(model, USER, h_score, sentiment_context)
                        audio_html = VoiceAssistant.speak(briefing_text)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                            st.session_state['briefing_played'] = True

                # Vykreslení UI Health Score
                h_col1, h_col2 = st.columns([1, 3])
                with h_col1:
                    h_color = "red" if h_score < 40 else ("orange" if h_score < 70 else "#00FF99")
                    st.markdown(f"<h2 style='text-align: center; color: {h_color}; margin-top: 0;'>{h_score}%</h2>", unsafe_allow_html=True)
                    st.progress(h_score / 100)
                with h_col2:
                    st.markdown(f"**Verdikt:** {health.get('comment', 'Diagnostika dokončena.')}")
                    st.caption("💡 Tip: AI hodnotí diverzifikaci sektorů a tvůj 'cash buffer'.")

            except Exception as e:
                st.error(f"Nepodařilo se načíst diagnostiku: {e}")

          # Tady pak budeme pokračovat s přesunem zbývajících částí dashboardu (metriky, grafy...)
