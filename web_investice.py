import notification_engine as notify
import engine_obchodu as engine
import bank_engine as bank
import engine_rpg as rpg
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
import ui_dashboard
import ui_watchlist
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
    SOUBOR_CASH, SOUBOR_VYVOJ, SOUBOR_WATCHLIST, SOUBOR_DIVIDENDY, SOUBOR_STATS, SOUBOR_STRATEGIE, 
    RISK_FREE_RATE,
    get_repo, zasifruj, uloz_csv, uloz_csv_bezpecne, nacti_csv,
    uloz_data_uzivatele, nacti_uzivatele, ziskej_info, save_df_to_github 
)
from utils import (
    ziskej_fear_greed, ziskej_zpravy, ziskej_yield, ziskej_earnings_datum,
    ziskej_detail_akcie, zjisti_stav_trhu, vytvor_pdf_report, odeslat_email,
    ziskej_ceny_hromadne, ziskej_kurzy, ziskej_info, calculate_sharpe_ratio
)
from ai_brain import (
    init_ai, ask_ai_guard, audit_portfolio, get_tech_analysis,
    generate_rpg_story, analyze_headlines_sentiment, get_chat_response, 
    get_strategic_advice, get_portfolio_health_score, get_voice_briefing_text, get_alert_voice_text
)
# --- NOVINKA: INTEGRACE HLASOVÉHO ASISTENTA ---
from voice_engine import VoiceAssistant

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

def invalidate_data_core():
    """
    VYNUCENÝ REFRESH: Zneplatní výpočty i syrová data.
    Tohle zajistí, že po každém nákupu/prodeji/změně watchlistu 
    se data načtou čerstvá z GitHubu bez nutnosti ručního refreshe.
    """
    # 1. Zneplatníme časové razítko vypočteného jádra
    if 'data_core' in st.session_state:
        st.session_state['data_core']['timestamp'] = datetime.now() - timedelta(minutes=6)
    
    # 2. KLÍČOVÝ KROK: Vymažeme syrová data ze stavu aplikace
    # Tím donutíme blok "if 'df' not in st.session_state" k opětovnému načtení
    raw_data_keys = ['df', 'df_hist', 'df_cash', 'df_div', 'df_watch']
    for key in raw_data_keys:
        if key in st.session_state:
            del st.session_state[key]

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
        add_xp(user, 10)
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


def pridat_dividendu(ticker, castka, mena, user):
    df_div = st.session_state['df_div']
    df_cash_temp = st.session_state['df_cash'].copy()
    
    # Krok 1: Záznam dividendy
    novy = pd.DataFrame([{"Ticker": ticker, "Castka": float(castka), "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_div = pd.concat([df_div, novy], ignore_index=True)
    
    # Krok 2: Pohyb peněz (Atomický)
    ok, msg, df_cash_temp = engine.proved_pohyb_hotovosti_engine(
    castka, mena, "Dividenda", f"Divi {ticker}", user, 
    df_cash_temp, uloz_data_uzivatele, SOUBOR_CASH
)
    
    # Krok 3: Uložení obou změn a invalidace
    try:
        uloz_data_uzivatele(df_div, user, SOUBOR_DIVIDENDY)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        
        # Aktualizace Session State AŽ PO ÚSPĚCHU
        st.session_state['df_div'] = df_div
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        add_xp(user, 30)
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

def get_user_stats(user):
    """Načte nebo inicializuje statistiky hráče s podporou perzistence questů."""
    df_s = nacti_csv(SOUBOR_STATS)
    user_row = df_s[df_s['Owner'] == str(user)]
    if user_row.empty:
        return {"Owner": user, "XP": 0, "Level": 1, "CompletedQuests": ""}
    return user_row.iloc[0].to_dict()

def add_xp(user, amount):
    """
    Zprostředkovatel mezi Engine a UI/Notifikacemi s kontrolou existence dat.
    Zajišťuje zápis do paměti i na disk (perzistence).
    """
    # 1. Kontrola existence dat v paměti
    if 'df_stats' not in st.session_state:
        st.session_state['df_stats'] = st.session_state.get('data_core', {}).get('stats', pd.DataFrame())

    # 2. Zavoláme engine pro výpočet nových hodnot
    ok, n_level, lvl_up, df_stats_new = rpg.pridej_xp_engine(
        user, amount, 
        st.session_state['df_stats'], 
        uloz_data_uzivatele, 
        SOUBOR_STATS
    )
    
    if ok:
        # A) AKTUALIZACE PAMĚTI (Session State)
        st.session_state['df_stats'] = df_stats_new
        
        # B) AKTUALIZACE DISKU (Pojistka proti rebootu)
        # Použijeme tvou funkci uloz_csv, aby se data zapsala do user_stats.csv navždy
        uloz_csv(df_stats_new, SOUBOR_STATS, f"XP gain: {amount} for {user}")
        
        st.toast(f"✨ +{amount} XP", icon="⭐")

        # C) LEVEL UP EFEKTY A NOTIFIKACE
        if lvl_up:
            st.balloons()
            st.success(f"🎉 GRATULUJEME! Postoupil jsi na úroveň {n_level}!")
            
            msg = (
                f"🎊 <b>LEVEL UP: {user.upper()}</b> 🎊\n"
                f"--------------------------------\n"
                f"Tvé investiční zkušenosti vzrostly!\n"
                f"Aktuální úroveň: <b>{n_level}</b> 🚀\n"
                f"<i>Jen tak dál, kapitáne!</i>"
            )
            notify.poslat_zpravu(msg)

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
    """
    Vykreslí stránku '🏠 Přehled' přes externí modul.
    VERZE 3.0 - Kompletní modularizace (všechny grafy, inicializace a tabulky jsou v ui_dashboard.py)
    """
    
    # 1. VOLÁNÍ MODULU
    # Předáváme veškerá data modulu. Inicializace stavů (if 'show_...') probíhá uvnitř modulu.
    ui_dashboard.render_dashboard(
        USER, 
        vdf, 
        hist_vyvoje, 
        kurzy, 
        celk_hod_usd, 
        celk_inv_usd, 
        celk_hod_czk, 
        zmena_24h, 
        pct_24h, 
        cash_usd, 
        AI_AVAILABLE, 
        model, 
        df_watch, 
        LIVE_DATA
    )
    

def render_sledovani_page(USER, df_watch, LIVE_DATA, AI_AVAILABLE, model):
    """Vykreslí stránku '🎯 Sledování' přes externí modul"""
    
    # Zavoláme modul a pošleme mu uloz_data_uzivatele (která teď vrací True/False)
    ui_watchlist.render_watchlist(
        USER, 
        df_watch, 
        LIVE_DATA, 
        AI_AVAILABLE, 
        model, 
        ziskej_info, 
        save_df_to_github # Tohle už vrací korektní výsledek
    )


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
    """Vykreslí vylepšenou RPG stránku napojenou na RPG Engine."""
    
    # 1. Inicializace session state
    if 'rpg_story_cache' not in st.session_state:
        st.session_state['rpg_story_cache'] = None
    if 'completed_quests_session' not in st.session_state:
        st.session_state['completed_quests_session'] = []
    
    # 2. ZÍSKÁNÍ DAT S POJISTKOU (Tady to sjednotíme)
    stats_df = st.session_state.get('df_stats', pd.DataFrame())
    
    # Pokud v paměti nic není nebo chybí sloupce, vytvoříme prázdnou strukturu
    if stats_df.empty or 'Owner' not in stats_df.columns:
        stats_df = pd.DataFrame(columns=['Owner', 'XP', 'LastLogin', 'Level', 'CompletedQuests'])
    
    # Najdeme řádek uživatele
    user_row = stats_df[stats_df['Owner'] == str(USER)]
    
    # Určíme celkové XP (pokud uživatel neexistuje, dáme 0)
    total_xp = user_row['XP'].iloc[0] if not user_row.empty else 0
    
    # 3. VOLÁNÍ MOTORU (Výpočty proběhnou v engine_rpg.py)
    level_rpg, xp_v_levelu, progress_pct_rpg, xp_do_dalsiho = rpg.vypocitej_detail_levelu(total_xp)
    current_rank_full = rpg.ziskej_hodnost_a_ikonu(level_rpg)

    st.title("🎮 INVESTIČNÍ ARÉNA (Profil Hráče)")
    # ... zbytek kódu (Hero Section, Badge, Questy) ...

    # --- ZOBRAZENÍ PROFILU (Hero Section) ---
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Level {level_rpg}: {USER.upper()}")
            st.progress(progress_pct_rpg)
            st.caption(f"✨ **{xp_v_levelu} / 500 XP** (Chybí {xp_do_dalsiho} XP do levelu {level_rpg + 1})")
        with col2:
            # Tady už čerpáme z tvého sjednoceného seznamu v Enginu
            icon = current_rank_full.split()[0]
            name = " ".join(current_rank_full.split()[1:])
            st.markdown(f"### {icon}")
            st.caption(name)

    # --- RPG ATRIBUTY (Ponecháno původní) ---
    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            trpelivost = len(vdf[vdf['Dan'] == '🟢 Free']) if not vdf.empty else 0
            st.metric("⏳ TRPĚLIVOST", f"{trpelivost}", help="Počet pozic držených v časovém testu.")
    with c2:
        with st.container(border=True):
            st.metric("🔥 AKTIVITA", f"{total_xp}", help="Tvé celkové zkušenostní skóre.")
    with c3:
        with st.container(border=True):
            # Tady používáme level_name z parametrů funkce (hodnost podle majetku)
            st.metric("💰 RANK", f"{level_name}", help="Tvá hodnost založená na celkovém jmění.")

    # --- SÍŇ SLÁVY (Ponecháno původní) ---
    st.divider()
    st.subheader("🏆 SÍŇ SLÁVY")
    
    has_first = not df.empty
    cnt = len(df['Ticker'].unique()) if not df.empty else 0
    divi_total = df_div['Castka'].sum() if not df_div.empty else 0

    def badge(title, desc, cond, icon):
        opacity = "1.0" if cond else "0.3"
        bg = "rgba(0, 255, 153, 0.1)" if cond else "transparent"
        st.markdown(f"""
            <div style="border: 1px solid #30363D; border-radius: 10px; padding: 15px; text-align: center; opacity: {opacity}; background-color: {bg};">
                <div style="font-size: 30px;">{icon}</div>
                <div style="font-weight: bold; font-size: 14px;">{title}</div>
                <div style="font-size: 10px; color: #8B949E;">{desc}</div>
            </div>
        """, unsafe_allow_html=True)

    b1, b2, b3, b4 = st.columns(4)
    with b1: badge("Začátečník", "Kup první akcii", has_first, "🥉")
    with b2: badge("Stratég", "3 různé firmy", cnt >= 3, "🥈")
    with b3: badge("Boháč", "Majetek > 100k", celk_hod_czk > 100000, "🥇")
    with b4: badge("Rentiér", "Dostal jsi divi", divi_total > 0, "💎")

    # --- AI DENNÍ ZÁPIS ---
    if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
        st.write("")
        with st.container(border=True):
            st.subheader("🎲 DENNÍ ZÁPIS (AI Narrator)")
            if st.button("🎲 GENEROVAT PŘÍBĚH DNE", use_container_width=True):
                with st.spinner("Vypravěč píše kapitolu..."):
                    sc, _ = ziskej_fear_greed()
                    res = generate_rpg_story(model, current_rank_full, 0, celk_hod_czk, sc if sc else 50)
                    st.session_state['rpg_story_cache'] = res
            if st.session_state.get('rpg_story_cache'):
                st.info(f"_{st.session_state['rpg_story_cache']}_")

    # --- 6. QUEST LOG (OPRAVENÁ VERZE) ---
    st.divider()
    st.subheader("📜 QUEST LOG (Aktivní výzvy)")

    # 1. Získáme aktuální seznam hotových úkolů přímo z naší proměnné user_row
    saved_quests_raw = str(user_row['CompletedQuests'].iloc[0] if not user_row.empty else "")
    completed_list = [q.strip() for q in saved_quests_raw.split(",") if q.strip()]

    # Procházíme definované RPG úkoly
    for i, task in enumerate(RPG_TASKS):
        is_completed = False
        try:
            df_w = st.session_state.get('df_watch', pd.DataFrame())
            is_completed = task['check_fn'](df, df_w, zustatky, vdf)
            current, target, progress_text = get_task_progress(i, df, df_w, zustatky, vdf)
        except Exception:
            current, target, progress_text = 0, 1, "Chyba dat"

        # LOGIKA ODMĚNY: Pokud je splněno a ID úkolu NENÍ v seznamu hotových
        if is_completed and str(i) not in completed_list:
            # A) Přidáme XP přes motor
            add_xp(USER, 100)
            
            # B) Aktualizujeme seznam v paměti aplikace (stopeka pro farmení)
            completed_list.append(str(i))
            new_completed_str = ",".join(completed_list)
            
            # C) Zapíšeme to přímo do Session State, aby o tom zbytek aplikace věděl hned
            if not st.session_state['df_stats'].empty:
                idx = st.session_state['df_stats'][st.session_state['df_stats']['Owner'] == str(USER)].index[0]
                st.session_state['df_stats'].at[idx, 'CompletedQuests'] = new_completed_str
                
                # D) Uložíme celou tabulku do CSV (už bez zbytečného nacti_csv)
                uloz_data_uzivatele(st.session_state['df_stats'], USER, SOUBOR_STATS)
            
            st.balloons()
            st.toast(f"🏆 Quest dokončen: {task['title']}", icon="✅")

        # --- Vykreslení karty questu (beze změny) ---
        with st.container(border=True):
            q_col1, q_col2 = st.columns([1, 5])
            with q_col1:
                icon_q = '✅' if is_completed else '📜'
                st.markdown(f"<div style='font-size: 25px; text-align: center;'>{icon_q}</div>", unsafe_allow_html=True)
            with q_col2:
                st.markdown(f"**{task['title']}**")
                st.caption(task['desc'])
                if target > 0:
                    pct = min(current / target, 1.0)
                    st.progress(pct)
                    st.caption(f"Postup: {progress_text} ({int(pct*100)}%)")


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
                            color_icon = "🟢"
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


# ... (zde končí kód funkcí pro renderování stránek a pod ním začíná) ...
# --- CENTRÁLNÍ DATOVÉ JÁDRO: VÝPOČET VŠECH METRIK ---

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
            # Původně bylo vdf_sorted, teď vdf_sorted_all
            vdf_sorted_all = vdf.sort_values('Dnes', ascending=False) 
            
            # Top Movers
            movers_text += "\n🔝 Vítězové:\n"
            # Bereme jen ty s kladným ziskem (ať to není matoucí)
            for _, row in vdf_sorted_all[vdf_sorted_all['Dnes'] > 0.001].head(3).iterrows():
                movers_text += f"  🚀 {row['Ticker']}: {row['Dnes']*100:+.2f}%\n"
            
            # Flop Movers
            movers_text += "🔻 Poražení:\n"
            # Bereme jen ty se záporným ziskem
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
    OPTIMALIZOVANÁ VERZE: Využívá hromadně stažená data (LIVE_DATA) a nevolá 
    zbytečně API pro každou akcii zvlášť.
    """
    
    # Krok 1: Inicializace a příprava seznamu tickerů
    all_tickers = []
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    
    # Odebereme duplicity a prázdné hodnoty
    all_tickers = list(set([t for t in all_tickers if str(t).strip() != '']))

    # Stáhneme živá data a kurzy (BATCH DOWNLOAD - TOTO JE TO ZRYCHLENÍ)
    with st.spinner("🚀 Bleskové načítání tržních dat..."):
        LIVE_DATA = cached_ceny_hromadne(all_tickers)
    
    # Aktualizace kurzů, pokud je Yahoo poslalo
    if LIVE_DATA:
        if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
        if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]
    
    # Uložíme do session state pro použití v jiných částech appky (např. Obchod)
    st.session_state['LIVE_DATA'] = LIVE_DATA if LIVE_DATA else {}
    
    # Krok 2: Fundamentální data (Cached)
    fundament_data = {}
    if not df.empty:
        tickers_in_portfolio = df['Ticker'].unique().tolist()
        for tkr in tickers_in_portfolio:
            # Fundamenty se mění málo, cache zde funguje dobře
            info, _ = cached_detail_akcie(tkr) 
            fundament_data[tkr] = info

    # Krok 3: Výpočet portfolia
    viz_data = []
    celk_hod_usd = 0
    celk_inv_usd = 0

    if not df.empty:
        # Seskupíme nákupy téže akcie
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        # Přesnější výpočet investice (suma: pocet * nákupka pro každou transakci)
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        
        # Iterace přes portfolio
        for i, (idx, row) in enumerate(df_g.iterrows()):
            tkr = row['Ticker']
            
            # --- ZDE BYLA TA CHYBA (N+1 Problém) ---
            # Původně: p, m, d_zmena = ziskej_info(tkr)  <-- TOTO ZPOMALOVALO
            
            # NOVĚ: Okamžitý lookup v paměti
            p = 0
            m = "USD"
            d_zmena = 0
            
            if tkr in LIVE_DATA:
                p = LIVE_DATA[tkr].get('price', 0)
                m = LIVE_DATA[tkr].get('curr', 'USD')
                # Pokud hromadná data nemají změnu (utils.py vrací jen price/curr), 
                # necháme 0, abychom nezpomalovali. Rychlost > Detail na dashboardu.
                d_zmena = LIVE_DATA[tkr].get('change', 0) 
            else:
                # Fallback: Jen pokud ticker chybí v balíku, zavoláme pomalou funkci
                p, m, d_zmena = ziskej_info(tkr)
            
            # Záchrana, pokud cena stále chybí (např. delisted)
            if p is None or p == 0: 
                p = row['Cena'] # Použijeme nákupní cenu, aby to nebylo 0

            # Zbytek logiky zůstává stejný...
            fundamenty = fundament_data.get(tkr, {})
            pe_ratio = fundamenty.get('trailingPE', 0)
            market_cap = fundamenty.get('marketCap', 0)

            try:
                raw_sektor = df[df['Ticker'] == tkr]['Sektor'].iloc[0]
                sektor = str(raw_sektor) if not pd.isna(raw_sektor) and str(raw_sektor).strip() != "" else "Doplnit"
            except Exception: sektor = "Doplnit"

            # Daňový test (beze změny)
            nakupy_data = df[df['Ticker'] == tkr]['Datum']
            dnes = datetime.now()
            limit_dni = 1095
            vsechny_ok = True
            vsechny_fail = True

            for d in nakupy_data:
                # Ošetření, pokud datum není datetime
                if not isinstance(d, datetime):
                    d = pd.to_datetime(d)
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
            hod = row['Pocet'] * p
            inv = row['Investice']
            z = hod - inv

            # Konverze měny pro celkový součet v USD
            try:
                if m == "CZK": k = 1.0 / kurzy.get("CZK", 20.85)
                elif m == "EUR": k = kurzy.get("EUR", 1.16)
                else: k = 1.0
            except Exception: k = 1.0

            celk_hod_usd += hod * k
            celk_inv_usd += inv * k

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

    # Krok 6: Sestavení Data Core
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

    # --- INICIALIZACE CHATU (Prevence KeyError) ---
    if 'chat_messages' not in st.session_state:
        st.session_state['chat_messages'] = [
        {"role": "assistant", "content": "Ahoj! Jsem tvůj AI asistent. Jak ti mohu dnes pomoci s tvým portfoliem?"}
    ]

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
                    df_u = nacti_uzivatele()
                    # 1. Oprava: Používáme 'ru' místo 'u'
                    row = df_u[df_u['username'] == ru] 
                    
                    # 2. Oprava: Kontrolujeme Záchranný kód, ne staré heslo 'old'
                    # POZOR: Ujisti se, že sloupec v CSV se jmenuje 'recovery_code'
                    # Pokud se jmenuje jinak (třeba 'kod'), přepiš to v závorce níže.
                    if not row.empty and str(row.iloc[0]['recovery_code']) == str(rk):
                        
                        # 3. Oprava: Používáme 'rnp' místo 'new' a 'conf' (potvrzení tu nemáš)
                        if len(rnp) > 0:
                             df_u.at[row.index[0], 'password'] = zasifruj(rnp)
                             uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}")
                             st.success("Hotovo! Heslo obnoveno.")
                        else: 
                             st.error("Heslo nesmí být prázdné.")
                    else: 
                        st.error("Chybné jméno nebo záchranný kód.")
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
                    # NOVINKA: Přečteme to
                    st.session_state['cli_voice_msg'] = ai_response

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
                    # NOVINKA: Přečteme to
                    st.session_state['cli_voice_msg'] = guard_res_text

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

            # --- V části process_cli_command() najdi tyto bloky a přepiš je ---

            elif cmd == "/buy" and len(cmd_parts) >= 3:
                t_cli = cmd_parts[1].upper()
                k_cli = float(cmd_parts[2])
                p_cli, m_cli, _ = ziskej_info(t_cli)
                if p_cli:
                    # TADY VOLÁME ENGINE MÍSTO SMAZANÉ FUNKCE
                    soubory_nakup = {'data': SOUBOR_DATA, 'cash': SOUBOR_CASH}
                    ok, msg, nove_p, nova_c = engine.proved_nakup_engine(
                        t_cli, k_cli, p_cli, USER, 
                        st.session_state['df'], st.session_state['df_cash'], 
                        get_zustatky(USER), ziskej_info, uloz_data_uzivatele, 
                        soubory_nakup
                    )
                    if ok:
                        st.session_state['df'] = nove_p
                        st.session_state['df_cash'] = nova_c
                        invalidate_data_core()
                        add_xp(USER, 50)
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
                    # TADY VOLÁME ENGINE MÍSTO SMAZANÉ FUNKCE
                    soubory_prodej = {'data': SOUBOR_DATA, 'historie': SOUBOR_HISTORIE, 'cash': SOUBOR_CASH}
                    ok, msg, nove_df, nova_hist, nova_cash = engine.proved_prodej_engine(
                        t_cli, k_cli, p_cli, USER, m_cli,
                        st.session_state['df'], st.session_state['df_hist'], st.session_state['df_cash'],
                        st.session_state.get('LIVE_DATA', {}), uloz_data_uzivatele, soubory_prodej
                    )
                    if ok:
                        st.session_state['df'] = nove_df
                        st.session_state['df_hist'] = nova_hist
                        st.session_state['df_cash'] = nova_cash
                        invalidate_data_core()
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


    # --- 8. KONTROLA WATCHLISTU (HLASOVÝ SNIPER RADAR) ---
    alerts = []
    # Inicializace paměti na odehrané alerty (pokud neexistuje)
    if 'played_alerts' not in st.session_state:
        st.session_state['played_alerts'] = set()

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
                
                    # Logika detekce
                    if buy_trg > 0 and price <= buy_trg:
                        action = "NÁKUP"
                        target = buy_trg
                        alert_triggered = True
                    elif sell_trg > 0 and price >= sell_trg:
                        action = "PRODEJ"
                        target = sell_trg
                        alert_triggered = True

                    if alert_triggered:
                        # Textový alert pro UI/Telegram
                        msg = f"{tk}: {action} ALERT! Cena {price:.2f} (Cíl: {target:.2f})"
                        alerts.append(msg)
                        st.toast(f"🔔 {tk} je na cíli!", icon="🎯")
                    
                        # --- HLASOVÁ ČÁST (Sniper) ---
                        # Vytvoříme unikátní klíč pro tento konkrétní alert (např. AAPL_NÁKUP)
                        alert_key = f"{tk}_{action}"
                    
                        # Pokud alert pro tuhle akci ještě dnes nezazněl a AI je aktivní
                        if alert_key not in st.session_state['played_alerts'] and st.session_state.get('ai_enabled', False) and AI_AVAILABLE:
                            with st.spinner(f"Attis AI hlásí příležitost na {tk}..."):
                                # 1. Necháme Gemini vygenerovat drsný text
                                voice_msg = get_alert_voice_text(model, tk, price, target, action)
                                # 2. Převedeme na audio
                                audio_html = VoiceAssistant.speak(voice_msg)
                                if audio_html:
                                    st.components.v1.html(audio_html, height=0)
                                    # 3. Zapamatujeme si, že jsme ho už přehráli
                                    st.session_state['played_alerts'].add(alert_key)
    

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
                
        # =====================================================================
        # 🎙️ SMART BRIEFING PRO ASISTENTA (V4.3) - TADY SE DĚJE TO KOUZLO
        # =====================================================================
        # 1. Základní briefing (Jméno a celkové peníze)
        briefing = f"Jsi Attis AI v aplikaci Terminal Pro. Uživatel: {USER}. Celkové jmění: {celk_hod_czk:,.0f} Kč. Hotovost: {cash_usd:,.0f} USD. "

        # 2. Rozbor portfolia (Akcie a sektory), aby věděl, co vlastníš
        if not vdf.empty:
            seznam_akcii = ", ".join(vdf['Ticker'].tolist())
            briefing += f"Vlastníš tyto akcie: {seznam_akcii}. "
            
            # Výpočet rozdělení sektorů (na tohle jsi se ptal)
            if 'Sektor' in vdf.columns and 'HodnotaUSD' in vdf.columns:
                sector_dist = vdf.groupby('Sektor')['HodnotaUSD'].sum()
                total_usd = sector_dist.sum()
                if total_usd > 0:
                    dist_str = ", ".join([f"{s}: {(v/total_usd)*100:.1f}%" for s, v in sector_dist.items()])
                    briefing += f"Tvé investice jsou rozděleny do těchto sektorů: {dist_str}. "
        else:
            briefing += "Portfolio je momentálně prázdné. "

        # 3. Info o bance
        if 'bank_data' in st.session_state:
            briefing += "Máš aktivní propojení s bankovním API pro transakce. "
        else:
            briefing += "Data z externí banky nejsou připojena. "

        # 4. VOLÁNÍ ASISTENTA S KONTEXTEM (TADY MU DÁVÁME TY OČI)
        VoiceAssistant.render_voice_ui(user_context=briefing)
        
        # --- NOVINKA: VELITELSKÁ ŘÁDKA (CLI) ---
        st.divider()
        with st.expander("💻 TERMINÁL", expanded=False):
            # Zobrazení zprávy z callbacku
            if st.session_state.get('cli_msg'):
                txt, ic = st.session_state['cli_msg']
                if ic in ["🔬", "👮"]:
                    st.toast(f"{ic} Nové hlášení od AI strážce!", icon=ic)
                    st.markdown(f"<div style='font-size: 10px;'>{txt}</div>", unsafe_allow_html=True)
                    # --- NOVINKA: HLAS ---
                    if 'cli_voice_msg' in st.session_state and st.session_state['cli_voice_msg']:
                        audio_html = VoiceAssistant.speak(st.session_state['cli_voice_msg'])
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                        st.session_state['cli_voice_msg'] = None # Přečteno, smazat

                else:
                    st.info(f"{ic} {txt}")
                st.session_state['cli_msg'] = None 

            st.text_input(">", key="cli_cmd", placeholder="/help", on_change=process_cli_command)

        # --- AKCE (Tlačítka dole) ---
        st.divider()
        c_act1, c_act2 = st.columns(2)
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
        render_sledovani_page(USER, df_watch, LIVE_DATA, AI_AVAILABLE, model)
        
    elif page == "📈 Analýza":
        st.title("📈 HLOUBKOVÁ ANALÝZA")
        
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(["🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA & SEKTORY", "🔮 VĚŠTEC", "🏆 BENCHMARK", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE", "📅 KALENDÁŘ", "🎯 STRATÉG"])

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

        with tab10:
            st.subheader("🎯 AI INVESTIČNÍ STRATÉG")
            st.info("Tento modul kombinuje tvé nákupní cíle, technickou analýzu (RSI) a AI pro návrh dalšího postupu.")

            if not df_watch.empty:
                col_gen, col_hist = st.columns([2, 1])
        
                with col_gen:
                    if st.button("🚀 GENEROVAT STRATEGICKÝ PLÁN", use_container_width=True):
                        with st.spinner("Kvantové počítače počítají trajektorie..."):
                            # 1. Příprava dat
                            strat_data = []
                            for _, r in df_watch.iterrows():
                                tk = r['Ticker']
                                info = LIVE_DATA.get(tk, {})
                                strat_data.append({
                                    "Ticker": tk,
                                    "Cena": info.get('price', 'N/A'),
                                    "Cíl_Nákup": r['TargetBuy'],
                                    "Cíl_Prodej": r['TargetSell']
                                })
                    
                            # 2. Kontext
                            score, rating = cached_fear_greed()
                            sentiment = f"{rating} ({score}/100)"
                            port_sum = f"Celkem: {celk_hod_czk:,.0f} Kč, Hotovost: {cash_usd:,.0f} USD"

                            # 3. Volání AI
                            advice = get_strategic_advice(model, sentiment, strat_data, port_sum)
                    
                            if not advice.startswith("Strategické spojení přerušeno"):
                                # --- NOVINKA: ULOŽENÍ DO HISTORIE ---
                                df_s = nacti_csv(SOUBOR_STRATEGIE)
                                new_row = pd.DataFrame([{
                                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "Owner": USER,
                                    "Sentiment": sentiment,
                                    "Advice": advice
                                }])
                                df_s = pd.concat([df_s, new_row], ignore_index=True)
                                uloz_csv(df_s, SOUBOR_STRATEGIE, f"Strategy save for {USER}")
                        
                                st.markdown("---")
                                st.markdown(advice)
                                add_xp(USER, 20)
                                st.toast("Strategie připravena a uložena! +20 XP", icon="🎯")
                            else:
                                st.error(f"❌ Chyba AI: {advice}")


                with col_hist:
                    st.write("📜 **Poslední rady**")
                    df_h = nacti_csv(SOUBOR_STRATEGIE)
                    if not df_h.empty:
                        # Filtrujeme pro aktuálního uživatele a vezmeme poslední 3
                        user_h = df_h[df_h['Owner'] == str(USER)].tail(3)[::-1]
                        for _, row in user_h.iterrows():
                            with st.expander(f"📅 {row['Timestamp']}"):
                                st.caption(f"Trh: {row['Sentiment']}")
                                st.write(row['Advice'])
                    else:
                        st.write("Zatím žádná historie.")
            else:
                st.warning("Tvůj Watchlist je prázdný. Přidej akcie a nákupní cíle, aby mohl stratég pracovat.")

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
            # 1. Defenzivní kontrola - pokud klíč chybí, vytvoříme ho "on the fly"
            if "chat_messages" not in st.session_state:
                st.session_state["chat_messages"] = []
    
            # 2. Příprava kontextu
            portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
            if viz_data_list: 
                portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data_list])
    
            # 3. Sestavení promptu
            prompt_to_send = f"Analyzuj tuto zprávu V KONTEXTU MÉHO PORTFOLIA. Zpráva: {title}. Jaký má dopad? (Odkaz: {link})"
    
            # 4. Přidání do historie chatu
            st.session_state["chat_messages"].append({"role": "user", "content": prompt_to_send})
    
            # 5. Otevření chatu a refresh
            st.session_state['chat_expanded'] = True
            st.toast("Analýza odeslána do AI chatu!", icon="🤖")
            time.sleep(0.5)
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
            
            # --- LOGIKA TLAČÍTKA S NOVÝM ENGINEM ---
            if mode == "🟢 NÁKUP":
                if total_est > 0:
                    c_info1, c_info2 = st.columns(2)
                    c_info1.info(f"Celkem: **{total_est:,.2f} {menu}**")
                    
                    if zustatek >= total_est:
                        c_info2.success(f"Na účtu: {zustatek:,.2f} {menu}")
                        
                        if st.button(f"KOUPIT {qty}x {ticker_input}", type="primary", use_container_width=True):
                            soubory_nakup = {'data': SOUBOR_DATA, 'cash': SOUBOR_CASH}
                            
                            uspech, zprava, nove_p, nova_c = engine.proved_nakup_engine(
                                ticker_input, qty, limit_price, USER, 
                                st.session_state['df'], st.session_state['df_cash'], 
                                get_zustatky(USER), ziskej_info, uloz_data_uzivatele, 
                                soubory_nakup
                            )

                            if uspech:
                                st.session_state['df'] = nove_p
                                st.session_state['df_cash'] = nova_c
                                invalidate_data_core()
                                add_xp(USER, 50)
                                st.balloons()
                                st.success(zprava)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(zprava)
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
                            soubory = {'data': SOUBOR_DATA, 'historie': SOUBOR_HISTORIE, 'cash': SOUBOR_CASH}
                            
                            uspech, zprava, nove_df, nova_hist, nova_cash = engine.proved_prodej_engine(
                                ticker_input, qty, limit_price, USER, menu,
                                st.session_state['df'], st.session_state['df_hist'], st.session_state['df_cash'],
                                st.session_state.get('LIVE_DATA', {}), uloz_data_uzivatele, soubory
                            )

                            if uspech:
                                st.session_state['df'] = nove_df
                                st.session_state['df_hist'] = nova_hist
                                st.session_state['df_cash'] = nova_cash
                                invalidate_data_core()
                                st.success(zprava)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(zprava)
                    else:
                        c_info2.error(f"Máš jen: {curr_qty} ks")
                        st.button("🚫 Nedostatek akcií", disabled=True, use_container_width=True)
                else:
                    st.button("Zadej množství", disabled=True, use_container_width=True)

        # --- 2. SEKCE PRO SPRÁVU PENĚZ ---
        st.write("")
        c_ex1, c_ex2 = st.columns(2)
        
        # LEVÝ SLOUPEC: SMĚNÁRNA
        with c_ex1:
            with st.expander("💱 SMĚNÁRNA", expanded=False):
                am = st.number_input("Částka", 0.0, step=100.0)
                fr = st.selectbox("Z", ["CZK", "USD", "EUR"], key="s_z")
                to = st.selectbox("Do", ["USD", "CZK", "EUR"], key="s_do")
                
                if st.button("💱 Směnit", use_container_width=True):
                    if zustatky.get(fr, 0) >= am:
                        # VOLÁME ENGINE
                        ok, msg, nova_cash = engine.proved_smenu_engine(
                            am, fr, to, USER, 
                            st.session_state['df_cash'], 
                            kurzy, 
                            uloz_data_uzivatele, 
                            SOUBOR_CASH
                        )
                        
                        if ok:
                            st.session_state['df_cash'] = nova_cash
                            invalidate_data_core()
                            st.success(msg)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("Chybí prostředky na zdrojovém účtu")

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

               # B) MANUÁLNÍ VKLAD/VÝBĚR
                st.caption("📝 Manuální operace")
                op = st.radio("Akce", ["Vklad", "Výběr"], horizontal=True, label_visibility="collapsed")
                v_a = st.number_input("Částka", 0.0, step=500.0, key="v_a")
                v_m = st.selectbox("Měna", ["CZK", "USD", "EUR"], key="v_m")
                
                if st.button(f"Provést {op}", use_container_width=True):
                    # Výpočet znaménka (Vklad +, Výběr -)
                    final_amount = v_a if op == "Vklad" else -v_a
                    
                    if op == "Výběr" and zustatky.get(v_m, 0) < v_a:
                        st.error("Nedostatek prostředků na účtu")
                    else:
                        # VOLÁME ENGINE
                        uspech, msg, nova_cash = engine.proved_pohyb_hotovosti_engine(
                            final_amount, v_m, op, "Manual", USER, 
                            st.session_state['df_cash'], 
                            uloz_data_uzivatele, 
                            SOUBOR_CASH
                        )
                        
                        if uspech:
                            st.session_state['df_cash'] = nova_cash
                            invalidate_data_core()
                            st.success(msg)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)
                            
        # Historie transakcí
        if not df_cash.empty:
            st.divider()
            st.caption("Poslední pohyby na účtu")
            st.dataframe(df_cash.sort_values('Datum', ascending=False).head(3), use_container_width=True, hide_index=True)

    # --- TADY ZAČÍNAJÍ DALŠÍ STRÁNKY (Musí být na stejné úrovni jako elif page == "💸 Obchod") ---
    elif page == "💎 Dividendy":
        render_dividendy_page(USER, df, df_div, kurzy, viz_data_list)

    elif page == "🎮 Gamifikace":
        render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky)


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

        if st.button("🔔 Otestovat Telegram notifikaci", key="btn_test_notify", use_container_width=True):
            # Tady už není žádný U+00A0
            ok, msg = notify.poslat_zpravu("🤖 [Terminal PRO] Testovací zpráva: Spojení je OK!")

            if ok:
                st.success("Testovací zpráva odeslána!")
            else:
                st.error(f"Chyba: {msg}. Zkontroluj TELEGRAM_BOT_TOKEN.")
                
    # --- BANKOVNÍ TESTER (Stránka) ---
    elif page == "🧪 Banka":
        render_bank_lab_page()

# =========================================================================
    # 🤖 PLOVOUCÍ AI ASISTENT (FINÁLNÍ VERZE S OŠETŘENÍM LIMITŮ)
    # =========================================================================
    if st.session_state.get('ai_enabled', False) and AI_AVAILABLE:
        
        with st.expander("AI ASISTENT", expanded=st.session_state.get('chat_expanded', False)):
            st.markdown('<div id="floating-bot-anchor"></div>', unsafe_allow_html=True)
            
            chat_container = st.container()
            
            # 1. Zobrazení historie
            messages = st.session_state.get('chat_messages', [])
            with chat_container:
                if not messages:
                    st.caption("Zatím žádné zprávy. Zeptej se mě na své portfolio!")
                for msg in messages:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])

            # 2. Manuální vstup
            if chat_prompt := st.chat_input("Zeptej se na portfolio...", key="floating_chat_input"):
                st.session_state['chat_messages'].append({"role": "user", "content": chat_prompt})
                st.rerun()

            # 3. AUTOMATICKÁ ODPOVĚĎ AI
            if messages and messages[-1]["role"] == "user":
                with chat_container:
                    with st.chat_message("assistant"):
                        with st.spinner("Analyzuji data a přemýšlím..."):
                            history_for_api = []
                            for m in messages:
                                role = "user" if m["role"] == "user" else "model"
                                history_for_api.append({"role": role, "parts": [{"text": m["content"]}]})
                            
                            current_context = f"Uživatel: {USER}. Celkové jmění: {celk_hod_czk:,.0f} Kč. Hotovost: {cash_usd:,.0f} USD."
                            
                            try:
                                response = get_chat_response(model, history_for_api, current_context)
                                if response:
                                    st.write(response)
                                    st.session_state['chat_messages'].append({"role": "assistant", "content": response})
                            except Exception as e:
                                # --- FORENZNÍ FILTR CHYB ---
                                error_msg = str(e)
                                if "429" in error_msg or "quota" in error_msg.lower():
                                    st.warning("⚠️ **AI má pauzu.** Překročili jsme limit bezplatných zpráv (Quota). Zkus to prosím za minutu.")
                                elif "401" in error_msg or "key" in error_msg.lower():
                                    st.error("🔑 Chyba API klíče. Zkontroluj nastavení.")
                                else:
                                    st.error(f"📡 Spojení s mozkem přerušeno: {error_msg}")

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












