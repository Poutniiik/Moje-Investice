import streamlit as st
import pandas as pd
from ai_brain import get_alert_voice_text
from voice_engine import VoiceAssistant

def render_watchlist(USER, df_watch, LIVE_DATA, AI_AVAILABLE, model, ziskej_info, save_df_to_github):
    """
    Renderuje stránku Watchlistu (Sledování).
    Obsahuje tabulku cílů, přidávání tickerů a hlasový Sniper Radar.
    """
    st.title("🎯 SNIPER RADAR & WATCHLIST")

    # --- 1. HLASOVÝ SNIPER RADAR (LOGIKA) ---
    if 'played_alerts' not in st.session_state:
        st.session_state['played_alerts'] = set()

    alerts = []
    if not df_watch.empty:
        for _, r in df_watch.iterrows():
            tk = r['Ticker']
            buy_trg = r['TargetBuy']
            sell_trg = r['TargetSell']

            if buy_trg > 0 or sell_trg > 0:
                inf = LIVE_DATA.get(tk, {})
                price = inf.get('price')
                if not price:
                    price, _, _ = ziskej_info(tk)

                if price:
                    alert_triggered = False
                    action = ""
                    target = 0
                    
                    if buy_trg > 0 and price <= buy_trg:
                        action = "NÁKUP"
                        target = buy_trg
                        alert_triggered = True
                    elif sell_trg > 0 and price >= sell_trg:
                        action = "PRODEJ"
                        target = sell_trg
                        alert_triggered = True

                    if alert_triggered:
                        msg = f"{tk}: {action} ALERT! Cena {price:.2f} (Cíl: {target:.2f})"
                        alerts.append(msg)
                        st.toast(f"🔔 {tk} je na cíli!", icon="🎯")
                        
                        # Hlasová část
                        alert_key = f"{tk}_{action}"
                        if alert_key not in st.session_state['played_alerts'] and st.session_state.get('ai_enabled', False) and AI_AVAILABLE:
                            with st.spinner(f"Attis AI hlásí příležitost na {tk}..."):
                                voice_msg = get_alert_voice_text(model, tk, price, target, action)
                                audio_html = VoiceAssistant.speak(voice_msg)
                                if audio_html:
                                    st.components.v1.html(audio_html, height=0)
                                    st.session_state['played_alerts'].add(alert_key)

    # --- 2. UI TABULKA A SPRÁVA ---
    with st.container(border=True):
        st.subheader("📋 Sledované pozice")
        if not df_watch.empty:
            # Přidáme aktuální cenu do zobrazení
            df_display = df_watch.copy()
            df_display['Live Cena'] = df_display['Ticker'].apply(lambda x: LIVE_DATA.get(x, {}).get('price', 0))
            
            st.dataframe(
                df_display,
                column_config={
                    "Ticker": st.column_config.TextColumn("Symbol"),
                    "TargetBuy": st.column_config.NumberColumn("Cíl Nákup", format="$%.2f"),
                    "TargetSell": st.column_config.NumberColumn("Cíl Prodej", format="$%.2f"),
                    "Live Cena": st.column_config.NumberColumn("Aktuální", format="$%.2f")
                },
                use_container_width=True, hide_index=True
            )
            
            if st.button("🗑️ VYMAZAT CELÝ WATCHLIST", use_container_width=True):
                df_watch = pd.DataFrame(columns=['Ticker', 'TargetBuy', 'TargetSell'])
                save_df_to_github(df_watch, f"data/{USER}_watch.csv", f"Reset watchlist {USER}")
                st.rerun()
        else:
            st.info("Watchlist je prázdný. Přidej první ticker níže.")

    # --- 3. PŘIDÁVÁNÍ TICKERŮ ---
    with st.expander("➕ PŘIDAT / UPRAVIT CÍL"):
        with st.form("watch_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            new_tk = col1.text_input("Ticker (např. AAPL)").upper()
            new_buy = col2.number_input("Nákupní cíl ($)", min_value=0.0, step=0.1)
            new_sell = col3.number_input("Prodejní cíl ($)", min_value=0.0, step=0.1)
            
            if st.form_submit_button("ULOŽIT DO RADARU"):
                if new_tk:
                    # Pokud už ticker existuje, smažeme ho a nahradíme novým
                    df_watch = df_watch[df_watch['Ticker'] != new_tk]
                    new_row = pd.DataFrame([{'Ticker': new_tk, 'TargetBuy': new_buy, 'TargetSell': new_sell}])
                    df_watch = pd.concat([df_watch, new_row], ignore_index=True)
                    
                    save_df_to_github(df_watch, f"data/{USER}_watch.csv", f"Update watch {new_tk}")
                    st.success(f"Radar nastaven na {new_tk}")
                    st.rerun()
                else:
                    st.warning("Zadej prosím Ticker.")
```

### 2. Úprava `web_investice.py` (Přepojení kabelů)

Nyní v hlavním souboru proveď tyto změny:

1. **Import:** Nahoru přidej:
   ```python
   import ui_watchlist
   ```

2. **Refaktoring funkce:** Najdi `render_sledovani_page` a celou ji nahraď touto krásnou zkratkou:
   ```python
   def render_sledovani_page(USER, df_watch, LIVE_DATA, AI_AVAILABLE, model):
       """Vykreslí stránku '🎯 Sledování' přes externí modul"""
       # Volání nového modulu
       ui_watchlist.render_watchlist(
           USER, df_watch, LIVE_DATA, AI_AVAILABLE, model, 
           ziskej_info, save_df_to_github
       )
