import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime
import random
from utils import (
    make_plotly_cyberpunk, make_matplotlib_cyberpunk, vytvor_pdf_report, 
    calculate_sharpe_ratio, ziskej_earnings_datum, ziskej_detail_akcie,
    cached_fear_greed, cached_zpravy, ziskej_info, zjisti_stav_trhu
)
from ai_brain import ask_ai_guard, generate_rpg_story, get_chat_response
import bank_engine
import notification_engine as notify
from data_manager import SOUBOR_DATA, SOUBOR_HISTORIE, SOUBOR_CASH, SOUBOR_DIVIDENDY, SOUBOR_WATCHLIST, uloz_data_uzivatele, nacti_csv, nacti_uzivatele, zasifruj, uloz_csv, SOUBOR_UZIVATELE
import io
import zipfile

# --- ZDE JSME SMAZALI IMPORT Z LOGIC_PORTFOLIO (bude uvnitř funkcí) ---

# --- UI HELPERY ---
def render_ticker_tape(data_dict):
    if not data_dict: return
    content = ""
    for ticker, info in data_dict.items():
        price = info.get('price', 0); curr = info.get('curr', '')
        content += f"&nbsp;&nbsp;&nbsp;&nbsp; <b>{ticker}</b>: {price:,.2f} {curr}"
    st.markdown(f"""
        <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 5px; padding: 8px; margin-bottom: 20px; white-space: nowrap; overflow: hidden;">
            <div style="display: inline-block; animation: marquee 20s linear infinite; color: #00CC96; font-family: 'Roboto Mono', monospace; font-weight: bold;">
                {content} {content} {content}
            </div>
        </div>
        <style>@keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}</style>
    """, unsafe_allow_html=True)

def add_download_button(fig, filename):
    try:
        buffer = io.BytesIO()
        fig.write_image(buffer, format="png", width=1200, height=800, scale=2)
        st.download_button(label=f"⬇️ Stáhnout graf", data=buffer.getvalue(), file_name=f"{filename}.png", mime="image/png", use_container_width=True)
    except: st.caption("💡 Tip: Pro stažení použij ikonu fotoaparátu v grafu.")

# --- RENDEROVACÍ FUNKCE STRÁNEK ---

def render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA):
    if 'show_cash_history' not in st.session_state: st.session_state['show_cash_history'] = False 
    if 'show_portfolio_live' not in st.session_state: st.session_state['show_portfolio_live'] = True
    
    st.title(f"🏠 PŘEHLED: {USER.upper()}")
    with st.container(border=True):
        k1, k2, k3, k4 = st.columns(4)
        kurz_czk = kurzy.get('CZK', 20.85)
        k1.metric("💰 JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{(celk_hod_usd-celk_inv_usd)*kurz_czk:+,.0f} Kč Zisk")
        k2.metric("🌎 JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} USD")
        k3.metric("📈 ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        k4.metric("💳 HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné prostředky")
    st.write("") 

    c_left, c_right = st.columns([1, 2])
    with c_left:
        with st.container(border=True):
            st.caption("🧠 PSYCHOLOGIE TRHU")
            score, rating = cached_fear_greed()
            if score:
                st.metric("Fear & Greed Index", f"{score}/100", rating)
                fig_gauge = go.Figure(go.Indicator(mode = "gauge+number", value = score, domain = {'x': [0, 1], 'y': [0, 1]}, gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "white"}, 'steps': [{'range': [0, 25], 'color': '#FF4136'}, {'range': [75, 100], 'color': '#2ECC40'}]}))
                fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=120, margin=dict(l=20, r=20, t=20, b=20), font={'color': "white"})
                st.plotly_chart(fig_gauge, use_container_width=True)
            st.divider()
            viz_data_list = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
            if viz_data_list:
                sorted_data = sorted(viz_data_list, key=lambda x: x.get('Dnes', 0) if x.get('Dnes') is not None else 0, reverse=True)
                best = sorted_data[0]; worst = sorted_data[-1]
                st.write(f"🚀 **{best['Ticker']}**: {best['Dnes']*100:+.2f}%")
                st.write(f"💀 **{worst['Ticker']}**: {worst['Dnes']*100:+.2f}%")

    with c_right:
        with st.container(border=True):
            st.caption("🧭 GLOBÁLNÍ KOMPAS")
            try:
                makro_tickers = {"🇺🇸 S&P 500": "^GSPC", "🥇 Zlato": "GC=F", "₿ Bitcoin": "BTC-USD", "🏦 Úroky 10Y": "^TNX"}
                makro_data = yf.download(list(makro_tickers.values()), period="5d", progress=False)['Close']
                mc1, mc2, mc3, mc4 = st.columns(4)
                cols_list = [mc1, mc2, mc3, mc4]
                for i, (name, ticker) in enumerate(makro_tickers.items()):
                    with cols_list[i]:
                        if isinstance(makro_data.columns, pd.MultiIndex): series = makro_data[ticker].dropna() if ticker in makro_data.columns.levels[0] else pd.Series()
                        else: series = makro_data[ticker].dropna() if ticker in makro_data.columns else pd.Series()
                        if not series.empty:
                            last = series.iloc[-1]; prev = series.iloc[-2] if len(series) > 1 else last
                            delta = ((last - prev) / prev) * 100
                            st.metric(name, f"{last:,.0f}", f"{delta:+.2f}%")
                            fig_spark = go.Figure(go.Scatter(y=series.values, mode='lines', line=dict(color='#238636' if delta >= 0 else '#da3633', width=2), fill='tozeroy'))
                            fig_spark.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=35, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
            except: st.error("Chyba kompasu")
        
        if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
             with st.container(border=True):
                if st.button("🛡️ SPUSTIT RANNÍ AI BRIEFING", use_container_width=True):
                    with st.spinner("Analyzuji rizika..."):
                         top_mover = best.get('Ticker', "N/A") if 'best' in locals() else "N/A"
                         flop_mover = worst.get('Ticker', "N/A") if 'worst' in locals() else "N/A"
                         res = ask_ai_guard(model, pct_24h, cash_usd, top_mover, flop_mover)
                         st.info(f"🤖 **AI:** {res}")

    col_graf1, col_graf2 = st.columns([2, 1])
    with col_graf1:
        with st.container(border=True):
            st.subheader("🌊 VÝVOJ MAJETKU")
            if not hist_vyvoje.empty:
                chart_data = hist_vyvoje.copy()
                chart_data['TotalCZK'] = chart_data['TotalUSD'] * kurzy.get("CZK", 20.85)
                fig_area = px.area(chart_data, x='Date', y='TotalCZK', template="plotly_dark")
                fig_area.update_traces(line_color='#00CC96', fillcolor='rgba(0, 204, 150, 0.2)')
                fig_area.update_layout(xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                st.plotly_chart(fig_area, use_container_width=True)

    with col_graf2:
        with st.container(border=True):
            tab_sec, tab_cur = st.tabs(["🏭 SEKTORY", "💱 MĚNY"])
            with tab_sec:
                if not vdf.empty:
                    df_sector = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
                    fig_pie = px.pie(df_sector, values='HodnotaUSD', names='Sektor', hole=0.7, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Bold)
                    fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=150, paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_pie, use_container_width=True)
                    st.dataframe(df_sector, use_container_width=True, hide_index=True)
                else: st.info("Žádná data")
            with tab_cur:
                if not vdf.empty:
                    df_curr = vdf.groupby('Měna')['HodnotaUSD'].sum().reset_index()
                    fig_cur = px.pie(df_curr, values='HodnotaUSD', names='Měna', hole=0.7, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_cur.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=150, paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_cur, use_container_width=True)
                    st.dataframe(df_curr, use_container_width=True, hide_index=True)
                else: st.info("Žádná data")

    st.write("")
    with st.container(border=True):
        c_head, c_check = st.columns([4, 1])
        c_head.subheader("📋 PORTFOLIO LIVE")
        st.session_state['show_portfolio_live'] = c_check.checkbox("Zobrazit", value=st.session_state['show_portfolio_live'])
        if st.session_state['show_portfolio_live'] and not vdf.empty:
            st.dataframe(vdf, use_container_width=True, hide_index=True)
        elif vdf.empty: st.info("Portfolio je prázdné.")

def render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST):
    # LOCAL IMPORT (Abychom se vyhnuli kruhové závislosti)
    from logic_portfolio import pridat_do_watchlistu, odebrat_z_watchlistu

    st.title("👀 WATCHLIST (Hlídač) – Cenové zóny")
    with st.expander("➕ Přidat novou akcii", expanded=False):
        with st.form("add_w", clear_on_submit=True):
            t = st.text_input("Symbol (např. AAPL)").upper()
            c_buy, c_sell = st.columns(2)
            with c_buy: target_buy = st.number_input("Cílová NÁKUPNÍ cena ($)", min_value=0.0)
            with c_sell: target_sell = st.number_input("Cílová PRODEJNÍ cena ($)", min_value=0.0)
            if st.form_submit_button("Sledovat"):
                if t and (target_buy > 0 or target_sell > 0): pridat_do_watchlistu(t, target_buy, target_sell, USER); st.rerun()
                else: st.warning("Zadejte symbol a alespoň jednu cílovou cenu.")

    if not df_watch.empty:
        st.dataframe(df_watch, use_container_width=True, hide_index=True)
        st.divider()
        c_del1, c_del2 = st.columns([3, 1])
        with c_del2:
            to_del = st.selectbox("Vyber pro smazání:", df_watch['Ticker'].unique())
            if st.button("🗑️ Smazat", use_container_width=True): odebrat_z_watchlistu(to_del, USER); st.rerun()
    else: st.info("Zatím nic nesleduješ.")

def render_dividendy_page(USER, df, df_div, kurzy, viz_data_list):
    # LOCAL IMPORT
    from logic_portfolio import pridat_dividendu

    st.title("💎 DIVIDENDOVÝ KALENDÁŘ")
    st.metric("CELKEM VYPLACENO (CZK)", f"{df_div['Castka'].sum():,.0f} (Hrubý odhad)" if not df_div.empty else "0")
    
    t_div1, t_div2, t_div3 = st.tabs(["HISTORIE VÝPLAT", "❄️ EFEKT SNĚHOVÉ KOULE", "PŘIDAT DIVIDENDU"])
    with t_div1:
        if not df_div.empty: st.dataframe(df_div, use_container_width=True, hide_index=True)
        else: st.info("Zatím žádné dividendy.")
    with t_div2:
        st.info("Graf kumulace dividend.")
    with t_div3:
        with st.form("add_div"):
            dt_ticker = st.selectbox("Ticker", df['Ticker'].unique() if not df.empty else ["Jiny"])
            dt_amount = st.number_input("Částka (Netto)", 0.0, step=0.1)
            dt_curr = st.selectbox("Měna", ["USD", "CZK", "EUR"])
            if st.form_submit_button("💰 PŘIPSAT DIVIDENDU"):
                pridat_dividendu(dt_ticker, dt_amount, dt_curr, USER)
                st.success("Připsáno!"); time.sleep(1); st.rerun()

def render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky):
    # LOCAL IMPORT
    from logic_portfolio import get_task_progress, RPG_TASKS

    st.title("🎮 INVESTIČNÍ ARÉNA")
    with st.container(border=True):
        c_lev1, c_lev2 = st.columns([3, 1])
        with c_lev1:
            st.subheader(f"Úroveň: {level_name}")
            st.progress(level_progress)
        with c_lev2:
            st.markdown(f"<h1 style='text-align: center; font-size: 50px;'>🏆</h1>", unsafe_allow_html=True)

    st.divider()
    st.subheader("📜 QUEST LOG")
    if 'rpg_tasks' not in st.session_state:
        st.session_state['rpg_tasks'] = []
        for i, task in enumerate(RPG_TASKS): st.session_state['rpg_tasks'].append({"id": i, "title": task["title"], "desc": task["desc"], "completed": False})

    df_w = st.session_state.get('df_watch', pd.DataFrame())
    for i, task_state in enumerate(st.session_state['rpg_tasks']):
        original_task = RPG_TASKS[task_state['id']]
        current, target, progress_text = get_task_progress(task_state['id'], df, df_w, zustatky, vdf)
        with st.container(border=True):
             st.write(f"**{original_task['title']}** - {progress_text}")
             st.progress
