import streamlit as st
import pandas as pd
import yfinance as yf
import time # Důležité pro řešení latence GitHubu
from ai_brain import get_alert_voice_text
from voice_engine import VoiceAssistant
from data_manager import SOUBOR_WATCHLIST # Importujeme konstantu pro správný soubor

def render_watchlist(USER, df_watch, LIVE_DATA, AI_AVAILABLE, model, ziskej_info, save_df_to_github):
    """
    Renderuje kompletní stránku Watchlistu (Sledování) se všemi indikátory a AI hlasem.
    Všechna logika (RSI, 52T, Sniper) je nyní izolována zde.
    """
    st.title("🎯 TAKTICKÝ RADAR (Hlídač)")

    # --- FORENZNÍ DIAGNOSTIKA (Logy) ---
    with st.expander("🔍 DIAGNOSTICKÝ LOG & OPRAVA", expanded=False):
        col_diag1, col_diag2 = st.columns(2)
        with col_diag1:
            st.write(f"**Aktivní uživatel:** `{USER}`")
            st.write(f"**Počet položek v paměti:** {len(df_watch)}")
        with col_diag2:
            if st.button("♻️ VYNUTIT REFRESH (Fix zamrzání)", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        if not df_watch.empty:
            st.write("**Aktuální seznam v paměti:**")
            st.code(", ".join(df_watch['Ticker'].tolist()))
        else:
            st.warning("⚠️ Paměť modulu je prázdná.")

    # --- 1. SEKCE PRO PŘIDÁNÍ ---
    with st.expander("➕ Přidat novou akcii / Upravit cíl", expanded=False):
        # Unikátní klíč formuláře pomáhá Streamlitu správně reagovat na změny
        with st.form(f"add_w_{len(df_watch)}", clear_on_submit=True):
            t = st.text_input("Symbol (např. AAPL, CEZ.PR)").upper().strip()
            c_buy, c_sell = st.columns(2)
            with c_buy: target_buy = st.number_input("Cílová NÁKUPNÍ cena ($)", min_value=0.0, key="tg_buy")
            with c_sell: target_sell = st.number_input("Cílová PRODEJNÍ cena ($)", min_value=0.0, key="tg_sell")

            if st.form_submit_button("Uložit do Radaru", use_container_width=True):
                if t and (target_buy > 0 or target_sell > 0):
                    with st.status(f"Zapisuji {t} na GitHub...") as s:
                        # Logika přidání
                        df_watch = df_watch[df_watch['Ticker'] != t]
                        new_row = pd.DataFrame([{'Ticker': t, 'TargetBuy': target_buy, 'TargetSell': target_sell, 'Owner': str(USER)}])
                        df_updated = pd.concat([df_watch, new_row], ignore_index=True)
                        
                        # Uložení na GitHub (přes alias na uloz_data_uzivatele)
                        success = save_df_to_github(df_updated, USER, SOUBOR_WATCHLIST)
                        if success:
                            s.update(label="✅ Zapsáno! Synchronizuji...", state="complete")
                            st.cache_data.clear() 
                            time.sleep(1) # Počkáme sekundu na GitHub
                            st.rerun()
                        else:
                            s.update(label="❌ Chyba při ukládání", state="error")
                else:
                    st.warning("Zadejte symbol a alespoň jednu cílovou cenu.")

    if not df_watch.empty:
        st.subheader("📡 AKTIVNÍ MONITORING")
        
        w_data = []
        tickers_list = df_watch['Ticker'].unique().tolist()
        batch_data = pd.DataFrame()

        if 'played_alerts' not in st.session_state:
            st.session_state['played_alerts'] = set()

        # Hromadné stažení dat pro technické indikátory
        if tickers_list:
            with st.spinner("Skenuji trh..."):
                try:
                    batch_data = yf.download(tickers_list, period="3mo", group_by='ticker', progress=False)
                except: batch_data = pd.DataFrame()

        for _, r in df_watch.iterrows():
            tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']

            inf = LIVE_DATA.get(tk, {})
            price = inf.get('price')
            cur = inf.get('curr', 'USD')
            if tk.upper().endswith(".PR"): cur = "CZK"
            elif tk.upper().endswith(".DE"): cur = "EUR"
            
            if not price:
                price, _, _ = ziskej_info(tk)

            # --- INDIKÁTORY (RSI + 52T) ---
            rsi_val = 50
            range_pos = 0.5
            try:
                if len(tickers_list) > 1:
                    hist = batch_data[tk]['Close'] if tk in batch_data.columns.levels[0] else pd.Series()
                else:
                    hist = batch_data['Close'] if 'Close' in batch_data.columns else pd.Series()

                if not hist.empty and len(hist) > 14:
                    delta = hist.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rsi_val = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
                
                t_obj = yf.Ticker(tk)
                y_low = t_obj.fast_info.year_low
                y_high = t_obj.fast_info.year_high
                
                if price and y_high > y_low:
                    range_pos = max(0.0, min(1.0, (price - y_low) / (y_high - y_low)))
            except: pass

            # --- LOGIKA SNIPERA + HLAS ---
            status_text = "Wait"; proximity_score = 0.0; active_target = 0; trig = False; act_type = ""

            if buy_trg > 0:
                active_target = buy_trg; act_type = "NÁKUP"
                if price and price > 0:
                    if price <= buy_trg:
                        status_text = "🔥 BUY NOW"; proximity_score = 1.0; trig = True
                    else:
                        diff = (price - buy_trg) / price
                        proximity_score = max(0.0, 1.0 - (diff / 0.20)) if diff <= 0.20 else 0.0
                        status_text = f"Blíží se ({diff*100:.1f}%)"
            elif sell_trg > 0:
                active_target = sell_trg; act_type = "PRODEJ"
                if price and price > 0:
                    if price >= sell_trg:
                        status_text = "💰 SELL NOW"; proximity_score = 1.0; trig = True
                    else:
                        diff = (sell_trg - price) / price
                        proximity_score = max(0.0, 1.0 - (diff / 0.20)) if diff <= 0.20 else 0.0
                        status_text = f"Blíží se ({diff*100:.1f}%)"

            # HLASOVÝ ALERT
            if trig:
                alert_key = f"{tk}_{act_type}"
                if alert_key not in st.session_state['played_alerts'] and st.session_state.get('ai_enabled', False) and AI_AVAILABLE:
                    with st.spinner(f"Attis AI hlásí {tk}..."):
                        voice_msg = get_alert_voice_text(model, tk, price, active_target, act_type)
                        audio_html = VoiceAssistant.speak(voice_msg)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                            st.session_state['played_alerts'].add(alert_key)

            w_data.append({
                "Symbol": tk, "Cena": price, "Měna": cur, "RSI": rsi_val,
                "Roční Rozsah": range_pos, "Cíl": active_target, "Akce": act_type,
                "🎯 Radar": proximity_score, "Status": status_text
            })

        wdf = pd.DataFrame(w_data)
        if not wdf.empty:
            st.dataframe(
                wdf,
                column_config={
                    "Cena": st.column_config.NumberColumn(format="%.2f"),
                    "Cíl": st.column_config.NumberColumn(format="%.2f"),
                    "RSI": st.column_config.NumberColumn(format="%.0f", help="<30 Levné, >70 Drahé"),
                    "Roční Rozsah": st.column_config.ProgressColumn(min_value=0, max_value=1, format=""),
                    "🎯 Radar": st.column_config.ProgressColumn(min_value=0, max_value=1, format=""),
                },
                column_order=["Symbol", "Cena", "Akce", "Cíl", "🎯 Radar", "Status", "RSI", "Roční Rozsah"],
                use_container_width=True, hide_index=True
            )

        st.divider()
        c_del1, c_del2 = st.columns([3, 1])
        with c_del2:
            to_del = st.selectbox("Smazat z radaru:", df_watch['Ticker'].unique(), key="del_box")
            if st.button("🗑️ Smazat", use_container_width=True):
                with st.status(f"Odstraňuji {to_del}...") as s:
                    df_to_save = df_watch[df_watch['Ticker'] != to_del]
                    success = save_df_to_github(df_to_save, USER, SOUBOR_WATCHLIST)
                    if success:
                        s.update(label="✅ Smazáno! Aktualizuji...", state="complete")
                        st.cache_data.clear()
                        time.sleep(1) # Klíčové pro GitHub
                        st.rerun()
                    else:
                        s.update(label="❌ Chyba při mazání", state="error")
    else:
        st.info("Zatím nic nesleduješ. Přidej první akcii nahoře.")
