import streamlit as st
import pandas as pd
import yfinance as yf
import time 
from datetime import datetime
from ai_brain import get_alert_voice_text
from voice_engine import VoiceAssistant
from data_manager import SOUBOR_WATCHLIST

def _calculate_indicators(tk, batch_data, price, tickers_list):
    """
    Pomocná funkce pro výpočet technických indikátorů.
    Oddělení matematiky od UI (Clean Code princip).
    """
    rsi_val = 50.0
    range_pos = 0.5
    
    try:
        # Získání historie z batch dat
        if len(tickers_list) > 1:
            hist = batch_data[tk]['Close'] if (tk in batch_data.columns.levels[0]) else pd.Series()
        else:
            hist = batch_data['Close'] if 'Close' in batch_data.columns else pd.Series()

        if not hist.empty and len(hist) > 14:
            hist = hist.dropna()
            delta = hist.diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            rsi_val = (100 - (100 / (1 + rs))).iloc[-1]
        
        # Roční rozsah přes fast_info
        t_obj = yf.Ticker(tk)
        f_info = t_obj.fast_info
        y_low = f_info.get('yearLow', 0)
        y_high = f_info.get('yearHigh', 0)
        if price and y_high > y_low:
            range_pos = max(0.0, min(1.0, (price - y_low) / (y_high - y_low)))
            
    except Exception:
        pass # V případě chyby vracíme bezpečné výchozí hodnoty
        
    return rsi_val, range_pos

def _evaluate_sniper_signal(price, buy_trg, sell_trg):
    """
    Vyhodnocuje nákupní/prodejní signály a blízkost k cíli.
    """
    status_text = "Wait"
    prox = 0.0
    active_target = 0
    trig = False
    act_type = ""

    if buy_trg > 0:
        active_target = buy_trg
        act_type = "NÁKUP"
        if price and price > 0:
            if price <= buy_trg: 
                status_text = "🔥 BUY NOW"
                prox = 1.0
                trig = True
            else:
                diff = (price - buy_trg) / price
                prox = max(0.0, 1.0 - (diff / 0.15)) if diff <= 0.15 else 0.0
                status_text = f"Blízko ({diff*100:.1f}%)"
    
    elif sell_trg > 0:
        active_target = sell_trg
        act_type = "PRODEJ"
        if price and price > 0:
            if price >= sell_trg: 
                status_text = "💰 SELL NOW"
                prox = 1.0
                trig = True
            else:
                diff = (sell_trg - price) / price
                prox = max(0.0, 1.0 - (diff / 0.15)) if diff <= 0.15 else 0.0
                status_text = f"Blízko ({diff*100:.1f}%)"

    return status_text, prox, active_target, trig, act_type

def render_watchlist(USER, df_watch, LIVE_DATA, AI_AVAILABLE, model, ziskej_info, save_df_to_github):
    """
    Renderuje kompletní stránku Watchlistu.
    """
    st.title("🎯 TAKTICKÝ RADAR (Hlídač)")

    # --- DIAGNOSTIKA ---
    with st.expander("🔍 DIAGNOSTICKÝ LOG", expanded=False):
        col_diag1, col_diag2 = st.columns(2)
        with col_diag1:
            st.write(f"**Uživatel:** `{USER}`")
            st.write(f"**Čas aktualizace:** `{datetime.now().strftime('%H:%M:%S')}`")
        with col_diag2:
            if st.button("♻️ VYNUTIT REFRESH", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

    # --- SEKCE PRO PŘIDÁNÍ ---
    with st.expander("➕ Přidat novou akcii / Upravit cíl", expanded=False):
        with st.form(f"add_w_{len(df_watch)}", clear_on_submit=True):
            t = st.text_input("Symbol (např. AAPL, CEZ.PR)").upper().strip()
            c_buy, c_sell = st.columns(2)
            with c_buy: target_buy = st.number_input("Cílová NÁKUPNÍ cena ($)", min_value=0.0, key="tg_buy")
            with c_sell: target_sell = st.number_input("Cílová PRODEJNÍ cena ($)", min_value=0.0, key="tg_sell")

            if st.form_submit_button("Uložit do Radaru", use_container_width=True):
                if t and (target_buy > 0 or target_sell > 0):
                    with st.status(f"Zapisuji {t} na GitHub...") as s:
                        df_filtered = df_watch[df_watch['Ticker'] != t]
                        new_row = pd.DataFrame([{'Ticker': t, 'TargetBuy': target_buy, 'TargetSell': target_sell, 'Owner': str(USER)}])
                        df_updated = pd.concat([df_filtered, new_row], ignore_index=True)
                        
                        success = save_df_to_github(df_updated, USER, SOUBOR_WATCHLIST)
                        if success:
                            s.update(label="✅ Zapsáno!", state="complete")
                            st.session_state['df_watch'] = df_updated
                            if 'data_core' in st.session_state: del st.session_state['data_core']
                            st.cache_data.clear() 
                            time.sleep(0.5)
                            st.rerun()

    if not df_watch.empty:
        st.subheader("📡 AKTIVNÍ MONITORING")
        w_data = []
        tickers_list = df_watch['Ticker'].unique().tolist()
        batch_data = pd.DataFrame()

        if 'played_alerts' not in st.session_state:
            st.session_state['played_alerts'] = set()

        if tickers_list:
            with st.spinner("Skenuji trh..."):
                try:
                    batch_data = yf.download(tickers_list, period="7mo", group_by='ticker', progress=False)
                except Exception as e:
                    st.error(f"Chyba při stahování dat: {e}")
                    batch_data = pd.DataFrame()

        # --- HLAVNÍ SMYČKA ZPRACOVÁNÍ ---
        for _, r in df_watch.iterrows():
            tk = r['Ticker']
            buy_trg = r['TargetBuy']
            sell_trg = r['TargetSell']
            
            inf = LIVE_DATA.get(tk, {})
            price = inf.get('price')
            cur = inf.get('curr', 'USD')
            
            if not price or price <= 0:
                price, _, _ = ziskej_info(tk)

            # 1. Výpočet indikátorů (přesunut do funkce)
            rsi_val, range_pos = _calculate_indicators(tk, batch_data, price, tickers_list)

            # 2. Sniper logika (přesunuta do funkce)
            status_text, prox, active_target, trig, act_type = _evaluate_sniper_signal(price, buy_trg, sell_trg)

            # 3. Hlasové upozornění
            if trig:
                alert_key = f"{tk}_{act_type}"
                if alert_key not in st.session_state['played_alerts'] and st.session_state.get('ai_enabled', False) and AI_AVAILABLE:
                    voice_msg = get_alert_voice_text(model, tk, price, active_target, act_type)
                    audio_html = VoiceAssistant.speak(voice_msg)
                    if audio_html:
                        st.components.v1.html(audio_html, height=0)
                        st.session_state['played_alerts'].add(alert_key)

            w_data.append({
                "Symbol": tk, "Cena": price, "Měna": cur, "RSI": rsi_val,
                "Roční Rozsah": range_pos, "Cíl": active_target, "Akce": act_type,
                "🎯 Radar": prox, "Status": status_text
            })

        # --- Vykreslení tabulky ---
        wdf = pd.DataFrame(w_data)
        if not wdf.empty:
            st.dataframe(
                wdf,
                column_config={
                    "Cena": st.column_config.NumberColumn(format="%.2f"),
                    "Cíl": st.column_config.NumberColumn(format="%.2f"),
                    "RSI": st.column_config.NumberColumn(format="%.0f", help="<30 Přeprodáno, >70 Překoupeno"),
                    "Roční Rozsah": st.column_config.ProgressColumn("Poloha v roce", min_value=0, max_value=1),
                    "🎯 Radar": st.column_config.ProgressColumn("Blízkost k cíli", min_value=0, max_value=1),
                },
                column_order=["Symbol", "Cena", "Akce", "Cíl", "🎯 Radar", "Status", "RSI", "Roční Rozsah"],
                use_container_width=True, hide_index=True
            )

        st.divider()
        # --- SEKCE PRO MAZÁNÍ ---
        with st.columns([3, 1])[1]:
            to_del = st.selectbox("Smazat z radaru:", df_watch['Ticker'].unique(), key="del_box")
            if st.button("🗑️ Smazat", use_container_width=True):
                df_to_save = df_watch[df_watch['Ticker'] != to_del]
                if save_df_to_github(df_to_save, USER, SOUBOR_WATCHLIST):
                    st.session_state['df_watch'] = df_to_save
                    if 'data_core' in st.session_state: del st.session_state['data_core']
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.info("Tvůj radar je zatím čistý. Přidej symbol k monitorování.")
