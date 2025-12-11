# =========================================================================
# SOUBOR: pages/dividends_page.py
# =========================================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import time
from datetime import datetime
import utils

def dividends_page(USER, df, df_div, kurzy, viz_data_list, pridat_dividendu_fn):
    """
    Stránka pro správu dividend.
    """
    st.title("💎 DIVIDENDOVÝ KALENDÁŘ")

    # --- 1. PROJEKTOR PASIVNÍHO PŘÍJMU ---
    est_annual_income_czk = 0
    
    # Bezpečný převod dat
    data_to_use = viz_data_list
    if isinstance(viz_data_list, pd.DataFrame):
        data_to_use = viz_data_list.to_dict('records')
        
    if data_to_use:
        for item in data_to_use:
            # Zkusíme najít Yield
            yield_val = item.get('Divi', 0.0)
            if yield_val is None: yield_val = 0.0
            
            # Zkusíme najít Hodnotu (podporujeme starý i nový název)
            val_usd = item.get('HodnotaUSD', item.get('Hodnota', 0.0))
            if val_usd is None: val_usd = 0.0
            
            try:
                yield_val = float(yield_val)
                val_usd = float(val_usd)
                if yield_val > 0 and val_usd > 0:
                    est_annual_income_czk += (val_usd * yield_val) * kurzy.get("CZK", 20.85)
            except:
                pass

    est_monthly_income_czk = est_annual_income_czk / 12

    with st.container(border=True):
        st.subheader("🔮 PROJEKTOR PASIVNÍHO PŘÍJMU")
        cp1, cp2 = st.columns(2)
        cp1.metric("Roční příjem (odhad)", f"{est_annual_income_czk:,.0f} Kč")
        cp2.metric("Měsíční průměr", f"{est_monthly_income_czk:,.0f} Kč")

    st.divider()

    # --- 2. HISTORIE VÝPLAT (GRAF) ---
    if not df_div.empty:
        # Oprava datumu pro zobrazení
        df_view = df_div.copy()
        df_view['Datum'] = pd.to_datetime(df_view['Datum'], errors='coerce')
        df_view = df_view.dropna(subset=['Datum'])
        
        # Graf
        df_grouped = df_view.groupby('Ticker')['Castka'].sum().reset_index()
        fig = px.bar(df_grouped, x='Ticker', y='Castka', title="Celkem vyplaceno dle tickeru")
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabulka
        st.caption("Historie transakcí")
        st.dataframe(df_view.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Zatím žádná historie dividend.")

    st.divider()

    # --- 3. PŘIDÁNÍ NOVÉ DIVIDENDY (DIAGNOSTICKÝ MÓD) ---
    st.header("💰 PŘIPSAT DIVIDENDU (DEBUG)")
    st.info("Tento formulář neprovádí automatický restart, abychom viděli výsledek.")

    # Příprava seznamu tickerů
    seznam_tickeru = ["Jiny"]
    if not df.empty:
        seznam_tickeru = df['Ticker'].unique().tolist()

    c1, c2 = st.columns(2)
    with c1:
        d_tick = st.selectbox("Ticker", seznam_tickeru, key="d_tick_final")
        d_amt = st.number_input("Částka (čistá)", min_value=0.0, step=0.1, key="d_amt_final")
    with c2:
        d_curr = st.selectbox("Měna", ["USD", "CZK", "EUR"], key="d_curr_final")
        st.write("")
        st.write("")
        
        # Tlačítko BEZ formuláře
        btn_uloz = st.button("💾 ULOŽIT DATA", type="primary", use_container_width=True)

    if btn_uloz:
        st.write("--- ZAČÁTEK DIAGNOSTIKY ---")
        st.write(f"1. Vstupní data: {d_tick}, {d_amt}, {d_curr}")
        
        if d_amt > 0:
            st.write("2. Volám ukládací funkci...")
            try:
                # Voláme funkci předanou z hlavního souboru
                ok, msg = pridat_dividendu_fn(d_tick, d_amt, d_curr, USER)
                
                st.write(f"3. Návratová hodnota: OK={ok}")
                st.write(f"4. Zpráva systému: {msg}")
                
                if ok:
                    st.success("✅ SYSTEM HLÁSÍ ÚSPĚCH!")
                    st.markdown("### 🛑 STOP! NERESTARTUJI.")
                    st.warning("Jdi teď na GitHub -> soubor 'dividends.csv' a zkontroluj, jestli tam ten řádek je.")
                else:
                    st.error(f"❌ SYSTEM HLÁSÍ CHYBU: {msg}")
            
            except Exception as e:
                st.error(f"💣 KRITICKÝ PÁD: {e}")
                st.error("Tip: Zkontroluj v 'web_investice.py', jestli posíláš funkci 'pridat_dividendu' správně.")
        else:
            st.warning("⚠️ Částka musí být větší než 0.")
