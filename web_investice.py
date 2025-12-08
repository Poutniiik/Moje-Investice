import notification_engine as notify
import bank_engine as bank
import bank_engine
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
# Tyto funkce obalují původní funkce do cache, aby se nevolaly zbytečně často.

@st.cache_data(ttl=3600) # 1 hodina cache pro detaily (fundamenty se mění pomalu)
def cached_detail_akcie(ticker):
    return ziskej_detail_akcie(ticker)

@st.cache_data(ttl=1800) # 30 minut cache pro Fear & Greed
def cached_fear_greed():
    return ziskej_fear_greed()

@st.cache_data(ttl=3600) # 1 hodina pro zprávy
def cached_zpravy():
    return ziskej_zpravy()

@st.cache_data(ttl=300) # 5 minut cache pro hromadné ceny (Live data)
def cached_ceny_hromadne(tickers_list):
    return ziskej_ceny_hromadne(tickers_list)

@st.cache_data(ttl=3600) # 1 hodina cache pro kurzy
def cached_kurzy():
    return ziskej_kurzy()

# -----------------------------------------------------

# --- NÁSTROJ PRO ŘÍZENÍ STAVU: ZNEHODNOCENÍ DAT ---
def invalidate_data_core():
    """Vynutí opětovný přepočet datového jádra při příštím zobrazení stránky."""
    if 'data_core' in st.session_state:
        # Nastavíme timestamp do minulosti, čímž vyprší 5minutový limit
        st.session_state['data_core']['timestamp'] = datetime.now() - timedelta(minutes=6)

# --- OPRAVA 1: CACHOVANÁ INICIALIZACE AI (Aby se nevolala pořád dokola) ---
@st.cache_resource(show_spinner="Připojuji neurální sítě...")
def get_cached_ai_connection():
    """
    Tato funkce zajistí, že se init_ai() zavolá jen JEDNOU za běh serveru,
    ne při každém kliknutí uživatele. To zabrání chybě 429.
    """
    try:
        return init_ai()
    except Exception as e:
        # Pokud to selže, vrátíme None a False, aby aplikace nepadla
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

# --- ATOMICKÁ FUNKCE: POHYB PENĚZ (Upravena pro atomicitu) ---
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
    """Vykreslí stránku '🏠 Přehled' (Dashboard) - VERZE 2.2 (Sektory + Měny Tabs)"""
    
    # --- BEZPEČNÁ INICIALIZACE ---
    if 'show_cash_history' not in st.session_state:
        st.session_state['show_cash_history'] = False 
    if 'show_portfolio_live' not in st.session_state: 
        st.session_state['show_portfolio_live'] = True
    
    # 1. HLAVIČKA A HLAVNÍ METRIKY
    st.title(f"🏠 PŘEHLED: {USER.upper()}")
    
    with st.container(border=True):
        k1, k2, k3, k4 = st.columns(4)
        kurz_czk = kurzy.get('CZK', 20.85)
        
        k1.metric("💰 JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{(celk_hod_usd-celk_inv_usd)*kurz_czk:+,.0f} Kč Zisk")
        k2.metric("🌎 JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} USD")
        k3.metric("📈 ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
        k4.metric("💳 HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné prostředky")

    st.write("") 

    # 2. ŘÁDEK: TRŽNÍ NÁLADA + KOMPAS
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
            st.caption("🧭 GLOBÁLNÍ KOMPAS")
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

    # 3. ŘÁDEK: GRAFY (VÝVOJ + NOVÝ TABBED BOX)
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

    # --- ZDE JE TA NOVÁ VYCHYTÁVKA (TABS) ---
    with col_graf2:
        with st.container(border=True):
            # Přepínání mezi Sektory a Měnami
            tab_sec, tab_cur = st.tabs(["🏭 SEKTORY", "💱 MĚNY"])
            
            # --- ZÁLOŽKA 1: SEKTORY ---
            with tab_sec:
                if not vdf.empty:
                    df_sector = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
                    total_val = df_sector['HodnotaUSD'].sum()
                    df_sector['Podíl'] = (df_sector['HodnotaUSD'] / total_val) * 100
                    
                    fig_pie = px.pie(df_sector, values='HodnotaUSD', names='Sektor', hole=0.7, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Bold)
                    fig_pie.update_traces(textinfo='none', hoverinfo='label+percent+value') 
                    fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=150, paper_bgcolor="rgba(0,0,0,0)")
                    
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    st.dataframe(
                        df_sector.sort_values('Podíl', ascending=False),
                        column_config={
                            "Sektor": st.column_config.TextColumn("Sektor"),
                            "Podíl": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100),
                            "HodnotaUSD": st.column_config.NumberColumn("$ USD", format="$%.0f")
                        },
                        column_order=["Sektor", "Podíl", "HodnotaUSD"], use_container_width=True, hide_index=True
                    )
                else: st.info("Žádná data")

            # --- ZÁLOŽKA 2: MĚNY (NOVÉ!) ---
            with tab_cur:
                if not vdf.empty:
                    # Agregace podle měny
                    df_curr = vdf.groupby('Měna')['HodnotaUSD'].sum().reset_index()
                    total_val_c = df_curr['HodnotaUSD'].sum()
                    df_curr['Podíl'] = (df_curr['HodnotaUSD'] / total_val_c) * 100
                    
                    # Graf měn (jiná paleta barev - pastelová)
                    fig_cur = px.pie(df_curr, values='HodnotaUSD', names='Měna', hole=0.7, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_cur.update_traces(textinfo='none', hoverinfo='label+percent+value')
                    fig_cur.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=150, paper_bgcolor="rgba(0,0,0,0)")
                    
                    st.plotly_chart(fig_cur, use_container_width=True)
                    
                    st.dataframe(
                        df_curr.sort_values('Podíl', ascending=False),
                        column_config={
                            "Měna": st.column_config.TextColumn("Měna"),
                            "Podíl": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100),
                            "HodnotaUSD": st.column_config.NumberColumn("Hodnota (v USD)", format="$%.0f")
                        },
                        column_order=["Měna", "Podíl", "HodnotaUSD"], use_container_width=True, hide_index=True
                    )
                else: st.info("Žádná data")
    # --------------------------------------------------------

    # 4. ŘÁDEK: SANKEY
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

    # 5. ŘÁDEK: PORTFOLIO LIVE
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
                },
                column_order=["Ticker", "Trend 30d", "HodnotaUSD", "Dnes", "Zisk"],
                use_container_width=True, hide_index=True
            )
            
            with st.expander("🔍 Zobrazit detailní tabulku"):
                st.dataframe(
                    vdf,
                    column_config={
                        "Ticker": st.column_config.TextColumn("Symbol"),
                        "Sektor": st.column_config.TextColumn("Sektor"),
                        "HodnotaUSD": st.column_config.ProgressColumn("Velikost", format="$%.0f", min_value=0, max_value=max(vdf["HodnotaUSD"])),
                        "Zisk": st.column_config.NumberColumn("Zisk/Ztráta", format="%.2f"),
                        "Dnes": st.column_config.NumberColumn("Dnes %", format="%.2f%%"),
                        "Divi": st.column_config.NumberColumn("Yield", format="%.2f%%"),
                        "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
                        "Trend 30d": st.column_config.LineChartColumn("Trend", width="medium")
                    },
                    column_order=["Ticker", "Trend 30d", "Sektor", "Měna", "Kusy", "Průměr", "Cena", "Dnes", "HodnotaUSD", "Zisk", "Divi", "P/E"],
                    use_container_width=True,
                    hide_index=True
                )
        elif vdf.empty:
             st.info("Portfolio je prázdné.")

    # 6. HISTORIE HOTOVOSTI
    st.write("")
    st.session_state['show_cash_history'] = st.checkbox("📜 Zobrazit historii hotovosti", value=st.session_state['show_cash_history'])

    if st.session_state['show_cash_history']:
        st.divider()
        st.subheader("🏦 HISTORIE HOTOVOSTI")
        df_cash_local = st.session_state.get('df_cash', pd.DataFrame())
        
        if not df_cash_local.empty:
            st.dataframe(df_cash_local.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Historie hotovosti je prázdná.")




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


def render_dividendy_page(USER, df, df_div, kurzy, viz_data_list):
    """Vykreslí stránku '💎 Dividendy'."""
    
    st.title("💎 DIVIDENDOVÝ KALENDÁŘ")

    # --- PROJEKTOR PASIVNÍHO PŘÍJMU (OPRAVENO A ZROBUSTNĚNO) ---
    est_annual_income_czk = 0
    # Abychom se vyhnuli chybě, zajistíme, že viz_data_list je list, i když je prázdný
    if isinstance(viz_data_list, pd.DataFrame):
        data_to_use = viz_data_list.to_dict('records')
    else:
        data_to_use = viz_data_list
        
    if data_to_use:
        for item in data_to_use:
            # Původní logika: HodnotaUSD * Divi Yield * Kurz CZK
            # ZAJIŠTĚNÍ ČÍSELNÉ HODNOTY A FALLBACK: 0.0
            # Divi je uložen jako desetinné číslo (např. 0.03 pro 3%)
            yield_val = item.get('Divi', 0.0)
            val_usd = item.get('HodnotaUSD', 0.0)
            
            # Konverze na float, pokud by náhodou byl 'Divi' NaN nebo None
            try:
                # Použijeme pd.isna pro robustní kontrolu Pandas NaN/None
                yield_val = float(yield_val) if pd.notna(yield_val) and yield_val is not False else 0.0
                val_usd = float(val_usd) if pd.notna(val_usd) and val_usd is not False else 0.0
            except ValueError:
                yield_val = 0.0
                val_usd = 0.0

            # ZMĚNA: Podmínka pro výpočet zůstává, ale proměnné jsou nyní bezpečné
            if yield_val > 0 and val_usd > 0:
                # Výpočet: USD Hodnota * (Dividendový Výnos, např. 0.03) * Kurz CZK
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

    with t_div1:
        if not df_div.empty:
            # Graf - OPRAVA VIZUALIZACE
            plot_df = df_div.copy()
            # Převedeme přesný čas jen na datum (string YYYY-MM-DD), aby měly sloupce šířku "1 den" a byly vidět
            plot_df['Datum_Den'] = pd.to_datetime(plot_df['Datum']).dt.strftime('%Y-%m-%d')

            # Seskupíme podle dne a tickeru (aby se v jednom dni sloupce sečetly/navrstvily)
            plot_df_grouped = plot_df.groupby(['Datum_Den', 'Ticker'])['Castka'].sum().reset_index()
            plot_df_grouped = plot_df_grouped.sort_values('Datum_Den')

            fig_div = px.bar(plot_df_grouped, x='Datum_Den', y='Castka', color='Ticker',
                             title="Historie výplat (po dnech)",
                             labels={'Datum_Den': 'Datum', 'Castka': 'Částka'},
                             template="plotly_dark")

            # Vynutíme, aby osa X byla kategorie (text), ne časová osa -> tlusté sloupce
            fig_div.update_xaxes(type='category')

            fig_div.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
            fig_div = make_plotly_cyberpunk(fig_div)
            st.plotly_chart(fig_div, use_container_width=True)

            # Tabulka - tu necháme s původními detailními daty
            st.dataframe(df_div.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
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
            
            # Použijeme globální funkci z Canvasu
            if st.form_submit_button("💰 PŘIPSAT DIVIDENDU"):
                pridat_dividendu(dt_ticker, dt_amount, dt_curr, USER)
                st.success(f"Připsáno {dt_amount} {dt_curr} od {dt_ticker}")
                time.sleep(1)
                st.rerun()


def render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky):
    """Vykreslí stránku '🎮 Gamifikace' - VERZE 2.1 (Mobile Grid)"""


    st.title("🎮 INVESTIČNÍ ARÉNA")
   
    # --- 1. LEVEL HRÁČE (STATUS BAR) ---
    with st.container(border=True):
        c_lev1, c_lev2 = st.columns([3, 1])
        with c_lev1:
            st.subheader(f"Úroveň: {level_name}")
            # Vlastní progress bar s popiskem
            st.progress(level_progress)
           
            # Výpočet do dalšího levelu
            next_level_val = 0
            if celk_hod_czk < 10000: next_level_val = 10000
            elif celk_hod_czk < 50000: next_level_val = 50000
            elif celk_hod_czk < 100000: next_level_val = 100000
            elif celk_hod_czk < 500000: next_level_val = 500000
           
            if next_level_val > 0:
                chybi = next_level_val - celk_hod_czk
                st.caption(f"Do další úrovně chybí: **{chybi:,.0f} Kč**")
            else:
                st.success("🎉 MAX LEVEL DOSAŽEN!")
       
        with c_lev2:
            # Velký avatar nebo ikona levelu
            icon_map = {"Novic": "🧒", "Učeň": "🧑‍🎓", "Trader": "💼", "Profi": "🎩", "Velryba": "🐋"}
            # Získáme čisté jméno bez emoji pro klíč
            clean_name = level_name.split()[0]
            ikona = icon_map.get(clean_name, "👾")
            st.markdown(f"<h1 style='text-align: center; font-size: 50px;'>{ikona}</h1>", unsafe_allow_html=True)


    # --- 2. SÍŇ SLÁVY (ODZNAKY) - GRID 2x2 ---
    st.write("")
    st.subheader("🏆 SÍŇ SLÁVY (Odznaky)")
   
    # Příprava podmínek
    has_first = not df.empty
    cnt = len(df['Ticker'].unique()) if not df.empty else 0
    divi_total = 0
    if not df_div.empty:
        divi_total = df_div.apply(
            lambda r: r['Castka'] * (
                kurzy.get('CZK', 20.85) if r['Mena'] == 'USD'
                else (kurzy.get('CZK', 20.85) / kurzy.get('EUR', 1.16) if r['Mena'] == 'EUR' else 1)
            ), axis=1).sum()


    # Pomocná funkce pro render karty
    def render_badge_card(col, title, desc, cond, icon, color):
        with col:
            # Vzhled karty - když je splněno, svítí. Když ne, je šedá.
            opacity = "1.0" if cond else "0.4"
            border_color = color if cond else "#30363D"
            bg_color = "rgba(255,255,255,0.05)" if cond else "transparent"
           
            st.markdown(f"""
            <div style="
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 15px;
                text-align: center;
                background-color: {bg_color};
                opacity: {opacity};
                margin-bottom: 10px;">
                <div style="font-size: 40px; margin-bottom: 10px;">{icon}</div>
                <div style="font-weight: bold; color: {color}; margin-bottom: 5px;">{title}</div>
                <div style="font-size: 12px; color: #8B949E;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)


    # Řádek 1 (2 sloupce)
    c1, c2 = st.columns(2)
    render_badge_card(c1, "Začátečník", "Kup první akcii", has_first, "🥉", "#CD7F32") # Bronz
    render_badge_card(c2, "Stratég", "Drž 3 různé firmy", cnt >= 3, "🥈", "#C0C0C0")   # Stříbro
   
    # Řádek 2 (2 sloupce)
    c3, c4 = st.columns(2)
    render_badge_card(c3, "Boháč", "Portfolio > 100k", celk_hod_czk > 100000, "🥇", "#FFD700") # Zlato
    render_badge_card(c4, "Rentiér", "Dividendy > 500 Kč", divi_total > 500, "💎", "#00BFFF") # Diamant


    # --- 3. DYNAMICKÉ VÝZVY (QUEST LOG) ---
    st.divider()
    st.subheader("📜 QUEST LOG (Aktivní výzvy)")
   
    if 'rpg_tasks' not in st.session_state:
        st.session_state['rpg_tasks'] = []
   
    if not st.session_state['rpg_tasks']:
        # Načtení úkolů (z global proměnné RPG_TASKS definované jinde)
        # Zde předpokládáme, že RPG_TASKS existuje v souboru web_investice.py
        # Pokud ne, musíme ji definovat, ale v tvém kódu byla.
        try:
            for i, task in enumerate(RPG_TASKS):
                st.session_state['rpg_tasks'].append({"id": i, "title": task["title"], "desc": task["desc"], "completed": False})
        except: pass # Kdyby náhodou RPG_TASKS nebyly definované
   
    all_tasks_completed = True
   
    # Zobrazení úkolů
    for i, task_state in enumerate(st.session_state['rpg_tasks']):
        # Získání dat pro kontrolu
        df_w = st.session_state.get('df_watch', pd.DataFrame())
        viz_data_list = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
       
        # Odkaz na globální RPG_TASKS
        try:
            original_task = RPG_TASKS[task_state['id']]
            # Kontrola
            is_completed = original_task['check_fn'](df, df_w, zustatky, viz_data_list)
            # Progress text
            current, target, progress_text = get_task_progress(task_state['id'], df, df_w, zustatky, viz_data_list)
        except:
            is_completed = False
            current, target, progress_text = 0, 1, "Neznámý stav"


        st.session_state['rpg_tasks'][i]['completed'] = is_completed
        if not is_completed: all_tasks_completed = False
           
        # Vykreslení Questu (Kompaktní karta)
        with st.container(border=True):
            col_q1, col_q2 = st.columns([1, 5])
            with col_q1:
                st.markdown(f"<div style='font-size: 25px; text-align: center;'>{'✅' if is_completed else '📜'}</div>", unsafe_allow_html=True)
            with col_q2:
                st.markdown(f"**{task_state['title']}**")
               
                # Progress Bar
                if target > 0:
                    pct = min(current / target, 1.0)
                    st.progress(pct)
                    st.caption(f"{progress_text} ({int(pct*100)}%)")
                else:
                    st.info(progress_text)


    if all_tasks_completed and len(st.session_state['rpg_tasks']) > 0:
        st.balloons()
        st.success("VŠECHNY QUESTY SPLNĚNY! ⚔️")
        if st.button("🔄 Generovat nové RPG úkoly"):
            st.session_state['rpg_tasks'] = []
            st.rerun()


    # --- 4. AI DENNÍ LOGBOOK ---
    if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
        st.divider()
        st.subheader("🎲 DENNÍ ZÁPIS (AI Narrator)")
       
        # Logika pro příběh
        denni_zmena_czk = (celk_hod_czk - (hist_vyvoje.iloc[-2]['TotalUSD'] * kurzy.get("CZK", 21))) if len(hist_vyvoje) > 1 else 0
       
        if 'rpg_story_cache' not in st.session_state:
            st.session_state['rpg_story_cache'] = None
           
        if st.button("🎲 GENEROVAT PŘÍBĚH DNE", type="secondary", use_container_width=True):
            with st.spinner("Dungeon Master hází kostkou..."):
                sc, _ = ziskej_fear_greed()
                actual_score = sc if sc else 50
                rpg_res_text = generate_rpg_story(model, level_name, denni_zmena_czk, celk_hod_czk, actual_score)
                st.session_state['rpg_story_cache'] = rpg_res_text


        if st.session_state['rpg_story_cache']:
            st.markdown(f"""
            <div style="background-color: #0D1117; border-left: 4px solid #AB63FA; padding: 15px; border-radius: 5px;">
                <p style="font-style: italic; color: #E6E6E6; margin: 0;">"{st.session_state['rpg_story_cache']}"</p>
            </div>
            """, unsafe_allow_html=True)
           
    # --- 5. MOUDRO DNE ---
    st.divider()
    if 'quote' not in st.session_state: st.session_state['quote'] = random.choice(CITATY)
    st.caption("💡 Moudro dne")
    st.info(f"*{st.session_state['quote']}*")



# --- NOVÉ FUNKCE PRO ANALÝZU (Tabulky 6, 7, 8, 9) ---

def render_analýza_rebalancing_page(df, vdf, kurzy):
    """Vykreslí Rebalanční kalkulačku (Tab7 Analýzy)."""
    st.subheader("⚖️ REBALANČNÍ KALKULAČKA")
    if not vdf.empty:
        df_reb = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
        total_val = df_reb['HodnotaUSD'].sum()
        st.write("Nastav cílové váhy pro sektory:")
        
        # Abychom se vyhnuli problémům s klíči, musíme zajistit, že klíče jsou konzistentní
        targets = {}; 
        cols = st.columns(3)
        for i, row in df_reb.iterrows():
            current_pct = (row['HodnotaUSD'] / total_val) * 100
            # Využití klíčů Session State pro uchování hodnoty slideru
            key = f"reb_{row['Sektor']}"
            with cols[i % 3]:
                targets[row['Sektor']] = st.number_input(
                    f"{row['Sektor']} (%)", 
                    min_value=0.0, 
                    max_value=100.0, 
                    value=float(round(current_pct, 1)), 
                    step=1.0, 
                    key=key
                )
        
        total_target = sum(targets.values())
        if abs(total_target - 100) > 0.1: st.warning(f"⚠️ Součet cílů je {total_target:.1f}%. Měl by být 100%.")
        
        df_reb['Cíl %'] = df_reb['Sektor'].map(targets)
        df_reb['Cílová Hodnota'] = total_val * (df_reb['Cíl %'] / 100)
        df_reb['Rozdíl'] = df_reb['Cílová Hodnota'] - df_reb['HodnotaUSD']
        
        st.divider(); st.subheader("🛠️ Návrh akcí")
        for _, r in df_reb.iterrows():
            diff = r['Rozdíl']
            if abs(diff) > 1:
                if diff > 0: st.success(f"🟢 **{r['Sektor']}**: DOKOUPIT za {diff:,.0f} USD")
                else: st.error(f"🔴 **{r['Sektor']}**: PRODAT za {abs(diff):,.0f} USD")
        
        st.dataframe(df_reb.style.format({"HodnotaUSD": "{:,.0f}", "Cílová Hodnota": "{:,.0f}", "Rozdíl": "{:+,.0f}"}))
    else: 
        st.info("Portfolio je prázdné.")

def render_analýza_korelace_page(df, kurzy):
    """Vykreslí Matice Korelace (Tab8 Analýzy)."""
    st.subheader("📊 MATICE KORELACE (Diversifikace)")
    st.info("Jak moc se tvé akcie hýbou společně? Čím více 'modrá', tím lepší diverzifikace.")
    
    if not df.empty:
        tickers_list = df['Ticker'].unique().tolist()
        if len(tickers_list) > 1:
            try:
                with st.spinner("Počítám korelace..."):
                    hist_data = yf.download(tickers_list, period="1y")['Close']
                    returns = hist_data.pct_change().dropna()
                    corr_matrix = returns.corr()
                    
                    fig_corr = px.imshow(corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", origin='lower')
                    fig_corr.update_layout(template="plotly_dark", height=600, font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    
                    fig_corr = make_plotly_cyberpunk(fig_corr)
                    st.plotly_chart(fig_corr, use_container_width=True)
                    
                    avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix.values, 1)].mean()
                    st.metric("Průměrná korelace portfolia", f"{avg_corr:.2f}")
                    
                    if avg_corr > 0.7: st.error("⚠️ Vysoká korelace! Tvé akcie se hýbou stejně.")
                    elif avg_corr < 0.3: st.success("✅ Nízká korelace! Dobrá diverzifikace.")
                    else: st.warning("⚖️ Střední korelace. Portfolio je vyvážené.")
            except Exception as e: 
                st.error(f"Chyba při výpočtu korelace: {e}")
        else: 
            st.warning("Pro výpočet korelace potřebuješ alespoň 2 různé akcie.")
    else: 
        st.info("Portfolio je prázdné.")

def render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd):
    """Vykreslí Měnový simulátor (Tab6 Analýzy)."""
    st.subheader("💱 MĚNOVÝ SIMULÁTOR")
    st.info("Jak změna kurzu koruny ovlivní hodnotu tvého portfolia?")
    assets_by_curr = {"USD": 0, "EUR": 0, "CZK": 0}
    
    if viz_data_list:
        if isinstance(viz_data_list, pd.DataFrame):
            data_to_use = viz_data_list.to_dict('records')
        else:
            data_to_use = viz_data_list

        for item in data_to_use:
            curr = item['Měna']; val = item['Hodnota']
            if curr in assets_by_curr: assets_by_curr[curr] += val
            else: assets_by_curr["USD"] += item['HodnotaUSD'] # Zajištění, že se používá HodnotaUSD

    kurz_usd_now = kurzy.get("CZK", 20.85)
    kurz_eur_now = kurzy.get("EUR", 1.16) * kurz_usd_now
    
    col_s1, col_s2 = st.columns(2)
    with col_s1: 
        sim_usd = st.slider(f"Kurz USD/CZK (Aktuálně: {kurz_usd_now:.2f})", 15.0, 30.0, float(kurz_usd_now))
    with col_s2: 
        sim_eur = st.slider(f"Kurz EUR/CZK (Aktuálně: {kurz_eur_now:.2f})", 15.0, 35.0, float(kurz_eur_now))
        
    val_now_czk = (assets_by_curr["USD"] * kurz_usd_now) + (assets_by_curr["EUR"] * kurz_eur_now) + assets_by_curr["CZK"]
    val_sim_czk = (assets_by_curr["USD"] * sim_usd) + (assets_by_curr["EUR"] * sim_eur) + assets_by_curr["CZK"]
    diff = val_sim_czk - val_now_czk
    
    st.divider()
    c_m1, c_m2 = st.columns(2)
    c_m1.metric("Hodnota Portfolia (Simulace)", f"{val_sim_czk:,.0f} Kč", delta=f"{diff:,.0f} Kč")
    
    impact_data = pd.DataFrame({
        "Měna": ["USD Aktiva", "EUR Aktiva", "CZK Aktiva"],
        "Hodnota CZK (Teď)": [assets_by_curr["USD"] * kurz_usd_now, assets_by_curr["EUR"] * kurz_eur_now, assets_by_curr["CZK"]],
        "Hodnota CZK (Simulace)": [assets_by_curr["USD"] * sim_usd, assets_by_curr["EUR"] * kurz_eur_now, assets_by_curr["CZK"]]
    })
    
    fig_curr = go.Figure(data=[
        go.Bar(name='Teď', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Teď)"], marker_color='#555555'),
        go.Bar(name='Simulace', x=impact_data["Měna"], y=impact_data["Hodnota CZK (Simulace)"], marker_color='#00CC96')
    ])
    fig_curr.update_layout(barmode='group', template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0), font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig_curr.update_xaxes(showgrid=False)
    fig_curr.update_yaxes(showgrid=True, gridcolor='#30363D')
    fig_curr = make_plotly_cyberpunk(fig_curr)
    st.plotly_chart(fig_curr, use_container_width=True)


def render_analýza_kalendář_page(df, df_watch, LIVE_DATA):
    """Vykreslí Kalendář výsledků (Tab9 Analýzy)."""
    st.subheader("📅 KALENDÁŘ VÝSLEDKŮ (Earnings)")
    st.info("Termíny zveřejňování hospodářských výsledků tvých firem. Očekávej volatilitu!")

    all_my_tickers = []
    if not df.empty:
        all_my_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty:
        all_my_tickers.extend(df_watch['Ticker'].unique().tolist())
    all_my_tickers = list(set(all_my_tickers))

    if all_my_tickers:
        earnings_data = []
        with st.spinner(f"Skenuji kalendáře pro {len(all_my_tickers)} firem..."):
            prog_bar = st.progress(0)
            for i, tk in enumerate(all_my_tickers):
                try:
                    e_date = ziskej_earnings_datum(tk)
                    if e_date:
                        if hasattr(e_date, 'date'):
                            e_date_norm = datetime.combine(e_date, datetime.min.time())
                        else:
                            e_date_norm = pd.to_datetime(e_date).to_pydatetime()

                        days_left = (e_date_norm - datetime.now()).days

                        status = "V budoucnu"
                        color_icon = "⚪️"

                        if 0 <= days_left <= 7:
                            status = f"🔥 POZOR! Za {days_left} dní"
                            color_icon = "🔴"
                            st.toast(f"⚠️ {tk} má výsledky za {days_left} dní!", icon="📢")
                        elif 7 < days_left <= 30:
                            status = f"Blíží se (za {days_left} dní)"
                            color_icon = "🟡"
                        elif days_left < 0:
                            status = "Již proběhlo"
                            color_icon = "✔️"
                        else:
                            status = f"Za {days_left} dní"
                            color_icon = "🟢"

                        if days_left > -7:
                            earnings_data.append({
                                "Symbol": tk,
                                "Datum": e_date_norm.strftime("%d.%m.%Y"),
                                "Dní do akce": days_left,
                                "Status": status,
                                "Ikona": color_icon
                            })
                except Exception:
                    pass
                try:
                    prog_bar.progress((i + 1) / len(all_my_tickers))
                except Exception:
                    pass
            prog_bar.empty()

        if earnings_data:
            df_cal = pd.DataFrame(earnings_data).sort_values('Dní do akce')
            try:
                st.dataframe(
                    df_cal,
                    column_config={
                        "Ikona": st.column_config.TextColumn("Riziko", width="small"),
                        "Dní do akce": st.column_config.NumberColumn("Odpočet (dny)", format="%d")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            except Exception:
                st.dataframe(df_cal, use_container_width=True)

            try:
                df_future = df_cal[df_cal['Dní do akce'] >= 0].copy()
                if not df_future.empty:
                    df_future['Datum_ISO'] = pd.to_datetime(df_future['Datum'], format="%d.%m.%Y")
                    fig_timeline = px.scatter(
                        df_future,
                        x="Datum_ISO",
                        y="Symbol",
                        color="Dní do akce",
                        color_continuous_scale="RdYlGn_r",
                        size=[20] * len(df_future),
                        title="Časová osa výsledkové sezóny",
                        template="plotly_dark"
                    )
                    fig_timeline.update_layout(
                        height=300,
                        xaxis_title="Datum",
                        yaxis_title="",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_family="Roboto Mono"
                    )
                    try:
                        fig_timeline = make_plotly_cyberpunk(fig_timeline)
                    except Exception:
                        pass
                    st.plotly_chart(fig_timeline, use_container_width=True)
            except Exception as e:
                st.error(f"Chyba timeline: {e}")
        else:
            st.info("Žádná data o výsledcích nebyla nalezena (nebo jsou příliš daleko).")
    else:
        st.warning("Nemáš žádné akcie v portfoliu ani ve sledování.")


def render_analýza_rentgen_page(df, df_watch, vdf, model, AI_AVAILABLE):
    """Vykreslí kartu Rentgen (Tab 1 Analýzy) - FINAL VERZE"""
    st.write("")
    
    # Výběr akcie
    vybrana_akcie = st.selectbox("Vyber firmu:", df['Ticker'].unique() if not df.empty else [])
    
    if vybrana_akcie:
        with st.spinner(f"Načítám rentgen pro {vybrana_akcie}..."):
            t_info, hist_data = ziskej_detail_akcie(vybrana_akcie)
            
            if t_info or (hist_data is not None and not hist_data.empty):
                try:
                    long_name = t_info.get('longName', vybrana_akcie) if t_info else vybrana_akcie
                    summary = t_info.get('longBusinessSummary', '') if t_info else ''
                    recommendation = t_info.get('recommendationKey', 'N/A').upper().replace('_', ' ') if t_info else 'N/A'
                    target_price = t_info.get('targetMeanPrice', 0) if t_info else 0
                    pe_ratio = t_info.get('trailingPE', 0) if t_info else 0
                    currency = t_info.get('currency', '?') if t_info else '?'
                    current_price = t_info.get('currentPrice', 0) if t_info else 0
                    profit_margin = t_info.get('profitMargins', 0)
                    roe = t_info.get('returnOnEquity', 0)
                    rev_growth = t_info.get('revenueGrowth', 0)
                    debt_equity = t_info.get('debtToEquity', 0)
                    insiders = t_info.get('heldPercentInsiders', 0)
                    institutions = t_info.get('heldPercentInstitutions', 0)
                    public = max(0, 1.0 - insiders - institutions)

                    if (not summary or summary == "MISSING_SUMMARY" or "Yahoo" in summary) and AI_AVAILABLE:
                        try:
                            summary = "Popis není k dispozici." 
                        except: summary = "Popis není k dispozici."
                    elif not summary or "Yahoo" in summary: summary = "Popis není k dispozici."

                    # --- 1. SEKCE ---
                    c_d1, c_d2 = st.columns([1, 2])
                    
                    with c_d1:
                        with st.container(border=True):
                            if recommendation != "N/A":
                                barva_rec = "green" if "BUY" in recommendation else ("red" if "SELL" in recommendation else "orange")
                                st.markdown(f"### :{barva_rec}[{recommendation}]")
                                st.caption("Názor analytiků")
                            else:
                                st.markdown("### 🤷‍♂️ Neznámé"); st.caption("Bez doporučení")
                            
                            st.divider()
                            if target_price > 0: st.metric("Cílová cena", f"{target_price:,.2f}", help=f"Průměrný cíl analytiků ({currency})")
                            else: st.metric("Cílová cena", "---")

                            if pe_ratio > 0: st.metric("P/E Ratio", f"{pe_ratio:.2f}")
                            else: st.metric("P/E Ratio", "---")

                    with c_d2:
                        # ČISTÝ NADPIS (BEZ UPDATE)
                        st.subheader(f"{long_name}")
                        st.caption(f"Cena: {current_price:,.2f} {currency}")
                        
                        if len(summary) > 200:
                            with st.expander("📝 Popis společnosti (Rozbalit)", expanded=False):
                                st.info(summary)
                                if t_info and t_info.get('website'): st.link_button("🌍 Web firmy", t_info.get('website'))
                        else:
                            st.info(summary)
                            if t_info and t_info.get('website'): st.link_button("🌍 Web firmy", t_info.get('website'))

                    st.divider()
                    st.subheader("🧬 FUNDAMENTÁLNÍ RENTGEN (Zdraví firmy)")
                    fc1, fc2, fc3, fc4 = st.columns(4)
                    fc1.metric("Zisková marže", f"{profit_margin*100:.1f} %")
                    fc2.metric("ROE (Efektivita)", f"{roe*100:.1f} %")
                    fc3.metric("Růst tržeb", f"{rev_growth*100:.1f} %")
                    fc4.metric("Dluh / Jmění", f"{debt_equity:.2f}")

                    st.write("")
                    st.subheader("🐳 VELRYBÍ RADAR (Vlastnická struktura)")

                    own_col1, own_col2 = st.columns([1, 2])
                    with own_col1:
                        with st.container(border=True):
                            st.metric("🏦 Instituce", f"{institutions*100:.1f} %")
                            st.divider()
                            st.metric("👔 Insideři", f"{insiders*100:.1f} %")

                    with own_col2:
                        own_df = pd.DataFrame({
                            "Kdo": ["Instituce 🏦", "Insideři 👔", "Veřejnost 👥"],
                            "Podíl": [institutions, insiders, public]
                        })
                        
                        fig_own = px.pie(own_df, values='Podíl', names='Kdo', hole=0.6,
                                         color='Kdo',
                                         color_discrete_map={"Instituce 🏦": "#58A6FF", "Insideři 👔": "#238636", "Veřejnost 👥": "#8B949E"},
                                         template="plotly_dark")
                        
                        fig_own.update_layout(
                            height=300, 
                            margin=dict(l=0, r=0, t=10, b=10), 
                            paper_bgcolor="rgba(0,0,0,0)", 
                            showlegend=True, 
                            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
                            font=dict(size=14)
                        )
                        fig_own.update_traces(textinfo='percent', textposition='outside')
                        st.plotly_chart(fig_own, use_container_width=True)

                    st.divider()
                    st.subheader(f"📈 PROFESIONÁLNÍ CHART")
                    if hist_data is not None and not hist_data.empty:
                        fig_candle = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'])])
                        fig_candle.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_candle, use_container_width=True)

                    if AI_AVAILABLE and st.button(f"🤖 SPUSTIT AI ANALÝZU", type="primary"):
                         st.info("AI funkce připravena.")

                except Exception as e: st.error(f"Chyba zobrazení rentgenu: {e}")
            else: st.error("Nepodařilo se načíst data o firmě.")




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
                        df_u = nacti_uzivatele(); row = df_u[df_u['username'] == u]
                        if not row.empty and row.iloc[0]['password'] == zasifruj(old):
                            if new == conf and len(new) > 0:
                                df_u.at[row.index[0], 'password'] = zasifruj(new); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}"); st.success("Hotovo!")
                            else: st.error("Chyba v novém hesle.")
                        else: st.error("Staré heslo nesedí.")
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
                time.sleep(0.3) # Rychlost bootování

            st.success("SYSTEM ONLINE")
            time.sleep(0.5)

        boot_placeholder.empty()
        st.session_state['boot_completed'] = True

    # --- DEFINICE CLI CALLBACKU (OPRAVA VYKONÁVÁNÍ PŘÍKAZŮ) ---
    if 'cli_msg' not in st.session_state: st.session_state['cli_msg'] = None

    def process_cli_command():
        cmd_raw = st.session_state.cli_cmd
        if not cmd_raw: return

        # 1. Okamžitě vymažeme vstup v session state (takže po reloadu bude prázdný)
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
                # Krok 1: Kontrola AI a Data Core (vždy provést před extenzivní logikou)
                if not AI_AVAILABLE or not st.session_state.get('ai_enabled', False):
                    msg_text = "❌ AI je neaktivní (Zkontroluj Nastavení nebo API klíč)."
                    msg_icon = "⚠️"
                    st.session_state['cli_msg'] = (msg_text, msg_icon)
                    return # Konec
                
                if 'data_core' not in st.session_state:
                    msg_text = "❌ Datové jádro není inicializováno. Zkus obnovit stránku."
                    msg_icon = "⚠️"
                    st.session_state['cli_msg'] = (msg_text, msg_icon)
                    return # Konec
                    
                core = st.session_state['data_core']
                LIVE_DATA = st.session_state.get('LIVE_DATA', {}) # Bezpečný přístup k Live datům

                if len(cmd_parts) > 1:
                    # --- CÍLENÝ AUDIT AKCIE ---
                    target_ticker = cmd_parts[1].upper()
                    
                    # 1. Najdi fundamentální data z cache Data Core
                    fund_info = core['fundament_data'].get(target_ticker, {})
                    
                    # NOVINKA: Pokud fundamenty chybí, zkusíme je stáhnout a přidat do cache
                    if not fund_info:
                        try:
                            # POZNÁMKA: V reálném kódu by se zde mělo zvážit, zda nechat uživatele čekat na externí API volání
                            t_info, _ = cached_detail_akcie(target_ticker) 
                            if t_info:
                                fund_info = t_info
                                core['fundament_data'][target_ticker] = t_info # Aktualizujeme cache
                                # Také zkusíme aktualizovat LIVE data, pokud je potřeba
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
                    
                    # Získání dat
                    current_price = LIVE_DATA.get(target_ticker, {}).get('price', 'N/A')
                    pe_ratio = fund_info.get('trailingPE', 'N/A')
                    
                    # Získání Divi Yield pro AI: Hledáme v Data Core (vdf) nebo v fundamentálních datech
                    divi_yield_raw = fund_info.get('dividendYield', 'N/A')
                    
                    # Zkusíme i z portfolia, pokud je akcie držená a má Divi
                    vdf = core['vdf']
                    if not vdf.empty and target_ticker in vdf['Ticker'].values:
                        portfolio_row = vdf[vdf['Ticker'] == target_ticker].iloc[0]
                        if pd.notna(portfolio_row.get('Divi')):
                            divi_yield_raw = portfolio_row['Divi']
                    
                    # Formátujeme yield pro AI prompt (z 0.005 na 0.5%)
                    if isinstance(divi_yield_raw, (float, int)) and pd.notna(divi_yield_raw):
                        # Pro AI pošleme hodnotu, aby ji mohla použít v logice
                        divi_yield_for_ai = divi_yield_raw
                        # Pro zobrazení pošleme formátované %
                        divi_yield_display = f"{divi_yield_raw * 100:.2f}%" 
                    else:
                        divi_yield_for_ai = 'N/A'
                        divi_yield_display = 'N/A'

                    # Sestavení textu pro AI model
                    ai_prompt = (
                        f"Jsi finanční analytik. Analyzuj akcii {target_ticker} na základě jejích fundamentálních dat:\n"
                        f"Aktuální P/E: {pe_ratio}. Dividendový výnos (jako desetinne cislo, napr. 0.03): {divi_yield_for_ai}.\n"
                        "Poskytni stručné shrnutí (max 3 věty) o tom, zda je akcie drahá, levná, nebo neutrální, a jaké je její hlavní riziko/příležitost. Pamatuj, ze vykazany dividendovy vynos je již v procentech."
                    )
                    
                    # Volání AI pro kontextuální analýzu akcie
                    try:
                        with st.spinner(f"AI provádí analýzu pro {target_ticker}..."):
                            ai_response = model.generate_content(ai_prompt).text
                    except Exception as e:
                        # Chyba AI volání (včetně 429 quota, síťové chyby, timeout)
                        if "429" in str(e):
                            msg_text = f"❌ Chyba kvóty (429): Překročena frekvence volání AI. Zkus to prosím za pár minut."
                        else:
                            msg_text = f"❌ Chyba AI ({target_ticker}): Analýza se nezdařila ({e})."
                        msg_icon = "⚠️"
                        st.session_state['cli_msg'] = (msg_text, msg_icon)
                        return # Konec

                    # Zobrazení výsledku (OPRAVENO FORMÁTOVÁNÍ PRO ČITELNOST)
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
                    # --- GLOBÁLNÍ AUDIT PORTFOLIA (Původní logika) ---
                    pct_24h = core['pct_24h']
                    cash_usd = core['cash_usd']
                    vdf = core['vdf']
                    
                    best_ticker = "N/A"
                    worst_ticker = "N/A"
                    if not vdf.empty and 'Dnes' in vdf.columns:
                        vdf_sorted = vdf.sort_values('Dnes', ascending=False)
                        best_ticker = vdf_sorted.iloc[0]['Ticker']
                        worst_ticker = vdf_sorted.iloc[-1]['Ticker']
                    
                    # Volání AI strážce
                    try:
                        guard_res_text = ask_ai_guard(model, pct_24h, cash_usd, best_ticker, worst_ticker)
                    except Exception as e:
                        if "429" in str(e):
                             msg_text = f"❌ Chyba kvóty (429): Překročena frekvence volání AI. Zkus to prosím za pár minut."
                        else:
                            msg_text = f"❌ Chyba AI: Globální audit se nezdařil ({e})."
                        msg_icon = "⚠️"
                        st.session_state['cli_msg'] = (msg_text, msg_icon)
                        return # Konec

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
                    # OPRAVA: Původně bylo 'm', nahrazeno za správné 'm_cli'
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

        # Uložíme zprávu do session state, aby se zobrazila po reloadu
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
            # Hist. vyvoje se necha na 0, aby se spravne inicializoval v calculate_all_data
            st.session_state['hist_vyvoje'] = aktualizuj_graf_vyvoje(USER, 0)
    
    df = st.session_state['df']
    df_cash = st.session_state['df_cash']
    df_div = st.session_state['df_div']
    df_watch = st.session_state['df_watch']
    zustatky = get_zustatky(USER)
    kurzy = cached_kurzy() # Inicializace, hodnoty se upřesní v jádru

    # --- 6. VÝPOČTY (CENTRALIZOVANÝ DAT CORE) ---
    # Zkontrolujeme cache (např. platnost 5 minut)
    cache_timeout = timedelta(minutes=5)
    
    if ('data_core' not in st.session_state or 
        (datetime.now() - st.session_state['data_core']['timestamp']) > cache_timeout):
        
        with st.spinner("🔄 Aktualizuji datové jádro (LIVE data)..."):
            data_core = calculate_all_data(USER, df, df_watch, zustatky, kurzy)
    else:
        # Použijeme data z cache
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
    LIVE_DATA = st.session_state['LIVE_DATA'] # Vždy musíme vytáhnout z SS, protože ho cachuje calculate_all_data
    
    # OPRAVA: Přepisujeme lokální kurzy z data_core pro použití ve všech podřízených funkcích.
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
                        alerts.append(f"{tk}: KUPNÍ ALERT! Cena {price:.2f} <= {buy_trg:.2f}")
                        st.toast(f"🔔 {tk} je ve slevě! ({price:.2f})", icon="🔥")

                    if sell_trg > 0 and price >= sell_trg:
                        alerts.append(f"{tk}: PRODEJNÍ ALERT! Cena {price:.2f} >= {sell_trg:.2f}")
                        st.toast(f"🔔 {tk} dosáhl cíle! ({price:.2f})", icon="💰")

    # --- 9. SIDEBAR ---
    # --- 9. SIDEBAR (Vylepšené rozložení pro mobil) ---
    with st.sidebar:
        # Lottie Animace
        lottie_url = "https://lottie.host/02092823-3932-4467-9d7e-976934440263/3q5XJg2Z2W.json"
        lottie_json = load_lottieurl(lottie_url)
        if lottie_json:
            st_lottie(lottie_json, height=120, key="sidebar_anim") # Trochu menší výška

        # Výběr tématu
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
        
        # --- 1. NAVIGACE (POSUNUTO NAHORU PRO LEPŠÍ OVLÁDÁNÍ) ---
        # Na mobilu je lepší mít tlačítka hned po ruce
        page = st.radio("Jít na:", ["🏠 Přehled", "👀 Sledování", "📈 Analýza", "📰 Zprávy", "💸 Obchod", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení", "🧪 Banka"], label_visibility="collapsed")
        
        st.divider()

        # --- 2. HERNÍ LEVEL ---
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

        # --- 3. INFORMACE (ZABALENO DO EXPANDERŮ PRO ÚSPORU MÍSTA) ---
        
        # A. Světové trhy
        with st.expander("🌍 SVĚTOVÉ TRHY", expanded=False):
            ny_time, ny_open = zjisti_stav_trhu("America/New_York", 9, 16)
            ln_time, ln_open = zjisti_stav_trhu("Europe/London", 8, 16)
            jp_time, jp_open = zjisti_stav_trhu("Asia/Tokyo", 9, 15)

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇺🇸 New York"); c_m2.markdown(f"**{ny_time}** {'🟢' if ny_open else '🔴'}")

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇬🇧 Londýn"); c_m2.markdown(f"**{ln_time}** {'🟢' if ln_open else '🔴'}")

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇯🇵 Tokio"); c_m2.markdown(f"**{jp_time}** {'🟢' if jp_open else '🔴'}")

        # B. Peněženka (Tohle zabíralo moc místa, teď je to schované)
        with st.expander("💰 STAV PENĚŽENKY", expanded=False):
            for mena in ["USD", "CZK", "EUR"]:
                castka = zustatky.get(mena, 0.0)
                sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
                # Použijeme menší formát než st.info pro úsporu místa
                st.markdown(f"""
                <div style="background-color: #0D1117; padding: 10px; border-radius: 5px; margin-bottom: 5px; border: 1px solid #30363D;">
                    <span style="color: #8B949E;">{mena}:</span> <span style="color: #00FF99; font-weight: bold; float: right;">{castka:,.2f} {sym}</span>
                </div>
                """, unsafe_allow_html=True)

        # --- SIDEBAR ALERTS ---
        if alerts:
            st.error("🔔 CENOVÉ ALERTY!", icon="🔥")
            for a in alerts:
                st.markdown(f"- **{a}**")

        # --- NOVINKA: VELITELSKÁ ŘÁDKA (CLI) ---
        st.divider()
        with st.expander("💻 TERMINÁL", expanded=False):
            # Zobrazení zprávy z callbacku
            if st.session_state.get('cli_msg'):
                txt, ic = st.session_state['cli_msg']
                if ic in ["🔬", "👮"]:
                    st.toast(f"{ic} Nové hlášení od AI strážce!", icon=ic)
                    st.markdown(f"<div style='font-size: 10px;'>{txt}</div>", unsafe_allow_html=True)
                else:
                    st.info(f"{ic} {txt}")
                st.session_state['cli_msg'] = None 

            st.text_input(">", key="cli_cmd", placeholder="/help", on_change=process_cli_command)

        # --- AKCE (Tlačítka dole) ---
        st.divider()
        
        # PDF a Email dáme vedle sebe, ať to nezabírá 2 řádky
        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("📧 REPORT", use_container_width=True):
                msg = f"<h2>Report {USER}</h2><p>Jmění: {celk_hod_czk:,.0f} Kč</p>"
                if odeslat_email(st.secrets["email"]["sender"], "Report", msg) == True: st.toast("Odesláno!", icon="✅")
                else: st.toast("Chyba odeslání", icon="❌")
        
        with c_act2:
            pdf_data = vytvor_pdf_report(USER, celk_hod_czk, cash_usd, (celk_hod_czk - celk_inv_czk), viz_data_list)
            st.download_button(label="📄 PDF", data=pdf_data, file_name=f"report.pdf", mime="application/pdf", use_container_width=True)

        with st.expander("🔐 Účet"):
            with st.form("pass_change"):
                old = st.text_input("Staré", type="password"); new = st.text_input("Nové", type="password"); conf = st.text_input("Potvrdit", type="password")
                if st.form_submit_button("Změnit heslo"):
                    df_u = nacti_uzivatele(); row = df_u[df_u['username'] == USER]
                    if not row.empty and row.iloc[0]['password'] == zasifruj(old):
                        if new == conf and len(new) > 0:
                            df_u.at[row.index[0], 'password'] = zasifruj(new); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Pass change {USER}"); st.success("Hotovo!")
                        else: st.error("Chyba")
                    else: st.error("Staré heslo nesedí.")

            if st.button("🚪 ODHLÁSIT", type="primary", use_container_width=True):
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
            # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
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
                        # Normalizace (Start na 0%)
                        normalized_data = raw_data.apply(lambda x: (x / x.iloc[0] - 1) * 100)

                        fig_multi_comp = px.line(
                            normalized_data,
                            title='Normalizovaná výkonnost (Změna v %) od počátku',
                            template="plotly_dark"
                        )
                        
                        # --- VYLEPŠENÍ PRO MOBIL (LEGENDA DOLE) ---
                        fig_multi_comp.update_layout(
                            xaxis_title="Datum",
                            yaxis_title="Změna (%)",
                            height=500,
                            margin=dict(t=50, b=0, l=0, r=0),
                            font_family="Roboto Mono",
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            legend=dict(
                                orientation="h",  # Horizontální legenda
                                yanchor="bottom", 
                                y=-0.2,           # Posunutá pod graf
                                xanchor="center", 
                                x=0.5
                            )
                        )
                        fig_multi_comp.update_xaxes(showgrid=False)
                        fig_multi_comp.update_yaxes(showgrid=True, gridcolor='#30363D')
                        st.plotly_chart(fig_multi_comp, use_container_width=True, key="fig_srovnani")
                        add_download_button(fig_multi_comp, "srovnani_akcii")

                        st.divider()
                        st.subheader("Detailní srovnání metrik")

                        # Tabulka metrik (zůstává stejná, je super)
                        comp_list = []
                        # Omezíme to na max 4 pro přehlednost v tabulce, nebo necháme vše
                        for t in tickers_to_compare[:4]: 
                            i, h = cached_detail_akcie(t)
                            if i:
                                mc = i.get('marketCap', 0)
                                pe = i.get('trailingPE', 0)
                                dy = i.get('dividendYield', 0)
                                # Bezpečný výpočet změny
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
                            # Transpozice pro hezčí tabulku: Sloupce = Tickery, Řádky = Metriky
                            final_data = {"Metrika": comp_list[0]["Metrika"]}
                            for item in comp_list:
                                final_data[item["Ticker"]] = item["Hodnota"]
                            
                            st.dataframe(pd.DataFrame(final_data), use_container_width=True, hide_index=True)

                except Exception as e:
                    st.error(f"Chyba při stahování dat: {e}")
            else:
                st.info("Vyberte alespoň jeden ticker.")



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

                    try:
                        fig_map = make_plotly_cyberpunk(fig_map)
                    except Exception:
                        pass

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

                        try:
                            # OPRAVA 2: Zde byla chyba - volalo se to na fig_map (zeměkouli) místo na treemap_fig
                            treemap_fig = make_plotly_cyberpunk(treemap_fig) 
                        except Exception:
                            pass

                        st.plotly_chart(treemap_fig, use_container_width=True, key="fig_sektor_map")
                        add_download_button(treemap_fig, "mapa_sektoru")

                        if 'Datum' in df.columns and 'Cena' in df.columns and not df.empty:
                            try:
                                # Toto je zbytečný řádek, pokud už máš treemap výše, ale ponecháno pro zachování původního kódu
                                line_fig = px.line(df.sort_values('Datum'), x='Datum', y='Cena', title='Vývoj ceny', markers=True)
                                line_fig.update_layout(
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    font_family="Roboto Mono",
                                    margin=dict(t=30, l=10, r=10, b=10)
                                )
                                try:
                                    line_fig = make_plotly_cyberpunk(line_fig)
                                except Exception:
                                    pass

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
            st.caption("Pokročilé simulace budoucnosti a zátěžové testy.")

            # --- 1. AI PREDIKCE ---
            with st.expander("🤖 AI PREDIKCE (Neuro-Věštec)", expanded=False):
                st.info("Experimentální modul využívající model Prophet (Meta) k predikci trendu.")

                c_ai1, c_ai2 = st.columns(2)
                with c_ai1:
                    pred_ticker = st.text_input("Ticker pro predikci:", value="BTC-USD").upper()
                with c_ai2:
                    pred_days = st.slider("Predikce na (dny):", 7, 90, 30)

                if st.button("🧠 AKTIVOVAT NEURONOVOU SÍŤ", type="primary"):
                    try:
                        from prophet import Prophet
                        with st.spinner(f"Trénuji model na datech {pred_ticker}..."):
                            hist_train = yf.download(pred_ticker, period="2y", progress=False)

                            if not hist_train.empty:
                                if isinstance(hist_train.columns, pd.MultiIndex):
                                    y_data = hist_train['Close'].iloc[:, 0]
                                else:
                                    y_data = hist_train['Close']

                                df_prophet = pd.DataFrame({'ds': y_data.index.tz_localize(None), 'y': y_data.values})
                                m = Prophet(daily_seasonality=True)
                                m.fit(df_prophet)
                                future = m.make_future_dataframe(periods=pred_days)
                                forecast = m.predict(future)

                                st.divider()
                                last_price = df_prophet['y'].iloc[-1]
                                future_price = forecast['yhat'].iloc[-1]
                                pct_pred = ((future_price - last_price) / last_price) * 100

                                c_res1, c_res2 = st.columns(2)
                                c_res1.metric("Cena dnes", f"{last_price:,.2f}")
                                c_res2.metric(f"Predikce (+{pred_days} dní)", f"{future_price:,.2f}", f"{pct_pred:+.2f} %")

                                fig_pred = go.Figure()
                                fig_pred.add_trace(go.Scatter(x=df_prophet['ds'], y=df_prophet['y'], name='Historie', line=dict(color='gray')))
                                future_part = forecast[forecast['ds'] > df_prophet['ds'].iloc[-1]]
                                fig_pred.add_trace(go.Scatter(x=future_part['ds'], y=future_part['yhat'], name='Predikce', line=dict(color='#58A6FF', width=3)))
                                fig_pred.add_trace(go.Scatter(
                                    x=pd.concat([future_part['ds'], future_part['ds'][::-1]]),
                                    y=pd.concat([future_part['yhat_upper'], future_part['yhat_lower'][::-1]]),
                                    fill='toself', fillcolor='rgba(88, 166, 255, 0.2)',
                                    line=dict(color='rgba(255,255,255,0)'), name='Rozptyl'
                                ))
                                fig_pred.update_layout(template="plotly_dark", height=400, paper_bgcolor="rgba(0,0,0,0)")
                                st.plotly_chart(fig_pred, use_container_width=True)
                            else: st.error("Nedostatek dat.")
                    except Exception as e: st.error(f"Chyba Prophet: {e}")

            # --- 2. DCA BACKTESTER ---
            with st.expander("⏳ DCA BACKTESTER (Stroj času)", expanded=False):
                st.info("Kolik bys měl, kdyby jsi pravidelně investoval v minulosti?")
                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    dca_ticker = st.text_input("Ticker:", value="BTC-USD", key="dca_t").upper()
                    dca_years = st.slider("Délka (roky)", 1, 10, 5, key="dca_y")
                with c_d2:
                    dca_amount = st.number_input("Měsíční vklad (Kč)", value=2000, step=500, key="dca_a")
                
                if st.button("🚀 SPUSTIT SIMULACI", key="btn_dca"):
                    with st.spinner("Počítám..."):
                        try:
                            start = datetime.now() - timedelta(days=dca_years*365)
                            hist = yf.download(dca_ticker, start=start, interval="1mo", progress=False)['Close']
                            if isinstance(hist, pd.DataFrame): hist = hist.iloc[:, 0]
                            hist = hist.dropna()
                            
                            rate = 1.0 if ".PR" in dca_ticker else kurzy.get("CZK", 21)
                            inv_total = 0; shares = 0; evol = []
                            
                            for d, p in hist.items():
                                p_czk = p * rate
                                shares += dca_amount / p_czk
                                inv_total += dca_amount
                                evol.append({"Datum": d, "Hodnota": shares * p_czk, "Vklad": inv_total})
                                
                            df_dca = pd.DataFrame(evol).set_index("Datum")
                            fin_val = df_dca["Hodnota"].iloc[-1]
                            profit = fin_val - inv_total
                            
                            c1, c2 = st.columns(2)
                            c1.metric("Vloženo", f"{inv_total:,.0f} Kč")
                            c2.metric("Hodnota DNES", f"{fin_val:,.0f} Kč", f"{profit:+,.0f} Kč")
                            
                            fig_dca = px.area(df_dca, x=df_dca.index, y=["Hodnota", "Vklad"], 
                                              color_discrete_map={"Hodnota": "#00CC96", "Vklad": "#AB63FA"}, template="plotly_dark")
                            fig_dca.update_layout(height=400, paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.2))
                            st.plotly_chart(fig_dca, use_container_width=True)
                        except Exception as e: st.error(f"Chyba: {e}")

            # --- 3. EFEKTIVNÍ HRANICE ---
            with st.expander("📊 EFEKTIVNÍ HRANICE (Optimalizace)", expanded=False):
                tickers_ef = df['Ticker'].unique().tolist()
                if len(tickers_ef) < 2:
                    st.warning("Potřebuješ alespoň 2 akcie v portfoliu.")
                else:
                    st.write(f"Optimalizace pro: {', '.join(tickers_ef)}")
                    if st.button("📈 Vypočítat optimální portfolio"):
                        with st.spinner("Simuluji 5000 portfolií..."):
                            try:
                                data = yf.download(tickers_ef, period="2y", progress=False)['Close']
                                returns = np.log(data / data.shift(1)).dropna()
                                results = np.zeros((3, 5000))
                                for i in range(5000):
                                    w = np.random.random(len(tickers_ef)); w /= np.sum(w)
                                    ret = np.sum(returns.mean() * w) * 252
                                    vol = np.sqrt(np.dot(w.T, np.dot(returns.cov() * 252, w)))
                                    results[0,i] = vol; results[1,i] = ret; results[2,i] = (ret - 0.04) / vol
                                
                                max_sharpe_idx = results[2].argmax()
                                sd_p, ret_p = results[0, max_sharpe_idx], results[1, max_sharpe_idx]
                                
                                c1, c2 = st.columns(2)
                                c1.metric("Max Sharpe Výnos", f"{ret_p*100:.1f}%")
                                c2.metric("Riziko (Volatilita)", f"{sd_p*100:.1f}%")
                                
                                fig_ef = go.Figure(go.Scatter(x=results[0], y=results[1], mode='markers', marker=dict(color=results[2], showscale=True)))
                                fig_ef.add_trace(go.Scatter(x=[sd_p], y=[ret_p], marker=dict(color='red', size=15), name='TOP'))
                                fig_ef.update_layout(template="plotly_dark", height=400, xaxis_title="Riziko", yaxis_title="Výnos", paper_bgcolor="rgba(0,0,0,0)")
                                st.plotly_chart(fig_ef, use_container_width=True)
                            except: st.error("Chyba výpočtu.")

            # --- 4. SLOŽENÉ ÚROČENÍ ---
            with st.expander("💰 SLOŽENÉ ÚROČENÍ (Kalkulačka)", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    vklad_mes = st.number_input("Měsíčně (Kč)", 500, 100000, 5000, step=500)
                    urok_pa = st.slider("Úrok p.a. (%)", 1, 15, 8)
                with c2:
                    roky_spo = st.slider("Délka (let)", 5, 40, 20)
                
                data_urok = []
                total = celk_hod_czk; vlozeno = celk_hod_czk
                for r in range(1, roky_spo + 1):
                    vlozeno += vklad_mes * 12
                    total = (total + vklad_mes * 12) * (1 + urok_pa/100)
                    data_urok.append({"Rok": datetime.now().year + r, "Hodnota": total, "Vklady": vlozeno})
                
                df_urok = pd.DataFrame(data_urok)
                zisk_final = df_urok.iloc[-1]['Hodnota'] - df_urok.iloc[-1]['Vklady']
                
                st.metric(f"Za {roky_spo} let budeš mít", f"{df_urok.iloc[-1]['Hodnota']:,.0f} Kč", f"Zisk z úroků: {zisk_final:,.0f} Kč")
                
                fig_urok = px.area(df_urok, x="Rok", y=["Hodnota", "Vklady"], color_discrete_map={"Hodnota": "#00CC96", "Vklady": "#333333"}, template="plotly_dark")
                fig_urok.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
                st.plotly_chart(fig_urok, use_container_width=True)

            # --- 5. MONTE CARLO ---
            with st.expander("🎲 MONTE CARLO (Simulace)", expanded=False):
                c1, c2 = st.columns(2)
                mc_years = c1.slider("Roky", 1, 20, 5)
                mc_vol = c2.slider("Volatilita %", 10, 50, 20) / 100
                
                if st.button("🔮 SPUSTIT MONTE CARLO"):
                    sims = []
                    start = celk_hod_czk if celk_hod_czk > 0 else 100000
                    for _ in range(30): # 30 simulací stačí pro mobil
                        path = [start]
                        for _ in range(mc_years):
                            shock = np.random.normal(0.08, mc_vol) # 8% průměrný výnos
                            path.append(path[-1] * (1 + shock))
                        sims.append(path)
                    
                    fig_mc = go.Figure()
                    for s in sims: fig_mc.add_trace(go.Scatter(y=s, mode='lines', opacity=0.3, showlegend=False))
                    avg_end = np.mean([s[-1] for s in sims])
                    fig_mc.add_trace(go.Scatter(y=[np.mean([s[i] for s in sims]) for i in range(mc_years+1)], mode='lines', line=dict(color='yellow', width=4), name='Průměr'))
                    
                    st.metric("Očekávaný výsledek (Průměr)", f"{avg_end:,.0f} Kč")
                    fig_mc.update_layout(template="plotly_dark", height=400, paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_mc, use_container_width=True)

            # --- 6. CRASH TEST ---
            with st.expander("💥 CRASH TEST (Zátěžová zkouška)", expanded=False):
                st.info("Co se stane s portfoliem, když přijde krize?")
                
                scenarios = {
                    "COVID-19 (2020)": {"drop": 34, "desc": "Pandemie (-34%)"},
                    "Finanční krize (2008)": {"drop": 57, "desc": "Hypoteční krize (-57%)"},
                    "Dot-com bublina (2000)": {"drop": 49, "desc": "Tech bublina (-49%)"},
                    "Black Monday (1987)": {"drop": 22, "desc": "Bleskový pád (-22%)"}
                }
                
                # Výběr scénáře (Selectbox je lepší pro mobil než 4 tlačítka)
                selected_scen = st.selectbox("Vyber historický scénář:", list(scenarios.keys()))
                manual_drop = st.slider("Nebo nastav vlastní propad (%)", 0, 90, scenarios[selected_scen]['drop'])
                
                ztrata = celk_hod_czk * (manual_drop / 100)
                zbytek = celk_hod_czk - ztrata
                
                c1, c2 = st.columns(2)
                c1.metric("Ztráta", f"-{ztrata:,.0f} Kč", f"-{manual_drop}%")
                c2.metric("Zůstatek", f"{zbytek:,.0f} Kč")
                
                fig_crash = px.pie(values=[ztrata, zbytek], names=["Ztráta", "Zůstatek"], 
                                   color_discrete_sequence=["#da3633", "#238636"], hole=0.5, template="plotly_dark")
                fig_crash.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
                # Text doprostřed
                fig_crash.add_annotation(text=f"-{manual_drop}%", showarrow=False, font=dict(size=20, color="white"))
                st.plotly_chart(fig_crash, use_container_width=True)


        with tab5:
            st.subheader("🏆 SROVNÁNÍ S TRHEM (S&P 500)")
            st.caption("Porážíš trh, nebo trh poráží tebe?")
            
            if not hist_vyvoje.empty and len(hist_vyvoje) > 1:
                user_df = hist_vyvoje.copy()
                user_df['Date'] = pd.to_datetime(user_df['Date']); user_df = user_df.sort_values('Date').set_index('Date')
                start_val = user_df['TotalUSD'].iloc[0]
                if start_val > 0: user_df['MyReturn'] = ((user_df['TotalUSD'] / start_val) - 1) * 100
                else: user_df['MyReturn'] = 0
                start_date = user_df.index[0].strftime('%Y-%m-%d')

                my_returns = user_df['TotalUSD'].pct_change().dropna()
                my_sharpe = calculate_sharpe_ratio(my_returns)
                
                # --- FIX: Ošetření NaN hodnot ---
                if pd.isna(my_sharpe) or np.isinf(my_sharpe): my_sharpe = 0.0

                try:
                    sp500 = yf.download("^GSPC", start=start_date, progress=False)
                    if not sp500.empty:
                        if isinstance(sp500.columns, pd.MultiIndex): close_col = sp500['Close'].iloc[:, 0]
                        else: close_col = sp500['Close']
                        sp500_start = close_col.iloc[0]
                        sp500_norm = ((close_col / sp500_start) - 1) * 100
                        sp500_returns = close_col.pct_change().dropna()
                        sp500_sharpe = calculate_sharpe_ratio(sp500_returns)
                        
                        # --- FIX: Ošetření NaN u S&P ---
                        if pd.isna(sp500_sharpe) or np.isinf(sp500_sharpe): sp500_sharpe = 0.0

                        # --- GRAF (Bez nadpisu, legenda dole) ---
                        fig_bench = go.Figure()
                        fig_bench.add_trace(go.Scatter(x=user_df.index, y=user_df['MyReturn'], mode='lines', name='Moje Portfolio', line=dict(color='#00CC96', width=3)))
                        fig_bench.add_trace(go.Scatter(x=sp500_norm.index, y=sp500_norm, mode='lines', name='S&P 500', line=dict(color='#808080', width=2, dash='dot')))
                        fig_bench.update_layout(
                            xaxis_title="", yaxis_title="Změna (%)", template="plotly_dark", 
                            font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            height=400,
                            margin=dict(t=10, l=0, r=0, b=0), # Menší okraje nahoře
                            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center") # Legenda dole
                        )
                        fig_bench.update_xaxes(showgrid=False)
                        fig_bench.update_yaxes(showgrid=True, gridcolor='#30363D')
                        st.plotly_chart(fig_bench, use_container_width=True, key="fig_benchmark")

                        # --- METRIKY (GRID 2x2 a bez NaN) ---
                        my_last = user_df['MyReturn'].iloc[-1]; sp_last = sp500_norm.iloc[-1]; diff = my_last - sp_last
                        
                        col_vy1, col_vy2 = st.columns(2)
                        with col_vy1: st.metric("Můj výnos", f"{my_last:+.2f} %")
                        with col_vy2: st.metric("S&P 500 výnos", f"{sp_last:+.2f} %", delta=f"{diff:+.2f} %")

                        st.write("") 
                        
                        col_sh1, col_sh2 = st.columns(2)
                        # Tady už se NaN neobjeví, ošetřili jsme to nahoře
                        with col_sh1: st.metric("Můj Sharpe", f"{my_sharpe:+.2f}", help="Riziko/Výnos (Vyšší je lepší)")
                        with col_sh2: st.metric("S&P 500 Sharpe", f"{sp500_sharpe:+.2f}")

                        if diff > 0: st.success("🎉 Gratuluji! Porážíš trh.")
                        else: st.warning("📉 Trh zatím vede.")

                    else: st.warning("Nepodařilo se stáhnout data S&P 500.")
                except Exception as e: st.error(f"Chyba benchmarku: {e}")
            else: st.info("Pro srovnání potřebuješ historii alespoň za 2 dny.")


        with tab6:
            # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
            render_analýza_měny_page(vdf, viz_data_list, kurzy, celk_hod_usd)

        with tab7:
            # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
            render_analýza_rebalancing_page(df, vdf, kurzy)

        with tab8:
            # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
            render_analýza_korelace_page(df, kurzy)


        with tab9:
            # POUZE VOLÁNÍ FUNKCE (Refaktorovaný kód)
            render_analýza_kalendář_page(df, df_watch, LIVE_DATA)

    elif page == "📰 Zprávy":
        st.title("📰 BURZOVNÍ ZPRAVODAJSTVÍ")
        
        # --- 1. MRAK SLOV (Wordcloud) ---
        # Na mobilu je lepší, když je to přes celou šířku
        try:
            from wordcloud import WordCloud
            import matplotlib.pyplot as plt

            raw_news_cloud = cached_zpravy() 
            if raw_news_cloud:
                with st.expander("☁️ TÉMATA DNE (Co hýbe trhem)", expanded=True):
                    text_data = " ".join([n['title'] for n in raw_news_cloud]).upper()
                    stop_words = ["A", "I", "O", "U", "V", "S", "K", "Z", "SE", "SI", "NA", "DO", "JE", "TO", "ŽE", "ALE", "PRO", "JAK", "TAK", "OD", "PO", "NEBO", "BUDE", "BYL", "MÁ", "JSOU", "KTERÝ", "KTERÁ", "ONLINE", "AKTUÁNĚ", "CENA", "BURZA", "TRH", "AKCIE", "INVESTICE", "ČESKÉ", "NOVINY", "IDNES", "SEZNAM"]

                    wc = WordCloud(
                        width=800, height=300, # Trochu vyšší pro mobil
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
        except: pass

        st.divider()

        # --- 2. HLAVNÍ OVLÁDACÍ PANEL ---
        # Tlačítko pro AI analýzu všech zpráv (Sentiment 2.0)
        if AI_AVAILABLE:
            if st.button("🧠 SPUSTIT AI SENTIMENT TRHU (Všechny zprávy)", type="primary", use_container_width=True):
                with st.spinner("AI čte noviny a analyzuje náladu..."):
                    raw_news = cached_zpravy()
                    # Vezmeme jen top 10 zpráv, ať to netrvá věčnost
                    titles = [n['title'] for n in raw_news[:10]]
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
                        st.success("Analýza dokončena!")
                    except Exception as e: st.error(f"Chyba AI: {e}")

        # --- 3. NEWS FEED (KARTY POD SEBOU) ---
        # Žádné sloupce! Jeden dlouhý feed, jako na Instagramu/Twitteru.
        
        def analyze_news_with_ai(title, link):
            portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
            if viz_data_list: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data_list])
            prompt_to_send = f"Analyzuj tuto zprávu V KONTEXTU MÉHO PORTFOLIA. Zpráva: {title}. Jaký má dopad? (Odkaz: {link})"
            st.session_state["chat_messages"].append({"role": "user", "content": prompt_to_send})
            st.session_state['chat_expanded'] = True
            st.rerun()

        news = cached_zpravy()
        ai_results = st.session_state.get('ai_news_analysis', {})
        
        if news:
            st.write("")
            st.subheader(f"🔥 Nejnovější zprávy ({len(news)})")
            
            for i, n in enumerate(news):
                with st.container(border=True):
                    # AI Výsledek (pokud existuje)
                    if i in ai_results:
                        res = ai_results[i]; score = res['score']; reason = res['reason']
                        if score >= 60: color = "green"; emoji = "🟢 BÝČÍ"
                        elif score <= 40: color = "red"; emoji = "🔴 MEDVĚDÍ"
                        else: color = "orange"; emoji = "🟡 NEUTRÁL"
                        
                        c_score, c_text = st.columns([1, 4])
                        with c_score: 
                            st.markdown(f"**{emoji}**")
                            st.markdown(f"**{score}/100**")
                        with c_text:
                            st.info(f"🤖 {reason}")
                        st.divider()
                    
                    # Titulek a Datum
                    st.markdown(f"### {n['title']}")
                    st.caption(f"📅 {n['published']} | Zdroj: RSS")
                    
                    # Akce
                    c_btn1, c_btn2 = st.columns([1, 1])
                    with c_btn1:
                        st.link_button("Číst článek ↗️", n['link'], use_container_width=True)
                    with c_btn2:
                        if AI_AVAILABLE:
                            if st.button(f"🤖 Dopad na portfolio", key=f"analyze_ai_{i}", use_container_width=True):
                                analyze_news_with_ai(n['title'], n['link'])
        else:
            st.info("Žádné nové zprávy.")

    elif page == "💸 Obchod":
        st.title("💸 OBCHODNÍ PULT")
        
        # --- 1. HLAVNÍ OBCHODNÍ KARTA (VELÍN) ---
        with st.container(border=True):
            # Přepínač režimu
            mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, label_visibility="collapsed")
            
            st.divider()
            
            # Vstupy pro Ticker a Live Cenu
            c1, c2 = st.columns([1, 1])
            with c1:
                # Ticker selector logic
                if mode == "🔴 PRODEJ" and not df.empty:
                    ticker_input = st.selectbox("Ticker", df['Ticker'].unique())
                else:
                    ticker_input = st.text_input("Ticker", placeholder="např. AAPL, CEZ.PR").upper()
            
            # Live Data Fetch
            current_price, menu, denni_zmena = 0, "USD", 0
            if ticker_input:
                info = LIVE_DATA.get(ticker_input)
                if info:
                    current_price = info.get('price', 0)
                    menu = info.get('curr', 'USD')
                else:
                    p, m, z = ziskej_info(ticker_input)
                    if p: current_price, menu, denni_zmena = p, m, z

                if current_price > 0:
                    with c2:
                        color_price = "green" if denni_zmena >= 0 else "red"
                        st.markdown(f"**Cena:** :{color_price}[{current_price:,.2f} {menu}]")
                        st.caption(f"Změna: {denni_zmena*100:+.2f}%")
                else:
                    with c2: st.warning("Cena nedostupná")

            # Množství a Limitní Cena
            st.write("")
            col_qty, col_price = st.columns(2)
            with col_qty:
                qty = st.number_input("Počet kusů", min_value=0.0, step=1.0, format="%.2f")
            with col_price:
                limit_price = st.number_input("Cena za kus", min_value=0.0, value=float(current_price) if current_price else 0.0, step=0.1)

            # Kalkulace celkem
            total_est = qty * limit_price
            zustatek = zustatky.get(menu, 0)
            
            st.write("") 
            
            # --- LOGIKA TLAČÍTKA A VALIDACE ---
            if mode == "🟢 NÁKUP":
                if total_est > 0:
                    c_info1, c_info2 = st.columns(2)
                    c_info1.info(f"Celkem: **{total_est:,.2f} {menu}**")
                    
                    if zustatek >= total_est:
                        c_info2.success(f"Na účtu: {zustatek:,.2f} {menu}")
                        if st.button(f"KOUPIT {qty}x {ticker_input}", type="primary", use_container_width=True):
                            ok, msg = proved_nakup(ticker_input, qty, limit_price, USER)
                            if ok: st.balloons(); st.success(msg); time.sleep(2); st.rerun()
                            else: st.error(msg)
                    else:
                        c_info2.error(f"Chybí: {total_est - zustatek:,.2f} {menu}")
                        st.button("🚫 Nedostatek prostředků", disabled=True, use_container_width=True)
                else:
                    st.button("Zadej množství", disabled=True, use_container_width=True)

            else: # PRODEJ
                if total_est > 0:
                    curr_qty = df[df['Ticker'] == ticker_input]['Pocet'].sum() if not df.empty else 0
                    
                    c_info1, c_info2 = st.columns(2)
                    c_info1.info(f"Příjem: **{total_est:,.2f} {menu}**")
                    
                    if curr_qty >= qty:
                        c_info2.success(f"Máš: {curr_qty} ks")
                        if st.button(f"PRODAT {qty}x {ticker_input}", type="primary", use_container_width=True):
                            ok, msg = proved_prodej(ticker_input, qty, limit_price, USER, menu)
                            if ok: st.success(msg); time.sleep(2); st.rerun()
                            else: st.error(msg)
                    else:
                        c_info2.error(f"Máš jen: {curr_qty} ks")
                        st.button("🚫 Nedostatek akcií", disabled=True, use_container_width=True)
                else:
                    st.button("Zadej množství", disabled=True, use_container_width=True)

        # --- 2. SEKCE PRO SPRÁVU PENĚZ ---
        st.write("")
        c_ex1, c_ex2 = st.columns(2)
        
        # LEVÝ SLOUPEC: SMĚNÁRNA (Beze změny)
        with c_ex1:
            with st.expander("💱 SMĚNÁRNA", expanded=False):
                am = st.number_input("Částka", 0.0, step=100.0)
                fr = st.selectbox("Z", ["CZK", "USD", "EUR"], key="s_z")
                to = st.selectbox("Do", ["USD", "CZK", "EUR"], key="s_do")
                
                if st.button("💱 Směnit", use_container_width=True):
                    if zustatky.get(fr, 0) >= am:
                        proved_smenu(am, fr, to, USER)
                        st.success("Hotovo"); time.sleep(1); st.rerun()
                    else:
                        st.error("Chybí prostředky")

        # PRAVÝ SLOUPEC: BANKA + MANUÁLNÍ VKLAD (Upraveno)
        with c_ex2:
            with st.expander("🏧 BANKA & BANKOMAT", expanded=False):
                
                # A) BANKOVNÍ PROPOJENÍ
                st.caption("🌐 Moje Banka (Plaid API)")
                if st.button("🔄 Synchronizovat zůstatky", key="sync_bank", use_container_width=True):
                    with st.spinner("Šifrované spojení..."):
                        t_msg = bank.simulace_pripojeni()
                        if "Chyba" in t_msg: st.error(t_msg)
                        else:
                            df_b = bank.stahni_zustatky(t_msg)
                            if df_b is not None:
                                st.session_state['bank_data'] = df_b
                                st.toast("Data z banky stažena!", icon="✅")
                            else: st.warning("Žádná data.")
                
                # Zobrazení dat z banky, pokud jsou načtena
                if 'bank_data' in st.session_state:
                    st.dataframe(st.session_state['bank_data'], use_container_width=True, hide_index=True)
                    # Malý součet pro efekt
                    celkem_banka = st.session_state['bank_data']['Zůstatek'].sum()
                    mena_banka = st.session_state['bank_data'].iloc[0]['Měna']
                    st.caption(f"Disponibilní v bance: **{celkem_banka:,.2f} {mena_banka}**")

                st.divider()

                # B) MANUÁLNÍ VKLAD/VÝBĚR (Tvé původní ovládání)
                st.caption("📝 Manuální operace")
                op = st.radio("Akce", ["Vklad", "Výběr"], horizontal=True, label_visibility="collapsed")
                v_a = st.number_input("Částka", 0.0, step=500.0, key="v_a")
                v_m = st.selectbox("Měna", ["CZK", "USD", "EUR"], key="v_m")
                
                if st.button(f"Provést {op}", use_container_width=True):
                    sign = 1 if op == "Vklad" else -1
                    if op == "Výběr" and zustatky.get(v_m, 0) < v_a:
                        st.error("Nedostatek prostředků")
                    else:
                        df_cash_new = pohyb_penez(v_a * sign, v_m, op, "Manual", USER, st.session_state['df_cash'])
                        uloz_data_uzivatele(df_cash_new, USER, SOUBOR_CASH)
                        st.session_state['df_cash'] = df_cash_new
                        invalidate_data_core()
                        st.success("Hotovo"); time.sleep(1); st.rerun()

        # Historie transakcí
        if not df_cash.empty:
            st.divider()
            st.caption("Poslední pohyby na účtu")
            st.dataframe(df_cash.sort_values('Datum', ascending=False).head(3), use_container_width=True, hide_index=True)


    elif page == "💎 Dividendy":
        # NOVĚ: Voláme refaktorovanou funkci
        render_dividendy_page(USER, df, df_div, kurzy, viz_data_list)


    elif page == "🎮 Gamifikace":
        # NOVĚ: Voláme refaktorovanou funkci
        render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky)


    # --- OPRAVA 2: BEZPEČNÁ STRÁNKA NASTAVENÍ (Zabraňuje zacyklení) ---
    elif page == "⚙️ Nastavení":
        st.title("⚙️ KONFIGURACE SYSTÉMU")
        
        # --- 1. AI KONFIGURACE ---
        with st.container(border=True):
            st.subheader("🤖 AI Jádro & Osobnost")
            c_stat1, c_stat2 = st.columns([1, 3])
            with c_stat1:
                if AI_AVAILABLE: st.success("API: ONLINE")
                else: st.error("API: OFFLINE")
            
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

            prompts_df = pd.DataFrame(list(st.session_state['ai_prompts'].items()), columns=["Funkce", "Instrukce (Prompt)"])
            edited_prompts = st.data_editor(prompts_df, use_container_width=True, num_rows="dynamic", key="prompt_editor")

            if st.button("💾 Uložit nastavení AI"):
                new_prompts = dict(zip(edited_prompts["Funkce"], edited_prompts["Instrukce (Prompt)"]))
                st.session_state['ai_prompts'] = new_prompts
                st.toast("Osobnost AI aktualizována!", icon="🧠")

        # --- 2. DATA EDITORY ---
        st.write("")
        st.subheader("💾 DATA & SPRÁVA")
        t1, t2 = st.tabs(["PORTFOLIO", "HISTORIE"])
        with t1:
            new_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Portfolio"): 
                st.session_state['df'] = new_df
                uloz_data_uzivatele(new_df, USER, SOUBOR_DATA)
                invalidate_data_core()
                st.success("Uloženo"); time.sleep(1); st.rerun()
        with t2:
            new_h = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Historii"): 
                st.session_state['df_hist'] = new_h
                uloz_data_uzivatele(new_h, USER, SOUBOR_HISTORIE)
                invalidate_data_core()
                st.success("Uloženo"); time.sleep(1); st.rerun()
        
        st.divider(); st.subheader("📦 ZÁLOHA")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for n, d in [(SOUBOR_DATA, 'df'), (SOUBOR_HISTORIE, 'df_hist'), (SOUBOR_CASH, 'df_cash'), (SOUBOR_DIVIDENDY, 'df_div'), (SOUBOR_WATCHLIST, 'df_watch')]:
                if d in st.session_state: zf.writestr(n, st.session_state[d].to_csv(index=False))
        st.download_button("Stáhnout Data", buf.getvalue(), f"backup_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")
                st.divider()
                st.subheader("📲 NOTIFIKACE(Telegram)")
                st.caption("Otestuj spojení s tvým mobilem.")

                #TADY JE TA MAGIE
                notify.otestovat_tlacitko
                
    # --- BANKOVNÍ TESTER (Stránka) ---
    elif page == "🧪 Banka":
        render_bank_lab_page()

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
                st.error("AI je neaktivní.")
            else: 
                st.session_state["chat_messages"].append({"role": "user", "content": prompt})
                st.rerun()

        if st.session_state["chat_messages"][-1]["role"] == "user":
            if not st.session_state.get('ai_enabled', False): st.info("AI vypnuta.")
            else:
                with st.spinner("Přemýšlím..."):
                    last_user_msg = st.session_state["chat_messages"][-1]["content"]
                    portfolio_context = f"Jmění: {celk_hod_czk:,.0f} CZK. "
                    if viz_data_list: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data_list])
                    
                    try:
                        ai_reply = get_chat_response(model, last_user_msg, portfolio_context)
                    except Exception as e:
                        ai_reply = "🛑 Došla mi energie (Quota)." if "429" in str(e) else f"⚠️ Chyba: {e}"
                    
                    st.session_state["chat_messages"].append({"role": "assistant", "content": ai_reply})
                    st.rerun()

# ==========================================
# 👇 FINÁLNÍ BANKOVNÍ CENTRÁLA (VERZE 3.1 - I SE ZŮSTATKY) 👇
# ==========================================
def render_bank_lab_page():
    st.title("🏦 BANKOVNÍ CENTRÁLA (Verze 3.1)")
    st.caption("Automatické propojení s bankovním účtem (Transakce + Zůstatky).")

    # 1. PŘIPOJENÍ (Pokud nemáme token)
    if 'bank_token' not in st.session_state:
        st.info("Zatím není připojena žádná banka.")
        
        if st.button("🔌 PŘIPOJIT BANKU (Sandbox)", type="primary"):
            with st.spinner("Volám bankovní motor..."):
                token = bank_engine.simulace_pripojeni()
                
                if "Chyba" in str(token):
                    st.error(token)
                else:
                    st.session_state['bank_token'] = token
                    st.balloons()
                    st.success("✅ Banka úspěšně připojena! Token uložen.")
                    time.sleep(1)
                    st.rerun()
    
    # 2. PRÁCE S DATY (Když už jsme připojeni)
    else:
        c1, c2 = st.columns([3, 1])
        with c1: st.success("🟢 Spojení aktivní: Test Bank (Sandbox)")
        with c2: 
            if st.button("Odpojit"):
                del st.session_state['bank_token']
                if 'bank_data' in st.session_state: del st.session_state['bank_data']
                if 'bank_balance' in st.session_state: del st.session_state['bank_balance']
                st.rerun()

        st.divider()
        
        # --- OVLÁDACÍ PANEL (Dvě tlačítka vedle sebe) ---
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            # TOTO JE TO NOVÉ TLAČÍTKO PRO ZŮSTATKY 👇
            if st.button("💰 ZOBRAZIT ZŮSTATKY", use_container_width=True):
                with st.spinner("Ptám se banky na stav konta..."):
                    # Voláme novou funkci z motoru
                    df_bal = bank_engine.stahni_zustatky(st.session_state['bank_token'])
                    if df_bal is not None:
                        st.session_state['bank_balance'] = df_bal
                    else:
                        st.error("Chyba při stahování zůstatků.")

        with col_btn2:
            if st.button("📥 STÁHNOUT TRANSAKCE", use_container_width=True):
                with st.spinner("Stahuji výpis..."):
                    df_trans = bank_engine.stahni_data(st.session_state['bank_token'])
                    if df_trans is not None:
                        st.session_state['bank_data'] = df_trans
                    else:
                        st.error("Chyba při stahování transakcí.")

        # --- SEKCE 1: ZŮSTATKY (Nové!) ---
        if 'bank_balance' in st.session_state:
            st.write("")
            st.subheader("💳 Aktuální stav účtů")
            df_b = st.session_state['bank_balance']
            
            # Vykreslíme jako kartičky vedle sebe
            cols = st.columns(len(df_b))
            for index, row in df_b.iterrows():
                # Aby to nepadalo u více účtů, použijeme modulo
                col_idx = index % len(cols)
                with cols[col_idx]:
                    st.metric(
                        label=row['Název účtu'], 
                        value=f"{row['Zůstatek']:,.2f} {row['Měna']}", 
                        delta="Aktuální"
                    )
            st.divider()

        # --- SEKCE 2: TRANSAKCE ---
        if 'bank_data' in st.session_state:
            df_t = st.session_state['bank_data']
            
            # Cashflow (Příjmy vs Výdaje za stažené období)
            total_spend = df_t[df_t['Částka'] < 0]['Částka'].sum()
            total_income = df_t[df_t['Částka'] > 0]['Částka'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Příjmy (90 dní)", f"{total_income:,.0f}")
            m2.metric("Výdaje (90 dní)", f"{total_spend:,.0f}")
            m3.metric("Cashflow", f"{total_income + total_spend:,.0f}")
            
            st.subheader("📜 Historie transakcí")
            st.dataframe(
                df_t, 
                column_config={
                    "Částka": st.column_config.NumberColumn("Částka", format="%.2f"),
                    "Kategorie": st.column_config.TextColumn("Druh"),
                },
                use_container_width=True
            )
            
            # Graf výdajů
            st.subheader("📊 Analýza výdajů")
            expenses = df_t[df_t['Částka'] < 0].copy()
            expenses['Částka'] = expenses['Částka'].abs() # Pro koláčový graf chceme kladná čísla
            
            if not expenses.empty:
                fig_exp = px.pie(expenses, values='Částka', names='Kategorie', hole=0.4, template="plotly_dark")
                st.plotly_chart(fig_exp, use_container_width=True)
                
if __name__ == "__main__":
    main()



