import streamlit as st
from src.utils import ziskej_zpravy, make_matplotlib_cyberpunk

def render_zpravy_page(AI_AVAILABLE, model, viz_data_list, celk_hod_czk):
    st.title("📰 BURZOVNÍ ZPRAVODAJSTVÍ")

    # --- CACHE WRAPPER (inline here or import from portfolio_service if reused) ---
    # Since cached_zpravy is only used here and in dashboard (maybe), let's import it or redefine.
    # To keep it consistent, I'll redefine the cache wrapper locally or import if I moved it to a shared place.
    # In web_investice.py it was cached. I should probably move cached_zpravy to portfolio_service.py or utils.py.
    # But ziskej_zpravy is in utils. Let's assume we call ziskej_zpravy directly or wrap it here.

    @st.cache_data(ttl=3600)
    def cached_zpravy_local():
        return ziskej_zpravy()

    # --- 1. MRAK SLOV (Wordcloud) ---
    # Na mobilu je lepší, když je to přes celou šířku
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt

        raw_news_cloud = cached_zpravy_local()
        if raw_news_cloud:
            with st.expander("☁️ TÉMATA DNE (Co hýbe trhem)", expanded=True):
                text_data = " ".join([n['title'] for n in raw_news_cloud]).upper()
                stop_words = ["A", "I", "O", "U", "V", "S", "K", "Z", "SE", "SI", "NA", "DO", "JE", "TO", "ŽE", "ALE", "PRO", "JAK", "TAK", "OD", "PO", "NEBO", "BUDE", "BYL", "MÁ", "JSOU", "KTERÝ", "KTERÁ", "ONLINE", "AKTUÁNĚ", "CENA", "BURZA", "TRH", "AKCIE", "INVESTICE", "ČESKÉ", "NOVINY", "IDNES", "SEZNAM"]

                wc = WordCloud(
                    width=800, height=300, # Trochu vyšší pro mobil
                    background_color=None,
                    mode="RGBA",
                    stopwords=stop_words,
                    min_font_size=12,
                    colormap="GnBu"
                ).generate(text_data)

                fig_cloud, ax = plt.subplots(figsize=(10, 4))
                ax.imshow(wc, interpolation="bilinear")
                ax.axis("off")
                fig_cloud.patch.set_alpha(0)
                ax.patch.set_alpha(0)
                make_matplotlib_cyberpunk(fig_cloud, ax)
                st.pyplot(fig_cloud, use_container_width=True)
    except: pass

    st.divider()

    # --- 2. HLAVNÍ OVLÁDACÍ PANEL ---
    # Tlačítko pro AI analýzu všech zpráv (Sentiment 2.0)
    if AI_AVAILABLE:
        if st.button("🧠 SPUSTIT AI SENTIMENT TRHU (Všechny zprávy)", type="primary", use_container_width=True):
            with st.spinner("AI čte noviny a analyzuje náladu..."):
                raw_news = cached_zpravy_local()
                # Vezmeme jen top 10 zpráv, ať to netrvá věčnost
                titles = [n['title'] for n in raw_news[:10]]
                titles_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
                prompt = f"""Jsi finanční analytik. Analyzuj tyto novinové titulky a urči jejich sentiment.\nTITULKY:\n{titles_str}\nPro každý titulek vrať přesně tento formát na jeden řádek (bez odrážek):\nINDEX|SKÓRE(0-100)|VYSVĚTLENÍ (česky, max 1 věta)"""
                try:
                    response = model.generate_content(prompt)
                    analysis_map = {}
                    for line in response.text.strip().split('\n'):
                        parts = line.split('|')
                        if len(parts) == 3:
                            try:
                                idx = int(parts[0].replace('.', '').strip()) - 1; score = int(parts[1].strip()); reason = parts[2].strip()
                                analysis_map[idx] = {'score': score, 'reason': reason}
                            except: pass
                    st.session_state['ai_news_analysis'] = analysis_map
                    st.success("Analýza dokončena!")
                except Exception as e: st.error(f"Chyba AI: {e}")

    # --- 3. NEWS FEED (KARTY POD SEBOU) ---
    # Žádné sloupce! Jeden dlouhý feed, jako na Instagramu/Twitteru.

    def analyze_news_with_ai(title, link):
        portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
        if viz_data_list: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data_list])
        prompt_to_send = f"Analyzuj tuto zprávu V KONTEXTU MÉHO PORTFOLIA. Zpráva: {title}. Jaký má dopad? (Odkaz: {link})"
        st.session_state["chat_messages"].append({"role": "user", "content": prompt_to_send})
        st.session_state['chat_expanded'] = True
        st.rerun()

    news = cached_zpravy_local()
    ai_results = st.session_state.get('ai_news_analysis', {})

    if news:
        st.write("")
        st.subheader(f"🔥 Nejnovější zprávy ({len(news)})")

        for i, n in enumerate(news):
            with st.container(border=True):
                # AI Výsledek (pokud existuje)
                if i in ai_results:
                    res = ai_results[i]; score = res['score']; reason = res['reason']
                    if score >= 60: color = "green"; emoji = "🟢 BÝČÍ"
                    elif score <= 40: color = "red"; emoji = "🔴 MEDVĚDÍ"
                    else: color = "orange"; emoji = "🟡 NEUTRÁL"

                    c_score, c_text = st.columns([1, 4])
                    with c_score:
                        st.markdown(f"**{emoji}**")
                        st.markdown(f"**{score}/100**")
                    with c_text:
                        st.info(f"🤖 {reason}")
                    st.divider()

                # Titulek a Datum
                st.markdown(f"### {n['title']}")
                st.caption(f"📅 {n['published']} | Zdroj: RSS")

                # Akce
                c_btn1, c_btn2 = st.columns([1, 1])
                with c_btn1:
                    st.link_button("Číst článek ↗️", n['link'], use_container_width=True)
                with c_btn2:
                    if AI_AVAILABLE:
                        if st.button(f"🤖 Dopad na portfolio", key=f"analyze_ai_{i}", use_container_width=True):
                            analyze_news_with_ai(n['title'], n['link'])
    else:
        st.info("Žádné nové zprávy.")
