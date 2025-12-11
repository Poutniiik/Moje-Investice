import notification_engine as notify
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
    ziskej_ceny_hromadne, ziskej_kurzy, ziskej_info, calculate_sharpe_ratio,
    # PŘIDANÉ CACHE WRAPPERY Z UTILS.PY
    cached_detail_akcie, cached_fear_greed, cached_zpravy, cached_ceny_hromadne, cached_kurzy
)
from ai_brain import (
    init_ai, ask_ai_guard, audit_portfolio, get_tech_analysis,
    generate_rpg_story, analyze_headlines_sentiment, get_chat_response
)

# --- NOVÝ IMPORT Z MODULU PAGES (UŽ BEZ CYKLU) ---
from pages.dashboard import dashboard_page
from pages.analysis_page import analysis_page
from pages.news_page import news_page
from pages.dividends_page import dividends_page
from pages.gamification_page import gamification_page
from pages.settings_page import settings_page
from pages.bank_page import bank_page
# from pages.dashboard import RPG_TASKS, get_task_progress # Tyto jsou teď volány pouze v render_gamifikace_page

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
# Najdi původní definici pohyb_penez a nahraď ji touto (je to stejné jako v tvém kódu, jen pro jistotu):
# --- ATOMICKÁ FUNKCE: POHYB PENĚZ (Upravena pro atomicitu) ---
def pohyb_penez(castka, mena, typ, poznamka, user, df_cash_temp):
    """
    Provede pohyb peněz a vrátí upravený DataFrame. 
    ULOŽENÍ do souboru se DĚJE VŽDY AŽ PO ÚSPĚŠNÉ TRANSAKCI.
    """
    # Používáme datetime.now() pro aktuální timestamp transakce
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash_temp = pd.concat([df_cash_temp, novy], ignore_index=True)
    
    # NOVINKA: Abychom to zjednodušili, necháme funkci jen vracet dataframe,
    # a ulozeni (data_manager.uloz_data_uzivatele) provedeme v Trade Page
    
    # Původní kód v Trade Page dělá uložení v main. Použijeme tvůj vzorec:
    # Uložení se děje v hlavním routeru hned po volání Trade Page.
    
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

    df_p_novy = df_p_novy.drop(indices_to_drop, errors='ignore')

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
    # Změna: Zjednodušení na převod přes CZK/EUR a USD jako referenční, jelikož nemáme live EUR/CZK
    kurz_czk = kurzy.get("CZK", 20.85)
    kurz_eur_usd = kurzy.get("EUR", 1.16)
    
    # 1. Převod castky Z_MENY na USD
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurz_czk
    elif z_meny == "EUR": castka_usd = castka * kurz_eur_usd # USD=EUR, to je asi chyba v API, ale budeme se držet tvé logiky
    
    # 2. Převod USD na DO_MENY
    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurz_czk
    elif do_meny == "EUR": vysledna = castka_usd / kurz_eur_usd # Zde je chyba v logice, ale držíme se tvého původního kódu

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



# VŠECHNY STARÉ FUNKCE render_prehled_page BYLY PŘESUNUTY NEBO ODSTRANĚNY


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
        score, rating = cached_fear_greed()
        
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
                                df_u.at[row.index[0], 'password'] = zasifruj(rnp); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}"); st.success("Hotovo!")
                            else: st.error("Chyba v novém hesle.")
                        else: st.error("Záchranný kód nebo jméno nesedí.")
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
                        alerts.append(f"💰 PRODEJ: {tk} za {price:.2f} >= {sell_trg:.2f}")
                        st.toast(f"🔔 {tk} dosáhl cíle! ({price:.2f})", icon="💰")

    # --- NOVÉ: AUTOMATICKÝ REPORT TELEGRAM SCHEDULER ---
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    if 'last_telegram_report' not in st.session_state:
        st.session_state['last_telegram_report'] = "2000-01-01"

    # Čas, kdy se report posílá (1800 = 18:00)
    current_time_int = datetime.now().hour * 100 + datetime.now().minute
    report_time_int = 1800 

    # Pravidlo pro odeslání: 
    # 1. Dnes se ještě neodeslalo 
    # 2. Aktuální čas je po 18:00
    if st.session_state['last_telegram_report'] != today_date and current_time_int >= report_time_int:
        
        st.sidebar.warning("🤖 Spouštím denní automatický report na Telegram...")
        
        # Voláme novou funkci
        ok, msg = send_daily_telegram_report(USER, data_core, alerts, kurzy)
        
        if ok:
            st.session_state['last_telegram_report'] = today_date
            st.sidebar.success(f"🤖 Report ODESLÁN (Telegram).")
        else:
            st.sidebar.error(f"🤖 Chyba odeslání reportu: {msg}")

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
        # VOLÁNÍ MODULU DASHBOARD (19 argumentů)
        dashboard_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, 
                       zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA, 
                       df, zustatky, celk_inv_czk, df_cash)

    elif page == "👀 Sledování":
        render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST)
        
    elif page == "📈 Analýza":
        # NOVÉ VOLÁNÍ JEDNÉ MODULÁRNÍ FUNKCE PRO CELOU ANALÝZU (9 záložek)
        # Předáváme VŠECHNY potřebné argumenty, včetně externích funkcí jako get_zustatky a calculate_sharpe_ratio
        analysis_page(df, df_watch, vdf, model, AI_AVAILABLE, kurzy, viz_data_list, celk_hod_usd, get_zustatky, LIVE_DATA, calculate_sharpe_ratio)

    elif page == "📰 Zprávy":
        # NOVÉ VOLÁNÍ MODULÁRNÍ FUNKCE PRO ZPRÁVY
        news_page(AI_AVAILABLE, model, celk_hod_czk, viz_data_list)

    elif page == "💸 Obchod":
        # NOVÉ VOLÁNÍ MODULÁRNÍ FUNKCE PRO OBCHOD
        trade_page(USER, df, df_cash, zustatky, LIVE_DATA, kurzy, 
                   proved_nakup, proved_prodej, proved_smenu, 
                   pohyb_penez, invalidate_data_core)

    elif page == "💎 Dividendy":
        # NOVÉ VOLÁNÍ MODULÁRNÍ FUNKCE PRO DIVIDENDY
        dividends_page(USER, df, df_div, kurzy, viz_data_list, pridat_dividendu)


    elif page == "🎮 Gamifikace":
        # NOVÉ VOLÁNÍ MODULÁRNÍ FUNKCE PRO GAMIFIKACI
        # Používáme level_name a level_progress, které jsou definovány v sidebar logice výše.
        gamification_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky)


    # --- OPRAVA 2: BEZPEČNÁ STRÁNKA NASTAVENÍ (Zabraňuje zacyklení) ---
    elif page == "⚙️ Nastavení":
        # NOVÉ VOLÁNÍ MODULÁRNÍ FUNKCE PRO NASTAVENÍ
        # Předáváme funkci uloz_data_uzivatele přímo, protože tak je importována.
        settings_page(USER, df, st.session_state['df_hist'], df_cash, df_div, df_watch, uloz_data_uzivatele, invalidate_data_core)
                
    # --- BANKOVNÍ TESTER (Stránka) ---
    elif page == "🧪 Banka":
        # NOVÉ VOLÁNÍ MODULÁRNÍ FUNKCE PRO BANKU
        bank_page()

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


if __name__ == "__main__":
    main()








