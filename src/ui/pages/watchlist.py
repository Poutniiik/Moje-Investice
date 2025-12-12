import streamlit as st
import pandas as pd
import yfinance as yf
from src.utils import ziskej_info
from src.services.portfolio_service import pridat_do_watchlistu, odebrat_z_watchlistu

def render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST):
    """Vykreslí stránku '👀 Sledování' (Watchlist) - VERZE 2.1 (Fix Buy/Sell Cíl)"""
    st.title("👀 WATCHLIST (Hlídač) – Cenové zóny")

    # Sekce pro přidání nové akcie
    with st.expander("➕ Přidat novou akcii", expanded=False):
        with st.form("add_w", clear_on_submit=True):
            t = st.text_input("Symbol (např. AAPL)").upper()
            c_buy, c_sell = st.columns(2)
            with c_buy: target_buy = st.number_input("Cílová NÁKUPNÍ cena ($)", min_value=0.0, key="tg_buy")
            with c_sell: target_sell = st.number_input("Cílová PRODEJNÍ cena ($)", min_value=0.0, key="tg_sell")

            if st.form_submit_button("Sledovat"):
                if t and (target_buy > 0 or target_sell > 0):
                    pridat_do_watchlistu(t, target_buy, target_sell, USER); st.rerun()
                else:
                    st.warning("Zadejte symbol a alespoň jednu cílovou cenu (Buy nebo Sell).")

    if not df_watch.empty:
        st.subheader("📡 TAKTICKÝ RADAR")
        st.info("Rychlý přehled technického stavu sledovaných akcií.")

        w_data = []
        tickers_list = df_watch['Ticker'].unique().tolist()
        batch_data = pd.DataFrame()

        # Hromadné stažení dat pro indikátory
        if tickers_list:
            with st.spinner("Skenuji trh a počítám indikátory..."):
                try:
                    batch_data = yf.download(tickers_list, period="3mo", group_by='ticker', progress=False)
                except: batch_data = pd.DataFrame()

        for _, r in df_watch.iterrows():
            tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']

            # Získání ceny
            inf = LIVE_DATA.get(tk, {})
            price = inf.get('price')
            cur = inf.get('curr', 'USD')
            if tk.upper().endswith(".PR"): cur = "CZK"
            elif tk.upper().endswith(".DE"): cur = "EUR"

            if not price:
                price, _, _ = ziskej_info(tk)

            # Výpočet RSI
            rsi_val = 50
            try:
                if len(tickers_list) > 1:
                    if tk in batch_data.columns.levels[0]: hist = batch_data[tk]['Close']
                    else: hist = pd.Series()
                else:
                    if 'Close' in batch_data.columns: hist = batch_data['Close']
                    else: hist = pd.Series()

                if not hist.empty and len(hist) > 14:
                    delta = hist.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi_series = 100 - (100 / (1 + rs))
                    rsi_val = rsi_series.iloc[-1]
            except: pass

            # 52 Week Range
            range_pos = 0.5
            try:
                t_obj = yf.Ticker(tk)
                year_low = t_obj.fast_info.year_low
                year_high = t_obj.fast_info.year_high
                if price and year_high > year_low:
                    range_pos = (price - year_low) / (year_high - year_low)
                    range_pos = max(0.0, min(1.0, range_pos))
            except: pass

            # --- LOGIKA SNIPERA (ZAMĚŘOVAČ) ---
            status_text = "💤 Wait"
            proximity_score = 0.0

            # --- FIX: Určení aktivního cíle a typu akce ---
            active_target = 0
            action_icon = "⚪️"

            if buy_trg > 0:
                active_target = buy_trg
                action_icon = "🟢 Buy"
                if price and price > 0:
                    if price <= buy_trg:
                        status_text = "🔥 BUY NOW"
                        proximity_score = 1.0
                    else:
                        diff_pct = (price - buy_trg) / price
                        if diff_pct > 0.20: proximity_score = 0.0
                        else:
                            proximity_score = 1.0 - (diff_pct / 0.20)
                            status_text = f"Blíží se ({diff_pct*100:.1f}%)"

            elif sell_trg > 0:
                active_target = sell_trg
                action_icon = "🔴 Sell"
                if price and price > 0:
                    if price >= sell_trg:
                        status_text = "💰 SELL NOW"
                        proximity_score = 1.0
                    else:
                        diff_pct = (sell_trg - price) / price
                        if diff_pct > 0.20: proximity_score = 0.0
                        else:
                            proximity_score = 1.0 - (diff_pct / 0.20)
                            status_text = f"Blíží se ({diff_pct*100:.1f}%)"

            # ULOŽENÍ DO DAT
            w_data.append({
                "Symbol": tk,
                "Cena": price,
                "Měna": cur,
                "RSI (14)": rsi_val,
                "52T Range": range_pos,
                "Cíl": active_target,     # Sloupec je nyní univerzální "Cíl"
                "Akce": action_icon,      # Nový sloupec s ikonkou
                "Zaměřovač": proximity_score,
                "Status": status_text
            })

        wdf = pd.DataFrame(w_data)

        if not wdf.empty:
            st.dataframe(
                wdf,
                column_config={
                    "Cena": st.column_config.NumberColumn(format="%.2f"),
                    "Cíl": st.column_config.NumberColumn(format="%.2f", help="Tvůj nastavený limit (Nákup nebo Prodej)"),
                    "Akce": st.column_config.TextColumn("Typ", width="small"),
                    "RSI (14)": st.column_config.NumberColumn(
                        "RSI",
                        help="< 30: Levné | > 70: Drahé",
                        format="%.0f",
                    ),
                    "52T Range": st.column_config.ProgressColumn(
                        "Roční Rozsah",
                        help="Vlevo = Low, Vpravo = High",
                        min_value=0, max_value=1, format=""
                    ),
                    "Zaměřovač": st.column_config.ProgressColumn(
                        "🎯 Radar",
                        help="Jak blízko je cena k limitu?",
                        min_value=0,
                        max_value=1,
                        format=""
                    )
                },
                # Upravené pořadí pro lepší mobile view
                column_order=["Symbol", "Cena", "Akce", "Cíl", "Zaměřovač", "Status", "RSI (14)", "52T Range"],
                use_container_width=True,
                hide_index=True
            )

            st.caption("💡 **RSI Legenda:** Pod **30** = Přeprodáno (Levné 📉), Nad **70** = Překoupeno (Drahé 📈).")

        st.divider()
        c_del1, c_del2 = st.columns([3, 1])
        with c_del2:
            to_del = st.selectbox("Vyber pro smazání:", df_watch['Ticker'].unique())
            if st.button("🗑️ Smazat", use_container_width=True):
                odebrat_z_watchlistu(to_del, USER); st.rerun()
    else:
        st.info("Zatím nic nesleduješ. Přidej první akcii nahoře.")
