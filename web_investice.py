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
import notification_engine as notify # TELEGRAM NOTIFIKACE
import bank_engine as bank # BANKOVNÍ ENGINE

# --- KONFIGURACE ---
# Důležité: set_page_config MUSÍ být voláno jako první Streamlit příkaz
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

# --- ANALÝZA SENTIMENTU ---
KW_POSITIVNI = ["RŮST", "ZISK", "REKORD", "DIVIDEND", "POKLES INFLACE", "BÝČÍ", "UP", "PROFIT", "HIGHS", "SKOK", "VYDĚLAL"]
KW_NEGATIVNI = ["PÁD", "ZTRÁTA", "KRIZE", "MEDVĚDÍ", "DOWN", "LOSS", "CRASH", "PRODĚLAL", "VÁLKA", "BANKROT", "INFLACE", "POKLES"]


# --- APLIKACE STYLU (Tohle se musí stát hned) ---
# Defaultně nastavíme Cyberpunk, ale uživatel si to může změnit v Sidebaru
if 'ui_theme' not in st.session_state:
    st.session_state['ui_theme'] = "🕹️ Cyberpunk (Retro)"

# Aplikujeme styl
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

# --- TURBO CACHE WRAPPERS (ZRYCHLENÍ APLIKACE) ---
@st.cache_data(ttl=3600) 
def cached_detail_akcie(ticker):
    return ziskej_detail_akcie(ticker)

@st.cache_data(ttl=1800) 
def cached_fear_greed():
    return ziskej_fear_greed()

@st.cache_data(ttl=3600) 
def cached_zpravy():
    return ziskej_zpravy()

@st.cache_data(ttl=300) 
def cached_ceny_hromadne(tickers_list):
    return ziskej_ceny_hromadne(tickers_list)

@st.cache_data(ttl=3600) 
def cached_kurzy():
    return ziskej_kurzy()

# -----------------------------------------------------

# --- NÁSTROJ PRO ŘÍZENÍ STAVU: ZNEHODNOCENÍ DAT ---
def invalidate_data_core():
    """Vynutí opětovný přepočet datového jádra při příštím zobrazení stránky."""
    if 'data_core' in st.session_state:
        st.session_state['data_core']['timestamp'] = datetime.now() - timedelta(minutes=6)

# --- OPRAVA 1: CACHOVANÁ INICIALIZACE AI ---
@st.cache_resource(show_spinner="Připojuji neurální sítě...")
def get_cached_ai_connection():
    """
    Tato funkce zajistí, že se init_ai() zavolá jen JEDNOU za běh serveru,
    ne při každém kliknutí uživatele. To zabrání chybě 429.
    """
    try:
        return init_ai()
    except Exception as e:
        print(f"Chyba init_ai: {e}")
        return None, False

# --- DATABÁZE A TRANSAKČNÍ FUNKCE (Zachovány) ---
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

# --- ATOMICKÁ FUNKCE: POHYB PENĚZ ---
def pohyb_penez(castka, mena, typ, poznamka, user, df_cash_temp):
    """
    Provede pohyb peněz a vrátí upravený DataFrame. 
    ULOŽENÍ do souboru se DĚJE VŽDY AŽ PO ÚSPĚŠNÉ TRANSAKCI.
    """
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash_temp = pd.concat([df_cash_temp, novy], ignore_index=True)
    return df_cash_temp

def pridat_dividendu(ticker, castka, mena, user):
    df_div = st.session_state['df_div']
    df_cash_temp = st.session_state['df_cash'].copy()
    
    # Krok 1: Záznam dividendy
    novy = pd.DataFrame([{"Ticker": ticker, "Castka": float(castka), "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_div = pd.concat([df_div, novy], ignore_index=True)
    
    # Krok 2: Pohyb peněz (Atomický)
    df_cash_temp = pohyb_penez(castka, mena, "Dividenda", f"Divi {ticker}", user, df_cash_temp)
    
    # Krok 3: Uložení obou změn a invalidace
    try:
        uloz_data_uzivatele(df_div, user, SOUBOR_DIVIDENDY)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        
        # Aktualizace Session State AŽ PO ÚSPĚCHU
        st.session_state['df_div'] = df_div
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        return True, f"✅ Připsáno {castka:,.2f} {mena} od {ticker}"
    except Exception as e:
        return False, f"❌ Chyba zápisu transakce (DIVI): {e}"


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

# --- ATOMICKÁ FUNKCE: PROVEDENÍ NÁKUPU ---
def proved_nakup(ticker, kusy, cena, user):
    df_p = st.session_state['df'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    
    _, mena, _ = ziskej_info(ticker)
    cost = kusy * cena
    zustatky = get_zustatky(user)

    if zustatky.get(mena, 0) >= cost:
        # Krok 1: Odepsání hotovosti (lokálně)
        df_cash_temp = pohyb_penez(-cost, mena, "Nákup", ticker, user, df_cash_temp)
        
        # Krok 2: Připsání akcií (lokálně)
        d = pd.DataFrame([{"Ticker": ticker, "Pocet": kusy, "Cena": cena, "Datum": datetime.now(), "Owner": user, "Sektor": "Doplnit", "Poznamka": "CLI/Auto"}])
        df_p = pd.concat([df_p, d], ignore_index=True)
        
        # Krok 3: Atomické uložení a invalidace
        try:
            uloz_data_uzivatele(df_p, user, SOUBOR_DATA)
            uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
            
            # Aktualizace Session State AŽ PO ÚSPĚCHU
            st.session_state['df'] = df_p
            st.session_state['df_cash'] = df_cash_temp
            invalidate_data_core()
            return True, f"✅ Koupeno: {kusy}x {ticker} za {cena:,.2f} {mena}"
        except Exception as e:
            # Selhal zápis, stav v Session State zůstává starý, nic není poškozen
            return False, f"❌ Chyba zápisu transakce (NÁKUP): {e}"
    else:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {zustatky.get(mena, 0):,.2f})"

# --- ATOMICKÁ FUNKCE: PROVEDENÍ PRODEJE ---
def proved_prodej(ticker, kusy, cena, user, mena_input):
    df_p = st.session_state['df'].copy()
    df_h = st.session_state['df_hist'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')

    # --- BEZPEČNOSTNÍ REFACTORING: Zjištění měny (fallback) ---
    final_mena = mena_input
    if final_mena is None or final_mena == "N/A":
        final_mena = "USD"
        if not df_t.empty and 'Měna' in df_p.columns:
            final_mena = df_p[df_p['Ticker'] == ticker].iloc[0].get('Měna', 'USD')
        elif 'LIVE_DATA' in st.session_state:
            final_mena = st.session_state['LIVE_DATA'].get(ticker, {}).get('curr', 'USD')


    if df_t.empty or df_t['Pocet'].sum() < kusy:
        return False, "Nedostatek kusů."

    zbyva, zisk, trzba = kusy, 0, kusy * cena
    df_p_novy = df_p.copy() # Pracujeme s kopií, dokud neprovedeme atomický zápis

    # Logika odebrání kusů z DF portfolia
    indices_to_drop = []
    
    for idx, row in df_t.iterrows():
        if zbyva <= 0: break
        ukrojeno = min(row['Pocet'], zbyva)
        zisk += (cena - row['Cena']) * ukrojeno
        
        if ukrojeno == row['Pocet']:
            indices_to_drop.append(idx)
        else:
            df_p_novy.at[idx, 'Pocet'] -= ukrojeno
        zbyva -= ukrojeno

    df_p_novy = df_p_novy.drop(indices_to_drop)

    # Krok 1: Záznam do historie
    new_h = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, "Mena": final_mena, "Datum": datetime.now(), "Owner": user}])
    df_h = pd.concat([df_h, new_h], ignore_index=True)
    
    # Krok 2: Připsání hotovosti (lokálně)
    df_cash_temp = pohyb_penez(trzba, final_mena, "Prodej", f"Prodej {ticker}", user, df_cash_temp)
    
    # Krok 3: Atomické uložení a invalidace
    try:
        uloz_data_uzivatele(df_p_novy, user, SOUBOR_DATA)
        uloz_data_uzivatele(df_h, user, SOUBOR_HISTORIE)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        
        # Aktualizace Session State AŽ PO ÚSPĚCHU
        st.session_state['df'] = df_p_novy
        st.session_state['df_hist'] = df_h
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        return True, f"Prodáno! +{trzba:,.2f} {final_mena} (Zisk: {zisk:,.2f})"
    except Exception as e:
        return False, f"❌ Chyba zápisu transakce (PRODEJ): {e}"

# --- ATOMICKÁ FUNKCE: PROVEDENÍ SMĚNY ---
def proved_smenu(castka, z_meny, do_meny, user):
    kurzy = st.session_state['data_core']['kurzy'] # Bereme aktuální kurzy z cache
    df_cash_temp = st.session_state['df_cash'].copy()
    
    # Kalkulace směny
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy.get("CZK", 20.85)
    elif z_meny == "EUR": castka_usd = castka / kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85) / kurzy.get("CZK", 20.85) # Aproximace

    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurzy.get("CZK", 20.85)
    elif do_meny == "EUR": vysledna = castka_usd / kurzy.get("EUR", 1.16)

    # Krok 1: Odepsání a připsání (lokálně)
    df_cash_temp = pohyb_penez(-castka, z_meny, "Směna", f"Směna na {do_meny}", user, df_cash_temp)
    df_cash_temp = pohyb_penez(vysledna, do_meny, "Směna", f"Směna z {z_meny}", user, df_cash_temp)
    
    # Krok 2: Atomické uložení a invalidace
    try:
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        return True, f"Směněno: {vysledna:,.2f} {do_meny}"
    except Exception as e:
        return False, f"❌ Chyba zápisu transakce (SMĚNA): {e}"


def render_ticker_tape(data_dict):
    if not data_dict: return
    content = ""
    for ticker, info in data_dict.items():
        price = info.get('price', 0)
        curr = info.get('curr', '')
        content += f"&nbsp;&nbsp;&nbsp;&nbsp; <b>{ticker}</b>: {price:,.2f} {curr}"

    st.markdown(f"""
        <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 5px; padding: 8px; margin-bottom: 20px; white-space: nowrap; overflow: hidden;">
            <div style="display: inline-block; animation: marquee 20s linear infinite; color: #00CC96; font-family: 'Roboto Mono', monospace; font-weight: bold;" class="ticker-text">
                {content} {content} {content}
            </div>
        </div>
        <style>
            @keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}
        </style>
    """, unsafe_allow_html=True)

def add_download_button(fig, filename):
    try:
        import io
        buffer = io.BytesIO()
        fig.write_image(buffer, format="png", width=1200, height=800, scale=2)

        st.download_button(
            label=f"⬇️ Stáhnout graf: {filename}",
            data=buffer.getvalue(),
            file_name=f"{filename}.png",
            mime="image/png",
            use_container_width=True
        )
    except Exception:
        st.caption("💡 Tip: Pro stažení obrázku použij ikonu fotoaparátu 📷, která se objeví v pravém horním rohu grafu po najetí myší.")

# --- NOVÁ FUNKCE: Progresní funkce pro RPG úkoly ---
def get_task_progress(task_id, df, df_w, zustatky, vdf):
    """Vrací tuple (current, target) pro vizuální progress bar."""
    
    # Úkoly jsou indexovány dle RPG_TASKS
    
    if task_id == 0: # První průzkum: Přidej do Watchlistu akcii, kterou nemáš v portfoliu.
        target = 1
        current = 1 if not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique()) else 0
        return current, target, f"Sledované (mimo portfolio): {current}/{target}"

    elif task_id == 1: # Diverzifikace: Sektor: Drž akcie ve 3 různých sektorech.
        target = 3
        current = df['Sektor'].nunique() if not df.empty else 0
        return current, target, f"Sektorů: {current}/{target}"

    elif task_id == 2: # Měnová rovnováha: Drž hotovost alespoň ve 2 měnách.
        target = 2
        current = sum(1 for v in zustatky.values() if v > 100)
        return current, target, f"Aktivních měn: {current}/{target}"

    elif task_id == 3: # Mód Rentiera: Drž 3 akcie s dividendovým výnosem > 1%.
        target = 3
        # Kontrola, zda vdf je DataFrame nebo list dictů
        viz_data_list_safe = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
        current = len([i for i in viz_data_list_safe if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01])
        return current, target, f"Dividendových akcií: {current}/{target}"
      
    elif task_id == 4: # Cílovací expert: Nastav cílovou nákupní cenu u jedné akcie A cílovou prodejní cenu u jiné.
        target = 2
        has_buy = (df_w['TargetBuy'] > 0).any()
        has_sell = (df_w['TargetSell'] > 0).any()
        current = (1 if has_buy else 0) + (1 if has_sell else 0)
        return current, target, f"Nastavené cíle (Buy + Sell): {current}/{target}"
      
    elif task_id == 5: # Pohotovostní fond: Drž alespoň 5 000 Kč v hotovosti.
        target = 5000
        current = zustatky.get('CZK', 0)
        # Progress bar by mel být limitován do 1.0, i když máme více
        current_progress = min(current, target)
        return current_progress, target, f"CZK hotovost: {current:,.0f}/{target:,.0f} Kč"

    return 0, 1, "Není kvantifikovatelné" # Výchozí hodnota

# --- NOVÉ STATICKÉ DATOVÉ STRUKTURY PRO ÚKOLY ---
# Zde rozšiřujeme a upřesňujeme seznam RPG úkolů
RPG_TASKS = [
    # 1. Watchlist research
    {"title": "První průzkum", "desc": "Přidej do Watchlistu akcii, kterou nemáš v portfoliu.", 
     "check_fn": lambda df, df_w, zustatky, vdf: not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique())},
    
    # 2. Diversification by sector
    {"title": "Diverzifikace: Sektor", "desc": "Drž akcie ve 3 různých sektorech (Zkontroluj v Portfoliu).", 
     "check_fn": lambda df, df_w, zustatky, vdf: df['Sektor'].nunique() >= 3 and df.shape[0] >= 3},
    
    # 3. Diversification by currency (cash)
    {"title": "Měnová rovnováha", "desc": "Drž hotovost alespoň ve 2 měnách (USD, CZK, EUR).", 
     "check_fn": lambda df, df_w, zustatky, vdf: sum(1 for v in zustatky.values() if v > 100) >= 2},
    
    # 4. Income investing
    {"title": "Mód Rentiera", "desc": "Drž 3 akcie s dividendovým výnosem > 1%.", 
     "check_fn": lambda df, df_w, zustatky, vdf: len([i for i in vdf.to_dict('records') if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01]) >= 3 if isinstance(vdf, pd.DataFrame) else len([i for i in vdf if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01]) >= 3},
      
    # 5. Risk management (Setting both types of targets)
    {"title": "Cílovací expert", "desc": "Nastav cílovou nákupní cenu u jedné akcie A cílovou prodejní cenu u jiné.", 
     "check_fn": lambda df, df_w, zustatky, vdf: (df_w['TargetBuy'] > 0).any() and (df_w['TargetSell'] > 0).any()},
    
    # 6. Liquidity (CZK cash buffer) - NOVÝ ÚKOL
    {"title": "Pohotovostní fond", "desc": "Drž alespoň 5 000 Kč v hotovosti (Měna CZK).", 
     "check_fn": lambda df, df_w, zustatky, vdf: zustatky.get('CZK', 0) >= 5000},
]


def render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA):
    """Vykreslí stránku '🏠 Přehled' (Dashboard) - VERZE 2.0 (Bento Grid)"""
    
    if 'show_cash_history' not in st.session_state:
        st.session_state['show_cash_history'] = False
    if 'show_portfolio_live' not in st.session_state:
        st.session_state['show_portfolio_live'] = True
    
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
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = score,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    gauge = {
                        'axis': {'range': [0, 100], 'tickwidth': 0},
                        'bar': {'color': "white"}, 'bgcolor': "black",
                        'steps': [{'range': [0, 25], 'color': '#FF4136'}, {'range': [75, 100], 'color': '#2ECC40'}],
                    }
                ))
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
            st.caption("🧭 GLOBÁLNÍ KOMPAS (Trhy dnes)")
            try:
                makro_tickers = {"🇺🇸 S&P 500": "^GSPC", "🥇 Zlato": "GC=F", "₿ Bitcoin": "BTC-USD", "🏦 Úroky 10Y": "^TNX"}
                makro_data = yf.download(list(makro_tickers.values()), period="5d", progress=False)['Close']
                
                mc1, mc2, mc3, mc4 = st.columns(4)
                cols_list = [mc1, mc2, mc3, mc4]
                
                for i, (name, ticker) in enumerate(makro_tickers.items()):
                    with cols_list[i]:
                        if isinstance(makro_data.columns, pd.MultiIndex):
                            series = makro_data[ticker].dropna() if ticker in makro_data.columns.levels[0] else pd.Series()
                        else:
                            series = makro_data[ticker].dropna() if ticker in makro_data.columns else pd.Series()

                        if not series.empty:
                            last = series.iloc[-1]; prev = series.iloc[-2] if len(series) > 1 else last
                            delta = ((last - prev) / prev) * 100
                            st.metric(name, f"{last:,.0f}", f"{delta:+.2f}%")
                            
                            line_color = '#238636' if delta >= 0 else '#da3633'
                            fig_spark = go.Figure(go.Scatter(y=series.values, mode='lines', line=dict(color=line_color, width=2), fill='tozeroy', fillcolor=f"rgba({'35, 134, 54' if delta >= 0 else '218, 54, 51'}, 0.1)"))
                            fig_spark.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=35, xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
            except Exception: st.error("Chyba kompasu")
        
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
                fig_area.update_xaxes(showgrid=False)
                fig_area.update_yaxes(showgrid=True, gridcolor='#30363D', tickprefix="Kč ")
                st.plotly_chart(fig_area, use_container_width=True)

    with col_graf2:
        with st.container(border=True):
            st.subheader("🍰 SEKTORY")
            if not vdf.empty:
                fig_pie = px.pie(vdf, values='HodnotaUSD', names='Sektor', hole=0.6, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Bold)
                fig_pie.update_traces(textposition='outside', textinfo='percent')
                fig_pie.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10), height=300, paper_bgcolor="rgba(0,0,0,0)", font=dict(size=14))
                st.plotly_chart(fig_pie, use_container_width=True)

    st.write("")
    with st.container(border=True):
        st.subheader("🌊 TOK KAPITÁLU (Sankey)")
        
        total_vklady_czk = 0
        df_cash_temp = st.session_state.get('df_cash', pd.DataFrame())
        if not df_cash_temp.empty:
            for _, row in df_cash_temp.iterrows():
                val_czk = row['Castka']
                if row['Mena'] == "USD": val_czk *= kurzy.get("CZK", 20.85)
                elif row['Mena'] == "EUR": val_czk *= (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                if row['Typ'] in ['Vklad', 'Deposit']: total_vklady_czk += val_czk
                elif row['Typ'] in ['Výběr', 'Withdrawal']: total_vklady_czk -= val_czk

        total_divi_czk = 0
        df_div_temp = st.session_state.get('df_div', pd.DataFrame())
        if not df_div_temp.empty:
             for _, r in df_div_temp.iterrows():
                amt = r['Castka']
                if r['Mena'] == "USD": total_divi_czk += amt * kurzy.get("CZK", 20.85)
                elif r['Mena'] == "EUR": total_divi_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                else: total_divi_czk += amt
        
        total_realized_czk = 0 
        
        unrealized_profit_czk = (celk_hod_czk - celk_inv_usd * kurzy.get("CZK", 20.85))
        total_market_profit_czk = total_divi_czk + total_realized_czk + unrealized_profit_czk
        cash_total_czk = cash_usd * kurzy.get("CZK", 20.85)
        
        label = ["Vklady (Netto)", "Tržní Zisk & Divi", "MŮJ KAPITÁL", "Hotovost"]
        top_stocks = []
        if not vdf.empty:
            vdf_sorted = vdf.sort_values('HodnotaUSD', ascending=False).head(5)
            for _, row in vdf_sorted.iterrows():
                stock_label = f"{row['Ticker']}"
                label.append(stock_label)
                top_stocks.append({'label': stock_label, 'value_czk': row['HodnotaUSD'] * kurzy.get("CZK", 20.85)})
        
        stock_total_czk = celk_hod_czk
        other_stocks_val_czk = stock_total_czk - sum([s['value_czk'] for s in top_stocks])
        if other_stocks_val_czk > 100: label.append("Ostatní")

        IDX_VKLADY = 0; IDX_ZISK = 1; IDX_KAPITAL = 2; IDX_CASH = 3; IDX_FIRST_STOCK = 4
        source = []; target = []; value = []
        
        if total_vklady_czk > 0: source.append(IDX_VKLADY); target.append(IDX_KAPITAL); value.append(total_vklady_czk)
        if total_market_profit_czk > 0: source.append(IDX_ZISK); target.append(IDX_KAPITAL); value.append(total_market_profit_czk)
        if cash_total_czk > 100: source.append(IDX_KAPITAL); target.append(IDX_CASH); value.append(cash_total_czk)
        
        curr_idx = IDX_FIRST_STOCK
        for s in top_stocks:
            source.append(IDX_KAPITAL); target.append(curr_idx); value.append(s['value_czk'])
            curr_idx += 1
        if other_stocks_val_czk > 100:
             source.append(IDX_KAPITAL); target.append(curr_idx); value.append(other_stocks_val_czk)

        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
                pad = 20, thickness = 20,
                line = dict(color = "black", width = 0.5),
                label = label,
                color = "rgba(0, 204, 150, 0.8)",
            ),
            link = dict(
                source = source, target = target, value = value,
                color = "rgba(100, 100, 100, 0.2)"
            ),
            textfont = dict(size=14, color="white", family="Roboto Mono")
        )])
        fig_sankey.update_layout(height=500, margin=dict(l=10, r=10, t=30, b=30), paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
        st.plotly_chart(fig_sankey, use_container_width=True)

    if 'show_portfolio_live' not in st.session_state: st.session_state['show_portfolio_live'] = True
    
    st.write("")
    with st.container(border=True):
        c_head, c_check = st.columns([4, 1])
        c_head.subheader("📋 PORTFOLIO LIVE")
        st.session_state['show_portfolio_live'] = c_check.checkbox("Zobrazit", value=st.session_state['show_portfolio_live'])
        
        if st.session_state['show_portfolio_live'] and not vdf.empty:
             
            tickers_list = vdf['Ticker'].tolist()
            spark_data = {}
            if tickers_list:
                try:
                    batch = yf.download(tickers_list, period="1mo", interval="1d", group_by='ticker', progress=False)
                    for t in tickers_list:
                         if len(tickers_list) > 1 and t in batch.columns.levels[0]: spark_data[t] = batch[t]['Close'].dropna().tolist()
                         elif len(tickers_list) == 1: spark_data[t] = batch['Close'].dropna().tolist()
                         else: spark_data[t] = []
                except: pass
            
            vdf['Trend 30d'] = vdf['Ticker'].map(spark_data)
            
            st.dataframe(
                vdf,
                column_config={
                    "Ticker": st.column_config.TextColumn("Symbol", width="small"),
                    "Trend 30d": st.column_config.LineChartColumn("Trend (30d)", width="small", y_min=0, y_max=None),
                    "HodnotaUSD": st.column_config.ProgressColumn("Velikost pozice", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"])),
                    "Dnes": st.column_config.NumberColumn("24h %", format="%.2f%%"),
                    "Zisk": st.column_config.NumberColumn("Zisk ($)", format="%.0f"),
                    "Dan": st.column_config.TextColumn("Daně", width="small"),
                },
                column_order=["Ticker", "Trend 30d", "HodnotaUSD", "Dnes", "Zisk", "Dan"],
                use_container_width=True, hide_index=True
            )
            
            st.caption("Legenda daní: 🟢 > 3 roky (Osvobozeno) | 🔴 < 3 roky (Zdanit) | 🟠 Mix nákupů")
            st.dataframe(
                vdf,
                column_config={
                    "Ticker": st.column_config.TextColumn("Symbol", help="Zkratka akcie"),
                    "Sektor": st.column_config.TextColumn("Sektor", help="Odvětví"),
                    "HodnotaUSD": st.column_config.ProgressColumn("Velikost", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"])),
                    "Zisk": st.column_config.NumberColumn("Zisk/Ztráta", format="%.2f"),
                    "Dnes": st.column_config.NumberColumn("Dnes %", format="%.2f%%"),
                    "Divi": st.column_config.NumberColumn("Yield", format="%.2f%%"),
                    "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f", help="Poměr ceny k ziskům. Nízká hodnota může značit podhodnocení."),
                    "Kapitalizace": st.column_config.NumberColumn("Kapitalizace", format="$%.1fB", help="Tržní kapitalizace ve formátu miliard USD."),
                    "Dan": st.column_config.TextColumn("Daně", help="🟢 > 3 roky (Osvobozeno)\n🔴 < 3 roky (Zdanit)\n🟠 Mix nákupů"),
                    "Země": "Země",
                    "Trend 30d": st.column_config.LineChartColumn(
                        "Trend (30 dní)",
                        width="medium",
                        help="Vývoj ceny za poslední měsíc"
                    )
                },
                column_order=["Ticker", "Trend 30d", "Sektor", "Měna", "Země", "Kusy", "Průměr", "Cena", "Dnes", "HodnotaUSD", "Zisk", "Divi", "P/E", "Kapitalizace", "Dan"],
                use_container_width=True,
                hide_index=True
            )
        else: st.info("Portfolio je prázdné.")

    if st.session_state.get('show_cash_history', False):
        st.divider()
        st.subheader("🏦 HISTORIE HOTOVOSTI")
        if not st.session_state['df_cash'].empty:
            st.dataframe(st.session_state['df_cash'].sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Historie hotovosti je prázdná.")


def render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST):
    """Vykreslí stránku '👀 Sledování' (Watchlist)."""
    st.title("👀 WATCHLIST (Hlídač) – Cenové zóny")

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

        if tickers_list:
            with st.spinner("Skenuji trh a počítám indikátory..."):
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

            range_pos = 0.5
            try:
                t_obj = yf.Ticker(tk)
                year_low = t_obj.fast_info.year_low
                year_high = t_obj.fast_info.year_high
                if price and year_high > year_low:
                    range_pos = (price - year_low) / (year_high - year_low)
                    range_pos = max(0.0, min(1.0, range_pos))
                else:
                    range_pos = (price - year_low) / (year_high - year_high)
                    range_pos = max(0.0, min(1.0, range_pos))
            except: pass

            status_text = "💤 Wait"
            proximity_score = 0.0

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

            w_data.append({
                "Symbol": tk,
                "Cena": price,
                "Měna": cur,
                "RSI (14)": rsi_val,
                "52T Range": range_pos,
                "Cíl": active_target,
                "Akce": action_icon,
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
                column_order=["Symbol", "Cena", "Akce", "Cíl", "Zaměřovač", "Status", "RSI (14)", "52T Range"],
                use_container_width=True,
                hide_index=True
            )

            st.caption("💡 **RSI Legenda:** Hodnoty pod **30** značí přeprodanost (možný odraz nahoru 📈). Hodnoty nad **70** značí překoupenost (možná korekce dolů 📉).")

        st.divider()
        c_del1, c_del2 = st.columns([3, 1])
        with c_del2:
            to_del = st.selectbox("Vyber pro smazání:", df_watch['Ticker'].unique())
            if st.button("🗑️ Smazat ze sledování", use_container_width=True):
                odebrat_z_watchlistu(to_del, USER); st.rerun()
    else:
        st.info("Zatím nic nesleduješ. Přidej první akcii nahoře.")


def render_dividendy_page(USER, df, df_div, kurzy, viz_data_list):
    """Vykreslí stránku '💎 Dividendy'."""
    
    st.title("💎 DIVIDENDOVÝ KALENDÁŘ")

    est_annual_income_czk = 0
    if isinstance(viz_data_list, pd.DataFrame):
        data_to_use = viz_data_list.to_dict('records')
    else:
        data_to_use = viz_data_list
        
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

    total_div_czk = 0
    if not df_div.empty:
        for _, r in df_div.iterrows():
            amt = r['Castka']; currency = r['Mena']
            if currency == "USD": total_div_czk += amt * kurzy.get("CZK", 20.85)
            elif currency == "EUR": total_div_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
            else: total_div_czk += amt

    st.metric("CELKEM VYPLACENO (CZK)", f"{total_div_czk:,.0f} Kč")

    t_div1, t_div2, t_div3 = st.tabs(["HISTORIE VÝPLAT", "❄️ EFEKT SNĚHOVÉ KOULE", "PŘIDAT DIVIDENDU"])

    with t_div1:
        if not df_div.empty:
            plot_df = df_div.copy()
            plot_df['Datum_Den'] = pd.to_datetime(plot_df['Datum']).dt.strftime('%Y-%m-%d')
            plot_df_grouped = plot_df.groupby(['Datum_Den', 'Ticker'])['Castka'].sum().reset_index()
            plot_df_grouped = plot_df_grouped.sort_values('Datum_Den')

            fig_div = px.bar(plot_df_grouped, x='Datum_Den', y='Castka', color='Ticker',
                             title="Historie výplat (po dnech)",
                             labels={'Datum_Den': 'Datum', 'Castka': 'Částka'},
                             template="plotly_dark")

            fig_div.update_xaxes(type='category')
            fig_div.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
            fig_div = make_plotly_cyberpunk(fig_div)
            st.plotly_chart(fig_div, use_container_width=True)

            st.dataframe(df_div.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Zatím žádné dividendy.")

    with t_div2:
        if not df_div.empty:
            st.subheader("❄️ KUMULATIVNÍ RŮST (Snowball)")
            st.info("Tento graf ukazuje, jak se tvé dividendy sčítají v čase. Cílem je exponenciální růst!")
            
            snowball_df = df_div.copy()
            snowball_df['Datum'] = pd.to_datetime(snowball_df['Datum'])
            snowball_df = snowball_df.sort_values('Datum')
            
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
                color_discrete_sequence=['#00BFFF']
            )
            
            fig_snow.update_traces(line_color='#00BFFF', fillcolor='rgba(0, 191, 255, 0.2)')
            fig_snow.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)", 
                font_family="Roboto Mono",
                yaxis_title="Celkem vyplaceno (Kč)",
                xaxis_title=""
            )
            fig_snow = make_plotly_cyberpunk(fig_snow)
            st.plotly_chart(fig_snow, use_container_width=True)
            
            last_total = snowball_df['Kumulativni'].iloc[-1]
            st.metric("Celková 'Sněhová koule'", f"{last_total:,.0f} Kč", help="Suma všech dividend, které jsi kdy obdržel.")
            
        else:
            st.info("Zatím nemáš data pro sněhovou kouli. Přidej první dividendu!")

    with t_div3:
        st.caption("Peníze se automaticky připíší do peněženky.")
        with st.form("add_div"):
            dt_ticker = st.selectbox("Ticker", df['Ticker'].unique() if not df.empty else ["Jiny"])
            dt_amount = st.number_input("Částka (Netto)", 0.0, step=0.1)
            dt_curr = st.selectbox("Měna", ["USD", "CZK", "EUR"])
            
            if st.form_submit_button("💰 PŘIPSAT DIVIDENDU"):
                pridat_dividendu(dt_ticker, dt_amount, dt_curr, USER)
                st.success(f"Připsáno {dt_amount} {dt_curr} od {dt_ticker}")
                time.sleep(1)
                st.rerun()


def render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky):
    """Vykreslí stránku '🎮 Gamifikace'."""

    st.title("🎮 INVESTIČNÍ ARÉNA")
    st.subheader(f"Tvá úroveň: {level_name}")
    st.progress(level_progress)
    if celk_hod_czk < 500000:
        st.caption("Do další úrovně ti chybí majetek.")
    else:
        st.success("Gratulace! Dosáhl jsi maximální úrovně Velryba 🐋")

    st.divider()
    st.subheader("🔥 AKTIVNÍ VÝZVY (Quest Log)")
    
    if 'rpg_tasks' not in st.session_state:
        st.session_state['rpg_tasks'] = []
    
    if not st.session_state['rpg_tasks']:
        for i, task in enumerate(RPG_TASKS):
            st.session_state['rpg_tasks'].append({
                "id": i,
                "title": task["title"],
                "desc": task["desc"],
                "completed": False,
            })
    
    all_tasks_completed = True
    
    for i, task_state in enumerate(st.session_state['rpg_tasks']):
        df_w = st.session_state['df_watch']
        
        if isinstance(vdf, pd.DataFrame):
            viz_data_list = vdf.to_dict('records')
        else:
            viz_data_list = vdf

        original_task = RPG_TASKS[task_state['id']]
        
        is_completed = False
        current = 0
        target = 1
        progress_text = "Probíhá..."
        
        try:
            is_completed = original_task['check_fn'](df, df_w, zustatky, viz_data_list)
            current, target, progress_text = get_task_progress(task_state['id'], df, df_w, zustatky, viz_data_list)
            
        except Exception as e:
            is_completed = False
            progress_text = f"Chyba kontroly: {e}" 
            
        st.session_state['rpg_tasks'][i]['completed'] = is_completed

        if not is_completed:
            all_tasks_completed = False
            
        icon = "✅" if is_completed else "⚪️"
        
        with st.container(border=True):
            st.markdown(f"**{icon} {task_state['title']}**")
            st.caption(f"_{task_state['desc']}_")
            
            if is_completed:
                st.success("HOTOVO!")
            else:
                if target > 0 and current <= target:
                    progress_pct = current / target if target != 0 else 0
                    
                    bar_color = "orange"
                    if progress_pct >= 1.0: bar_color = "green"
                    elif progress_pct < 0.5: bar_color = "yellow"

                    st.markdown(f"""
                        <div style="width: 100%; background-color: #30363D; border-radius: 5px; margin-top: 10px; margin-bottom: 10px;">
                            <div style="width: {progress_pct*100:.0f}%; background-color: {bar_color}; height: 15px; border-radius: 5px; text-align: center; color: black; font-weight: bold; font-size: 10px;">
                                {progress_pct*100:.0f}%
                            </div>
                        </div>
                        <p style='margin:0; font-size: 12px; color: #8B949E;'>{progress_text}</p>
                    """, unsafe_allow_html=True)
                else:
                    st.info(progress_text)
            
    if all_tasks_completed and len(st.session_state['rpg_tasks']) > 0:
        st.balloons()
        st.success("Všechny denní/týdenní úkoly splněny! Klikni na tlačítko níže pro novou várku!")
        if st.button("🔄 Generovat nové RPG úkoly", key="reset_rpg_tasks"):
            st.session_state['rpg_tasks'] = []
            st.rerun()
            
    
    if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
        st.divider()
        st.subheader("🎲 DENNÍ LOGBOOK (AI Narrator)")

        denni_zmena_czk = (celk_hod_czk - (hist_vyvoje.iloc[-2]['TotalUSD'] * kurzy.get("CZK", 21))) if len(hist_vyvoje) > 1 else 0
        nalada_ikona = "💀" if denni_zmena_czk < 0 else "💰"

        if 'rpg_story_cache' not in st.session_state:
            st.session_state['rpg_story_cache'] = None
            
        if st.button("🎲 GENEROVAT PŘÍBĚH DNE", type="secondary"):
            with st.spinner("Dungeon Master hází kostkou..."):
                st.session_state['rpg_story_cache'] = None
                sc, _ = ziskej_fear_greed()
                actual_score = sc if sc else 50
                rpg_res_text = generate_rpg_story(model, level_name, denni_zmena_czk, celk_hod_czk, actual_score)
                st.session_state['rpg_story_cache'] = rpg_res_text

        if st.session_state['rpg_story_cache']:
            rpg_res_text = st.session_state['rpg_story_cache']
            st.markdown(f"""
            <div style="background-color: #161B22; border-left: 5px solid {'#da3633' if denni_zmena_czk < 0 else '#238636'}; padding: 15px; border-radius: 5px;">
                <h4 style="margin:0">{nalada_ikona} DENNÍ ZÁPIS</h4>
                <p style="font-style: italic; color: #8B949E; margin-top: 10px;">"{rpg_res_text}"</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Stisknutím tlačítka výše vygeneruješ svůj RPG deník!")


    st.divider()
    st.subheader("🏆 SÍŇ SLÁVY (Odznaky)")
    c1, c2, c3, c4 = st.columns(4)
    has_first = not df.empty
    cnt = len(df['Ticker'].unique()) if not df.empty else 0
    divi_total = 0
    if not df_div.empty:
        divi_total = df_div.apply(
            lambda r: r['Castka'] * (
                kurzy.get('CZK', 20.85) if r['Mena'] == 'USD'
                else (kurzy.get('CZK', 20.85) / kurzy.get('EUR', 1.16) if r['Mena'] == 'EUR' else 1)
            ),
            axis=1
        ).sum()

    def render_badge(col, title, desc, cond, icon, color):
        with col:
            with st.container(border=True):
                if cond:
                    st.markdown(f"<div style='text-align:center; color:{color}'><h1>{icon}</h1><h3>{title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)
                    st.success("ZÍSKÁNO")
                else:
                    st.markdown(f"<div style='text-align:center; color:gray; opacity:0.3'><h1>{icon}</h1><h3>{title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)
                    st.caption("UZAMČENO")

    render_badge(c1, "Začátečník", "Kup první akcii", has_first, "🥉", "#CD7F32")
    render_badge(c2, "Stratég", "Drž 3 různé firmy", cnt >= 3, "🥈", "#C0C0C0")
    render_badge(c3, "Boháč", "Portfolio > 100k", celk_hod_czk > 100000, "🥇", "#FFD700")
    render_badge(c4, "Rentiér", "Dividendy > 500 Kč", divi_total > 500, "💎", "#00BFFF")
    st.divider()
    st.subheader("💡 Moudro dne")
    if 'quote' not in st.session_state: st.session_state['quote'] = random.choice(CITATY)
    st.info(f"*{st.session_state['quote']}*")


# --- NOVÁ FUNKCE: SESTAVENÍ A ODESLÁNÍ TELEGRAM REPORTU ---
def send_daily_telegram_report(USER, data_core, alerts, kurzy):
    """
    Sestaví ucelený denní report a odešle jej na Telegram.
    """
    try:
        # Extrakce dat z data_core
        celk_hod_czk = data_core['celk_hod_usd'] * kurzy.get("CZK", 20.85)
        pct_24h = data_core['pct_24h']
        cash_usd = data_core['cash_usd']
        vdf = data_core['vdf']
        score, rating = ziskej_fear_greed()
        
        # --- 1. HLAVIČKA A SHRNUTÍ ---
        summary_text = f"<b>💸 DENNÍ REPORT: {USER.upper()}</b>\n"
        summary_text += f"📅 {datetime.now().strftime('%d.%m.%Y')}\n"
        summary_text += "--------------------------------------\n"
        summary_text += f"Celkové jmění: <b>{celk_hod_czk:,.0f} CZK</b>\n"
        
        # Změna 24h
        zmena_emoji = '🟢' if pct_24h >= 0 else '🔴'
        summary_text += f"24h Změna: {zmena_emoji} <b>{pct_24h:+.2f}%</b>\n"
        
        # Hotovost
        summary_text += f"Volná hotovost: ${cash_usd:,.0f}\n"
        summary_text += f"Nálada trhu: <b>{rating}</b> ({score}/100)\n"
        summary_text += "--------------------------------------\n"
        
        # --- 2. TOP/FLOP MOVERS (3 nejlepší/nejhorší) ---
        movers_text = "<b>📈 Největší pohyby (Dnes):</b>\n"
        
        if not vdf.empty and 'Dnes' in vdf.columns:
            vdf_sorted_all = vdf.sort_values('Dnes', ascending=False)
            
            movers_text += "\n🔝 Vítězové:\n"
            for _, row in vdf_sorted_all[vdf_sorted_all['Dnes'] > 0.001].head(3).iterrows():
                movers_text += f"  🚀 {row['Ticker']}: {row['Dnes']*100:+.2f}%\n"
            
            movers_text += "🔻 Poražení:\n"
            for _, row in vdf_sorted_all[vdf_sorted_all['Dnes'] < -0.001].tail(3).iterrows():
                movers_text += f"  💀 {row['Ticker']}: {row['Dnes']*100:+.2f}%\n"

            summary_text += movers_text
            summary_text += "--------------------------------------\n"

        # --- 3. CENOVÉ ALERTY ---
        if alerts:
            summary_text += "<b>🚨 AKTIVNÍ ALERTY:</b>\n" + "\n".join(alerts) + "\n"
            summary_text += "--------------------------------------\n"
            
        # --- 4. ZÁVĚR ---
        summary_text += "<i>Mějte úspěšný investiční den!</i>"
        
        # Odeslání zprávy přes Telegram Engine
        return notify.poslat_zpravu(summary_text)

    except Exception as e:
        return False, f"❌ Chyba generování reportu: {e}"

# --- CENTRÁLNÍ DATOVÉ JÁDRO: VÝPOČET VŠECH METRIK ---
def calculate_all_data(USER, df, df_watch, zustatky, kurzy):
    """
    Spouští všechny složité výpočty a cachuje výsledky do session_state.
    Tím se zabrání zbytečnému opakování stahování dat a kalkulací.
    """
    
    # Krok 1: Inicializace (zajištění, že máme data k práci)
    all_tickers = []
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    
    # Stáhneme živá data a kurzy (POUŽITÍ CACHE WRAPPERU)
    LIVE_DATA = cached_ceny_hromadne(list(set(all_tickers)))
    
    # Poznámka: LIVE_DATA může být None, pokud se nepovedlo stažení, ale ziskej_ceny_hromadne obvykle vrací {}
    if LIVE_DATA:
        if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
        if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]
    
    st.session_state['LIVE_DATA'] = LIVE_DATA if LIVE_DATA else {} # Uložíme pro fallback v proved_prodej
    
    # Krok 2: Fundamentální data pro portfolio (POUŽITÍ CACHE WRAPPERU)
    fundament_data = {}
    if not df.empty:
        tickers_in_portfolio = df['Ticker'].unique().tolist()
        for tkr in tickers_in_portfolio:
            info, _ = cached_detail_akcie(tkr) # Použití cache místo přímého volání
            fundament_data[tkr] = info

    # Krok 3: Výpočet portfolia
    viz_data = []
    celk_hod_usd = 0
    celk_inv_usd = 0

    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        df_g['Cena'] = df_g['Investice'] / df_g['Pocet']

        for i, (idx, row) in enumerate(df_g.iterrows()):
            tkr = row['Ticker']
            p, m, d_zmena = ziskej_info(tkr)
            if p is None: p = row['Cena']
            if m is None or m == "N/A": m = "USD"

            fundamenty = fundament_data.get(tkr, {})
            pe_ratio = fundamenty.get('trailingPE', 0)
            market_cap = fundamenty.get('marketCap', 0)

            try:
                raw_sektor = df[df['Ticker'] == tkr]['Sektor'].iloc[0]
                sektor = str(raw_sektor) if not pd.isna(raw_sektor) and str(raw_sektor).strip() != "" else "Doplnit"
            except Exception: sektor = "Doplnit"

            nakupy_data = df[df['Ticker'] == tkr]['Datum']
            dnes = datetime.now()
            limit_dni = 1095
            vsechny_ok = True
            vsechny_fail = True

            for d in nakupy_data:
                if (dnes - d).days < limit_dni: vsechny_ok = False
                else: vsechny_fail = False

            if vsechny_ok: dan_status = "🟢 Free"
            elif vsechny_fail: dan_status = "🔴 Zdanit"
            else: dan_status = "🟠 Mix"

            country = "United States"
            tkr_upper = str(tkr).upper()
            if tkr_upper.endswith(".PR"): country = "Czechia"
            elif tkr_upper.endswith(".DE"): country = "Germany"
            elif tkr_upper.endswith(".L"): country = "United Kingdom"
            elif tkr_upper.endswith(".PA"): country = "France"

            div_vynos = ziskej_yield(tkr)
            hod = row['Pocet']*p
            inv = row['Investice']
            z = hod-inv

            try:
                if m == "CZK": k = 1.0 / kurzy.get("CZK", 20.85)
                elif m == "EUR": k = kurzy.get("EUR", 1.16)
                else: k = 1.0
            except Exception: k = 1.0

            celk_hod_usd += hod*k
            celk_inv_usd += inv*k

            viz_data.append({
                "Ticker": tkr, "Sektor": sektor, "HodnotaUSD": hod*k, "Zisk": z, "Měna": m,
                "Hodnota": hod, "Cena": p, "Kusy": row['Pocet'], "Průměr": row['Cena'], "Dan": dan_status, "Investice": inv, "Divi": div_vynos, "Dnes": d_zmena,
                "Země": country,
                "P/E": pe_ratio,
                "Kapitalizace": market_cap / 1e9 if market_cap else 0
            })

    vdf = pd.DataFrame(viz_data) if viz_data else pd.DataFrame()

    # Krok 4: Výpočet denní změny
    hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    zmena_24h = 0
    pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if pd.notnull(vcera) and vcera > 0:
            zmena_24h = celk_hod_usd - vcera
            pct_24h = (zmena_24h / vcera * 100)

    # Krok 5: Výpočet hotovosti (USD ekvivalent)
    cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))

    # Krok 6: Sestavení a uložení Data Core
    data_core = {
        'vdf': vdf,
        'viz_data_list': viz_data,
        'celk_hod_usd': celk_hod_usd,
        'celk_inv_usd': celk_inv_usd,
        'hist_vyvoje': hist_vyvoje,
        'zmena_24h': zmena_24h,
        'pct_24h': pct_24h,
        'cash_usd': cash_usd,
        'fundament_data': fundament_data,
        'kurzy': kurzy,
        'timestamp': datetime.now()
    }
    st.session_state['data_core'] = data_core
    return data_core


# --- HLAVNÍ FUNKCE (Router) ---
def main():
    # --- 1. BEZPEČNÁ INICIALIZACE AI (Fix 1: Použití cache wrapperu) ---
    model, AI_AVAILABLE = get_cached_ai_connection()

    # 1. Start Cookie Manager
    cookie_manager = get_manager()

    # 2. Inicializace stavu (Session State)
    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False
        st.session_state['user'] = ""

    # 3. ZPOŽDĚNÍ PRO COOKIES (Nutné pro stx)
    time.sleep(0.3)

    # 4. LOGIKA PŘIHLÁŠENÍ (Gatekeeper)
    if 'chat_expanded' not in st.session_state:
        st.session_state['chat_expanded'] = False

    if not st.session_state['prihlasen']:
        cookie_user = cookie_manager.get("invest_user")
        if cookie_user:
            st.session_state['prihlasen'] = True
            st.session_state['user'] = cookie_user
            st.rerun()

    # --- ZOBRAZENÍ LOGIN FORMULÁŘE ---
    if not st.session_state['prihlasen']:
        c1,c2,c3 = st.columns([1, 2, 1])
        with c2:
            st.title("🔐 INVESTIČNÍ TERMINÁL")
            t1, t2, t3 = st.tabs(["PŘIHLÁŠENÍ", "REGISTRACE", "OBNOVA HESLA"])
            with t1:
                with st.form("l"):
                    u=st.text_input("Uživatelské jméno")
                    p=st.text_input("Heslo", type="password")
                    if st.form_submit_button("VSTOUPIT", use_container_width=True):
                        df_u = nacti_uzivatele(); row = df_u[df_u['username'] == u]
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            cookie_manager.set("invest_user", u, expires_at=datetime.now() + timedelta(days=30))
                            st.session_state.update({'prihlasen':True, 'user':u})
                            st.toast("Přihlašování...", icon="⏳")
                            time.sleep(1)
                            st.rerun()
                        else: st.toast("Chyba přihlášení", icon="❌")
            with t2:
                with st.form("r"):
                    nu=st.text_input("Nové jméno")
                    new_pass=st.text_input("Nové heslo", type="password")
                    nr=st.text_input("Záchranný kód", help="Slouží pro obnovu zapomenutého hesla.")
                    if st.form_submit_button("VYTVOŘIT ÚČET", use_container_width=True):
                        df_u = nacti_uzivatele()
                        if not df_u.empty and nu in df_u['username'].values:
                            st.toast("Jméno již existuje.", icon="⚠️")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(new_pass), "recovery_key": zasifruj(nr)}])
                            uloz_csv(pd.concat([df_u, new], ignore_index=True), SOUBOR_UZIVATELE, "New user")
                            st.toast("Účet vytvořen!", icon="✅")
            with t3:
                st.caption("Zapomněl jsi heslo?")
                with st.form("recovery"):
                    ru = st.text_input("Jméno")
                    rk = st.text_input("Záchranný kód")
                    rnp = st.text_input("Nové heslo", type="password")
                    if st.form_submit_button("OBNOVIT"):
                        df_u = nacti_uzivatele(); row = df_u[df_u['username'] == ru]
                        if not row.empty and row.iloc[0]['recovery_key'] == zasifruj(rk):
                            if rnp and len(rnp) > 0:
                                df_u.at[row.index[0], 'password'] = zasifruj(rnp)
                                uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}")
                                st.success("Heslo obnoveno!")
                            else: st.error("Nové heslo nesmí být prázdné.")
                        else: st.error("Jméno nebo záchranný kód nesedí.")
        return

    # =========================================================================
    # ZDE ZAČÍNÁ APLIKACE PRO PŘIHLÁŠENÉHO UŽIVATELE
    # =========================================================================

    USER = st.session_state['user']

    # --- BOOT SEQUENCE (POUZE JEDNOU) ---
    if 'boot_completed' not in st.session_state:
        st.session_state['boot_completed'] = False

    if not st.session_state['boot_completed']:
        boot_placeholder = st.empty()
        with boot_placeholder.container():
            st.markdown("""<style>.stApp {background-color: black !important;}</style>""", unsafe_allow_html=True)
            st.markdown("## 🖥️ TERMINAL PRO v4.0", unsafe_allow_html=True)

            steps = [
                "Initializing secure connection...",
                "Loading neural network weights...",
                "Accessing global market data...",
                "Decrypting user wallet...",
                "Bypassing firewalls...",
                "ACCESS GRANTED"
            ]

            bar = st.progress(0)
            status_text = st.empty()

            for i, step in enumerate(steps):
                status_text.markdown(f"```bash\n> {step}\n```")
                bar.progress((i + 1) * (100 // len(steps)))
                time.sleep(0.3)

            st.success("SYSTEM ONLINE")
            time.sleep(0.5)

        boot_placeholder.empty()
        st.session_state['boot_completed'] = True

    # --- DEFINICE CLI CALLBACKU (OPRAVA VYKONÁVÁNÍ PŘÍKAZŮ) ---
    if 'cli_msg' not in st.session_state: st.session_state['cli_msg'] = None

    def process_cli_command():
        cmd_raw = st.session_state.cli_cmd
        if not cmd_raw: return

        st.session_state.cli_cmd = ""

        cmd_parts = cmd_raw.strip().split()
        cmd = cmd_parts[0].lower()

        msg_text = None
        msg_icon = None

        try:
            if cmd == "/help":
                msg_text = "Příkazy:\n/price [TICKER]\n/buy [TICKER] [KUSY]\n/sell [TICKER] [KUSY]\n/cash\n/ai_audit [TICKER]"
                msg_icon = "ℹ️"

            elif cmd == "/ai_audit":
                if not AI_AVAILABLE or not st.session_state.get('ai_enabled', False):
                    msg_text = "❌ AI je neaktivní (Zkontroluj Nastavení nebo API klíč)."
                    msg_icon = "⚠️"
                    st.session_state['cli_msg'] = (msg_text, msg_icon)
                    return 
                
                if 'data_core' not in st.session_state:
                    msg_text = "❌ Datové jádro není inicializováno. Zkus obnovit stránku."
                    msg_icon = "⚠️"
                    st.session_state['cli_msg'] = (msg_text, msg_icon)
                    return 
                    
                core = st.session_state['data_core']
                LIVE_DATA = st.session_state.get('LIVE_DATA', {})

                if len(cmd_parts) > 1:
                    target_ticker = cmd_parts[1].upper()
                    
                    fund_info = core['fundament_data'].get(target_ticker, {})
                    
                    if not fund_info:
                        try:
                            t_info, _ = cached_detail_akcie(target_ticker) 
                            if t_info:
                                fund_info = t_info
                                core['fundament_data'][target_ticker] = t_info
                                if target_ticker not in LIVE_DATA:
                                    LIVE_DATA[target_ticker] = {"price": fund_info.get('currentPrice', 'N/A'), "curr": fund_info.get('currency', 'USD')}
                            else:
                                msg_text = f"❌ Fundamentální data pro {target_ticker} nebyla nalezena. Analýza nemožná."
                                msg_icon = "⚠️"
                                st.session_state['cli_msg'] = (msg_text, msg_icon)
                                return
                        except Exception as e:
                            msg_text = f"❌ Chyba při získávání dat pro {target_ticker}: {e}"
                            msg_icon = "⚠️"
                            st.session_state['cli_msg'] = (msg_text, msg_icon)
                            return
                    
                    current_price = LIVE_DATA.get(target_ticker, {}).get('price', 'N/A')
                    pe_ratio = fund_info.get('trailingPE', 'N/A')
                    
                    divi_yield_raw = fund_info.get('dividendYield', 'N/A')
                    vdf = core['vdf']
                    if not vdf.empty and target_ticker in vdf['Ticker'].values:
                        portfolio_row = vdf[vdf['Ticker'] == target_ticker].iloc[0]
                        if pd.notna(portfolio_row.get('Divi')):
                            divi_yield_raw = portfolio_row['Divi']
                    
                    if isinstance(divi_yield_raw, (float, int)) and pd.notna(divi_yield_raw):
                        divi_yield_for_ai = divi_yield_raw
                        divi_yield_display = f"{divi_yield_raw * 100:.2f}%" 
                    else:
                        divi_yield_for_ai = 'N/A'
                        divi_yield_display = 'N/A'

                    ai_prompt = (
                        f"Jsi finanční analytik. Analyzuj akcii {target_ticker} na základě jejích fundamentálních dat:\n"
                        f"Aktuální P/E: {pe_ratio}. Dividendový výnos (jako desetinne cislo, napr. 0.03): {divi_yield_for_ai}.\n"
                        "Poskytni stručné shrnutí (max 3 věty) o tom, zda je akcie drahá, levná, nebo neutrální, a jaké je její hlavní riziko/příležitost. Pamatuj, ze vykazany dividendovy vynos je již v procentech."
                    )
                    
                    try:
                        with st.spinner(f"AI provádí analýzu pro {target_ticker}..."):
                            ai_response = model.generate_content(ai_prompt).text
                    except Exception as e:
                        if "429" in str(e):
                            msg_text = f"❌ Chyba kvóty (429): Překročena frekvence volání AI. Zkus to prosím za pár minut."
                        else:
                            msg_text = f"❌ Chyba AI ({target_ticker}): Analýza se nezdařila ({e})."
                        msg_icon = "⚠️"
                        st.session_state['cli_msg'] = (msg_text, msg_icon)
                        return

                    summary_text = (
                        f"## 🕵️ Analýza: {target_ticker}\n"
                        f"- Cena: {current_price}\n"
                        f"- P/E Ratio: {pe_ratio}\n"
                        f"- Dividend Yield: {divi_yield_display}\n"
                        "---"
                    )
                    
                    msg_text = f"🛡️ **HLÁŠENÍ PRO {target_ticker}:**\n{summary_text}\n🤖 **AI Verdikt:** {ai_response}"
                    msg_icon = "🔬"

                else:
                    pct_24h = core['pct_24h']
                    cash_usd = core['cash_usd']
                    vdf = core['vdf']
                    
                    best_ticker = "N/A"
                    worst_ticker = "N/A"
                    if not vdf.empty and 'Dnes' in vdf.columns:
                        vdf_sorted = vdf.sort_values('Dnes', ascending=False)
                        best_ticker = vdf_sorted.iloc[0]['Ticker']
                        worst_ticker = vdf_sorted.iloc[-1]['Ticker']
                    
                    try:
                        guard_res_text = ask_ai_guard(model, pct_24h, cash_usd, best_ticker, worst_ticker)
                    except Exception as e:
                        if "429" in str(e):
                             msg_text = f"❌ Chyba kvóty (429): Překročena frekvence volání AI. Zkus to prosím za pár minut."
                        else:
                            msg_text = f"❌ Chyba AI: Globální audit se nezdařil ({e})."
                        msg_icon = "⚠️"
                        st.session_state['cli_msg'] = (msg_text, msg_icon)
                        return

                    msg_text = f"🛡️ **HLÁŠENÍ STRÁŽCE:**\n{guard_res_text}"
                    msg_icon = "👮"

            elif cmd == "/price" and len(cmd_parts) > 1:
                t_cli = cmd_parts[1].upper()
                p_cli, m_cli, z_cli = ziskej_info(t_cli)
                if p_cli:
                    msg_text = f"💰 {t_cli}: {p_cli:,.2f} {m_cli} ({z_cli*100:+.2f}%)"
                    msg_icon = "📈"
                else:
                    msg_text = f"❌ Ticker {t_cli} nenalezen."
                    msg_icon = "⚠️"

            elif cmd == "/cash":
                bals = get_zustatky(USER)
                txt = " | ".join([f"{k}: {v:,.0f}" for k,v in bals.items()])
                msg_text = f"🏦 {txt}"
                msg_icon = "💵"

            elif cmd == "/buy" and len(cmd_parts) >= 3:
                t_cli = cmd_parts[1].upper()
                k_cli = float(cmd_parts[2])
                p_cli, m_cli, _ = ziskej_info(t_cli)
                if p_cli:
                    ok, msg = proved_nakup(t_cli, k_cli, p_cli, USER)
                    msg_text = msg
                    msg_icon = "✅" if ok else "❌"
                else:
                    msg_text = "❌ Chyba ceny"
                    msg_icon = "⚠️"

            elif cmd == "/sell" and len(cmd_parts) >= 3:
                t_cli = cmd_parts[1].upper()
                k_cli = float(cmd_parts[2])
                p_cli, m_cli, _ = ziskej_info(t_cli)
                if p_cli:
                    ok, msg = proved_prodej(t_cli, k_cli, p_cli, USER, m_cli)
                    msg_text = msg
                    msg_icon = "✅" if ok else "❌"
                else:
                    msg_text = "❌ Chyba ceny"
                    msg_icon = "⚠️"
            else:
                msg_text = "❌ Neznámý příkaz nebo formát"
                msg_icon = "❓"
        except Exception as e:
            msg_text = f"❌ Neočekávaná chyba: {str(e)}"
            msg_icon = "⚠️"

        if msg_text:
            st.session_state['cli_msg'] = (msg_text, msg_icon)

    # -----------------------------------------------------------

    # --- 5. NAČTENÍ ZÁKLADNÍCH DAT A JÁDRA ---
    if 'df' not in st.session_state:
        with st.spinner("NAČÍTÁM DATA..."):
            st.session_state['df'] = nacti_csv(SOUBOR_DATA).query(f"Owner=='{USER}'").copy()
            st.session_state['df_hist'] = nacti_csv(SOUBOR_HISTORIE).query(f"Owner=='{USER}'").copy()
            st.session_state['df_cash'] = nacti_csv(SOUBOR_CASH).query(f"Owner=='{USER}'").copy()
            st.session_state['df_div'] = nacti_csv(SOUBOR_DIVIDENDY).query(f"Owner=='{USER}'").copy()
            st.session_state['df_watch'] = nacti_csv(SOUBOR_WATCHLIST).query(f"Owner=='{USER}'").copy()
            st.session_state['hist_vyvoje'] = aktualizuj_graf_vyvoje(USER, 0)
    
    df = st.session_state['df']
    df_cash = st.session_state['df_cash']
    df_div = st.session_state['df_div']
    df_watch = st.session_state['df_watch']
    zustatky = get_zustatky(USER)
    kurzy = cached_kurzy() 

    # --- 6. VÝPOČTY (CENTRALIZOVANÝ DAT CORE) ---
    cache_timeout = timedelta(minutes=5)
    
    if ('data_core' not in st.session_state or 
        (datetime.now() - st.session_state['data_core']['timestamp']) > cache_timeout):
        
        with st.spinner("🔄 Aktualizuji datové jádro (LIVE data)..."):
            data_core = calculate_all_data(USER, df, df_watch, zustatky, kurzy)
    else:
        data_core = st.session_state['data_core']

    # --- 7. EXTRACT DATA CORE ---
    vdf = data_core['vdf']
    viz_data_list = data_core['viz_data_list']
    celk_hod_usd = data_core['celk_hod_usd']
    celk_inv_usd = data_core['celk_inv_usd']
    hist_vyvoje = data_core['hist_vyvoje']
    zmena_24h = data_core['zmena_24h']
    pct_24h = data_core['pct_24h']
    cash_usd = data_core['cash_usd']
    fundament_data = data_core['fundament_data']
    LIVE_DATA = st.session_state['LIVE_DATA'] 
    
    kurzy = data_core['kurzy'] 

    kurz_czk = kurzy.get("CZK", 20.85)
    celk_hod_czk = celk_hod_usd * kurz_czk
    celk_inv_czk = celk_inv_usd * kurz_czk


    # --- 8. KONTROLA WATCHLISTU (ALERTY) ---
    alerts = []
    if not df_watch.empty:
        for _, r in df_watch.iterrows():
            tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']

            if buy_trg > 0 or sell_trg > 0:
                inf = LIVE_DATA.get(tk, {})
                price = inf.get('price')
                if not price:
                    price, _, _ = ziskej_info(tk)

                if price:
                    if buy_trg > 0 and price <= buy_trg:
                        alerts.append(f"🔥 KUP: {tk} za {price:.2f} <= {buy_trg:.2f}")
                        st.toast(f"🔔 {tk} je ve slevě! ({price:.2f})", icon="🔥")

                    if sell_trg > 0 and price >= sell_trg:
                        alerts.append(f"💰 PRODEJ: {tk} za {price:.2f} >= {sell_trg:.2f}")
                        st.toast(f"🔔 {tk} dosáhl cíle! ({price:.2f})", icon="💰")

    # --- NOVÉ: AUTOMATICKÝ REPORT TELEGRAM SCHEDULER ---
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    if 'last_telegram_report' not in st.session_state:
        st.session_state['last_telegram_report'] = "2000-01-01"

    current_time_int = datetime.now().hour * 100 + datetime.now().minute
    report_time_int = 1800 

    if st.session_state['last_telegram_report'] != today_date and current_time_int >= report_time_int:
        
        st.sidebar.warning("🤖 Spouštím denní automatický report na Telegram...")
        
        ok, msg = send_daily_telegram_report(USER, data_core, alerts, kurzy)
        
        if ok:
            st.session_state['last_telegram_report'] = today_date
            st.sidebar.success(f"🤖 Report ODESLÁN (Telegram).")
        else:
            st.sidebar.error(f"🤖 Chyba odeslání reportu: {msg}")

    # --- 9. SIDEBAR ---
    with st.sidebar:
        lottie_url = "https://lottie.host/02092823-3932-4467-9d7e-976934440263/3q5XJg2Z2W.json"
        lottie_json = load_lottieurl(lottie_url)
        if lottie_json:
            st_lottie(lottie_json, height=150, key="sidebar_anim")

        selected_theme = st.selectbox(
            "🎨 Vzhled aplikace",
            ["🕹️ Cyberpunk (Retro)", "💎 Glassmorphism (Modern)", "💼 Wall Street (Profi)"],
            index=["🕹️ Cyberpunk (Retro)", "💎 Glassmorphism (Modern)", "💼 Wall Street (Profi)"].index(st.session_state.get('ui_theme', "🕹️ Cyberpunk (Retro)"))
        )

        if selected_theme != st.session_state.get('ui_theme'):
            st.session_state['ui_theme'] = selected_theme
            st.rerun()

        st.divider()
        st.header(f"👤 {USER.upper()}")

        with st.expander("🌍 SVĚTOVÉ TRHY", expanded=True):
            ny_time, ny_open = zjisti_stav_trhu("America/New_York", 9, 16)
            ln_time, ln_open = zjisti_stav_trhu("Europe/London", 8, 16)
            jp_time, jp_open = zjisti_stav_trhu("Asia/Tokyo", 9, 15)

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇺🇸 New York"); c_m2.markdown(f"**{ny_time}** {'🟢' if ny_open else '🔴'}")

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇬🇧 Londýn"); c_m2.markdown(f"**{ln_time}** {'🟢' if ln_open else '🔴'}")

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇯🇵 Tokio"); c_m2.markdown(f"**{jp_time}** {'🟢' if jp_open else '🔴'}")

        st.divider()

        level_name = "Novic"
        level_progress = 0.0

        if celk_hod_czk < 10000:
            level_name = "Novic 🧒"
            level_progress = min(celk_hod_czk / 10000, 1.0)
        elif celk_hod_czk < 50000:
            level_name = "Učeň 🧑‍🎓"
            level_progress = min((celk_hod_czk - 10000) / 40000, 1.0)
        elif celk_hod_czk < 100000:
            level_name = "Trader 💼"
            level_progress = min((celk_hod_czk - 50000) / 50000, 1.0)
        elif celk_hod_czk < 500000:
            level_name = "Profi 🎩"
            level_progress = min((celk_hod_czk - 100000) / 400000, 1.0)
        else:
            level_name = "Velryba 🐋"
            level_progress = 1.0

        st.caption(f"Úroveň: **{level_name}**")
        st.progress(level_progress)

        st.write("")
        st.caption("Stav peněženky:")
        for mena in ["USD", "CZK", "EUR"]:
            castka = zustatky.get(mena, 0.0)
            sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
            st.info(f"**{castka:,.2f} {sym}**", icon="💰")

        if alerts:
            st.divider()
            st.error("🔔 CENOVÉ ALERTY!", icon="🔥")
            for a in alerts:
                st.markdown(f"- **{a}**")

        st.divider()
        st.caption("💻 TERMINÁL (Příkazová řádka)")

        if st.session_state.get('cli_msg'):
            txt, ic = st.session_state['cli_msg']
            
            if ic in ["🔬", "👮"]:
                st.toast(f"{ic} Nové hlášení od AI strážce!", icon=ic)
                
                st.markdown(
                    f"""
                    <div style="background-color: #161B22; border-left: 4px solid #58A6FF; padding: 15px; border-radius: 5px; margin-top: 15px;">
                        <p style="margin:0; font-family: 'Roboto Mono'; font-weight: bold;">{txt.replace('\n', '<br>')}</p>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            else:
                st.toast(txt, icon=ic)

            st.session_state['cli_msg'] = None

        st.text_input(">", key="cli_cmd", placeholder="/help pro nápovědu", on_change=process_cli_command)
        
        st.divider(); st.subheader("NAVIGACE")
        page = st.radio("Jít na:", ["🏠 Přehled", "👀 Sledování", "📈 Analýza", "📰 Zprávy", "💸 Obchod", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení"], label_visibility="collapsed")

        st.divider()
        
        # --- AUTOMATICKÝ REPORT INFO (Místo starého email tlačítka) ---
        # report_time_int je definován nahoře
        st.info(f"🤖 Automatický report se odesílá kolem {report_time_int//100}:{(report_time_int%100):02d}.")
        
        # Ponecháme jen PDF tlačítko
        pdf_data = vytvor_pdf_report(USER, celk_hod_czk, cash_usd, (celk_hod_czk - celk_inv_czk), viz_data_list)
        st.download_button(label="📄 STÁHNOUT PDF REPORT", data=pdf_data, file_name=f"report_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)

        st.divider()
        with st.expander("🔐 Změna hesla"):
            with st.form("pass_change"):
                old = st.text_input("Staré", type="password"); new = st.text_input("Nové", type="password"); conf = st.text_input("Potvrdit", type="password")
                if st.form_submit_button("Změnit"):
                    df_u = nacti_uzivatele(); row = df_u[df_u['username'] == USER]
                    if not row.empty and row.iloc[0]['password'] == zasifruj(old):
                        if new == conf and len(new) > 0:
                            df_u.at[row.index[0], 'password'] = zasifruj(new); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Pass change {USER}"); st.success("Hotovo!")
                        else: st.error("Chyba v novém hesle.")
                    else: st.error("Staré heslo nesedí.")

        if st.button("🚪 ODHLÁSIT", use_container_width=True):
            cookie_manager.delete("invest_user")
            st.session_state.clear()
            st.rerun()

    # BĚŽÍCÍ PÁS
    if page not in ["🎮 Gamifikace", "⚙️ Nastavení"]:
        render_ticker_tape(LIVE_DATA)

    # --- 10. STRÁNKY (Refaktorovaný router) ---
    if page == "🏠 Přehled":
        render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, 
                            zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA)

    elif page == "👀 Sledování":
        render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST)
        
    elif page == "📈 Analýza":
        st.title("📈 HLOUBKOVÁ ANALÝZA")
        
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA & SEKTORY", "🔮 VĚŠTEC", "🏆 BENCHMARK", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE", "📅 KALENDÁŘ"])

        with tab1:
            render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE)

        with tab2:
            st.subheader("⚔️ SROVNÁNÍ VÝKONNOSTI AKCIÍ")

            portfolio_tickers = df['Ticker'].unique().tolist() if not df.empty else []
            default_tickers = ['AAPL', 'MSFT', '^GSPC']
            initial_selection = list(set(portfolio_tickers[:5] + ['^GSPC']))

            tickers_to_compare = st.multiselect(
                "Vyberte akcie/indexy pro srovnání výkonnosti:",
                options=list(set(default_tickers + portfolio_tickers)),
                default=initial_selection,
                key="multi_compare"
            )

            if tickers_to_compare:
                try:
                    with st.spinner(f"Stahuji historická data pro {len(tickers_to_compare)} tickerů..."):
                        raw_data = yf.download(tickers_to_compare, period="1y", interval="1d", progress=False)['Close']

                    if raw_data.empty:
                        st.warning("Nepodařilo se načíst historická data pro vybrané tickery.")
                    else:
                        normalized_data = raw_data.apply(lambda x: (x / x.iloc[0] - 1) * 100)

                        fig_multi_comp = px.line(
                            normalized_data,
                            title='Normalizovaná výkonnost (Změna v %) od počátku',
                            template="plotly_dark"
                        )
                        fig_multi_comp.update_layout(
                            xaxis_title="Datum",
                            yaxis_title="Změna (%)",
                            height=500,
                            margin=dict(t=50, b=0, l=0, r=0),
                            font_family="Roboto Mono",
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=-0.2,
                                xanchor="center",
                                x=0.5
                            )
                        )
                        fig_multi_comp.update_xaxes(showgrid=False)
                        fig_multi_comp.update_yaxes(showgrid=True, gridcolor='#30363D')
                        fig_multi_comp = make_plotly_cyberpunk(fig_multi_comp)
                        st.plotly_chart(fig_multi_comp, use_container_width=True, key="fig_srovnani")
                        add_download_button(fig_multi_comp, "srovnani_akcii")

                        st.divider()
                        st.subheader("Detailní srovnání metrik")

                        comp_list = []
                        for t in tickers_to_compare[:4]:
                            i, h = cached_detail_akcie(t) 
                            if i:
                                mc = i.get('marketCap', 0)
                                pe = i.get('trailingPE', 0)
                                dy = i.get('dividendYield', 0)
                                perf = 0
                                if h is not None and not h.empty:
                                    start_p = h['Close'].iloc[0]
                                    end_p = h['Close'].iloc[-1]
                                    if start_p != 0:
                                        perf = ((end_p / start_p) - 1) * 100

                                comp_list.append({
                                    "Metrika": [f"Kapitalizace", f"P/E Ratio", f"Dividenda", f"Změna 1R"],
                                    "Hodnota": [
                                        f"${mc/1e9:.1f}B",
                                        f"{pe:.2f}" if pe > 0 else "N/A",
                                        f"{dy*100:.2f}%" if dy else "0%",
                                        f"{perf:+.2f}%"
                                    ],
                                    "Ticker": t
                                })

                        if comp_list:
                            final_data = {"Metrika": comp_list[0]["Metrika"]}
                            for item in comp_list:
                                final_data[item["Ticker"]] = item["Hodnota"]
                            
                            st.dataframe(pd.DataFrame(final_data), use_container_width=True, hide_index=True)

                except Exception as e:
                    st.error(f"Chyba při stahování/zpracování dat: Zkuste vybrat jiné tickery. (Detail: {e})")
            else:
                st.info("Vyberte alespoň jeden ticker (akcii nebo index) pro zobrazení srovnávacího grafu.")


        with tab3:
            if not vdf.empty:
                st.subheader("🌍 MAPA IMPÉRIA")
                try:
                    df_map = vdf.groupby('Země')['HodnotaUSD'].sum().reset_index()
                    fig_map = px.scatter_geo(
                        df_map,
                        locations="Země",
                        locationmode="country names",
                        hover_name="Země",
                        size="HodnotaUSD",
                        projection="orthographic",
                        color="Země",
                        template="plotly_dark"
                    )
                    fig_map.update_geos(
                        bgcolor="#161B22",
                        showcountries=True,
                        countrycolor="#30363D",
                        showocean=True,
                        oceancolor="#0E1117",
                        showland=True,
                        landcolor="#1c2128"
                    )
                    fig_map.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        font={"color": "white", "family": "Roboto Mono"},
                        height=500,
                        margin={"r": 0, "t": 0, "l": 0, "b": 0}
                    )

                    fig_map = make_plotly_cyberpunk(fig_map)

                    st.plotly_chart(fig_map, use_container_width=True, key="fig_mapa_imperia")
                    add_download_button(fig_map, "mapa_imperia")
                except Exception as e:
                    st.error(f"Chyba mapy: {e}")

                st.divider()
                st.caption("MAPA TRHU (Sektory)")

                try:
                    if vdf.empty:
                        st.info("Portfolio je prázdné.")
                    else:
                        treemap_fig = px.treemap(
                            vdf,
                            path=[px.Constant("PORTFOLIO"), 'Sektor', 'Ticker'],
                            values='HodnotaUSD',
                            color='Zisk',
                            color_continuous_scale=['red', '#161B22', 'green'],
                            color_continuous_midpoint=0
                        )
                        treemap_fig.update_layout(
                            font_family="Roboto Mono",
                            paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(t=30, l=10, r=10, b=10),
                            title="Treemap: rozložení podle sektorů"
                        )

                        treemap_fig = make_plotly_cyberpunk(treemap_fig)

                        st.plotly_chart(treemap_fig, use_container_width=True, key="fig_sektor_map")
                        add_download_button(treemap_fig, "mapa_sektoru")

                        if 'Datum' in df.columns and 'Cena' in df.columns and not df.empty:
                            try:
                                line_fig = px.line(df.sort_values('Datum'), x='Datum', y='Cena', title='Vývoj ceny', markers=True)
                                line_fig.update_layout(
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    font_family="Roboto Mono",
                                    margin=dict(t=30, l=10, r=10, b=10)
                                )
                                line_fig = make_plotly_cyberpunk(line_fig)

                                st.plotly_chart(line_fig, use_container_width=True, key="fig_vyvoj_ceny")
                                add_download_button(fig_map, "vyvoj_ceny")
                            except Exception:
                                st.warning("Nepodařilo se vykreslit graf vývoje ceny.")
                except Exception:
                    st.error("Chyba mapy.")
            else:
                st.info("Portfolio je prázdné.")

        with tab4:
            st.subheader("🔮 FINANČNÍ STROJ ČASU")

            with st.expander("🤖 AI PREDIKCE (Neuro-Věštec)", expanded=False):
                st.info("Experimentální modul využívající model Prophet (Meta/Facebook) k predikci budoucího trendu.")

                c_ai1, c_ai2 = st.columns(2)
                with c_ai1:
                    pred_ticker = st.text_input("Ticker pro predikci:", value="BTC-USD").upper()
                with c_ai2:
                    pred_days = st.slider("Predikce na (dny):", 7, 90, 30)

                if st.button("🧠 AKTIVOVAT NEURONOVOU SÍŤ", type="primary"):
                    try:
                        from prophet import Prophet

                        with st.spinner(f"Trénuji model na datech {pred_ticker}... (Může to trvat)"):
                            hist_train = yf.download(pred_ticker, period="2y", progress=False)

                            if not hist_train.empty:
                                if isinstance(hist_train.columns, pd.MultiIndex):
                                    y_data = hist_train['Close'].iloc[:, 0]
                                else:
                                    y_data = hist_train['Close']

                                df_prophet = pd.DataFrame({
                                    'ds': y_data.index.tz_localize(None),
                                    'y': y_data.values
                                })

                                m = Prophet(daily_seasonality=True)
                                m.fit(df_prophet)

                                future = m.make_future_dataframe(periods=pred_days)
                                forecast = m.predict(future)

                                st.divider()
                                st.subheader(f"🔮 Predikce pro {pred_ticker} na {pred_days} dní")

                                last_price = df_prophet['y'].iloc[-1]
                                future_price = forecast['yhat'].iloc[-1]
                                diff_pred = future_price - last_price
                                pct_pred = (diff_pred / last_price) * 100

                                col_res1, col_res2 = st.columns(2)
                                with col_res1:
                                    st.metric("Poslední známá cena", f"{last_price:,.2f}")
                                with col_res2:
                                    st.metric(f"Predikce (+{pred_days} dní)", f"{future_price:,.2f}", f"{pct_pred:+.2f} %")

                                fig_pred = go.Figure()

                                fig_pred.add_trace(go.Scatter(x=df_prophet['ds'], y=df_prophet['y'], name='Historie', line=dict(color='gray')))

                                future_part = forecast[forecast['ds'] > df_prophet['ds'].iloc[-1]]
                                fig_pred.add_trace(go.Scatter(x=future_part['ds'], y=future_part['yhat'], name='Predikce', line=dict(color='#58A6FF', width=3)))

                                fig_pred.add_trace(go.Scatter(
                                    x=pd.concat([future_part['ds'], future_part['ds'][::-1]]),
                                    y=pd.concat([future_part['yhat_upper'], future_part['yhat_lower'][::-1]]),
                                    fill='toself',
                                    fillcolor='rgba(88, 166, 255, 0.2)',
                                    line=dict(color='rgba(255,255,255,0)'),
                                    name='Rozptyl (Nejistota)'
                                ))

                                fig_pred.update_layout(template="plotly_dark", height=500, font_family="Roboto Mono", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                                fig_pred = make_plotly_cyberpunk(fig_pred)
                                st.plotly_chart(fig_pred, use_container_width=True)

                                st.warning("⚠️ **Disclaimer:** Toto je statistický model, ne křišťálová koule. Šedá zóna ukazuje možný rozptyl. Nikdy neobchoduj jen podle tohoto grafu!")

                            else:
                                st.error(f"Nedostatek dat pro trénink modelu {pred_ticker}.")
                    except Exception as e:
                        st.error(f"Chyba Neuronové sítě: {e}")
                        st.caption("Tip: Ujisti se, že máš v requirements.txt knihovnu 'prophet'.")

            st.divider()

            with st.expander("⏳ DCA BACKTESTER (Co kdybych investoval pravidelně?)", expanded=True):
                st.info("Zjisti, kolik bys měl dnes, kdyby jsi pravidelně nakupoval konkrétní akcii v minulosti.")

                c_dca1, c_dca2, c_dca3 = st.columns(3)
                with c_dca1:
                    dca_ticker = st.text_input("Ticker (např. AAPL, CEZ.PR, BTC-USD)", value="BTC-USD").upper()
                with c_dca2:
                    dca_amount = st.number_input("Měsíční vklad (Kč)", value=2000, step=500)
                with c_dca3:
                    dca_years = st.slider("Délka investice (roky)", 1, 10, 5)

                if st.button("🚀 SPUSTIT STROJ ČASU", type="primary"):
                    with st.spinner(f"Vracím se do roku {datetime.now().year - dca_years}..."):
                        try:
                            start_date_dca = datetime.now() - timedelta(days=dca_years*365)
                            dca_hist = yf.download(dca_ticker, start=start_date_dca, interval="1mo", progress=False)

                            if not dca_hist.empty:
                                if isinstance(dca_hist.columns, pd.MultiIndex):
                                    close_prices = dca_hist['Close'].iloc[:, 0]
                                else:
                                    close_prices = dca_hist['Close']

                                close_prices = close_prices.dropna()

                                is_czk_stock = ".PR" in dca_ticker
                                conversion_rate = 1.0 if is_czk_stock else kurzy.get("CZK", 21)

                                total_invested_czk = 0
                                total_shares = 0
                                portfolio_evolution = []

                                for date, price in close_prices.items():
                                    price_czk = price * conversion_rate

                                    shares_bought = dca_amount / price_czk
                                    total_shares += shares_bought
                                    total_invested_czk += dca_amount

                                    current_value = total_shares * price_czk

                                    portfolio_evolution.append({
                                        "Datum": date,
                                        "Hodnota portfolia": current_value,
                                        "Vloženo celkem": total_invested_czk
                                    })

                                dca_df = pd.DataFrame(portfolio_evolution).set_index("Datum")
                                final_val = dca_df["Hodnota portfolia"].iloc[-1]
                                final_profit = final_val - total_invested_czk
                                final_roi = (final_profit / total_invested_czk) * 100

                                st.divider()
                                cm1, cm2, cm3 = st.columns(3)
                                cm1.metric("Vloženo celkem", f"{total_invested_czk:,.0f} Kč")
                                cm2.metric("Hodnota DNES", f"{final_val:,.0f} Kč", delta=f"{final_profit:+,.0f} Kč")
                                cm3.metric("Zhodnocení", f"{final_roi:+.2f} %")

                                st.subheader("📈 Vývoj v čase")
                                fig_dca = px.area(dca_df, x=dca_df.index, y=["Hodnota portfolia", "Vloženo celkem"],
                                                  color_discrete_map={"Hodnota portfolia": "#00CC96", "Vloženo celkem": "#AB63FA"},
                                                  template="plotly_dark")
                                fig_dca.update_layout(xaxis_title="", yaxis_title="Hodnota (Kč)", legend=dict(orientation="h", y=1.1), font_family="Roboto Mono", paper_bgcolor="rgba(0,0,0,0)")
                                fig_dca = make_plotly_cyberpunk(fig_dca)
                                st.plotly_chart(fig_dca, use_container_width=True)

                                if final_profit > 0:
                                    st.success(f"🎉 Kdybys začal před {dca_years} lety, mohl jsi si dnes koupit ojeté auto (nebo hodně zmrzliny).")
                                else:
                                    st.error("📉 Au. I s pravidelným investováním bys byl v mínusu. To chce silné nervy.")

                            else:
                                st.warning(f"Nepodařilo se stáhnout historii pro {dca_ticker}. Zkus jiný symbol.")
                        except Exception as e:
                            st.error(f"Chyba ve stroji času: {e}")

            st.divider()

            st.subheader("💥 CRASH TEST & HISTORICKÉ SCÉNÁŘE")
            st.info("Otestuj odolnost svého portfolia proti historickým krizím nebo vlastnímu scénáři.")

            scenarios = {
                "COVID-19 (2020)": {"drop": 34, "desc": "Pandemie. Rychlý pád o 34 % za měsíc. Následovalo rychlé oživení (V-shape).", "icon": "🦠"},
                "Finanční krize (2008)": {"drop": 57, "desc": "Hypoteční krize. Pád o 57 % trval 17 měsíců. Dlouhá recese.", "icon": "📉"},
                "Dot-com bublina (2000)": {"drop": 49, "desc": "Splasknutí technologické bubliny. Nasdaq spadl o 78 %, S&P 500 o 49 %.", "icon": "💻"},
                "Black Monday (1987)": {"drop": 22, "desc": "Černé pondělí. Největší jednodenní propad v historii (-22 %).", "icon": "⚡"}
            }

            st.write("### 📜 Vyber scénář z historie:")
            cols = st.columns(4)

            if 'crash_sim_drop' not in st.session_state:
                st.session_state['crash_sim_drop'] = 20
            if 'crash_sim_name' not in st.session_state:
                st.session_state['crash_sim_name'] = "Vlastní scénář"
            if 'crash_sim_desc' not in st.session_state:
                st.session_state['crash_sim_desc'] = "Manuální nastavení."

            for i, (name, data) in enumerate(scenarios.items()):
                with cols[i]:
                    if st.button(f"{data['icon']} {name}\n(-{data['drop']}%)", use_container_width=True):
                        st.session_state['crash_sim_drop'] = data['drop']
                        st.session_state['crash_sim_name'] = name
                        st.session_state['crash_sim_desc'] = data['desc']
                        st.rerun()

            st.write("### 🎛️ Nebo nastav vlastní propad:")

            current_drop_val = int(st.session_state['crash_sim_drop'])

            propad = st.slider("Simulace pádu trhu (%)", 5, 90, current_drop_val, step=1, key="crash_slider_manual")

            scenario_name = st.session_state['crash_sim_name']
            scenario_desc = st.session_state['crash_sim_desc']

            if propad != current_drop_val:
                scenario_name = "Vlastní scénář"
                scenario_desc = f"Simulace manuálního propadu o {propad} %."
                st.session_state['crash_sim_drop'] = propad

            ztrata_usd = celk_hod_usd * (propad / 100)
            zbytek_usd = celk_hod_usd * (1 - propad / 100)

            ztrata_czk = ztrata_usd * kurzy.get("CZK", 21)
            zbytek_czk = zbytek_usd * kurzy.get("CZK", 21)

            st.subheader(f"🛡️ VÝSLEDEK: {scenario_name}")
            st.caption(scenario_desc)

            c_cr1, c_cr2 = st.columns([1, 2])
            with c_cr1:
                st.metric("Tvoje ZTRÁTA", f"-{ztrata_czk:,.0f} Kč", delta=f"-{propad} %", delta_color="inverse")
                st.metric("Zůstatek po pádu", f"{zbytek_czk:,.0f} Kč")

            with c_cr2:
                chart_data = pd.DataFrame({
                    "Stav": ["Ztráta 💸", "Zůstatek 💰"],
                    "Hodnota": [ztrata_czk, zbytek_czk]
                })
                fig_crash = px.pie(chart_data, values='Hodnota', names='Stav', hole=0.5,
                                   color='Stav', color_discrete_map={"Ztráta 💸": "#da3633", "Zůstatek 💰": "#238636"})
                fig_crash.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0), showlegend=True, paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
                fig_crash = make_plotly_cyberpunk(fig_crash)
                st.plotly_chart(fig_crash, use_container_width=True)

            if propad > 40:
                st.error("⚠️ Tohle je brutální scénář. Historie ukazuje, že trhy se nakonec vždy vrátily, ale trvalo to roky.")
            elif propad > 20:
                st.warning("⚠️ Typický medvědí trh. Dobrá příležitost k nákupu, pokud máš hotovost.")
            else:
                st.info("ℹ️ Běžná korekce. Nic, co by tě mělo rozhodit.")

        with tab5:
            st.subheader("🏆 SROVNÁNÍ S TRHEM (S&P 500) & SHARPE RATIO")
            if not hist_vyvoje.empty and len(hist_vyvoje) > 1:
                user_df = hist_vyvoje.copy();
                user_df['Date'] = pd.to_datetime(user_df['Date']); user_df = user_df.sort_values('Date').set_index('Date')
                start_val = user_df['TotalUSD'].iloc[0]
                if start_val > 0: user_df['MyReturn'] = ((user_df['TotalUSD'] / start_val) - 1) * 100
                else: user_df['MyReturn'] = 0
                start_date = user_df.index[0].strftime('%Y-%m-%d')

                my_returns = user_df['TotalUSD'].pct_change().dropna()
                my_sharpe = calculate_sharpe_ratio(my_returns)

                try:
                    sp500 = yf.download("^GSPC", start=start_date, progress=False)
                    if not sp500.empty:
                        if isinstance(sp500.columns, pd.MultiIndex): close_col = sp500['Close'].iloc[:, 0]
                        else: close_col = sp500['Close']
                        sp500_start = close_col.iloc[0]
                        sp500_norm = ((close_col / sp500_start) - 1) * 100

                        sp500_returns = close_col.pct_change().dropna()
                        sp500_sharpe = calculate_sharpe_ratio(sp500_returns)

                        fig_bench = go.Figure()
                        fig_bench.add_trace(go.Scatter(x=user_df.index, y=user_df['MyReturn'], mode='lines', name='Moje Portfolio', line=dict(color='#00CC96', width=3)))
                        fig_bench.add_trace(go.Scatter(x=sp500_norm.index, y=sp500_norm, mode='lines', name='S&P 500', line=dict(color='#808080', width=2, dash='dot')))
                        fig_bench.update_layout(title="Výkonnost v % od začátku měření", xaxis_title="", yaxis_title="Změna (%)", template="plotly_dark", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01), font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                        fig_bench.update_xaxes(showgrid=False)
                        fig_bench.update_yaxes(showgrid=True, gridcolor='#30363D')
                        fig_bench = make_plotly_cyberpunk(fig_bench)
                        st.plotly_chart(fig_bench, use_container_width=True, key="fig_benchmark")
                        add_download_button(fig_bench, "benchmark_analyza")

                        my_last = user_df['MyReturn'].iloc[-1]; sp_last = sp500_norm.iloc[-1]; diff = my_last - sp_last
                        c_b1, c_b2, c_b3, c_b4 = st.columns(4)

                        c_b1.metric("Můj výnos", f"{my_last:+.2f} %")
                        c_b2.metric("S&P 500 výnos", f"{sp_last:+.2f} %")
                        c_b3.metric("Můj Sharpe", f"{my_sharpe:+.2f}", help="Měří výnos na jednotku rizika.")
                        c_b4.metric("S&P 500 Sharpe", f"{sp500_sharpe:+.2f}", help="Měří výnos na jednotku rizika indexu.")

                        if diff > 0: st.success("🎉 Gratuluji! Porážíš trh na výnosu.")
                        else: st.warning("📉 Trh zatím vede na výnosu. Zvaž indexové ETF.")

                        st.divider()
                        if my_sharpe > sp500_sharpe and my_sharpe > 0:
                            st.markdown("✅ **Analýza rizika (Sharpe):** Tvé portfolio dosahuje lepších výnosů v poměru k podstoupenému riziku než S&P 500. Skvělá práce s rizikem!")
                        elif my_sharpe < sp500_sharpe and my_sharpe > 0:
                            st.markdown("⚠️ **Analýza rizika (Sharpe):** S&P 500 dosahuje vyššího výnosu na jednotku rizika. Zkus zvážit diverzifikaci pro snížení volatility.")
                        else:
                            st.markdown("ℹ️ **Analýza rizika (Sharpe):** Pro smysluplné Sharpe Ratio potřebujeme více dat nebo kladné výnosy.")

                    else: st.warning("Nepodařilo se stáhnout data S&P 500.")
                except Exception as e: st.error(f"Chyba benchmarku: {e}")
            else: st.info("Pro srovnání potřebuješ historii alespoň za 2 dny.")

        with tab6:
            render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd)

        with tab7:
            render_analýza_rebalancing_page(df, vdf, kurzy)

        with tab8:
            render_analýza_korelace_page(df, kurzy)


        with tab9:
            render_analýza_kalendář_page(df, df_watch, LIVE_DATA)

    elif page == "📰 Zprávy":
        st.title("📰 BURZOVNÍ ZPRAVODAJSTVÍ")
        try:
            from wordcloud import WordCloud
            import matplotlib.pyplot as plt

            raw_news_cloud = cached_zpravy() 
            if raw_news_cloud:
                with st.expander("☁️ TÉMATA DNE (Co hýbe trhem)", expanded=True):
                    text_data = " ".join([n['title'] for n in raw_news_cloud]).upper()

                    stop_words = ["A", "I", "O", "U", "V", "S", "K", "Z", "SE", "SI", "NA", "DO", "JE", "TO", "ŽE", "ALE", "PRO", "JAK", "TAK", "OD", "PO", "NEBO", "BUDE", "BYL", "MÁ", "JSOU", "KTERÝ", "KTERÁ", "ONLINE", "AKTUÁNĚ", "CENA", "BURZA", "TRH", "AKCIE", "INVESTICE", "ČESKÉ", "NOVINY", "IDNES", "SEZNAM"]

                    wc = WordCloud(
                        width=800, height=300,
                        background_color=None,
                        mode="RGBA",
                        stopwords=stop_words,
                        min_font_size=12,
                        colormap="GnBu"
                    ).generate(text_data)

                    fig_cloud, ax = plt.subplots(figsize=(10, 4))
                    ax.imshow(wc, interpolation="bilinear")
                    ax.axis("off")
                    fig_cloud.patch.set_alpha(0)
                    ax.patch.set_alpha(0)
                    make_matplotlib_cyberpunk(fig_cloud, ax)
                    st.pyplot(fig_cloud, use_container_width=True)
        except ImportError:
            st.warning("⚠️ Pro zobrazení Mraku slov nainstaluj knihovnu: `pip install wordcloud`")
        except Exception as e:
            st.error(f"Chyba WordCloud: {e}")
        
        st.divider()

        if AI_AVAILABLE:
            def analyze_news_with_ai(title, link):
                portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
                if viz_data_list: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data_list])

                prompt_to_send = f"Analyzuj následující finanční zprávu V KONTEXTU MÉHO PORTFOLIA. Zpráva: {title} (Odkaz: {link}). Jaký by mala mít dopad na mé současné držby?"
                st.session_state["chat_messages"].append({"role": "user", "content": prompt_to_send})
                st.session_state['chat_expanded'] = True
                st.rerun()

            if st.button("🧠 SPUSTIT AI SENTIMENT 2.0", type="primary"):
                with st.spinner("AI analyzuje trh..."):
                    raw_news = cached_zpravy() 
                    titles = [n['title'] for n in raw_news[:8]]
                    titles_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
                    prompt = f"""Jsi finanční analytik. Analyzuj tyto novinové titulky a urči jejich sentiment.\nTITULKY:\n{titles_str}\nPro každý titulek vrať přesně tento formát na jeden řádek (bez odrážek):\nINDEX|SKÓRE(0-100)|VYSVĚTLENÍ (česky, max 1 věta)"""
                    try:
                        response = model.generate_content(prompt)
                        analysis_map = {}
                        for line in response.text.strip().split('\n'):
                            parts = line.split('|')
                            if len(parts) == 3:
                                try:
                                    idx = int(parts[0].replace('.', '').strip()) - 1; score = int(parts[1].strip()); reason = parts[2].strip()
                                    analysis_map[idx] = {'score': score, 'reason': reason}
                                except: pass
                        st.session_state['ai_news_analysis'] = analysis_map
                        st.session_state['news_timestamp'] = datetime.now()
                        st.success("Analýza dokončena!")
                    except Exception as e: st.error(f"Chyba AI: {e}")

        news = cached_zpravy() 
        ai_results = st.session_state.get('ai_news_analysis', {})
        if news:
            c1, c2 = st.columns(2)
            for i, n in enumerate(news):
                col = c1 if i % 2 == 0 else c2
                with col:
                    with st.container(border=True):
                        if i in ai_results:
                            res = ai_results[i]; score = res['score']; reason = res['reason']
                            if score >= 60: color = "green"; emoji = "🟢 BÝČÍ"
                            elif score <= 40: color = "red"; emoji = "🔴 MEDVĚDÍ"
                            else: color = "orange"; emoji = "🟡 NEUTRÁL"
                            st.markdown(f"#### {n['title']}")
                            st.caption(f"📅 {n['published']}")
                            st.markdown(f"**{emoji} (Skóre: {score}/100)**"); st.progress(score); st.info(f"🤖 {reason}")
                        else:
                            title_upper = n['title'].upper(); sentiment = "neutral"
                            for kw in KW_POSITIVNI:
                                if kw in title_upper: sentiment = "positive"; break
                            if sentiment == "neutral":
                                for kw in KW_NEGATIVNI:
                                    if kw in title_upper: sentiment = "negative"; break
                            if sentiment == "positive": st.success(f"🟢 **BÝČÍ ZPRÁVA**")
                            elif sentiment == "negative": st.error(f"🔴 **MEDVĚDÍ SIGNÁL**")
                            st.markdown(f"### {n['title']}"); st.caption(f"📅 {n['published']}")

                        st.link_button("Číst článek", n['link'], help="Otevře článek v novém okně.")
                        if AI_AVAILABLE:
                            if st.button(f"🤖 Analyzovat s AI (Kontext)", key=f"analyze_ai_{i}"):
                                analyze_news_with_ai(n['title'], n['link'])
        else: st.info("Žádné nové zprávy.")

    elif page == "💸 Obchod":
        st.title("💸 OBCHODNÍ TERMINÁL")
        t1, t2, t3, t4 = st.tabs(["NÁKUP", "PRODEJ", "SMĚNÁRNA", "VKLADY/VÝBĚRY"])
        with t1:
            c1, c2 = st.columns(2)
            with c1:
                t = st.text_input("Ticker (např. AAPL)").upper()
                k = st.number_input("Počet kusů", 0.0, step=0.1)
                c = st.number_input("Nákupní cena ($)", 0.0, step=0.1)
            with c2:
                st.info("Zkontroluj zůstatek v peněžence!")
                if st.button("KOUPIT AKCIE", use_container_width=True):
                    _, m, _ = ziskej_info(t)
                    final_c = c if c > 0 else ziskej_info(t)[0]

                    if final_c and final_c > 0:
                        ok, msg = proved_nakup(t, k, final_c, USER)
                        if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error(msg)
                    else:
                        st.error("Nepodařilo se získat cenu. Zadej ji ručně.")
        with t2:
            ts = df['Ticker'].unique() if not df.empty else []
            s_t = st.selectbox("Prodat:", ts)
            s_k = st.number_input("Kusy", 0.0, step=0.1, key="sk")
            s_c = st.number_input("Cena ($)", 0.0, step=0.1, key="sc")
            if st.button("PRODAT", use_container_width=True):
                _, m, _ = ziskej_info(s_t)
                ok, msg = proved_prodej(s_t, s_k, s_c, USER, m)
                if ok: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)
        with t3:
            col1, col2, col3 = st.columns(3)
            with col1: am = st.number_input("Částka", 0.0)
            with col2: fr = st.selectbox("Z", ["USD", "CZK", "EUR"])
            with col3: to = st.selectbox("Do", ["CZK", "USD", "EUR"])
            if st.button("SMĚNIT", use_container_width=True):
                if zustatky.get(fr, 0) >= am:
                    proved_smenu(am, fr, to, USER); st.success("Hotovo"); time.sleep(1); st.rerun()
                else: st.error("Chybí prostředky")
        with t4:
            c1, c2 = st.columns(2)
            with c1:
                v_a = st.number_input("Vklad/Výběr", 0.0)
                v_m = st.selectbox("Měna", ["USD", "CZK", "EUR"], key="vm")
                if st.button("VLOŽIT"): pohyb_penez(v_a, v_m, "Vklad", "Man", USER, st.session_state['df_cash']); st.rerun()
                if st.button("VYBRAT"): pohyb_penez(-v_a, v_m, "Výběr", "Man", USER, st.session_state['df_cash']); st.rerun()
            with c2:
                st.dataframe(df_cash.sort_values('Datum', ascending=False).head(10), use_container_width=True, hide_index=True)

    elif page == "💎 Dividendy":
        render_dividendy_page(USER, df, df_div, kurzy, viz_data_list)

    elif page == "🎮 Gamifikace":
        render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky)

    elif page == "⚙️ Nastavení":
        st.title("⚙️ KONFIGURACE SYSTÉMU")
        
        with st.container(border=True):
            st.subheader("🤖 AI Jádro & Osobnost")
            
            c_stat1, c_stat2 = st.columns([1, 3])
            with c_stat1:
                if AI_AVAILABLE:
                    st.success("API: ONLINE")
                else:
                    st.error("API: OFFLINE")
            
            with c_stat2:
                is_on = st.toggle("Povolit AI funkce", value=st.session_state.get('ai_enabled', False))
                if is_on != st.session_state.get('ai_enabled', False):
                    st.session_state['ai_enabled'] = is_on
                    st.rerun()

            st.divider()

            st.caption("🎭 Nastavení chování (System Prompts)")
            
            if 'ai_prompts' not in st.session_state:
                st.session_state['ai_prompts'] = {
                    "Ranní report": "Jsi cynický burzovní makléř z Wall Street. Používej finanční slang.",
                    "Analýza akcií": "Jsi konzervativní Warren Buffett. Hledej hodnotu a bezpečí.",
                    "Chatbot": "Jsi stručný a efektivní asistent Terminalu Pro."
                }

            prompts_df = pd.DataFrame(
                list(st.session_state['ai_prompts'].items()),
                columns=["Funkce", "Instrukce (Prompt)"]
            )
            
            edited_prompts = st.data_editor(
                prompts_df,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "Funkce": st.column_config.TextColumn(disabled=True),
                    "Instrukce (Prompt)": st.column_config.TextColumn(width="large")
                },
                key="prompt_editor"
            )

            if st.button("💾 Uložit nastavení AI"):
                new_prompts = dict(zip(edited_prompts["Funkce"], edited_prompts["Instrukce (Prompt)"]))
                st.session_state['ai_prompts'] = new_prompts
                st.toast("Osobnost AI aktualizována!", icon="🧠")

        st.write("")
        st.subheader("💾 DATA & SPRÁVA")
        st.info("Zde můžeš editovat data natvrdo.")
        t1, t2 = st.tabs(["PORTFOLIO", "HISTORIE"])
        with t1:
            new_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Portfolio"): 
                st.session_state['df'] = new_df
                uloz_data_uzivatele(new_df, USER, SOUBOR_DATA)
                invalidate_data_core()
                st.success("Uloženo")
                time.sleep(1)
                st.rerun()
        with t2:
            new_h = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Historii"): 
                st.session_state['df_hist'] = new_h
                uloz_data_uzivatele(new_h, USER, SOUBOR_HISTORIE)
                invalidate_data_core()
                st.success("Uloženo")
                time.sleep(1)
                st.rerun()
        
        st.divider(); st.subheader("📦 ZÁLOHA")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for n, d in [(SOUBOR_DATA, 'df'), (SOUBOR_HISTORIE, 'df_hist'), (SOUBOR_CASH, 'df_cash'), (SOUBOR_DIVIDENDY, 'df_div'), (SOUBOR_WATCHLIST, 'df_watch')]:
                if d in st.session_state: zf.writestr(n, st.session_state[d].to_csv(index=False))
        st.download_button("Stáhnout Data", buf.getvalue(), f"backup_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")
        
        st.divider()
        st.subheader("📲 NOTIFIKACE (Telegram)")
        st.caption("Otestuj spojení s tvým mobilem.")

        notify.otestovat_tlacitko()
        
    # --- AI CHATBOT (Vždy dole) ---
    with st.expander("🤖 AI ASISTENT", expanded=st.session_state.get('chat_expanded', False)):
        st.markdown('<span id="floating-bot-anchor"></span>', unsafe_allow_html=True)

        c_clear, _ = st.columns([1, 2])
        with c_clear:
            if st.button("🧹 Nová konverzace", key="clear_chat"):
                st.session_state["chat_messages"] = [{"role": "assistant", "content": "Paměť vymazána. O čem se chceš bavit teď? 🧠"}]
                st.rerun()

        if "chat_messages" not in st.session_state: 
            st.session_state["chat_messages"] = [{"role": "assistant", "content": "Ahoj! Jsem tvůj AI průvodce. Co pro tebe mohu udělat?"}]
        
        for msg in st.session_state["chat_messages"]: 
            st.chat_message(msg["role"]).write(msg["content"])
            
        if prompt := st.chat_input("Zeptej se..."):
            if not AI_AVAILABLE or not st.session_state.get('ai_enabled', False):
                st.error("AI je neaktivní nebo chybí API klíč. Zkontroluj Nastavení.")
            else: 
                st.session_state["chat_messages"].append({"role": "user", "content": prompt})
                st.rerun()

        if st.session_state["chat_messages"][-1]["role"] == "user":
            if not st.session_state.get('ai_enabled', False):
                st.info("AI je momentálně vypnutá.")
            else:
                with st.spinner("Přemýšlím..."):
                    last_user_msg = st.session_state["chat_messages"][-1]["content"]
                    
                    portfolio_context = f"Jmění: {celk_hod_czk:,.0f} CZK. "
                    if viz_data_list: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data_list])
                    
                    ai_reply = ""
                    try:
                        ai_reply = get_chat_response(model, last_user_msg, portfolio_context)
                    except Exception as e:
                        error_msg = str(e)
                        if "429" in error_msg:
                            ai_reply = "🛑 **Došla mi energie (Quota Exceeded).** Google API limit byl vyčerpán. Zkus to prosím za chvíli."
                        else:
                            ai_reply = f"⚠️ Chyba komunikace: {error_msg}"
                    
                    st.session_state["chat_messages"].append({"role": "assistant", "content": ai_reply})
                    st.rerun()

if __name__ == "__main__":
    main()
