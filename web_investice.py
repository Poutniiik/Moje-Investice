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
    uloz_data_uzivatele, nacti_uzivatele, nacti_csv, uloz_csv
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
from portfolio_engine import calculate_all_data, aktualizuj_graf_vyvoje
from components.auth import render_login_screen

# --- NOVÝ IMPORT Z MODULU PAGES (UŽ BEZ CYKLU) ---
from pages.dashboard import dashboard_page
from pages.analysis_page import analysis_page
from pages.news_page import news_page 
from pages.trade_page import trade_page
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

# V souboru web_investice.py

def pridat_dividendu(ticker, castka, mena, user):
    """
    Přidá dividendu do historie a připíše peníze do hotovosti.
    """
    # 1. Načtení aktuálního stavu
    df_div = st.session_state['df_div']
    df_cash_temp = st.session_state['df_cash'].copy()
    
    # 2. Vytvoření nového řádku (S OPRAVOU DATA NA STRING)
    novy = pd.DataFrame([{
        "Ticker": ticker, 
        "Castka": float(castka), 
        "Mena": mena, 
        "Datum": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # <--- TADY JE ZMĚNA
        "Owner": user
    }])
    
    # 3. Spojení starých dat a nového řádku
    updated_div = pd.concat([df_div, novy], ignore_index=True)
    
    # 4. Pohyb peněz (přičtení hotovosti)
    df_cash_temp = pohyb_penez(castka, mena, "Dividenda", f"Divi {ticker}", user, df_cash_temp)
    
    # 5. Uložení a AKTUALIZACE STAVU
    try:
        # Zápis na disk
        uloz_data_uzivatele(updated_div, user, SOUBOR_DIVIDENDY)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        
        # Aktualizace paměti (session_state)
        st.session_state['df_div'] = updated_div
        st.session_state['df_cash'] = df_cash_temp
        
        # Vynucení přepočtu (volitelné, pokud používáš data_core)
        try:
             del st.session_state['data_core']
        except: pass
        
        return True, f"✅ Připsáno {castka:,.2f} {mena} od {ticker}"
    except Exception as e:
        return False, f"❌ Chyba zápisu transakce (DIVI): {e}"




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


# --- Skrytí automatické navigace Streamlitu ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)


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

        if not st.session_state['prihlasen']:  # <--- Tady je dvojtečka
        # 👇 Tady MUSÍ být mezera/odsazení
            render_login_screen(cookie_manager)
            st.stop()
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







