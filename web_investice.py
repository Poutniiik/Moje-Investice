import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils import make_plotly_cyberpunk
from github import Github
from io import StringIO
from datetime import datetime, timedelta
from utils import make_matplotlib_cyberpunk
import matplotlib.pyplot as plt
import hashlib
import time
import zipfile
import io
import requests
import feedparser
from streamlit_lottie import st_lottie
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from fpdf import FPDF
import extra_streamlit_components as stx
import random
import pytz
from styles import get_css
from data_manager import (
    REPO_NAZEV, SOUBOR_DATA, SOUBOR_UZIVATELE, SOUBOR_HISTORIE,
    SOUBOR_CASH, SOUBOR_VYVOJ, SOUBOR_WATCHLIST, SOUBOR_DIVIDENDY,
    RISK_FREE_RATE,
    get_repo, zasifruj, uloz_csv, uloz_csv_bezpecne, nacti_csv,
    uloz_data_uzivatele, nacti_uzivatele
)
from utils import (
    ziskej_fear_greed, ziskej_zpravy, ziskej_yield, ziskej_earnings_datum,
    ziskej_detail_akcie, zjisti_stav_trhu, vytvor_pdf_report, odeslat_email,
    ziskej_ceny_hromadne, ziskej_kurzy, ziskej_info, calculate_sharpe_ratio
)
from ai_brain import (
    init_ai, ask_ai_guard, audit_portfolio, get_tech_analysis,
    generate_rpg_story, analyze_headlines_sentiment, get_chat_response
)

# --- KONFIGURACE ---
st.set_page_config(
    page_title="Terminal Pro",
    layout="wide",
    page_icon="💹",
    initial_sidebar_state="expanded"
)

# --- CITÁTY ---
CITATY = [
    "„Cena je to, co zaplatíš. Hodnota je to, co dostaneš.“ — Warren Buffett",
    "„Riziko pochází z toho, že nevíte, co děláte.“ — Warren Buffett",
    "„Trh je nástroj k přesunu peněz od netrpělivých k trpělivým.“ — Warren Buffett",
    "„Investování bez výzkumu je jako hrát poker a nedívat se na karty.“ — Peter Lynch",
    "„V krátkodobém horizontu je trh hlasovací stroj, v dlouhodobém váha.“ — Benjamin Graham",
    "„Neutrácejte to, co zbude po utrácení. Utrácejte to, co zbude po spoření.“ — Warren Buffett",
    "„Znáte ten pocit, když trh padá? To je výprodej. Nakupujte.“ — Neznámý",
    "„Bohatství není o tom mít hodně peněz, ale o tom mít hodně možností.“ — Chris Rock"
]

# --- APLIKACE STYLU ---
if 'ui_theme' not in st.session_state:
    st.session_state['ui_theme'] = "🕹️ Cyberpunk (Retro)"
st.markdown(f"<style>{get_css(st.session_state['ui_theme'])}</style>", unsafe_allow_html=True)

# --- COOKIE MANAGER ---
def get_manager():
    return stx.CookieManager(key="cookie_manager_inst")

# --- LOTTIE LOADER ---
@st.cache_data
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200: return None
    return r.json()

# --- CACHED WRAPPERS ---
@st.cache_data(ttl=3600)
def cached_detail_akcie(ticker): return ziskej_detail_akcie(ticker)

@st.cache_data(ttl=1800)
def cached_fear_greed(): return ziskej_fear_greed()

@st.cache_data(ttl=3600)
def cached_zpravy(): return ziskej_zpravy()

@st.cache_data(ttl=300)
def cached_ceny_hromadne(tickers_list): return ziskej_ceny_hromadne(tickers_list)

@st.cache_data(ttl=3600)
def cached_kurzy(): return ziskej_kurzy()

# --- UTILS ---
def invalidate_data_core():
    if 'data_core' in st.session_state:
        st.session_state['data_core']['timestamp'] = datetime.now() - timedelta(minutes=6)

@st.cache_resource(show_spinner="Připojuji neurální sítě...")
def get_cached_ai_connection():
    try: return init_ai()
    except Exception as e: print(f"Chyba init_ai: {e}"); return None, False

# --- TRANSAKČNÍ FUNKCE ---
def pridat_do_watchlistu(ticker, target_buy, target_sell, user):
    df_w = st.session_state['df_watch']
    if ticker not in df_w['Ticker'].values:
        new = pd.DataFrame([{"Ticker": ticker, "TargetBuy": float(target_buy), "TargetSell": float(target_sell), "Owner": user}])
        updated = pd.concat([df_w, new], ignore_index=True)
        st.session_state['df_watch'] = updated
        uloz_data_uzivatele(updated, user, SOUBOR_WATCHLIST)
        return True
    return False

def odebrat_z_watchlistu(ticker, user):
    df_w = st.session_state['df_watch']
    updated = df_w[df_w['Ticker'] != ticker]
    st.session_state['df_watch'] = updated
    uloz_data_uzivatele(updated, user, SOUBOR_WATCHLIST)

def get_zustatky(user):
    df_cash = st.session_state.get('df_cash', pd.DataFrame())
    if df_cash.empty: return {}
    return df_cash.groupby('Mena')['Castka'].sum().to_dict()

def pohyb_penez(castka, mena, typ, poznamka, user, df_cash_temp):
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash_temp = pd.concat([df_cash_temp, novy], ignore_index=True)
    return df_cash_temp

def pridat_dividendu(ticker, castka, mena, user):
    df_div = st.session_state['df_div']
    df_cash_temp = st.session_state['df_cash'].copy()
    
    novy = pd.DataFrame([{"Ticker": ticker, "Castka": float(castka), "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_div = pd.concat([df_div, novy], ignore_index=True)
    df_cash_temp = pohyb_penez(castka, mena, "Dividenda", f"Divi {ticker}", user, df_cash_temp)
    
    try:
        uloz_data_uzivatele(df_div, user, SOUBOR_DIVIDENDY)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        st.session_state['df_div'] = df_div
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        return True, f"✅ Připsáno {castka:,.2f} {mena} od {ticker}"
    except Exception as e: return False, f"❌ Chyba zápisu (DIVI): {e}"

def aktualizuj_graf_vyvoje(user, aktualni_hodnota_usd):
    if pd.isna(aktualni_hodnota_usd): return pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    full_hist = nacti_csv(SOUBOR_VYVOJ)
    today = datetime.now().strftime("%Y-%m-%d")
    user_hist = full_hist[full_hist['Owner'] == str(user)].copy()
    dnes_zapsano = False

    if not user_hist.empty:
        last_date = user_hist.iloc[-1]['Date']
        if pd.notnull(last_date) and last_date.strftime("%Y-%m-%d") == today:
            dnes_zapsano = True
            full_hist.at[user_hist.index[-1], 'TotalUSD'] = aktualni_hodnota_usd

    if not dnes_zapsano:
        new_row = pd.DataFrame([{"Date": datetime.now(), "TotalUSD": aktualni_hodnota_usd, "Owner": str(user)}])
        full_hist = pd.concat([full_hist, new_row], ignore_index=True)

    uloz_csv(full_hist, SOUBOR_VYVOJ, "Daily snapshot")
    return full_hist[full_hist['Owner'] == str(user)]

def proved_nakup(ticker, kusy, cena, user):
    df_p = st.session_state['df'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    _, mena, _ = ziskej_info(ticker)
    cost = kusy * cena
    zustatky = get_zustatky(user)

    if zustatky.get(mena, 0) >= cost:
        df_cash_temp = pohyb_penez(-cost, mena, "Nákup", ticker, user, df_cash_temp)
        d = pd.DataFrame([{"Ticker": ticker, "Pocet": kusy, "Cena": cena, "Datum": datetime.now(), "Owner": user, "Sektor": "Doplnit", "Poznamka": "CLI/Auto"}])
        df_p = pd.concat([df_p, d], ignore_index=True)
        try:
            uloz_data_uzivatele(df_p, user, SOUBOR_DATA)
            uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
            st.session_state['df'] = df_p
            st.session_state['df_cash'] = df_cash_temp
            invalidate_data_core()
            return True, f"✅ Koupeno: {kusy}x {ticker}"
        except Exception as e: return False, f"❌ Chyba zápisu: {e}"
    else: return False, f"❌ Nedostatek {mena}"

def proved_prodej(ticker, kusy, cena, user, mena_input):
    df_p = st.session_state['df'].copy()
    df_h = st.session_state['df_hist'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')

    final_mena = mena_input
    if final_mena is None or final_mena == "N/A":
        final_mena = "USD"
        if not df_t.empty and 'Měna' in df_p.columns: final_mena = df_p[df_p['Ticker'] == ticker].iloc[0].get('Měna', 'USD')
        elif 'LIVE_DATA' in st.session_state: final_mena = st.session_state['LIVE_DATA'].get(ticker, {}).get('curr', 'USD')

    if df_t.empty or df_t['Pocet'].sum() < kusy: return False, "Nedostatek kusů."

    zbyva, zisk, trzba = kusy, 0, kusy * cena
    df_p_novy = df_p.copy()
    indices_to_drop = []
    
    for idx, row in df_t.iterrows():
        if zbyva <= 0: break
        ukrojeno = min(row['Pocet'], zbyva)
        zisk += (cena - row['Cena']) * ukrojeno
        if ukrojeno == row['Pocet']: indices_to_drop.append(idx)
        else: df_p_novy.at[idx, 'Pocet'] -= ukrojeno
        zbyva -= ukrojeno

    df_p_novy = df_p_novy.drop(indices_to_drop)
    new_h = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, "Mena": final_mena, "Datum": datetime.now(), "Owner": user}])
    df_h = pd.concat([df_h, new_h], ignore_index=True)
    df_cash_temp = pohyb_penez(trzba, final_mena, "Prodej", f"Prodej {ticker}", user, df_cash_temp)
    
    try:
        uloz_data_uzivatele(df_p_novy, user, SOUBOR_DATA)
        uloz_data_uzivatele(df_h, user, SOUBOR_HISTORIE)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        st.session_state['df'] = df_p_novy
        st.session_state['df_hist'] = df_h
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        return True, f"Prodáno! +{trzba:,.2f} {final_mena}"
    except Exception as e: return False, f"❌ Chyba zápisu: {e}"

def proved_smenu(castka, z_meny, do_meny, user):
    kurzy = st.session_state['data_core']['kurzy']
    df_cash_temp = st.session_state['df_cash'].copy()
    
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy.get("CZK", 20.85)
    elif z_meny == "EUR": castka_usd = castka / kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85) / kurzy.get("CZK", 20.85)

    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurzy.get("CZK", 20.85)
    elif do_meny == "EUR": vysledna = castka_usd / kurzy.get("EUR", 1.16)

    df_cash_temp = pohyb_penez(-castka, z_meny, "Směna", f"Směna na {do_meny}", user, df_cash_temp)
    df_cash_temp = pohyb_penez(vysledna, do_meny, "Směna", f"Směna z {z_meny}", user, df_cash_temp)
    
    try:
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        return True, f"Směněno: {vysledna:,.2f} {do_meny}"
    except Exception as e: return False, f"❌ Chyba směny: {e}"

# --- HELPER VIZUALIZACE ---
def render_ticker_tape(data_dict):
    if not data_dict: return
    content = ""
    for ticker, info in data_dict.items():
        content += f"&nbsp;&nbsp;&nbsp;&nbsp; <b>{ticker}</b>: {info.get('price', 0):,.2f} {info.get('curr', '')}"
    st.markdown(f"""<div style="background-color: #161B22; border: 1px solid #30363D; padding: 8px; margin-bottom: 20px; white-space: nowrap; overflow: hidden;"><div style="display: inline-block; animation: marquee 20s linear infinite; color: #00CC96; font-family: 'Roboto Mono'; font-weight: bold;">{content} {content} {content}</div></div><style>@keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}</style>""", unsafe_allow_html=True)

def add_download_button(fig, filename):
    try:
        buffer = io.BytesIO()
        fig.write_image(buffer, format="png", width=1200, height=800, scale=2)
        st.download_button(label=f"⬇️ Stáhnout: {filename}", data=buffer.getvalue(), file_name=f"{filename}.png", mime="image/png", use_container_width=True)
    except: st.caption("💡 Tip: Pro stažení použij ikonu fotoaparátu v grafu.")

# --- RPG SYSTÉM ---
def get_task_progress(task_id, df, df_w, zustatky, vdf):
    if task_id == 0: # Watchlist
        current = 1 if not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique()) else 0
        return current, 1, f"Sledované: {current}/1"
    elif task_id == 1: # Sektory
        current = df['Sektor'].nunique() if not df.empty else 0
        return current, 3, f"Sektorů: {current}/3"
    elif task_id == 2: # Měny
        current = sum(1 for v in zustatky.values() if v > 100)
        return current, 2, f"Měn: {current}/2"
    elif task_id == 3: # Dividendy
        viz_data_list_safe = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
        current = len([i for i in viz_data_list_safe if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01])
        return current, 3, f"Divi akcií: {current}/3"
    elif task_id == 4: # Targets
        has_buy = (df_w['TargetBuy'] > 0).any(); has_sell = (df_w['TargetSell'] > 0).any()
        current = (1 if has_buy else 0) + (1 if has_sell else 0)
        return current, 2, f"Cíle: {current}/2"
    elif task_id == 5: # Cash CZK
        current = zustatky.get('CZK', 0); target = 5000
        return min(current, target), target, f"CZK: {current:,.0f}/{target:,.0f}"
    return 0, 1, "N/A"

RPG_TASKS = [
    {"title": "První průzkum", "desc": "Přidej do Watchlistu novou akcii.", "check_fn": lambda df, df_w, z, v: not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique())},
    {"title": "Diverzifikace", "desc": "Drž akcie ve 3 sektorech.", "check_fn": lambda df, df_w, z, v: df['Sektor'].nunique() >= 3},
    {"title": "Měnová rovnováha", "desc": "Drž hotovost ve 2 měnách.", "check_fn": lambda df, df_w, z, v: sum(1 for val in z.values() if val > 100) >= 2},
    {"title": "Mód Rentiera", "desc": "Drž 3 divi akcie (>1%).", "check_fn": lambda df, df_w, z, vdf: len([i for i in (vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf) if i.get('Divi', 0) > 0.01]) >= 3},
    {"title": "Cílovací expert", "desc": "Nastav Buy i Sell target.", "check_fn": lambda df, df_w, z, v: (df_w['TargetBuy'] > 0).any() and (df_w['TargetSell'] > 0).any()},
    {"title": "Pohotovostní fond", "desc": "Drž 5000 CZK hotovost.", "check_fn": lambda df, df_w, z, v: z.get('CZK', 0) >= 5000},
]

# --- STRÁNKY ---
def render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA):
    st.title(f"🏠 PŘEHLED: {USER.upper()}")
    with st.container(border=True):
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{(celk_hod_usd-celk_inv_usd)*kurzy.get('CZK', 21):+,.0f} Kč Zisk")
        k2.metric("🌎 JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} USD")
        k3.metric("📈 ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        k4.metric("💳 HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné prostředky")

    c_left, c_right = st.columns([1, 2])
    with c_left:
        with st.container(border=True):
            st.caption("🧠 PSYCHOLOGIE TRHU")
            score, rating = cached_fear_greed()
            if score:
                st.metric("Fear & Greed Index", f"{score}/100", rating)
                fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=score, domain={'x': [0, 1], 'y': [0, 1]}, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "white"}, 'steps': [{'range': [0, 25], 'color': '#FF4136'}, {'range': [75, 100], 'color': '#2ECC40'}]}))
                fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=120, margin=dict(l=20,r=20,t=20,b=20), font={'color': "white"})
                st.plotly_chart(fig_gauge, use_container_width=True)

    with c_right:
        with st.container(border=True):
            st.caption("🧭 GLOBÁLNÍ KOMPAS")
            try:
                makro = {"🇺🇸 S&P 500": "^GSPC", "🥇 Zlato": "GC=F", "₿ Bitcoin": "BTC-USD", "🏦 Úroky": "^TNX"}
                data = yf.download(list(makro.values()), period="5d", progress=False)['Close']
                mc1, mc2, mc3, mc4 = st.columns(4)
                cols = [mc1, mc2, mc3, mc4]
                for i, (name, tick) in enumerate(makro.items()):
                    with cols[i]:
                        ser = data[tick].dropna() if tick in data else pd.Series()
                        if not ser.empty:
                            l = ser.iloc[-1]; p = ser.iloc[-2]
                            d = ((l-p)/p)*100
                            st.metric(name, f"{l:,.0f}", f"{d:+.2f}%")
                            fig_s = go.Figure(go.Scatter(y=ser.values, mode='lines', line=dict(color='#238636' if d>=0 else '#da3633', width=2), fill='tozeroy'))
                            fig_s.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=35, xaxis={'visible':False}, yaxis={'visible':False}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_s, use_container_width=True, config={'displayModeBar': False})
            except: st.error("Chyba kompasu")

    if not hist_vyvoje.empty:
        chart = hist_vyvoje.copy(); chart['TotalCZK'] = chart['TotalUSD'] * kurzy.get("CZK", 21)
        fig = px.area(chart, x='Date', y='TotalCZK', template="plotly_dark")
        fig.update_traces(line_color='#00CC96', fillcolor='rgba(0, 204, 150, 0.2)')
        fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)
    
    if not vdf.empty:
        st.dataframe(vdf, use_container_width=True, hide_index=True)

def render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST):
    st.title("👀 WATCHLIST")
    with st.expander("➕ Přidat", expanded=False):
        with st.form("add_w"):
            t = st.text_input("Symbol").upper()
            c1, c2 = st.columns(2)
            with c1: b = st.number_input("Buy Target", min_value=0.0)
            with c2: s = st.number_input("Sell Target", min_value=0.0)
            if st.form_submit_button("Sledovat"):
                if t and (b>0 or s>0): pridat_do_watchlistu(t, b, s, USER); st.rerun()
    
    if not df_watch.empty:
        w_data = []
        for _, r in df_watch.iterrows():
            tk = r['Ticker']
            inf = LIVE_DATA.get(tk, {})
            p = inf.get('price'); c = inf.get('curr', 'USD')
            if not p: p, _, _ = ziskej_info(tk)
            
            stat = "Wait"; score = 0.0
            if p:
                if r['TargetBuy'] > 0:
                    if p <= r['TargetBuy']: stat="🔥 BUY"; score=1.0
                    else: score = max(0, 1 - ((p-r['TargetBuy'])/p)/0.2)
                elif r['TargetSell'] > 0:
                    if p >= r['TargetSell']: stat="💰 SELL"; score=1.0
                    else: score = max(0, 1 - ((r['TargetSell']-p)/p)/0.2)
            
            w_data.append({"Symbol": tk, "Cena": p, "Měna": c, "Cíl Buy": r['TargetBuy'], "Zaměřovač": score, "Status": stat})
        
        st.dataframe(pd.DataFrame(w_data), column_config={"Zaměřovač": st.column_config.ProgressColumn(min_value=0, max_value=1)}, use_container_width=True, hide_index=True)
        
        to_del = st.selectbox("Smazat:", df_watch['Ticker'].unique())
        if st.button("🗑️ Smazat"): odebrat_z_watchlistu(to_del, USER); st.rerun()

def render_obchod_page(USER, df, zustatky, kurzy):
    st.title("💸 OBCHODNÍ TERMINÁL")
    t1, t2, t3 = st.tabs(["NÁKUP", "PRODEJ", "SMĚNÁRNA"])
    
    with t1:
        with st.form("buy_f"):
            tk = st.text_input("Ticker (např. AAPL)").upper()
            ks = st.number_input("Kusy", min_value=0.01, step=0.1)
            if st.form_submit_button("Koupit"):
                p, _, _ = ziskej_info(tk)
                if p:
                    ok, msg = proved_nakup(tk, ks, p, USER)
                    if ok: st.success(msg); time.sleep(1); st.rerun()
                    else: st.error(msg)
                else: st.error("Nenalezena cena")
                
    with t2:
        with st.form("sell_f"):
            tk_s = st.selectbox("Akcie", df['Ticker'].unique() if not df.empty else [])
            ks_s = st.number_input("Kusy na prodej", min_value=0.01, step=0.1)
            if st.form_submit_button("Prodat"):
                p, m, _ = ziskej_info(tk_s)
                ok, msg = proved_prodej(tk_s, ks_s, p, USER, m)
                if ok: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)

    with t3:
        with st.form("ex_f"):
            c1, c2, c3 = st.columns(3)
            with c1: amt = st.number_input("Částka", min_value=1.0)
            with c2: fr = st.selectbox("Z měny", ["CZK", "USD", "EUR"])
            with c3: to = st.selectbox("Do měny", ["USD", "CZK", "EUR"])
            if st.form_submit_button("Směnit"):
                if get_zustatky(USER).get(fr, 0) >= amt:
                    ok, msg = proved_smenu(amt, fr, to, USER)
                    if ok: st.success(msg); time.sleep(1); st.rerun()
                    else: st.error(msg)
                else: st.error("Nedostatek prostředků")

def render_zpravy_page(AI_AVAILABLE, model):
    st.title("📰 ZPRÁVY Z TRHU")
    if st.button("🔄 Obnovit zprávy"): st.cache_data.clear(); st.rerun()
    
    news = cached_zpravy()
    
    if news:
        if AI_AVAILABLE:
            with st.expander("🤖 AI Analýza Sentimentu (Beta)", expanded=True):
                if 'sentiment_cache' not in st.session_state:
                    st.session_state['sentiment_cache'] = analyze_headlines_sentiment(news, model)
                st.write(st.session_state['sentiment_cache'])
        
        for n in news[:15]:
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                with c1: st.caption(n['published'])
                with c2:
                    st.markdown(f"**[{n['title']}]({n['link']})**")
                    st.caption(f"Zdroj: {n['source']}")
    else: st.info("Žádné nové zprávy.")

def render_dividendy_page(USER, df, df_div, kurzy, viz_data_list):
    st.title("💎 DIVIDENDY")
    est = 0
    data = viz_data_list.to_dict('records') if isinstance(viz_data_list, pd.DataFrame) else viz_data_list
    if data:
        for i in data:
            yld = i.get('Divi', 0); val = i.get('HodnotaUSD', 0)
            if yld and val: est += (val * yld) * kurzy.get("CZK", 21)
    
    st.metric("Očekávaný roční příjem (CZK)", f"{est:,.0f} Kč", f"{est/12:,.0f} Kč měsíčně")
    
    with st.form("add_d"):
        t = st.selectbox("Ticker", df['Ticker'].unique() if not df.empty else ["Jiny"])
        a = st.number_input("Částka Netto", 0.1)
        c = st.selectbox("Měna", ["USD", "CZK", "EUR"])
        if st.form_submit_button("Připsat"):
            pridat_dividendu(t, a, c, USER); st.rerun()
            
    if not df_div.empty:
        st.dataframe(df_div.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)

def render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, df, df_watch, zustatky, vdf, model, AI_AVAILABLE):
    st.title("🎮 ARÉNA")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader(f"Level: {level_name}")
        st.progress(level_progress)
        lottie_url = "https://assets5.lottiefiles.com/packages/lf20_bkjkaw6u.json"
        lottie_json = load_lottieurl(lottie_url)
        if lottie_json: st_lottie(lottie_json, height=150)
    
    with c2:
        st.subheader("📜 Tvůj příběh")
        if AI_AVAILABLE:
            if 'rpg_story' not in st.session_state:
                with st.spinner("Dungeon Master píše osud..."):
                    st.session_state['rpg_story'] = generate_rpg_story(level_name, celk_hod_czk, model)
            st.info(st.session_state['rpg_story'])
            if st.button("🎲 Přepsat osud"):
                del st.session_state['rpg_story']; st.rerun()
        else:
            st.warning("AI Modul nedostupný pro RPG příběh.")

    st.divider(); st.subheader("Výzvy")
    for i, t in enumerate(RPG_TASKS):
        done = t['check_fn'](df, df_watch, zustatky, vdf)
        curr, targ, txt = get_task_progress(i, df, df_watch, zustatky, vdf)
        with st.container(border=True):
            tc1, tc2 = st.columns([1, 5])
            with tc1: st.write("✅" if done else "🔒")
            with tc2:
                st.write(f"**{t['title']}**")
                st.caption(t['desc'])
                if not done and targ > 0:
                    st.progress(min(curr/targ, 1.0))
                    st.caption(f"{txt}")

def render_nastaveni_page(USER):
    st.title("⚙️ NASTAVENÍ")
    st.info(f"Přihlášen jako: {USER}")
    if st.button("Vymazat mezipaměť"): st.cache_data.clear(); st.rerun()
    with st.expander("Vývojářské nástroje"):
        st.json(st.session_state)

# --- ANALÝZA (RENTGEN + CRASH TEST KOMPLETNÍ) ---
def render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE):
    st.subheader("🔍 RENTGEN AKCIE")
    
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        search_ticker = st.text_input("Hledat Ticker (např. TSLA, AAPL)", "").upper()
    
    # Priorita vyhledávání: Input -> Selectbox
    if search_ticker:
        sel = search_ticker
    else:
        sel = st.selectbox("Vyber z portfolia:", df['Ticker'].unique() if not df.empty else [])

    if sel:
        info, hist = ziskej_detail_akcie(sel)
        
        if info:
            st.title(f"{info.get('shortName', sel)} ({sel})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Cena", f"{info.get('currentPrice', 'N/A')} {info.get('currency', 'USD')}")
            c2.metric("Target (Analytici)", f"{info.get('targetMeanPrice', 'N/A')}")
            c3.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A')}")
            c4.metric("52 Week High", f"{info.get('fiftyTwoWeekHigh', 'N/A')}")

            tab1, tab2, tab3 = st.tabs(["📊 Graf", "📑 Fundamenty", "🤖 AI Názor"])
            
            with tab1:
                if hist is not None and not hist.empty:
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Cena"), secondary_y=False)
                    fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Objem", opacity=0.3), secondary_y=True)
                    fig.update_layout(height=400, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)
                    add_download_button(fig, f"graf_{sel}")

            with tab2:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    st.write("**Popis:**")
                    st.caption(info.get('longBusinessSummary', 'N/A'))
                with col_f2:
                    st.write("**Klíčová data:**")
                    st.write(f"Sektor: {info.get('sector', 'N/A')}")
                    st.write(f"Beta: {info.get('beta', 'N/A')}")
                    st.write(f"Dividend Yield: {info.get('dividendYield', 0)*100:.2f}%")
            
            with tab3:
                if AI_AVAILABLE:
                    st.write("💬 **Zeptej se AI na tuto akcii:**")
                    user_q = st.text_input("Tvůj dotaz:", f"Jaký je výhled pro {sel}?")
                    if st.button("Odeslat dotaz"):
                        with st.spinner("AI analyzuje..."):
                            resp = ask_ai_guard(user_q, model)
                            st.markdown(resp)
                else:
                    st.warning("AI není připojena.")

def render_analýza_crash_test(celk_hod_czk):
    st.subheader("💥 CRASH TEST")
    st.markdown("Simulace dopadu historických krizí na tvé portfolio.")
    
    scenarios = {
        "COVID-19 (2020)": {"drop": 34, "icon": "🦠", "desc": "Pandemie zastavila světovou ekonomiku."},
        "Finanční krize (2008)": {"drop": 57, "icon": "📉", "desc": "Kolaps trhu s bydlením v USA."},
        "Dot-com (2000)": {"drop": 49, "icon": "💻", "desc": "Splasknutí technologické bubliny."},
        "Black Monday (1987)": {"drop": 22, "icon": "⚡", "desc": "Největší jednodenní propad v historii."}
    }
    
    if 'crash_sim_drop' not in st.session_state: st.session_state['crash_sim_drop'] = 20
    if 'crash_sim_name' not in st.session_state: st.session_state['crash_sim_name'] = "Vlastní"

    cols = st.columns(4)
    for i, (name, data) in enumerate(scenarios.items()):
        with cols[i]:
            if st.button(f"{data['icon']} {name}", key=f"btn_crash_{i}", use_container_width=True):
                st.session_state['crash_sim_drop'] = data['drop']
                st.session_state['crash_sim_name'] = name

    st.divider()
    drop_pct = st.session_state['crash_sim_drop']
    name_sim = st.session_state['crash_sim_name']
    
    current_val = celk_hod_czk
    after_crash = current_val * (1 - drop_pct/100)
    loss = current_val - after_crash
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric(f"Scénář: {name_sim}", f"-{drop_pct} %")
        st.progress(drop_pct/100)
    with c2:
        st.metric("Zůstatek po pádu", f"{after_crash:,.0f} Kč", f"-{loss:,.0f} Kč", delta_color="inverse")
    
    # Jednoduchý vizuál pádu
    chart_data = pd.DataFrame({
        "Fáze": ["Před krizí", "Dno krize"],
        "Hodnota": [current_val, after_crash]
    })
    fig = px.bar(chart_data, x="Fáze", y="Hodnota", color="Fáze", color_discrete_map={"Před krizí": "#00CC96", "Dno krize": "#EF553B"}, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Poznámka: Historie ukazuje, že trhy se nakonec vždy zotavily. Otázkou je, zda máš nervy to ustát.")

# --- DAT CORE ---
def calculate_all_data(USER, df, df_watch, zustatky, kurzy):
    all_tickers = []
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    
    LIVE_DATA = cached_ceny_hromadne(list(set(all_tickers)))
    st.session_state['LIVE_DATA'] = LIVE_DATA if LIVE_DATA else {}
    if LIVE_DATA:
        if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
        if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]

    fundament_data = {}
    if not df.empty:
        for tkr in df['Ticker'].unique(): fundament_data[tkr], _ = cached_detail_akcie(tkr)

    viz_data = []; celk_hod_usd = 0; celk_inv_usd = 0
    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        for _, row in df_g.iterrows():
            tkr = row['Ticker']; p, m, d_zmena = ziskej_info(tkr)
            if p is None: p = row['Cena']
            if m is None or m == "N/A": m = "USD"
            k = 1.0
            if m == "CZK": k = 1.0 / kurzy.get("CZK", 21)
            elif m == "EUR": k = kurzy.get("EUR", 1.16)
            
            val = row['Pocet']*p
            celk_hod_usd += val*k
            celk_inv_usd += (row['Pocet']*row['Cena'])*k
            
            fund = fundament_data.get(tkr, {})
            viz_data.append({
                "Ticker": tkr, "HodnotaUSD": val*k, "Zisk": (p-row['Cena'])*row['Pocet'],
                "Měna": m, "Kusy": row['Pocet'], "Cena": p, "Dnes": d_zmena, "Divi": ziskej_yield(tkr),
                "Sektor": df[df['Ticker']==tkr]['Sektor'].iloc[0] if 'Sektor' in df.columns else "N/A"
            })

    vdf = pd.DataFrame(viz_data) if viz_data else pd.DataFrame()
    hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    zmena_24h = 0; pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if vcera > 0: zmena_24h = celk_hod_usd - vcera; pct_24h = (zmena_24h/vcera)*100
        
    cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 21)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))
    
    return {
        'vdf': vdf, 'viz_data_list': viz_data, 'celk_hod_usd': celk_hod_usd,
        'celk_inv_usd': celk_inv_usd, 'hist_vyvoje': hist_vyvoje, 'zmena_24h': zmena_24h,
        'pct_24h': pct_24h, 'cash_usd': cash_usd, 'fundament_data': fundament_data,
        'kurzy': kurzy, 'timestamp': datetime.now()
    }

# --- MAIN ---
def main():
    model, AI_AVAILABLE = get_cached_ai_connection()
    cookie_manager = get_manager()
    
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False
        st.session_state['user'] = ""

    time.sleep(0.1)
    if not st.session_state['prihlasen']:
        u_cook = cookie_manager.get("invest_user")
        if u_cook: st.session_state.update({'prihlasen': True, 'user': u_cook}); st.rerun()

    if not st.session_state['prihlasen']:
        st.title("🔐 Login")
        with st.form("log"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                df_u = nacti_uzivatele()
                row = df_u[df_u['username'] == u]
                if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                    cookie_manager.set("invest_user", u, expires_at=datetime.now()+timedelta(days=30))
                    st.session_state.update({'prihlasen': True, 'user': u})
                    st.rerun()
                else: st.error("Chyba")
        return

    USER = st.session_state['user']
    
    # Load Data
    if 'df' not in st.session_state:
        st.session_state['df'] = nacti_csv(SOUBOR_DATA).query(f"Owner=='{USER}'").copy()
        st.session_state['df_hist'] = nacti_csv(SOUBOR_HISTORIE).query(f"Owner=='{USER}'").copy()
        st.session_state['df_cash'] = nacti_csv(SOUBOR_CASH).query(f"Owner=='{USER}'").copy()
        st.session_state['df_div'] = nacti_csv(SOUBOR_DIVIDENDY).query(f"Owner=='{USER}'").copy()
        st.session_state['df_watch'] = nacti_csv(SOUBOR_WATCHLIST).query(f"Owner=='{USER}'").copy()
    
    df = st.session_state['df']; df_watch = st.session_state['df_watch']
    zustatky = get_zustatky(USER); kurzy = cached_kurzy()

    # Core Calculation
    if 'data_core' not in st.session_state or (datetime.now() - st.session_state['data_core']['timestamp']) > timedelta(minutes=5):
        with st.spinner("Aktualizuji..."):
            data_core = calculate_all_data(USER, df, df_watch, zustatky, kurzy)
            st.session_state['data_core'] = data_core
    else: data_core = st.session_state['data_core']
    
    # Extract
    vdf = data_core['vdf']; celk_hod_usd = data_core['celk_hod_usd']; celk_inv_usd = data_core['celk_inv_usd']
    celk_hod_czk = celk_hod_usd * kurzy.get("CZK", 21)
    hist_vyvoje = data_core['hist_vyvoje']; cash_usd = data_core['cash_usd']
    LIVE_DATA = st.session_state.get('LIVE_DATA', {}); fundament_data = data_core['fundament_data']

    # Sidebar
    with st.sidebar:
        st.header(f"👤 {USER}")
        page = st.radio("Navigace", ["🏠 Přehled", "👀 Sledování", "💸 Obchod", "📰 Zprávy", "📈 Analýza", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení"])
        if st.button("🚪 Odhlásit"): cookie_manager.delete("invest_user"); st.session_state.clear(); st.rerun()

    render_ticker_tape(LIVE_DATA)

    # Router
    if page == "🏠 Přehled":
        render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, data_core['zmena_24h'], data_core['pct_24h'], cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA)
    elif page == "👀 Sledování":
        render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST)
    elif page == "💸 Obchod":
        render_obchod_page(USER, df, zustatky, kurzy)
    elif page == "📰 Zprávy":
        render_zpravy_page(AI_AVAILABLE, model)
    elif page == "📈 Analýza":
        t1, t2 = st.tabs(["Rentgen", "Crash Test"])
        with t1: render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE)
        with t2: render_analýza_crash_test(celk_hod_czk)
    elif page == "💎 Dividendy":
        render_dividendy_page(USER, df, st.session_state['df_div'], kurzy, vdf)
    elif page == "🎮 Gamifikace":
        # Level logic simplified
        lvl = "Novic" if celk_hod_czk < 10000 else "Profi"
        prog = min(celk_hod_czk/10000, 1.0)
        render_gamifikace_page(USER, lvl, prog, celk_hod_czk, df, df_watch, zustatky, vdf, model, AI_AVAILABLE)
    elif page == "⚙️ Nastavení":
        render_nastaveni_page(USER)

if __name__ == "__main__":
    main()
