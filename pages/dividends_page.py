# =========================================================================
# SOUBOR: pages/dividends_page.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "💎 Dividendy"
# =========================================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import time
from datetime import datetime

# Imports z root modulů
import utils
# Využíváme make_plotly_cyberpunk přímo z utils

# --- HLAVNÍ FUNKCE STRÁNKY ---
def dividends_page(USER, df, df_div, kurzy, viz_data_list, pridat_dividendu_fn):
    """
    st.error(f"DEBUG KONTROLA: 'pridat_dividendu_fn' je typu: {type(pridat_dividendu_fn)}")
    # 👆👆👆👆👆👆
    Vykreslí stránku '💎 Dividendy'.
    Přijímá: USER, df, df_div, kurzy, viz_data_list, a FUNKCI pridat_dividendu_fn
    """
    
    st.title("💎 DIVIDENDOVÝ KALENDÁŘ")

    # --- PROJEKTOR PASIVNÍHO PŘÍJMU (OPRAVENO A ZROBUSTNĚNO) ---
    est_annual_income_czk = 0
    
    data_to_use = viz_data_list.to_dict('records') if isinstance(viz_data_list, pd.DataFrame) else viz_data_list
        
    if data_to_use:
        for item in data_to_use:
            yield_val = item.get('Divi', 0.0)
            val_usd = item.get('HodnotaUSD', 0.0)
            
            try:
                yield_val = float(yield_val) if pd.notna(yield_val) and yield_val is not False else 0.0
                val_usd = float(val_usd) if pd.notna(val_usd) and val_usd is not False else 0.0
            except ValueError:
                yield_val = 0.0
                val_usd = 0.0

            if yield_val > 0 and val_usd > 0:
                est_annual_income_czk += (val_usd * yield_val) * kurzy.get("CZK", 20.85)

    est_monthly_income_czk = est_annual_income_czk / 12

    with st.container(border=True):
        st.subheader("🔮 PROJEKTOR PASIVNÍHO PŘÍJMU")
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("Očekávaný roční příjem", f"{est_annual_income_czk:,.0f} Kč", help="Hrubý odhad na základě aktuálního dividendového výnosu držených akcií.")
        cp2.metric("Měsíční průměr", f"{est_monthly_income_czk:,.0f} Kč", help="Kolik to dělá měsíčně k dobru.")

        levels = {
            "Netflix (300 Kč)": 300,
            "Internet (600 Kč)": 600,
            "Energie (2 000 Kč)": 2000,
            "Nájem/Hypo (15 000 Kč)": 15000
        }

        next_goal = "Rentier"
        next_val = 100000 
        progress = 0.0

        for name, val in levels.items():
            if est_monthly_income_czk < val:
                next_goal = name
                next_val = val
                progress = min(est_monthly_income_czk / val, 1.0)
                break
            else:
                pass

        if est_monthly_income_czk > 15000:
            next_goal = "Finanční Svoboda 🏖️"
            progress = 1.0

        cp3.caption(f"Cíl: **{next_goal}**")
        cp3.progress(progress)

    st.divider()

    # 1. Metriky
    total_div_czk = 0
    if not df_div.empty:
        for _, r in df_div.iterrows():
            amt = r['Castka']; currency = r['Mena']
            if currency == "USD": total_div_czk += amt * kurzy.get("CZK", 20.85)
            elif currency == "EUR": total_div_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85)) # approx
            else: total_div_czk += amt

    st.metric("CELKEM VYPLACENO (CZK)", f"{total_div_czk:,.0f} Kč")

    t_div1, t_div2, t_div3 = st.tabs(["HISTORIE VÝPLAT", "❄️ EFEKT SNĚHOVÉ KOULE", "PŘIDAT DIVIDENDU"])

   # SOUBOR: pages/dividends_page.py
# (Najdi řádek "with t_div1:" a nahraď jeho obsah tímto)

    # SOUBOR: pages/dividends_page.py (sekce with t_div1:)

    with t_div1:
        if not df_div.empty:
            # --- ZÁCHRANNÁ BRZDA: Vyčistíme data pro zobrazení ---
            df_view = df_div.copy()
            # Převedeme na datum a chyby (texty) změníme na NaT (neplatné), aby to nespadlo
            df_view['Datum'] = pd.to_datetime(df_view['Datum'], errors='coerce')
            # -----------------------------------------------------

            # Graf
            plot_df = df_view.copy()
            plot_df = plot_df.dropna(subset=['Datum']) # Vyhodíme případné chyby
            plot_df['Datum_Den'] = plot_df['Datum'].dt.strftime('%Y-%m-%d')

            plot_df_grouped = plot_df.groupby(['Datum_Den', 'Ticker'])['Castka'].sum().reset_index()
            plot_df_grouped = plot_df_grouped.sort_values('Datum_Den')

            fig_div = px.bar(plot_df_grouped, x='Datum_Den', y='Castka', color='Ticker',
                             title="Historie výplat (po dnech)",
                             labels={'Datum_Den': 'Datum', 'Castka': 'Částka'},
                             template="plotly_dark")
            fig_div.update_xaxes(type='category')
            fig_div.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
            fig_div = utils.make_plotly_cyberpunk(fig_div)
            st.plotly_chart(fig_div, use_container_width=True)

            # Tabulka - ZDE BYL PROBLÉM
            # Řadíme už opravená data (df_view)
            st.dataframe(df_view.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Zatím žádné dividendy.")

    with t_div2:
        if not df_div.empty:
            st.subheader("❄️ KUMULATIVNÍ RŮST (Snowball)")
            st.info("Tento graf ukazuje, jak se tvé dividendy sčítají v čase. Cílem je exponenciální růst!")
            
            # Příprava dat pro snowball
            snowball_df = df_div.copy()
            snowball_df['Datum'] = pd.to_datetime(snowball_df['Datum'])
            snowball_df = snowball_df.sort_values('Datum')
            
            # Přepočet na CZK pro jednotný graf
            def convert_to_czk(row):
                amt = row['Castka']; currency = row['Mena']
                if currency == "USD": return amt * kurzy.get("CZK", 20.85)
                elif currency == "EUR": return amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                return amt
            
            snowball_df['CastkaCZK'] = snowball_df.apply(convert_to_czk, axis=1)
            snowball_df['Kumulativni'] = snowball_df['CastkaCZK'].cumsum()
            
            fig_snow = px.area(
                snowball_df, 
                x='Datum', 
                y='Kumulativni',
                title="Celkem vyplaceno v čase (CZK)",
                template="plotly_dark",
                color_discrete_sequence=['#00BFFF'] # Deep Sky Blue
            )
            
            fig_snow.update_traces(line_color='#00BFFF', fillcolor='rgba(0, 191, 255, 0.2)')
            fig_snow.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)", 
                font_family="Roboto Mono",
                yaxis_title="Celkem vyplaceno (Kč)",
                xaxis_title=""
            )
            fig_snow = utils.make_plotly_cyberpunk(fig_snow)
            st.plotly_chart(fig_snow, use_container_width=True)
            
            last_total = snowball_df['Kumulativni'].iloc[-1]
            st.metric("Celková 'Sněhová koule'", f"{last_total:,.0f} Kč", help="Suma všech dividend, které jsi kdy obdržel.")
            
        else:
            st.info("Zatím nemáš data pro sněhovou kouli. Přidej první dividendu!")


# ... (zbytek kódu nahoře v dividends_page.py) ...

    # TOTO VLOŽ ÚPLNĚ DOLŮ (MIMO st.tabs)
    st.divider()
    st.header("💰 PŘIPSAT NOVOU DIVIDENDU")
    
    col_test1, col_test2 = st.columns(2)
    
    with col_test1:
        # Seznam tickerů
        tick_list = ["Jiny"]
        if not df.empty:
            tick_list = df['Ticker'].unique().tolist()
            
        d_tick = st.selectbox("Vyber akcii", tick_list, key="final_tick")
        d_amt = st.number_input("Částka (v čistém)", min_value=0.0, step=0.1, key="final_amt")
    
    with col_test2:
        d_curr = st.selectbox("Měna", ["USD", "CZK", "EUR"], key="final_curr")
        st.write("")
        st.write("")
        
        # Tlačítko přímo na stránce (žádný formulář, žádné záložky)
        if st.button("💾 ULOŽIT (TEST)", type="primary", use_container_width=True):
            st.toast("⏳ Pracuji...", icon="⚙️")
            
            # 1. Volání funkce
            try:
                ok, msg = pridat_dividendu_fn(d_tick, d_amt, d_curr, USER)
                
                if ok:
                    #st.success(f"✅ HOTOVO: {msg}")
                    #import time
                    #time.sleep(1)
                    #st.rerun()
                else:
                    st.error(f"❌ CHYBA FUNKCE: {msg}")
                    
            except Exception as e:
                st.error(f"❌ KRITICKÁ CHYBA: {e}")
