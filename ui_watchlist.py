import streamlit as st
import pandas as pd
import yfinance as yf
from ai_brain import get_alert_voice_text
from voice_engine import VoiceAssistant
from data_manager import SOUBOR_WATCHLIST # Importujeme konstantu pro správný soubor

def render_watchlist(USER, df_watch, LIVE_DATA, AI_AVAILABLE, model, ziskej_info, save_df_to_github):
    """
    Renderuje kompletní stránku Watchlistu (Sledování) se všemi indikátory a AI hlasem.
    Všechna logika (RSI, 52T, Sniper) je nyní izolována zde.
    """
    st.title("🎯 TAKTICKÝ RADAR (Hlídač)")

    # --- 1. SEKCE PRO PŘIDÁNÍ ---
    with st.expander("➕ Přidat novou akcii / Upravit cíl", expanded=False):
        with st.form("add_w", clear_on_submit=True):
            t = st.text_input("Symbol (např. AAPL, CEZ.PR)").upper()
            c_buy, c_sell = st.columns(2)
            with c_buy: target_buy = st.number_input("Cílová NÁKUPNÍ cena ($)", min_value=0.0, key="tg_buy")
            with c_sell: target_sell = st.number_input("Cílová PRODEJNÍ cena ($)", min_value=0.0, key="tg_sell")

            if st.form_submit_button("Uložit do Radaru"):
                if t and (target_buy > 0 or target_sell > 0):
                    # Logika přidání: Smažeme starý záznam a přidáme nový
                    df_watch = df_watch[df_watch['Ticker'] != t]
                    new_row = pd.DataFrame([{'Ticker': t, 'TargetBuy': target_buy, 'TargetSell': target_sell, 'Owner': USER}])
                    df_watch = pd.concat([df_watch, new_row], ignore_index=True)
                    
                    # Uložení na GitHub (přes alias na uloz_data_uzivatele)
                    save_df_to_github(df_watch, USER, SOUBOR_WATCHLIST)
                    st.success(f"Akcie {t} byla přidána do radaru.")
                    st.rerun()
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
            with st.spinner("Skenuji trh a počítám RSI..."):
                try:
                    batch_data = yf.download(tickers_list, period="3mo", group_by='ticker', progress=False)
                except: batch_data = pd.DataFrame()

        for _, r in df_watch.iterrows():
            tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']

            # Získání ceny a určení měny
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
                    rs = gain / loss
                    rsi_val = (100 - (100 / (1 + rs))).iloc[-1]
                
                t_obj = yf.Ticker(tk)
                y_low = t_obj.fast_info.year_low
                y_high = t_obj.fast_info.year_high
                
                # OPRAVENO: Používáme y_low, jak bylo definováno výše
                if price and y_high > y_low:
                    range_pos = max(0.0, min(1.0, (price - y_low) / (y_high - y_low)))
            except: pass

            # --- LOGIKA SNIPERA + HLAS ---
            status_text = "Wait"
            proximity_score = 0.0
            active_target = 0
            action_icon = "⚪️"
            alert_triggered = False
            action_type = ""

            if buy_trg > 0:
                active_target = buy_trg; action_icon = "🟢 Buy"; action_type = "NÁKUP"
                if price and price > 0:
                    if price <= buy_trg:
                        status_text = "🔥 BUY NOW"; proximity_score = 1.0; alert_triggered = True
                    else:
                        diff = (price - buy_trg) / price
                        proximity_score = max(0.0, 1.0 - (diff / 0.20)) if diff <= 0.20 else 0.0
                        status_text = f"Blíží se ({diff*100:.1f}%)"
            elif sell_trg > 0:
                active_target = sell_trg; action_icon = "🔴 Sell"; action_type = "PRODEJ"
                if price and price > 0:
                    if price >= sell_trg:
                        status_text = "💰 SELL NOW"; proximity_score = 1.0; alert_triggered = True
                    else:
                        diff = (sell_trg - price) / price
                        proximity_score = max(0.0, 1.0 - (diff / 0.20)) if diff <= 0.20 else 0.0
                        status_text = f"Blíží se ({diff*100:.1f}%)"

            # HLASOVÝ ALERT
            if alert_triggered:
                st.toast(f"🔔 {tk} je na cíli!", icon="🎯")
                alert_key = f"{tk}_{action_type}"
                if alert_key not in st.session_state['played_alerts'] and st.session_state.get('ai_enabled', False) and AI_AVAILABLE:
                    with st.spinner(f"Attis AI hlásí {tk}..."):
                        voice_msg = get_alert_voice_text(model, tk, price, active_target, action_type)
                        audio_html = VoiceAssistant.speak(voice_msg)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                            st.session_state['played_alerts'].add(alert_key)

            w_data.append({
                "Symbol": tk, "Cena": price, "Měna": cur, "RSI": rsi_val,
                "Roční Rozsah": range_pos, "Cíl": active_target, "Akce": action_icon,
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
            to_del = st.selectbox("Smazat z radaru:", df_watch['Ticker'].unique())
            if st.button("🗑️ Smazat", use_container_width=True):
                df_watch = df_watch[df_watch['Ticker'] != to_del]
                save_df_to_github(df_watch, USER, SOUBOR_WATCHLIST)
                st.warning(f"Akcie {to_del} byla smazána.")
                st.rerun()
    else:
        st.info("Zatím nic nesleduješ. Přidej první akcii nahoře.")
