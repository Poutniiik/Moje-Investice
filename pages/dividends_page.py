import streamlit as st
import pandas as pd
import plotly.express as px
import time
from datetime import datetime
import utils

def dividends_page(USER, df, df_div, kurzy, viz_data_list, pridat_dividendu_fn):
    st.title("💎 DIVIDENDOVÝ KALENDÁŘ")

    # --- 1. PROJEKTOR PASIVNÍHO PŘÍJMU ---
    est_annual_income_czk = 0
    data_to_use = viz_data_list if isinstance(viz_data_list, list) else viz_data_list.to_dict('records')
    
    if data_to_use:
        for item in data_to_use:
            yld = float(item.get('Divi', 0) or 0)
            val = float(item.get('HodnotaUSD', item.get('Hodnota', 0)) or 0)
            if yld > 0 and val > 0:
                est_annual_income_czk += (val * yld) * kurzy.get("CZK", 20.85)

    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.metric("Roční dividendy (odhad)", f"{est_annual_income_czk:,.0f} Kč")
        c2.metric("Měsíční průměr", f"{est_annual_income_czk/12:,.0f} Kč")

    st.divider()

    # --- 2. HISTORIE ---
    if not df_div.empty:
        df_view = df_div.copy()
        df_view['Datum'] = pd.to_datetime(df_view['Datum'], errors='coerce')
        # Graf
        grp = df_view.groupby('Ticker')['Castka'].sum().reset_index()
        st.plotly_chart(px.bar(grp, x='Ticker', y='Castka'), use_container_width=True)
        # Tabulka
        st.dataframe(df_view.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)

    st.divider()

    # --- 3. PŘIDAT DIVIDENDU ---
    st.header("💰 PŘIPSAT DIVIDENDU")
    
    t_list = df['Ticker'].unique().tolist() if not df.empty else ["Jiny"]
    
    c1, c2 = st.columns(2)
    with c1:
        d_tick = st.selectbox("Ticker", t_list)
        d_amt = st.number_input("Částka (Netto)", min_value=0.0, step=0.1)
    with c2:
        d_curr = st.selectbox("Měna", ["USD", "CZK", "EUR"])
        st.write("")
        st.write("")
        
        # Tlačítko
        if st.button("💾 ULOŽIT", type="primary", use_container_width=True):
            if d_amt > 0:
                # Voláme funkci. Pokud vrátí True, sama provede restart.
                # Pokud vrátí False, vypíšeme chybu zde.
                ok, msg = pridat_dividendu_fn(d_tick, d_amt, d_curr, USER)
                if not ok:
                    st.error(f"Chyba: {msg}")
            else:
                st.warning("Zadej částku.")
