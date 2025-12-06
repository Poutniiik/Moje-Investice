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
    "„Trh je nástroj k přesunu peněz od netrpělivých k trpělivým.“ — Benjamin Graham",
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


# --- DATABÁZE ---
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

def pohyb_penez(castka, mena, typ, poznamka, user):
    df_cash = st.session_state['df_cash']
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash = pd.concat([df_cash, novy], ignore_index=True)
    st.session_state['df_cash'] = df_cash
    uloz_data_uzivatele(df_cash, user, SOUBOR_CASH)

def pridat_dividendu(ticker, castka, mena, user):
    df_div = st.session_state['df_div']
    novy = pd.DataFrame([{"Ticker": ticker, "Castka": float(castka), "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_div = pd.concat([df_div, novy], ignore_index=True)
    st.session_state['df_div'] = df_div
    uloz_data_uzivatele(df_div, user, SOUBOR_DIVIDENDY)
    pohyb_penez(castka, mena, "Dividenda", f"Divi {ticker}", user)

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

# --- NOVÁ FUNKCE: PROVEDENÍ NÁKUPU (Refactoring pro CLI) ---
def proved_nakup(ticker, kusy, cena, user):
    df_p = st.session_state['df']
    _, mena, _ = ziskej_info(ticker)
    cost = kusy * cena
    zustatky = get_zustatky(user)

    if zustatky.get(mena, 0) >= cost:
        pohyb_penez(-cost, mena, "Nákup", ticker, user)
        d = pd.DataFrame([{"Ticker": ticker, "Pocet": kusy, "Cena": cena, "Datum": datetime.now(), "Owner": user, "Sektor": "Doplnit", "Poznamka": "CLI/Auto"}])
        st.session_state['df'] = pd.concat([df_p, d], ignore_index=True)
        uloz_data_uzivatele(st.session_state['df'], user, SOUBOR_DATA)
        return True, f"✅ Koupeno: {kusy}x {ticker} za {cena} {mena}"
    else:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {zustatky.get(mena, 0):,.2f})"

def proved_prodej(ticker, kusy, cena, user, mena):
    df_p = st.session_state['df'].copy()
    df_h = st.session_state['df_hist'].copy()
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')

    if df_t.empty or df_t['Pocet'].sum() < kusy:
        return False, "Nedostatek kusů."

    zbyva, zisk, trzba = kusy, 0, kusy * cena

    for idx, row in df_t.iterrows():
        if zbyva <= 0: break
        ukrojeno = min(row['Pocet'], zbyva)
        zisk += (cena - row['Cena']) * ukrojeno
        if ukrojeno == row['Pocet']:
            df_p = df_p.drop(idx)
        else:
            df_p.at[idx, 'Pocet'] -= ukrojeno
        zbyva -= ukrojeno

    new_h = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_h = pd.concat([df_h, new_h], ignore_index=True)
    pohyb_penez(trzba, mena, "Prodej", f"Prodej {ticker}", user)

    st.session_state['df'] = df_p
    st.session_state['df_hist'] = df_h
    uloz_data_uzivatele(df_p, user, SOUBOR_DATA)
    uloz_data_uzivatele(df_h, user, SOUBOR_HISTORIE)
    return True, f"Prodáno! +{trzba:,.2f}"

def proved_smenu(castka, z_meny, do_meny, user):
    kurzy = ziskej_kurzy()
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy.get("CZK", 20.85)
    elif z_meny == "EUR": castka_usd = castka * kurzy.get("EUR", 1.16)

    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurzy.get("CZK", 20.85)
    elif do_meny == "EUR": vysledna = castka_usd / kurzy.get("EUR", 1.16)

    pohyb_penez(-castka, z_meny, "Směna", f"Směna na {do_meny}", user)
    pohyb_penez(vysledna, do_meny, "Směna", f"Směna z {z_meny}", user)
    return True, f"Směněno: {vysledna:,.2f} {do_meny}"

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
    # Tlačítko se pokusíme vygenerovat, ale pokud chybí systémové knihovny (což je časté na cloudu),
    # zobrazíme jen návod na alternativní stažení, abychom uživatele neděsili chybou.
    try:
        import io
        buffer = io.BytesIO()
        # Pokus o renderování
        fig.write_image(buffer, format="png", width=1200, height=800, scale=2)

        st.download_button(
            label=f"⬇️ Stáhnout graf: {filename}",
            data=buffer.getvalue(),
            file_name=f"{filename}.png",
            mime="image/png",
            use_container_width=True
        )
    except Exception:
        # Tichý fallback - pokud to nejde, zobrazíme jen jemný tip místo chyby
        st.caption("💡 Tip: Pro stažení obrázku použij ikonu fotoaparátu 📷, která se objeví v pravém horním rohu grafu po najetí myší.")


# --- HLAVNÍ FUNKCE ---
def main():
    # --- INICIALIZACE ---
    model, AI_AVAILABLE = init_ai()

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
                        if not row.empty and row.iloc[0]['password'] == zasifruj(rk):
                            df_u.at[row.index[0], 'password'] = zasifruj(rnp); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}")
                            st.success("Heslo změněno!")
                        else: st.error("Chyba údajů.")
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
                msg_text = "Příkazy:\n/price [TICKER]\n/buy [TICKER] [KUSY]\n/sell [TICKER] [KUSY]\n/cash"
                msg_icon = "ℹ️"

            elif cmd == "/price" and len(cmd_parts) > 1:
                t_cli = cmd_parts[1].upper()
                p_cli, m_cli, z_cli = ziskej_info(t_cli)
                if p_cli:
                    msg_text = f"💰 {t_cli}: {p_cli:.2f} {m_cli} ({z_cli*100:+.2f}%)"
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
            msg_text = f"❌ Chyba: {str(e)}"
            msg_icon = "⚠️"

        # Uložíme zprávu do session state, aby se zobrazila po reloadu
        if msg_text:
            st.session_state['cli_msg'] = (msg_text, msg_icon)

    # -----------------------------------------------------------

    # --- 2. NAČTENÍ DAT ---
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
    kurzy = ziskej_kurzy()

    # --- 3. VÝPOČTY ---
    all_tickers = []
    viz_data = []
    celk_hod_usd = 0
    celk_inv_usd = 0

    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())

    LIVE_DATA = ziskej_ceny_hromadne(list(set(all_tickers)))
    if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
    if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]

    # --- 3.5. KONTROLA WATCHLISTU (ALERTY) ---
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

    # --- VÝPOČET PORTFOLIA + ZÍSKÁNÍ FUNDAMENTŮ ---
    fundament_data = {}
    if not df.empty:
        tickers_in_portfolio = df['Ticker'].unique().tolist()
        for tkr in tickers_in_portfolio:
            info, _ = ziskej_detail_akcie(tkr)
            fundament_data[tkr] = info

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
                "Kapitalizace": market_cap / 1e9 if market_cap else 0 # Oprava formátování na Miliardy (B)
            })

    vdf = pd.DataFrame(viz_data) if viz_data else pd.DataFrame()

    hist_vyvoje = st.session_state['hist_vyvoje']
    if celk_hod_usd > 0 and pd.notnull(celk_hod_usd):
        hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)

    kurz_czk = kurzy.get("CZK", 20.85)
    celk_hod_czk = celk_hod_usd * kurz_czk
    celk_inv_czk = celk_inv_usd * kurz_czk

    zmena_24h = 0
    pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if pd.notnull(vcera) and vcera > 0:
            zmena_24h = celk_hod_usd - vcera
            pct_24h = (zmena_24h / vcera * 100)

    try:
        cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))
    except Exception: cash_usd = 0

    # --- 4. SIDEBAR ---
    with st.sidebar:
        # Lottie Animation Placeholder - Generic tech loop
        lottie_url = "https://lottie.host/02092823-3932-4467-9d7e-976934440263/3q5XJg2Z2W.json" # Public generic tech URL
        lottie_json = load_lottieurl(lottie_url)
        if lottie_json:
            st_lottie(lottie_json, height=150, key="sidebar_anim")

        # Vlož pod st_lottie(...) a před st.header(...)
        # --- THEME SELECTOR ---
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

        # --- NOVÉ: SVĚTOVÉ TRHY (HODINY) ---
        with st.expander("🌍 SVĚTOVÉ TRHY", expanded=True):
            ny_time, ny_open = zjisti_stav_trhu("America/New_York", 9, 16) # NYSE: 9:30 - 16:00 (zjednodušeno na hodiny)
            ln_time, ln_open = zjisti_stav_trhu("Europe/London", 8, 16) # LSE
            jp_time, jp_open = zjisti_stav_trhu("Asia/Tokyo", 9, 15) # TSE

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇺🇸 New York"); c_m2.markdown(f"**{ny_time}** {'🟢' if ny_open else '🔴'}")

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇬🇧 Londýn"); c_m2.markdown(f"**{ln_time}** {'🟢' if ln_open else '🔴'}")

            c_m1, c_m2 = st.columns([3, 1])
            c_m1.caption("🇯🇵 Tokio"); c_m2.markdown(f"**{jp_time}** {'🟢' if jp_open else '🔴'}")

        st.divider()
        # -----------------------------------

        # --- GAME LEVELING SYSTEM ---
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

        # --- WALLET IN SIDEBAR ---
        st.write("")
        st.caption("Stav peněženky:")
        for mena in ["USD", "CZK", "EUR"]:
            castka = zustatky.get(mena, 0.0)
            sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
            st.info(f"**{castka:,.2f} {sym}**", icon="💰")

        # --- SIDEBAR ALERTS ---
        if alerts:
            st.divider()
            st.error("🔔 CENOVÉ ALERTY!", icon="🔥")
            for a in alerts:
                st.markdown(f"- **{a}**")

        # --- NOVINKA: VELITELSKÁ ŘÁDKA (CLI) - S CALLBACKEM ---
        st.divider()
        st.caption("💻 TERMINÁL (Příkazová řádka)")

        # Zobrazení zprávy z callbacku (pokud existuje z minulé akce)
        if st.session_state.get('cli_msg'):
            txt, ic = st.session_state['cli_msg']
            st.toast(txt, icon=ic)
            st.session_state['cli_msg'] = None # Vyčistit po zobrazení, aby se toast neopakoval

        # Input s callbackem - klíčová změna!
        st.text_input(">", key="cli_cmd", placeholder="/help pro nápovědu", on_change=process_cli_command)
        # ---------------------------------------

        st.divider(); st.subheader("NAVIGACE")
        page = st.radio("Jít na:", ["🏠 Přehled", "👀 Sledování", "📈 Analýza", "📰 Zprávy", "💸 Obchod", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení"], label_visibility="collapsed")

        st.divider()
        if st.button("📧 ODESLAT RANNÍ REPORT", use_container_width=True):
            msg = f"<h2>Report {USER}</h2><p>Jmění: {celk_hod_czk:,.0f} Kč</p>"
            if odeslat_email(st.secrets["email"]["sender"], "Report", msg) == True: st.success("Odesláno!")
            else: st.error("Chyba")

        pdf_data = vytvor_pdf_report(USER, celk_hod_czk, cash_usd, (celk_hod_czk - celk_inv_czk), viz_data)
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

    # --- 5. STRÁNKY ---
    # Zde začíná velký blok, kde každý "elif" musí být na STEJNÉ úrovni
    if page == "🏠 Přehled":
        st.title(f"🏠 PŘEHLED: {USER.upper()}")

        # --- MAKRO KOMPAS (Globální trhy) ---
        st.caption("🧭 GLOBÁLNÍ KOMPAS")
        try:
            # Definice tickerů: S&P500, Zlato, Ropa, Bitcoin, Úrokové sazby
            makro_tickers = {
                "🇺🇸 S&P 500": "^GSPC",
                "🥇 Zlato": "GC=F",
                "🛢️ Ropa": "CL=F",
                "₿ Bitcoin": "BTC-USD",
                "🏦 Úroky 10Y": "^TNX"
            }

            # Stáhneme data hromadně (rychlé)
            makro_data = yf.download(list(makro_tickers.values()), period="5d", progress=False)['Close']

            # Vytvoříme sloupce (5 vedle sebe)
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            cols_list = [mc1, mc2, mc3, mc4, mc5]

            for i, (name, ticker) in enumerate(makro_tickers.items()):
                with cols_list[i]:
                    # Získání dat pro konkrétní ticker
                    # Ošetření MultiIndexu
                    if isinstance(makro_data.columns, pd.MultiIndex):
                        if ticker in makro_data.columns.levels[0]:
                            series = makro_data[ticker].dropna()
                        else:
                            series = pd.Series()
                    else:
                        series = makro_data[ticker].dropna() if ticker in makro_data.columns else pd.Series()

                    if not series.empty:
                        last = series.iloc[-1]
                        prev = series.iloc[-2] if len(series) > 1 else last
                        delta = ((last - prev) / prev) * 100

                        # Barva grafu podle změny
                        line_color = '#238636' if delta >= 0 else '#da3633'

                        # Sparkline graf (zjednodušený)
                        fig_spark = go.Figure(go.Scatter(
                            y=series.values,
                            mode='lines',
                            line=dict(color=line_color, width=2),
                            fill='tozeroy',
                            fillcolor=f"rgba({'35, 134, 54' if delta >= 0 else '218, 54, 51'}, 0.2)"
                        ))
                        fig_spark.update_layout(
                            margin=dict(l=0, r=0, t=0, b=0),
                            height=30,
                            showlegend=False,
                            xaxis=dict(visible=False),
                            yaxis=dict(visible=False),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)'
                        )

                        st.metric(name, f"{last:,.2f}", f"{delta:+.2f}%")
                        fig_spark = make_plotly_cyberpunk(fig_spark)
                        st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
                    else:
                        st.metric(name, "N/A")

        except Exception as e:
            st.error(f"Kompas rozbitý: {e}")

        st.divider()
        # 👆👆👆 KONEC NOVÉHO BLOKU 👆👆👆

        # HLAVNÍ METRIKY
        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("JMĚNÍ (USD)", f"$ {celk_hod_usd:,.0f}", f"{celk_hod_usd-celk_inv_usd:+,.0f} Zisk")
            k2.metric("JMĚNÍ (CZK)", f"{celk_hod_czk:,.0f} Kč", f"{(celk_hod_usd-celk_inv_usd)*kurzy['CZK']:+,.0f} Kč")
            k3.metric("ZMĚNA 24H", f"${zmena_24h:+,.0f}", f"{pct_24h:+.2f}%")
            k4.metric("HOTOVOST (USD)", f"${cash_usd:,.0f}", "Volné")

        # --- AI BODYGUARD (Novinka) ---
        if AI_AVAILABLE:
            st.write("") # Mezera
            if st.button("🛡️ VYŽÁDAT RANNÍ HLÁŠENÍ (AI)", use_container_width=True, type="secondary"):
                with st.spinner("Strážce skenuje perimetr..."):
                    # Kontext pro AI
                    top_mover = best['Ticker'] if 'best' in locals() else "N/A"
                    flop_mover = worst['Ticker'] if 'worst' in locals() else "N/A"

                    prompt_guard = f"""
                    Jsi "Osobní strážce portfolia". Stručně (max 2 věty) zhodnoť situaci pro velitele.
                    DATA:
                    - Celková změna portfolia: {pct_24h:+.2f}%
                    - Hotovost k dispozici: {cash_usd:,.0f} USD
                    - Nejlepší akcie dne: {top_mover}
                    - Nejhorší akcie dne: {flop_mover}

                    INSTRUKCE:
                    - Pokud je trh dole a je hotovost > 1000 USD -> Navrhni nákup.
                    - Pokud je trh nahoře -> Pochval strategii.
                    - Pokud je velký propad -> Uklidni velitele.
                    - Mluv stručně, vojensky/profesionálně, česky.
                    """

                    # --- AI BODYGUARD (Novinka) ---
                    # Voláme novou funkci z ai_brain.py
                    try:
                        # 1. Získáme text od AI
                        guard_res_text = ask_ai_guard(model, pct_24h, cash_usd, top_mover, flop_mover)

                        # 2. Rozhodneme o barvě hlášení podle toho, jestli jsme v plusu
                        if pct_24h >= 0:
                            st.success(f"👮 **HLÁŠENÍ:** {guard_res_text}")
                        else:
                            st.warning(f"👮 **HLÁŠENÍ:** {guard_res_text}")

                    except Exception as e:
                        st.error("Strážce neodpovídá.")

        # --- NOVÉ: SKOKAN A PROPADÁK DNE ---
        if viz_data:
            # Seřadíme data podle % změny (Dnes)
            sorted_data = sorted(viz_data, key=lambda x: x['Dnes'], reverse=True)
            best = sorted_data[0]
            worst = sorted_data[-1]

            st.write("")
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                st.success(f"🚀 SKOKAN DNE: **{best['Ticker']}**")
                st.metric("Změna", f"{best['Dnes']*100:+.2f} %", f"Cena: {best['Cena']:.2f} {best['Měna']}")
            with c_m2:
                st.error(f"💀 PROPADÁK DNE: **{worst['Ticker']}**")
                st.metric("Změna", f"{worst['Dnes']*100:+.2f} %", f"Cena: {worst['Cena']:.2f} {worst['Měna']}")
        # -----------------------------------

        # --- AI PORTFOLIO AUDITOR ---
        if AI_AVAILABLE and viz_data:
            with st.expander("🧠 AI AUDIT PORTFOLIA (Strategie)", expanded=False):
                st.info("AI zanalyzuje tvé rozložení aktiv, rizikovost a navrhne vylepšení.")

                if st.button("🕵️ SPUSTIT HLOUBKOVÝ AUDIT"):
                    with st.spinner("AI počítá rizikové modely..."):
                        # 1. Příprava dat (jen seznam pozic, čísla předáme přímo)
                        port_summary = "\n".join([f"- {i['Ticker']} ({i['Sektor']}): {i['HodnotaUSD']:.0f} USD ({i['Zisk']:.0f} USD zisk)" for i in viz_data])

                        # 2. Volání MOZKU (ai_brain.py)
                        audit_res_text = audit_portfolio(model, celk_hod_usd, cash_usd, port_summary)

                        # 3. Zobrazení výsledku
                        st.markdown("### 📝 VÝSLEDEK AUDITU")
                        st.markdown(audit_res_text)

        st.write("")

        # --- FEAR & GREED INDEX (TACHOMETR) ---
        score, rating = ziskej_fear_greed()
        if score is not None:
            st.subheader(f"😨🤑 TRŽNÍ NÁLADA: {rating} ({score})")
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': "white"},
                    'bgcolor': "black",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, 25], 'color': '#FF4136'},
                        {'range': [25, 45], 'color': '#FF851B'},
                        {'range': [45, 55], 'color': '#AAAAAA'},
                        {'range': [55, 75], 'color': '#7FDBFF'},
                        {'range': [75, 100], 'color': '#2ECC40'}
                    ],
                }
            ))
            fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white", 'family': "Roboto Mono"}, height=250, margin=dict(l=20, r=20, t=30, b=20))
            fig_gauge = make_plotly_cyberpunk(fig_gauge)
            st.plotly_chart(fig_gauge, use_container_width=True)

        st.divider()

        col_graf1, col_graf2 = st.columns([2, 1])

        with col_graf1:
            if not hist_vyvoje.empty:
                st.subheader("🌊 VÝVOJ MAJETKU (CZK)")
                chart_data = hist_vyvoje.copy()
                chart_data['Date'] = pd.to_datetime(chart_data['Date'])
                chart_data['TotalCZK'] = chart_data['TotalUSD'] * kurzy.get("CZK", 20.85)
                fig_area = px.area(chart_data, x='Date', y='TotalCZK', template="plotly_dark", color_discrete_sequence=['#00CC96'])
                fig_area.update_traces(line_color='#00CC96', fillcolor='rgba(0, 204, 150, 0.3)')
                fig_area.update_layout(xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, font_family="Roboto Mono")
                fig_area.update_xaxes(showgrid=False)
                fig_area.update_yaxes(showgrid=True, gridcolor='#30363D')
                fig_area = make_plotly_cyberpunk(fig_area)
                st.plotly_chart(fig_area, use_container_width=True, key="fig_vyvoj_maj")
                add_download_button(fig_area, "vyvoj_majetku")

        with col_graf2:
            if not vdf.empty:
                st.subheader("🍰 SEKTORY")
                fig_pie = px.pie(vdf, values='HodnotaUSD', names='Sektor', hole=0.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=300, paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
                fig_pie = make_plotly_cyberpunk(fig_pie)
                st.plotly_chart(fig_pie, use_container_width=True, key="fig_sektory")
                add_download_button(fig_pie, "sektorova_analyza")

        # --- NOVINKA: SANKEY DIAGRAM (TOK PENĚZ) ---
        st.divider()
        st.subheader("🌊 TOK KAPITÁLU (Sankey)")

        # 1. Příprava dat pro Sankey
        # Zdroje (Odkud peníze přišly)
        total_vklady_czk = 0
        if not df_cash.empty:
            # Sečteme vklady mínus výběry (přibližný přepočet na CZK pro vizualizaci)
            for _, row in df_cash.iterrows():
                cst = row['Castka']
                men = row['Mena']
                val_czk = cst
                if men == "USD": val_czk = cst * kurzy.get("CZK", 20.85)
                elif men == "EUR": val_czk = cst * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))

                if row['Typ'] in ['Vklad', 'Deposit']: total_vklady_czk += val_czk
                elif row['Typ'] in ['Výběr', 'Withdrawal']: total_vklady_czk -= val_czk

        total_divi_czk = 0
        if not df_div.empty:
             for _, r in df_div.iterrows():
                amt = r['Castka']; currency = r['Mena']
                if currency == "USD": total_divi_czk += amt * kurzy.get("CZK", 20.85)
                elif currency == "EUR": total_divi_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                else: total_divi_czk += amt

        # Zisky (Nerealizované + Realizované)
        total_realized_czk = 0
        if not st.session_state['df_hist'].empty:
             for _, r in st.session_state['df_hist'].iterrows():
                 # Zjednodušený odhad realizovaného zisku v CZK
                 zsk = r['Zisk'] # Předpokládáme, že Zisk je v měně obchodu, ale tady to pro vizualizaci zjednodušíme nebo převedeme
                 men = r['Mena']
                 if men == "USD": total_realized_czk += zsk * kurzy.get("CZK", 20.85)
                 elif men == "EUR": total_realized_czk += zsk * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85))
                 else: total_realized_czk += zsk

        unrealized_profit_czk = (celk_hod_czk - celk_inv_czk)
        total_market_profit_czk = total_divi_czk + total_realized_czk + unrealized_profit_czk

        # Cíle (Kde peníze jsou)
        cash_total_czk = cash_usd * kurzy.get("CZK", 20.85)
        stock_total_czk = celk_hod_czk

        # Konstrukce uzlů
        label = ["Vklady (Netto)", "Tržní Zisk & Divi", "MŮJ KAPITÁL", "Hotovost"]
        color = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd"]

        # Přidáme jednotlivé akcie (Top 5 pro přehlednost)
        top_stocks = []
        if not vdf.empty:
            vdf_sorted = vdf.sort_values('HodnotaUSD', ascending=False).head(5)
            for _, row in vdf_sorted.iterrows():
                stock_label = f"Akcie {row['Ticker']}"
                label.append(stock_label)
                color.append("#e377c2") # Barva pro akcie
                top_stocks.append({'label': stock_label, 'value_czk': row['HodnotaUSD'] * kurzy.get("CZK", 20.85)})

        # Jiné akcie (zbytek)
        other_stocks_val_czk = stock_total_czk - sum([s['value_czk'] for s in top_stocks])
        if other_stocks_val_czk > 100: # Jen pokud tam něco zbývá
            label.append("Ostatní Akcie")
            color.append("#7f7f7f")

        # Indexy uzlů
        IDX_VKLADY = 0
        IDX_ZISK = 1
        IDX_KAPITAL = 2
        IDX_CASH = 3
        IDX_FIRST_STOCK = 4

        source = []
        target = []
        value = []

        # Tok 1: Vklady -> Kapitál
        if total_vklady_czk > 0:
            source.append(IDX_VKLADY); target.append(IDX_KAPITAL); value.append(total_vklady_czk)

        # Tok 2: Zisk -> Kapitál (jen pokud jsme v plusu celkově)
        if total_market_profit_czk > 0:
            source.append(IDX_ZISK); target.append(IDX_KAPITAL); value.append(total_market_profit_czk)

        # Tok 3: Kapitál -> Hotovost
        if cash_total_czk > 100: # Filtrujeme drobné
            source.append(IDX_KAPITAL); target.append(IDX_CASH); value.append(cash_total_czk)

        # Tok 4: Kapitál -> Akcie
        current_stock_idx = IDX_FIRST_STOCK
        for s in top_stocks:
            source.append(IDX_KAPITAL); target.append(current_stock_idx); value.append(s['value_czk'])
            current_stock_idx += 1

        if other_stocks_val_czk > 100:
            source.append(IDX_KAPITAL); target.append(current_stock_idx); value.append(other_stocks_val_czk)

        # Vykreslení
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
              pad = 15,
              thickness = 20,
              line = dict(color = "black", width = 0.5),
              label = label,
              color = "rgba(0, 204, 150, 0.6)" # Defaultní barva uzlů
            ),
            link = dict(
              source = source,
              target = target,
              value = value,
              color = "rgba(100, 100, 100, 0.3)" # Průhledná šedá pro toky
          ))])

        fig_sankey.update_layout(title_text="Tok peněz v portfoliu (CZK)", font_size=12, height=400, paper_bgcolor="rgba(0,0,0,0)", font_family="Roboto Mono")
        fig_sankey = make_plotly_cyberpunk(fig_sankey)
        st.plotly_chart(fig_sankey, use_container_width=True)
        # ----------------------------------------

        st.subheader("💰 INVESTOVÁNO DLE MĚN")
        inv_usd, inv_czk, inv_eur = 0, 0, 0
        if viz_data:
            for item in viz_data:
                if item['Měna'] == 'USD': inv_usd += item['Investice']
                elif item['Měna'] == 'CZK': inv_czk += item['Investice']
                elif item['Měna'] == 'EUR': inv_eur += item['Investice']

        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Investováno (USD)", f"${inv_usd:,.0f}")
        ic2.metric("Investováno (CZK)", f"{inv_czk:,.0f} Kč")
        ic3.metric("Investováno (EUR)", f"{inv_eur:,.0f} €")

        st.divider()

        if 'show_portfolio_live' not in st.session_state:
            st.session_state['show_portfolio_live'] = True
        if 'show_cash_history' not in st.session_state:
            st.session_state['show_cash_history'] = False

        col_view1, col_view2, _ = st.columns([1, 1, 3])
        with col_view1:
            st.session_state['show_portfolio_live'] = st.checkbox("Zobrazit Portfolio Tabulku", value=st.session_state['show_portfolio_live'], key="chk_portfolio")
        with col_view2:
            st.session_state['show_cash_history'] = st.checkbox("Zobrazit Historii Hotovosti", value=st.session_state['show_cash_history'], key="chk_cash")
        st.write("")

        if st.session_state['show_portfolio_live']:
            st.subheader("📋 PORTFOLIO LIVE")
            if not vdf.empty:
                # --- PŘÍPRAVA SPARKLINES (MINIGRAFY) ---
                # Hromadné stažení dat pro minigrafy (30 dní)
                tickers_list = vdf['Ticker'].tolist()
                spark_data = {}

                if tickers_list:
                    with st.spinner("Stahuji data pro sparklines..."):
                        try:
                            # Stáhneme data najednou (rychlejší než cyklus)
                            batch_history = yf.download(tickers_list, period="1mo", interval="1d", group_by='ticker', progress=False)

                            for t in tickers_list:
                                # Získání dat pro konkrétní ticker (ošetření multi-indexu vs single indexu)
                                if len(tickers_list) > 1:
                                    if t in batch_history.columns.levels[0]:
                                        closes = batch_history[t]['Close'].dropna().tolist()
                                        spark_data[t] = closes
                                    else:
                                        spark_data[t] = []
                                else:
                                    # Pokud je v portfoliu jen jedna akcie, struktura DF je jiná
                                    closes = batch_history['Close'].dropna().tolist()
                                    spark_data[t] = closes
                        except Exception:
                            pass # Pokud selže stahování, grafy prostě nebudou (safe fail)

                # Přidání sloupce s daty pro graf do dataframe
                vdf['Trend 30d'] = vdf['Ticker'].map(spark_data)
                # ---------------------------------------

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

        if st.session_state['show_cash_history']:
            st.divider()
            st.subheader("🏦 HISTORIE HOTOVOSTI")
            if not df_cash.empty:
                st.dataframe(df_cash.sort_values('Datum', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Historie hotovosti je prázdná.")

    elif page == "👀 Sledování":
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

            # Příprava dat pro Radar
            w_data = []
            tickers_list = df_watch['Ticker'].unique().tolist()

            # Hromadné stažení historie pro RSI (rychlejší než po jednom)
            if tickers_list:
                with st.spinner("Skenuji trh a počítám indikátory..."):
                    try:
                        batch_data = yf.download(tickers_list, period="3mo", group_by='ticker', progress=False)
                    except: batch_data = pd.DataFrame()

            # Procházíme sledované akcie
            for _, r in df_watch.iterrows():
                tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']

                # Získání live ceny a info
                inf = LIVE_DATA.get(tk, {})
                price = inf.get('price')
                cur = inf.get('curr', 'USD')

                # Fallback pro měnu
                if tk.upper().endswith(".PR"): cur = "CZK"
                elif tk.upper().endswith(".DE"): cur = "EUR"

                if not price:
                    price, _, _ = ziskej_info(tk)

                # Výpočet RSI
                rsi_val = 50 # Default neutral
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
                year_low = 0; year_high = 0; range_pos = 0.5
                try:
                    t_obj = yf.Ticker(tk)
                    year_low = t_obj.fast_info.year_low
                    year_high = t_obj.fast_info.year_high
                    if price and year_high > year_low:
                        range_pos = (price - year_low) / (year_high - year_low)
                        range_pos = max(0.0, min(1.0, range_pos))
                except: pass

                # --- NOVÁ LOGIKA SNIPERA (ZAMĚŘOVAČ) ---
                status_text = "💤 Wait"
                proximity_score = 0.0 # 0 = Daleko, 1 = Cíl zasažen

                if price and price > 0:
                    # Logika pro NÁKUP (Chceme, aby cena klesla k TargetBuy)
                    if buy_trg > 0:
                        if price <= buy_trg:
                            status_text = "🔥 BUY NOW"
                            proximity_score = 1.0 # Plný zásah
                        else:
                            # Pokud je cena do 20% nad cílem, začne se bar plnit
                            diff_pct = (price - buy_trg) / price
                            if diff_pct > 0.20: proximity_score = 0.0
                            else:
                                proximity_score = 1.0 - (diff_pct / 0.20)
                                status_text = f"Blíží se ({diff_pct*100:.1f}%)"

                    # Logika pro PRODEJ (Chceme, aby cena rostla k TargetSell)
                    elif sell_trg > 0:
                        if price >= sell_trg:
                            status_text = "💰 SELL NOW"
                            proximity_score = 1.0
                        else:
                            # Pokud je cena do 20% pod cílem
                            diff_pct = (sell_trg - price) / price
                            if diff_pct > 0.20: proximity_score = 0.0
                            else:
                                proximity_score = 1.0 - (diff_pct / 0.20)
                                status_text = f"Blíží se ({diff_pct*100:.1f}%)"

                # ULOŽENÍ DO DAT (Tohle jsi tam předtím neměl!)
                w_data.append({
                    "Symbol": tk,
                    "Cena": price,
                    "Měna": cur,
                    "RSI (14)": rsi_val,
                    "52T Range": range_pos,
                    "Cíl Buy": buy_trg,
                    "Zaměřovač": proximity_score, # <--- TADY JE TEN BENZÍN!
                    "Status": status_text
                })

            wdf = pd.DataFrame(w_data)

            if not wdf.empty:
                st.dataframe(
                    wdf,
                    column_config={
                        "Cena": st.column_config.NumberColumn(format="%.2f"),
                        "Cíl Buy": st.column_config.NumberColumn(format="%.2f"),
                        "RSI (14)": st.column_config.NumberColumn(
                            "RSI Indikátor",
                            help="< 30: Přeprodáno (Levné) | > 70: Překoupeno (Drahé)",
                            format="%.0f",
                        ),
                        "52T Range": st.column_config.ProgressColumn(
                            "Roční Rozsah",
                            help="Vlevo = Low, Vpravo = High",
                            min_value=0, max_value=1, format=""
                        ),
                        # 👇👇👇 NOVÝ SLOUPEC ZAMĚŘOVAČ 👇👇👇
                        "Zaměřovač": st.column_config.ProgressColumn(
                            "🎯 Vzdálenost k cíli",
                            help="Jak blízko je cena k tvému limitu? (Plný = Akce!)",
                            min_value=0,
                            max_value=1,
                            format="" # Schováme čísla, chceme jen vizuál
                        )
                    },
                    # Přidáme "Zaměřovač" do pořadí sloupců
                    column_order=["Symbol", "Cena", "Cíl Buy", "Zaměřovač", "Status", "RSI (14)", "52T Range", "Měna"],
                    use_container_width=True,
                    hide_index=True
                )

                # Legenda k RSI
                st.caption("💡 **RSI Legenda:** Hodnoty pod **30** značí přeprodanost (možný odraz nahoru 📈). Hodnoty nad **70** značí překoupenost (možná korekce dolů 📉).")

            st.divider()
            c_del1, c_del2 = st.columns([3, 1])
            with c_del2:
                to_del = st.selectbox("Vyber pro smazání:", df_watch['Ticker'].unique())
                if st.button("🗑️ Smazat ze sledování", use_container_width=True):
                    odebrat_z_watchlistu(to_del, USER); st.rerun()
        else:
            st.info("Zatím nic nesleduješ. Přidej první akcii nahoře.")

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
                    # --- POUŽITÍ NOVÉ FUNKCE proved_nakup ---
                    _, m, _ = ziskej_info(t)
                    # Pokud uživatel nezadal cenu (0), zkusíme ji stáhnout
                    final_c = c if c > 0 else ziskej_info(t)[0]

                    if final_c and final_c > 0:
                        ok, msg = proved_nakup(t, k, final_c, USER)
                        if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error(msg)
                    else:
                        st.error("Nepodařilo se získat cenu. Zadej ji ručně.")
                    # ----------------------------------------
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
                if st.button("VLOŽIT"): pohyb_penez(v_a, v_m, "Vklad", "Man", USER); st.rerun()
                if st.button("VYBRAT"): pohyb_penez(-v_a, v_m, "Výběr", "Man", USER); st.rerun()
            with c2:
                st.dataframe(df_cash.sort_values('Datum', ascending=False).head(10), use_container_width=True, hide_index=True)

    elif page == "💎 Dividendy":
        st.title("💎 DIVIDENDOVÝ KALENDÁŘ")

        # --- NOVINKA: PROJEKTOR PASIVNÍHO PŘÍJMU ---
        est_annual_income_czk = 0
        if viz_data:
            for item in viz_data:
                # Výpočet: Hodnota pozice * Dividend Yield
                # viz_data má HodnotaUSD a Divi (v desítkovém tvaru, např. 0.05 pro 5%)
                yield_val = item.get('Divi', 0)
                val_usd = item.get('HodnotaUSD', 0)
                if yield_val > 0 and val_usd > 0:
                    est_annual_income_czk += (val_usd * yield_val) * kurzy.get("CZK", 20.85)

        est_monthly_income_czk = est_annual_income_czk / 12

        with st.container(border=True):
            st.subheader("🔮 PROJEKTOR PASIVNÍHO PŘÍJMU")
            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("Očekávaný roční příjem", f"{est_annual_income_czk:,.0f} Kč", help="Hrubý odhad na základě aktuálního dividendového výnosu držených akcií.")
            cp2.metric("Měsíční průměr", f"{est_monthly_income_czk:,.0f} Kč", help="Kolik to dělá měsíčně k dobru.")

            # Svoboda Levels
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
                    # Pokud splněno, progress je 100% pro tento level
                    pass

            if est_monthly_income_czk > 15000:
                next_goal = "Finanční Svoboda 🏖️"
                progress = 1.0

            cp3.caption(f"Cíl: **{next_goal}**")
            cp3.progress(progress)

        st.divider()
        # -------------------------------------------

        # 1. Metriky
        total_div_czk = 0
        if not df_div.empty:
            for _, r in df_div.iterrows():
                amt = r['Castka']; currency = r['Mena']
                if currency == "USD": total_div_czk += amt * kurzy.get("CZK", 20.85)
                elif currency == "EUR": total_div_czk += amt * (kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85)) # approx
                else: total_div_czk += amt

        st.metric("CELKEM VYPLACENO (CZK)", f"{total_div_czk:,.0f} Kč")

        t_div1, t_div2 = st.tabs(["HISTORIE & GRAF", "PŘIDAT DIVIDENDU"])

        with t_div1:
            if not df_div.empty:
                # Graf - OPRAVA VIZUALIZACE
                # Vytvoříme pomocný dataframe jen pro graf
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

    elif page == "📈 Analýza":
        st.title("📈 HLOUBKOVÁ ANALÝZA")
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["🔍 RENTGEN", "⚔️ SOUBOJ", "🗺️ MAPA & SEKTORY", "🔮 VĚŠTEC", "🏆 BENCHMARK", "💱 MĚNY", "⚖️ REBALANCING", "📊 KORELACE", "📅 KALENDÁŘ"])

        with tab1:
            st.write("")
            vybrana_akcie = st.selectbox("Vyber firmu:", df['Ticker'].unique() if not df.empty else [])
            if vybrana_akcie:
                with st.spinner(f"Načítám data pro {vybrana_akcie}..."):
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

                            # --- NOVÉ FUNDAMENTY ---
                            profit_margin = t_info.get('profitMargins', 0)
                            roe = t_info.get('returnOnEquity', 0)
                            rev_growth = t_info.get('revenueGrowth', 0)
                            debt_equity = t_info.get('debtToEquity', 0)

                            # --- NOVÉ VLASTNICTVÍ ---
                            insiders = t_info.get('heldPercentInsiders', 0)
                            institutions = t_info.get('heldPercentInstitutions', 0)
                            public = max(0, 1.0 - insiders - institutions) # Zbytek je veřejnost
                            # ----------------------

                            if (not summary or summary == "MISSING_SUMMARY" or "Yahoo" in summary) and AI_AVAILABLE:
                                try:
                                    prompt_desc = f"Napíš krátký popis (max 2 věty) pre firmu {vybrana_akcie} v češtině. Jde o investiční aplikaci."
                                    res_desc = model.generate_content(prompt_desc)
                                    summary = f"🤖 AI Shrnutí: {res_desc.text}"
                                except: summary = "Popis není k dispozici."
                            elif not summary or "Yahoo" in summary: summary = "Popis není k dispozici."

                            c_d1, c_d2 = st.columns([1, 3])
                            with c_d1:
                                if recommendation != "N/A":
                                    barva_rec = "green" if "BUY" in recommendation else ("red" if "SELL" in recommendation else "orange")
                                    st.markdown(f"### :{barva_rec}[{recommendation}]")
                                    st.caption("Názor analytiků")
                                else:
                                    st.markdown("### 🤷‍♂️ Neznámé"); st.caption("Bez doporučení")

                                if target_price > 0: st.metric("Cílová cena", f"{target_price} {currency}")
                                else: st.metric("Cílová cena", "---")

                                if pe_ratio > 0: st.metric("P/E Ratio", f"{pe_ratio:.2f}")
                                else: st.metric("P/E Ratio", "---")

                            with c_d2:
                                col_h1, col_h2 = st.columns([3, 1])
                                with col_h1: st.subheader(long_name)
                                with col_h2:
                                    if current_price > 0: st.metric("Cena", f"{current_price:,.2f} {currency}")
                                st.info(summary)
                                if t_info and t_info.get('website'): st.link_button("🌍 Web firmy", t_info.get('website'))
                                else: st.link_button("🔍 Hledat na Google", f"https://www.google.com/search?q={vybrana_akcie}+stock")

                            st.divider()
                            st.subheader("🧬 FUNDAMENTÁLNÍ RENTGEN (Zdraví firmy)")
                            fc1, fc2, fc3, fc4 = st.columns(4)
                            fc1.metric("Zisková marže", f"{profit_margin*100:.1f} %", help="Kolik % z tržeb zůstane jako čistý zisk.")
                            fc2.metric("ROE (Efektivita)", f"{roe*100:.1f} %", help="Návratnost vlastního kapitálu. Nad 15 % je super.")
                            fc3.metric("Růst tržeb (YoY)", f"{rev_growth*100:.1f} %", help="Meziroční růst příjmů.")
                            fc4.metric("Dluh / Vlastní jmění", f"{debt_equity:.2f}", help="Poměr dluhu k majetku akcionářů. Pod 1.0 je bezpečné, nad 2.0 rizikové.")

                            # --- NOVÉ: VELRYBÍ RADAR (GRAF VLASTNICTVÍ) ---
                            st.write("")
                            st.subheader("🐳 VELRYBÍ RADAR (Kdo to vlastní?)")

                            own_col1, own_col2 = st.columns([1, 2])
                            with own_col1:
                                st.metric("🏦 Instituce (Fondy)", f"{institutions*100:.1f} %", help="Banky, hedge fondy, penzijní fondy. 'Smart Money'.")
                                st.metric("👔 Insideři (Vedení)", f"{insiders*100:.1f} %", help="Lidé z vedení firmy. Vysoké číslo = věří si.")

                            with own_col2:
                                own_df = pd.DataFrame({
                                    "Kdo": ["Instituce 🏦", "Insideři 👔", "Veřejnost 👥"],
                                    "Podíl": [institutions, insiders, public]
                                })
                                fig_own = px.pie(own_df, values='Podíl', names='Kdo', hole=0.6,
                                                 color='Kdo',
                                                 color_discrete_map={"Instituce 🏦": "#58A6FF", "Insideři 👔": "#238636", "Veřejnost 👥": "#8B949E"},
                                                 template="plotly_dark")
                                fig_own.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", showlegend=True, legend=dict(y=0.5))
                                fig_own.update_traces(textinfo='percent+label', textposition='outside')
                                fig_own = make_plotly_cyberpunk(fig_own)
                                st.plotly_chart(fig_own, use_container_width=True)


                            st.write("")
                            st.subheader("📊 HISTORIE VÝSLEDKŮ (Rostou, nebo stagnují?)")

                            try:
                                with st.spinner("Stahuji účetní výkazy..."):
                                    # Získáme čerstvé finanční výkazy přímo z Yahoo
                                    stock_obj = yf.Ticker(vybrana_akcie)
                                    financials = stock_obj.financials

                                    if financials is not None and not financials.empty:
                                        # Transpozice (otočení tabulky), aby roky byly řádky
                                        fin_T = financials.T
                                        # Seřadíme od nejstaršího po nejnovější
                                        fin_T = fin_T.sort_index()

                                        # Zkusíme najít klíčové sloupce (Yahoo občas mění názvy)
                                        col_rev = next((c for c in fin_T.columns if 'Total Revenue' in c or 'TotalRevenue' in c), None)
                                        col_inc = next((c for c in fin_T.columns if 'Net Income' in c or 'NetIncome' in c), None)

                                        if col_rev and col_inc:
                                            # Vytvoření dat pro graf
                                            plot_data = pd.DataFrame({
                                                "Rok": fin_T.index.strftime('%Y'),
                                                "Tržby (Revenue)": fin_T[col_rev],
                                                "Čistý Zisk (Income)": fin_T[col_inc]
                                            })

                                            # Převod na "Long format" pro Plotly (aby šlo udělat Grouped Bar)
                                            plot_melted = plot_data.melt(id_vars="Rok", var_name="Metrika", value_name="Hodnota")

                                            # Vykreslení grafu
                                            fig_fin = px.bar(plot_melted, x="Rok", y="Hodnota", color="Metrika",
                                                             barmode="group",
                                                             title=f"Tržby vs. Zisk: {vybrana_akcie}",
                                                             color_discrete_map={"Tržby (Revenue)": "#58A6FF", "Čistý Zisk (Income)": "#238636"},
                                                             template="plotly_dark")

                                            fig_fin.update_layout(
                                                xaxis_title="",
                                                yaxis_title="USD",
                                                legend=dict(orientation="h", y=1.1),
                                                paper_bgcolor="rgba(0,0,0,0)",
                                                plot_bgcolor="rgba(0,0,0,0)",
                                                font_family="Roboto Mono",
                                                height=350
                                            )

                                            # Formátování osy Y na miliardy (B) nebo miliony (M)
                                            fig_fin.update_yaxes(tickprefix="$")
                                            fig_fin = make_plotly_cyberpunk(fig_fin)
                                            st.plotly_chart(fig_fin, use_container_width=True)

                                            # Rychlý AI komentář k trendu (Bezpečnější verze)
                                            try:
                                                last_rev = plot_data["Tržby (Revenue)"].iloc[-1]
                                                first_rev = plot_data["Tržby (Revenue)"].iloc[0]

                                                # Ověříme, že máme čísla a ne nuly/NaN
                                                if pd.notnull(last_rev) and pd.notnull(first_rev) and first_rev != 0:
                                                    growth = ((last_rev / first_rev) - 1) * 100

                                                    if growth > 20:
                                                        st.success(f"🚀 **Růstová mašina:** Tržby za zobrazené období vzrostly o {growth:.1f} %.")
                                                    elif growth > 0:
                                                        st.info(f"⚖️ **Stabilita:** Mírný růst tržeb o {growth:.1f} %.")
                                                    else:
                                                        st.error(f"⚠️ **Varování:** Tržby klesají ({growth:.1f} %).")
                                                else:
                                                    st.info("ℹ️ Data pro výpočet růstu nejsou kompletní.")
                                            except:
                                                st.info("ℹ️ Nelze automaticky vyhodnotit trend.")
                                        else:
                                            st.warning("Data o tržbách nejsou v databázi dostupná pod standardními názvy.")
                                    else:
                                        st.info("Pro tuto firmu nejsou detailní finanční výkazy k dispozici (často u ETF).")
                            except Exception as e:
                                st.warning(f"Nepodařilo se načíst graf výsledků ({e})")

                            st.divider()
                            # -----------------------------------------------

                            if target_price > 0 and current_price > 0:
                                st.divider()
                                st.subheader("🎯 CÍL ANALYTIKŮ (Upside Potential)")
                                fig_target = go.Figure(go.Indicator(
                                    mode = "gauge+number+delta",
                                    value = current_price,
                                    domain = {'x': [0, 1], 'y': [0, 1]},
                                    title = {'text': f"Cena vs Cíl ({target_price} {currency})", 'font': {'size': 14}},
                                    delta = {'reference': target_price, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
                                    gauge = {
                                        'axis': {'range': [0, target_price * 1.5], 'tickwidth': 1, 'tickcolor': "white"},
                                        'bar': {'color': "#58A6FF"},
                                        'bgcolor': "black",
                                        'borderwidth': 2,
                                        'bordercolor': "gray",
                                        'threshold': {
                                            'line': {'color': "yellow", 'width': 4},
                                            'thickness': 0.75,
                                            'value': target_price
                                        }
                                    }
                                ))
                                fig_target.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white", 'family': "Roboto Mono"}, height=250)
                                fig_target = make_plotly_cyberpunk(fig_target)
                                st.plotly_chart(fig_target, use_container_width=True)

                            st.divider()
                            st.subheader(f"📈 PROFESIONÁLNÍ CHART: {vybrana_akcie}")

                            if hist_data is not None and not hist_data.empty:
                                # --- OVLÁDÁNÍ GRAFU (Interaktivita) ---
                                c_ch1, c_ch2, c_ch3, c_ch4, c_ch5 = st.columns(5)
                                show_sma = c_ch1.checkbox("SMA (Průměry)", value=True)
                                show_bb = c_ch2.checkbox("Bollinger Bands", value=True)
                                show_rsi = c_ch3.checkbox("RSI", value=True)
                                show_macd = c_ch4.checkbox("MACD (Trend)", value=True)
                                show_vol = c_ch5.checkbox("Volume (Objem)", value=True)
                                # --------------------------------------

                                # --- 1. VÝPOČTY INDIKÁTORŮ ---
                                # Bollinger Bands
                                hist_data['BB_Middle'] = hist_data['Close'].rolling(window=20).mean()
                                hist_data['BB_Std'] = hist_data['Close'].rolling(window=20).std()
                                hist_data['BB_Upper'] = hist_data['BB_Middle'] + (hist_data['BB_Std'] * 2)
                                hist_data['BB_Lower'] = hist_data['BB_Middle'] - (hist_data['BB_Std'] * 2)

                                # RSI
                                delta = hist_data['Close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                                rs = gain / loss
                                hist_data['RSI'] = 100 - (100 / (1 + rs))

                                # SMA
                                hist_data['SMA20'] = hist_data['Close'].rolling(window=20).mean()
                                hist_data['SMA50'] = hist_data['Close'].rolling(window=50).mean()

                                # MACD (Novinka)
                                exp12 = hist_data['Close'].ewm(span=12, adjust=False).mean()
                                exp26 = hist_data['Close'].ewm(span=26, adjust=False).mean()
                                hist_data['MACD'] = exp12 - exp26
                                hist_data['Signal'] = hist_data['MACD'].ewm(span=9, adjust=False).mean()
                                hist_data['MACD_Hist'] = hist_data['MACD'] - hist_data['Signal']

                                # --- 2. PŘÍPRAVA DAT PRO AI ---
                                valid_data = hist_data.dropna(subset=['SMA50'])
                                if not valid_data.empty:
                                    last_row = valid_data.iloc[-1]
                                else:
                                    last_row = hist_data.iloc[-1]

                                current_price_scan = last_row['Close']
                                rsi_scan = last_row['RSI']
                                sma20_scan = last_row['SMA20']
                                sma50_scan = last_row['SMA50']
                                bb_upper_scan = last_row['BB_Upper']
                                bb_lower_scan = last_row['BB_Lower']
                                # ----------------------------------------

                                # --- 3. VYKRESLENÍ GRAFU (DYNAMIC ROWS) ---
                                # Určení počtu řádků podle vybraných indikátorů
                                rows_specs = [[{"rowspan": 1}]] # Cena je vždy
                                row_heights = [0.5] # Cena zabere 50%
                                current_row = 2

                                if show_vol:
                                    rows_specs.append([{"rowspan": 1}])
                                    row_heights.append(0.15)
                                if show_rsi:
                                    rows_specs.append([{"rowspan": 1}])
                                    row_heights.append(0.15)
                                if show_macd:
                                    rows_specs.append([{"rowspan": 1}])
                                    row_heights.append(0.20)

                                # Normalizace výšek, aby součet byl 1.0 (pokud ne, plotly si poradí, ale pro jistotu)
                                total_h = sum(row_heights)
                                row_heights = [h/total_h for h in row_heights]

                                fig_candle = make_subplots(
                                    rows=len(row_heights),
                                    cols=1,
                                    shared_xaxes=True,
                                    vertical_spacing=0.02,
                                    row_heights=row_heights
                                )

                                # --- HLAVNÍ GRAF (Cena) ---
                                fig_candle.add_trace(go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], name=vybrana_akcie), row=1, col=1)

                                if show_bb:
                                    fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['BB_Upper'], mode='lines', name='BB Upper', line=dict(color='gray', width=1), showlegend=False), row=1, col=1)
                                    fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['BB_Lower'], mode='lines', name='BB Lower', line=dict(color='gray', width=1), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.05)', showlegend=False), row=1, col=1)

                                if show_sma:
                                    fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['SMA20'], mode='lines', name='SMA 20', line=dict(color='orange', width=1.5)), row=1, col=1)
                                    fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['SMA50'], mode='lines', name='SMA 50', line=dict(color='cyan', width=1.5)), row=1, col=1)

                                # Osobní hladiny (Buy/Sell targets) - přidáme vždy
                                user_watch = df_watch[df_watch['Ticker'] == vybrana_akcie]
                                if not user_watch.empty:
                                    tg_buy = user_watch.iloc[0]['TargetBuy']; tg_sell = user_watch.iloc[0]['TargetSell']
                                    if tg_buy > 0: fig_candle.add_hline(y=tg_buy, line_dash="dot", line_color="#238636", row=1, col=1, annotation_text="BUY CÍL")
                                    if tg_sell > 0: fig_candle.add_hline(y=tg_sell, line_dash="dot", line_color="#da3633", row=1, col=1, annotation_text="SELL CÍL")

                                next_plot_row = 2

                                # --- VOLUME (Objem) ---
                                if show_vol:
                                    colors = ['#238636' if c >= o else '#da3633' for c, o in zip(hist_data['Close'], hist_data['Open'])]
                                    fig_candle.add_trace(go.Bar(x=hist_data.index, y=hist_data['Volume'], name='Volume', marker_color=colors), row=next_plot_row, col=1)
                                    fig_candle.update_yaxes(title_text="Vol", row=next_plot_row, col=1, showgrid=False)
                                    next_plot_row += 1

                                # --- RSI ---
                                if show_rsi:
                                    fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['RSI'], mode='lines', name='RSI', line=dict(color='#A56CC1', width=2)), row=next_plot_row, col=1)
                                    fig_candle.add_hline(y=70, line_dash="dot", line_color="red", row=next_plot_row, col=1)
                                    fig_candle.add_hline(y=30, line_dash="dot", line_color="green", row=next_plot_row, col=1)
                                    fig_candle.update_yaxes(title_text="RSI", row=next_plot_row, col=1, range=[0, 100], showgrid=True, gridcolor='#30363D')
                                    next_plot_row += 1

                                # --- MACD ---
                                if show_macd:
                                    # Histogram colors
                                    hist_colors = ['#238636' if h >= 0 else '#da3633' for h in hist_data['MACD_Hist']]
                                    fig_candle.add_trace(go.Bar(x=hist_data.index, y=hist_data['MACD_Hist'], name='MACD Hist', marker_color=hist_colors), row=next_plot_row, col=1)
                                    fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['MACD'], mode='lines', name='MACD', line=dict(color='#58A6FF', width=1.5)), row=next_plot_row, col=1)
                                    fig_candle.add_trace(go.Scatter(x=hist_data.index, y=hist_data['Signal'], mode='lines', name='Signal', line=dict(color='orange', width=1.5)), row=next_plot_row, col=1)
                                    fig_candle.update_yaxes(title_text="MACD", row=next_plot_row, col=1, showgrid=True, gridcolor='#30363D')
                                    next_plot_row += 1

                                fig_candle.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=800, margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), font_family="Roboto Mono")
                                fig_candle.update_yaxes(showgrid=True, gridcolor='#30363D')
                                fig_candle.update_xaxes(showgrid=False)
                                fig_candle = make_plotly_cyberpunk(fig_candle)
                                st.plotly_chart(fig_candle, use_container_width=True)
                                add_download_button(fig_candle, f"rentgen_{vybrana_akcie}")

                                # --- NOVÁ FUNKCE: AI TECHNICKÁ ANALÝZA ---
                                if AI_AVAILABLE:
                                    st.divider()
                                if st.button(f"🤖 SPUSTIT AI TECHNICKOU ANALÝZU PRO {vybrana_akcie}", type="primary"):
                                    with st.spinner(f"AI analyzuje indikátory pro {vybrana_akcie}..."):
                                        # 1. Zavoláme funkci z ai_brain.py
                                        tech_res_text = get_tech_analysis(model, vybrana_akcie, last_row)

                                        # 2. Zobrazíme výsledek
                                        st.markdown(f"""
                                        <div style="background-color: #0D1117; border: 1px solid #30363D; border-radius: 10px; padding: 20px; margin-top: 10px;">
                                            <h3 style="color: #58A6FF; margin-top: 0;">🤖 AI VERDIKT: {vybrana_akcie}</h3>
                                            {tech_res_text}
                                        </div>
                                        """, unsafe_allow_html=True)

                            else: st.warning("Graf historie není k dispozici.")
                        except Exception as e: st.error(f"Chyba zobrazení rentgenu: {e}")
                    else: st.error("Nepodařilo se načíst data o firmě.")

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
                                paper_bgcolor="rgba(0,0,0,0)"
                            )
                            fig_multi_comp.update_xaxes(showgrid=False)
                            fig_multi_comp.update_yaxes(showgrid=True, gridcolor='#30363D')
                            fig_multi_comp = make_plotly_cyberpunk(fig_multi_comp)
                            st.plotly_chart(fig_multi_comp, use_container_width=True, key="fig_srovnani")
                            add_download_button(fig_multi_comp, "srovnani_akcii")

                            st.divider()
                            st.subheader("Detailní srovnání metrik")

                            comp_list = []
                            for t in tickers_to_compare[:2]:
                                i, h = ziskej_detail_akcie(t)
                                if i:
                                    mc = i.get('marketCap', 0)
                                    pe = i.get('trailingPE', 0)
                                    dy = i.get('dividendYield', 0)
                                    perf = ((h['Close'].iloc[-1] / h['Close'].iloc[0]) - 1) * 100 if h is not None and not h.empty and h['Close'].iloc[0] != 0 else 0

                                    comp_list.append({
                                        "Metrika": [f"Kapitalizace {t}", f"P/E Ratio {t}", f"Dividenda {t}", f"Změna 1R {t}"],
                                        "Hodnota": [
                                            f"${mc/1e9:.1f}B",
                                            f"{pe:.2f}" if pe > 0 else "N/A",
                                            f"{dy*100:.2f}%" if dy else "0%",
                                            f"{perf:+.2f}%"
                                        ]
                                    })

                            if len(comp_list) >= 2:
                                comp_data = {
                                    "Metrika": ["Kapitalizace", "P/E Ratio", "Dividenda", "Změna 1R"],
                                    tickers_to_compare[0]: [comp_list[0]['Hodnota'][i] for i in range(4)],
                                    tickers_to_compare[1]: [comp_list[1]['Hodnota'][i] for i in range(4)]
                                }
                                st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)
                            elif tickers_to_compare:
                                st.info(f"Pro detailní srovnávací tabulku (metriky P/E, Kapitalizace) vyberte alespoň 2 akcie.")

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
                            treemap_fig = make_plotly_cyberpunk(treemap_fig)
                        except Exception:
                            pass

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
                                try:
                                    line_fig = make_plotly_cyberpunk(line_fig)
                                except Exception:
                                    pass

                                st.plotly_chart(line_fig, use_container_width=True, key="fig_vyvoj_ceny")
                                add_download_button(line_fig, "vyvoj_ceny")
                            except Exception:
                                st.warning("Nepodařilo se vykreslit graf vývoje ceny.")
                except Exception:
                    st.error("Chyba mapy.")
            else:
                st.info("Portfolio je prázdné.")

        with tab4:
            st.subheader("🔮 FINANČNÍ STROJ ČASU")

            # --- AI PREDIKCE (Neuro-Věštec) ---

            with st.expander("🤖 AI PREDIKCE (Neuro-Věštec)", expanded=False):
                st.info("Experimentální modul využívající model Prophet (Meta/Facebook) k predikci budoucího trendu.")

                c_ai1, c_ai2 = st.columns(2)
                with c_ai1:
                    # Výběr aktiva - předvyplníme Bitcoin, protože ten je pro predikce nejzábavnější
                    pred_ticker = st.text_input("Ticker pro predikci:", value="BTC-USD").upper()
                with c_ai2:
                    pred_days = st.slider("Predikce na (dny):", 7, 90, 30)

                if st.button("🧠 AKTIVOVAT NEURONOVOU SÍŤ", type="primary"):
                    try:
                        # Importujeme Prophet až tady uvnitř, aby to nebrzdilo start celé aplikace
                        from prophet import Prophet

                        with st.spinner(f"Trénuji model na datech {pred_ticker}... (Může to trvat)"):
                            # 1. Stáhneme maximum dat pro trénink (aspoň 2 roky)
                            hist_train = yf.download(pred_ticker, period="2y", progress=False)

                            if not hist_train.empty:
                                # 2. Příprava dat do formátu pro Prophet (ds = datum, y = hodnota)
                                # Ošetření pro různé verze yfinance (MultiIndex vs SingleIndex)
                                if isinstance(hist_train.columns, pd.MultiIndex):
                                    y_data = hist_train['Close'].iloc[:, 0]
                                else:
                                    y_data = hist_train['Close']

                                # Odstraníme časové zóny (tz_localize(None)), Prophet je nemá rád
                                df_prophet = pd.DataFrame({
                                    'ds': y_data.index.tz_localize(None),
                                    'y': y_data.values
                                })

                                # 3. Trénink modelu (Fit)
                                m = Prophet(daily_seasonality=True)
                                m.fit(df_prophet)

                                # 4. Budoucnost (Make Future)
                                future = m.make_future_dataframe(periods=pred_days)
                                forecast = m.predict(future)

                                # 5. Vizualizace
                                st.divider()
                                st.subheader(f"🔮 Predikce pro {pred_ticker} na {pred_days} dní")

                                # Vytáhneme dnešní a budoucí cenu z predikce
                                last_price = df_prophet['y'].iloc[-1]
                                future_price = forecast['yhat'].iloc[-1]
                                diff_pred = future_price - last_price
                                pct_pred = (diff_pred / last_price) * 100

                                # Verdikt v metrice
                                col_res1, col_res2 = st.columns(2)
                                with col_res1:
                                    st.metric("Poslední známá cena", f"{last_price:,.2f}")
                                with col_res2:
                                    st.metric(f"Predikce (+{pred_days} dní)", f"{future_price:,.2f}", f"{pct_pred:+.2f} %")

                                # Graf s "intervalem jistoty"
                                fig_pred = go.Figure()

                                # Historie (Šedá)
                                fig_pred.add_trace(go.Scatter(x=df_prophet['ds'], y=df_prophet['y'], name='Historie', line=dict(color='gray')))

                                # Predikce (Modrá) - ukážeme jen tu budoucí část
                                future_part = forecast[forecast['ds'] > df_prophet['ds'].iloc[-1]]
                                fig_pred.add_trace(go.Scatter(x=future_part['ds'], y=future_part['yhat'], name='Predikce', line=dict(color='#58A6FF', width=3)))

                                # Horní a dolní hranice (Stín nejistoty)
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

            # --- DCA BACKTESTER ---

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
                            # 1. Stažení historických dat
                            start_date_dca = datetime.now() - timedelta(days=dca_years*365)
                            # Stáhneme data s měsíčním intervalem, abychom simulovali výplatu
                            # Interval '1mo' nám dá cenu vždy k začátku/konci měsíce
                            dca_hist = yf.download(dca_ticker, start=start_date_dca, interval="1mo", progress=False)

                            if not dca_hist.empty:
                                # Ošetření MultiIndexu (pokud by yfinance zlobilo)
                                if isinstance(dca_hist.columns, pd.MultiIndex):
                                    close_prices = dca_hist['Close'].iloc[:, 0]
                                else:
                                    close_prices = dca_hist['Close']

                                # Vyhodíme prázdné řádky (NaN)
                                close_prices = close_prices.dropna()

                                # Získání měny pro přepočet (zjednodušeně)
                                is_czk_stock = ".PR" in dca_ticker
                                conversion_rate = 1.0 if is_czk_stock else kurzy.get("CZK", 21) # Použijeme tvůj fixní kurz nebo načtený

                                total_invested_czk = 0
                                total_shares = 0
                                portfolio_evolution = []

                                # Simulace měsíc po měsíci
                                for date, price in close_prices.items():
                                    price_czk = price * conversion_rate

                                    # Nákup za měsíční vklad
                                    shares_bought = dca_amount / price_czk
                                    total_shares += shares_bought
                                    total_invested_czk += dca_amount

                                    # Aktuální hodnota v daném měsíci
                                    current_value = total_shares * price_czk

                                    portfolio_evolution.append({
                                        "Datum": date,
                                        "Hodnota portfolia": current_value,
                                        "Vloženo celkem": total_invested_czk
                                    })

                                # Výsledek
                                dca_df = pd.DataFrame(portfolio_evolution).set_index("Datum")
                                final_val = dca_df["Hodnota portfolia"].iloc[-1]
                                final_profit = final_val - total_invested_czk
                                final_roi = (final_profit / total_invested_czk) * 100

                                st.divider()
                                # Metriky
                                cm1, cm2, cm3 = st.columns(3)
                                cm1.metric("Vloženo celkem", f"{total_invested_czk:,.0f} Kč")
                                cm2.metric("Hodnota DNES", f"{final_val:,.0f} Kč", delta=f"{final_profit:+,.0f} Kč")
                                cm3.metric("Zhodnocení", f"{final_roi:+.2f} %")

                                # Graf (Area Chart)
                                st.subheader("📈 Vývoj v čase")
                                fig_dca = px.area(dca_df, x=dca_df.index, y=["Hodnota portfolia", "Vloženo celkem"],
                                                  color_discrete_map={"Hodnota portfolia": "#00CC96", "Vloženo celkem": "#AB63FA"},
                                                  template="plotly_dark")
                                fig_dca.update_layout(xaxis_title="", yaxis_title="Hodnota (Kč)", legend=dict(orientation="h", y=1.1), font_family="Roboto Mono", paper_bgcolor="rgba(0,0,0,0)")
                                fig_dca = make_plotly_cyberpunk(fig_dca)
                                st.plotly_chart(fig_dca, use_container_width=True)

                                if final_profit > 0:
                                    st.success(f"🎉 Kdybys začal před {dca_years} lety, mohl jsi si dnes koupil ojeté auto (nebo hodně zmrzliny).")
                                else:
                                    st.error("📉 Au. I s pravidelným investováním bys byl v mínusu. To chce silné nervy.")

                            else:
                                st.warning(f"Nepodařilo se stáhnout historii pro {dca_ticker}. Zkus jiný symbol.")
                        except Exception as e:
                            st.error(f"Chyba ve stroji času: {e}")

            st.divider()

            # --- EFEKTIVNÍ HRANICE ---

            tickers_for_ef = df['Ticker'].unique().tolist()
            st.write("")

            if len(tickers_for_ef) < 2:
                st.warning("⚠️ Pro simulaci Efektivní hranice potřebujete mít v portfoliu alespoň 2 různé akcie.")
            else:
                st.subheader("📊 Efektivní Hranice (Optimalizace Riziko/Výnos)")
                st.info(f"Proběhne simulace {len(tickers_for_ef)} akcií z tvého portfolia za posledních 5 let.")

                num_portfolios = st.slider("Počet simulací:", 1000, 10000, 5000, step=1000)

                if st.button("📈 SPUSTIT OPTIMALIZACI PORTFOLIA", type="primary", key="run_ef"):
                    try:
                        with st.spinner("Počítám tisíce náhodných portfolií..."):
                            end_date = datetime.now()
                            start_date = end_date - timedelta(days=5 * 365)

                            price_data = yf.download(tickers_for_ef, start=start_date, end=end_date, progress=False)['Close']
                            price_data = price_data.dropna()

                            if price_data.empty or len(price_data) < 252:
                                st.error("Nelze provést simulaci: Historická data pro vybrané akcie nejsou dostupná nebo jsou nedostatečná (potřeba min. 1 rok dat).")
                                raise ValueError("Nedostatečná data pro EF")

                            log_returns = np.log(price_data / price_data.shift(1)).dropna()
                            num_assets = len(tickers_for_ef)

                            results = np.zeros((3 + num_assets, num_portfolios))

                            for i in range(num_portfolios):
                                weights = np.random.random(num_assets)
                                weights /= np.sum(weights)

                                portfolio_return = np.sum(log_returns.mean() * weights) * 252

                                portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(log_returns.cov() * 252, weights)))

                                sharpe_ratio = (portfolio_return - RISK_FREE_RATE) / portfolio_volatility

                                results[0,i] = portfolio_volatility
                                results[1,i] = portfolio_return
                                results[2,i] = sharpe_ratio
                                for j in range(num_assets):
                                    results[3+j,i] = weights[j]

                            cols = ['Volatilita', 'Výnos', 'Sharpe'] + tickers_for_ef
                            results_frame = pd.DataFrame(results.T, columns=cols)

                            max_sharpe_portfolio = results_frame.loc[results_frame['Sharpe'].idxmax()]

                            min_vol_portfolio = results_frame.loc[results_frame['Volatilita'].idxmin()]

                            fig_ef = go.Figure()

                            fig_ef.add_trace(go.Scatter(
                                x=results_frame['Volatilita'],
                                y=results_frame['Výnos'],
                                mode='markers',
                                marker=dict(
                                    color=results_frame['Sharpe'],
                                    size=5,
                                    colorscale='Viridis',
                                    showscale=True,
                                    colorbar=dict(title='Sharpe Ratio')
                                ),
                                name='Simulovaná Portfolia'
                            ))

                            fig_ef.add_trace(go.Scatter(
                                x=[min_vol_portfolio['Volatilita']],
                                y=[min_vol_portfolio['Výnos']],
                                mode='markers',
                                marker=dict(color='red', size=15, symbol='star'),
                                name='Minimální Riziko'
                            ))

                            fig_ef.add_trace(go.Scatter(
                                x=[max_sharpe_portfolio['Volatilita']],
                                y=[max_sharpe_portfolio['Výnos']],
                                mode='markers',
                                marker=dict(color='lightgreen', size=15, symbol='star'),
                                name='Max Sharpe Ratio'
                            ))

                            fig_ef.update_layout(
                                title='Efektivní Hranice',
                                xaxis_title='Volatilita (Riziko)',
                                yaxis_title='Očekávaný Roční Výnos',
                                template="plotly_dark",
                                hovermode='closest',
                                height=550,
                                font_family="Roboto Mono",
                                plot_bgcolor="rgba(0,0,0,0)",
                                paper_bgcolor="rgba(0,0,0,0)"
                            )
                            fig_ef.update_xaxes(showgrid=False)
                            fig_ef.update_yaxes(showgrid=True, gridcolor='#30363D')
                            fig_ef = make_plotly_cyberpunk(fig_ef)
                            st.plotly_chart(fig_ef, use_container_width=True, key="fig_ef_frontier")
                            add_download_button(fig_ef, "efektivni_hranice")

                            st.divider()
                            c_ef1, c_ef2 = st.columns(2)

                            with c_ef1:
                                st.success("🟢 OPTIMÁLNÍ SHARPE RATIO PORTFOLIO (Max. výnos k riziku)")
                                st.metric("Sharpe Ratio", f"{max_sharpe_portfolio['Sharpe']:.2f}")
                                st.metric("Roční výnos", f"{max_sharpe_portfolio['Výnos'] * 100:.2f} %")
                                st.metric("Roční riziko (Volatilita)", f"{max_sharpe_portfolio['Volatilita'] * 100:.2f} %")
                                st.markdown("**Doporučené váhy:**")
                                max_sharpe_weights_df = max_sharpe_portfolio[tickers_for_ef].to_frame(name="Váha (%)").T.copy()
                                max_sharpe_weights_df.index = ['Doporučená váha']
                                st.dataframe(
                                    max_sharpe_weights_df.T.style.format({"Váha (%)": "{:.1%}"}),
                                    use_container_width=True,
                                    hide_index=False
                                )

                            with c_ef2:
                                st.error("🔴 MINIMÁLNÍ RIZIKO PORTFOLIO (Nejnižší volatilita)")
                                st.metric("Sharpe Ratio", f"{min_vol_portfolio['Sharpe']:.2f}")
                                st.metric("Roční výnos", f"{min_vol_portfolio['Výnos'] * 100:.2f} %")
                                st.metric("Roční riziko (Volatilita)", f"{min_vol_portfolio['Volatilita'] * 100:.2f} %")
                                st.markdown("**Doporučené váhy:**")
                                min_vol_weights_df = min_vol_portfolio[tickers_for_ef].to_frame(name="Váha (%)").T.copy()
                                min_vol_weights_df.index = ['Doporučená váha']
                                st.dataframe(
                                    min_vol_weights_df.T.style.format({"Váha (%)": "{:.1%}"}),
                                    use_container_width=True,
                                    hide_index=False
                                )

                    except ValueError:
                        pass
                    except Exception as e:
                        st.error(f"Při simulaci došlo k neočekávané chybě: {e}")

            st.divider()
            st.subheader("🔮 Složené úročení (Původní funkce)")

            col_v1, col_v2 = st.columns([1, 2])
            with col_v1:
                vklad = st.number_input("Měsíční vklad (Kč)", value=5000, step=500, key="vklad_orig")
                roky = st.slider("Počet let", 5, 40, 15, key="roky_orig")
                urok = st.slider("Očekávaný úrok p.a. (%)", 1.0, 15.0, 8.0, key="urok_orig")
            with col_v2:
                data_budoucnost = []; aktualni_hodnota = celk_hod_czk; vlozeno = celk_hod_czk
                for r in range(1, roky + 1):
                    rocni_vklad = vklad * 12; vlozeno += rocni_vklad
                    aktualni_hodnota = (aktualni_hodnota + rocni_vklad) * (1 + urok/100)
                    data_budoucnost.append({"Rok": datetime.now().year + r, "Hodnota": round(aktualni_hodnota), "Vklady": round(vlozeno)})
                st.area_chart(pd.DataFrame(data_budoucnost).set_index("Rok"), color=["#00FF00", "#333333"])
                st.metric(f"Hodnota v roce {datetime.now().year + roky}", f"{aktualni_hodnota:,.0f} Kč", f"Zisk: {aktualni_hodnota - vlozeno:,.0f} Kč")

            st.divider()
            st.subheader("🎲 MONTE CARLO: Simulace budoucnosti (Původní funkce)")
            st.info("Simulace 50 možných scénářů vývoje tvého portfolia na základě volatility trhu.")
            c_mc1, c_mc2 = st.columns(2)
            with c_mc1:
                mc_years = st.slider("Délka simulace (roky)", 1, 20, 5, key="mc_years")
                mc_volatility = st.slider("Očekávaná volatilita (%)", 5, 50, 20, key="mc_vol") / 100
            with c_mc2:
                mc_return = st.slider("Očekávaný výnos p.a. (%)", -5, 20, 8, key="mc_ret") / 100
                start_val = celk_hod_czk if celk_hod_czk > 0 else 100000
            if st.button("🔮 SPUSTIT SIMULACI", key="run_mc", type="primary"):
                days = mc_years * 252; dt = 1/252; mu = mc_return; sigma = mc_volatility; num_simulations = 50
                sim_data = pd.DataFrame()
                for i in range(num_simulations):
                    price_path = [start_val]
                    for _ in range(days):
                        shock = np.random.normal(0, 1)
                        price = price_path[-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shock)
                        price_path.append(price)
                    sim_data[f"Sim {i}"] = price_path
                fig_mc = go.Figure()
                for col in sim_data.columns: fig_mc.add_trace(go.Scatter(y=sim_data[col], mode='lines', line=dict(width=1), opacity=0.3, showlegend=False))
                sim_data['Average'] = sim_data.mean(axis=1)
                fig_mc.add_trace(go.Scatter(y=sim_data['Average'], mode='lines', name='Průměrný scénář', line=dict(color='yellow', width=4)))
                fig_mc.update_layout(title=f"Monte Carlo: {num_simulations} scénářů na {mc_years} let", xaxis_title="Dny", yaxis_title="Hodnota (CZK)", template="plotly_dark", font_family="Roboto Mono", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                fig_mc.update_xaxes(showgrid=False)
                fig_mc.update_yaxes(showgrid=True, gridcolor='#30363D')
                fig_mc = make_plotly_cyberpunk(fig_mc)
                st.plotly_chart(fig_mc, use_container_width=True)
                st.success(f"Průměrná hodnota na konci: {sim_data['Average'].iloc[-1]:,.0f} Kč")


            st.divider()
            st.subheader("💥 CRASH TEST & HISTORICKÉ SCÉNÁŘE")
            st.info("Otestuj odolnost svého portfolia proti historickým krizím nebo vlastnímu scénáři.")

            # 1. Definice historických krizí
            scenarios = {
                "COVID-19 (2020)": {"drop": 34, "desc": "Pandemie. Rychlý pád o 34 % za měsíc. Následovalo rychlé oživení (V-shape).", "icon": "🦠"},
                "Finanční krize (2008)": {"drop": 57, "desc": "Hypoteční krize. Pád o 57 % trval 17 měsíců. Dlouhá recese.", "icon": "📉"},
                "Dot-com bublina (2000)": {"drop": 49, "desc": "Splasknutí technologické bubliny. Nasdaq spadl o 78 %, S&P 500 o 49 %.", "icon": "💻"},
                "Black Monday (1987)": {"drop": 22, "desc": "Černé pondělí. Největší jednodenní propad v historii (-22 %).", "icon": "⚡"}
            }

            # 2. Tlačítka pro rychlou volbu
            st.write("### 📜 Vyber scénář z historie:")
            cols = st.columns(4)

            # Inicializace session state pro crash test, pokud neexistuje
            if 'crash_sim_drop' not in st.session_state:
                st.session_state['crash_sim_drop'] = 20
            if 'crash_sim_name' not in st.session_state:
                st.session_state['crash_sim_name'] = "Vlastní scénář"
            if 'crash_sim_desc' not in st.session_state:
                st.session_state['crash_sim_desc'] = "Manuální nastavení."

            # Vykreslení tlačítek
            for i, (name, data) in enumerate(scenarios.items()):
                with cols[i]:
                    if st.button(f"{data['icon']} {name}\n(-{data['drop']}%)", use_container_width=True):
                        st.session_state['crash_sim_drop'] = data['drop']
                        st.session_state['crash_sim_name'] = name
                        st.session_state['crash_sim_desc'] = data['desc']
                        st.rerun()

            # 3. Posuvník (Manual Override)
            st.write("### 🎛️ Nebo nastav vlastní propad:")

            # Načteme hodnotu ze session state
            current_drop_val = int(st.session_state['crash_sim_drop'])

            propad = st.slider("Simulace pádu trhu (%)", 5, 90, current_drop_val, step=1, key="crash_slider_manual")

            # Logika pro aktualizaci textů při posunu slideru
            scenario_name = st.session_state['crash_sim_name']
            scenario_desc = st.session_state['crash_sim_desc']

            if propad != current_drop_val:
                scenario_name = "Vlastní scénář"
                scenario_desc = f"Simulace manuálního propadu o {propad} %."
                # Aktualizujeme state, aby si to pamatoval
                st.session_state['crash_sim_drop'] = propad

            # 4. Výpočet a Vizualizace
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
                # Vizuální reprezentace "krvácení"
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
                user_df = hist_vyvoje.copy()
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
            st.subheader("💱 MĚNOVÝ SIMULÁTOR")
            st.info("Jak změna kurzu koruny ovlivní hodnotu tvého portfolia?")
            assets_by_curr = {"USD": 0, "EUR": 0, "CZK": 0}
            if viz_data:
                for item in viz_data:
                    curr = item['Měna']; val = item['Hodnota']
                    if curr in assets_by_curr: assets_by_curr[curr] += val
                    else: assets_by_curr["USD"] += item['HodnotaUSD']
            kurz_usd_now = kurzy.get("CZK", 20.85); kurz_eur_now = kurzy.get("EUR", 1.16) * kurz_usd_now
            col_s1, col_s2 = st.columns(2)
            with col_s1: sim_usd = st.slider(f"Kurz USD/CZK (Aktuálně: {kurz_usd_now:.2f})", 15.0, 30.0, float(kurz_usd_now))
            with col_s2: sim_eur = st.slider(f"Kurz EUR/CZK (Aktuálně: {kurz_eur_now:.2f})", 15.0, 35.0, float(kurz_eur_now))
            val_now_czk = (assets_by_curr["USD"] * kurz_usd_now) + (assets_by_curr["EUR"] * kurz_eur_now) + assets_by_curr["CZK"]
            val_sim_czk = (assets_by_curr["USD"] * sim_usd) + (assets_by_curr["EUR"] * sim_eur) + assets_by_curr["CZK"]
            diff = val_sim_czk - val_now_czk
            st.divider()
            c_m1, c_m2 = st.columns(2)
            c_m1.metric("Hodnota Portfolia (Simulace)", f"{val_sim_czk:,.0f} Kč", delta=f"{diff:,.0f} Kč")
            impact_data = pd.DataFrame({
                "Měna": ["USD Aktiva", "EUR Aktiva", "CZK Aktiva"],
                "Hodnota CZK (Teď)": [assets_by_curr["USD"] * kurz_usd_now, assets_by_curr["EUR"] * kurz_eur_now, assets_by_curr["CZK"]],
                "Hodnota CZK (Simulace)": [assets_by_curr["USD"] * sim_usd, assets_by_curr["EUR"] * sim_eur, assets_by_curr["CZK"]]
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

        with tab7:
            st.subheader("⚖️ REBALANČNÍ KALKULAČKA")
            if not vdf.empty:
                df_reb = vdf.groupby('Sektor')['HodnotaUSD'].sum().reset_index()
                total_val = df_reb['HodnotaUSD'].sum()
                st.write("Nastav cílové váhy pro sektory:")
                targets = {}; cols = st.columns(3)
                for i, row in df_reb.iterrows():
                    current_pct = (row['HodnotaUSD'] / total_val) * 100
                    with cols[i % 3]:
                        targets[row['Sektor']] = st.number_input(f"{row['Sektor']} (%)", min_value=0.0, max_value=100.0, value=float(round(current_pct, 1)), step=1.0, key=f"reb_{row['Sektor']}")
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
            else: st.info("Portfolio je prázdné.")

        with tab8:
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
                    except Exception as e: st.error(f"Chyba při výpočtu korelace: {e}")
                else: st.warning("Pro výpočet korelace potřebuješ alespoň 2 různé akcie.")
            else: st.info("Portfolio je prázdné.")

        with tab9:
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

    elif page == "🎮 Gamifikace":
        st.title("🎮 INVESTIČNÍ ARÉNA")
        st.subheader(f"Tvá úroveň: {level_name}")
        st.progress(level_progress)
        if celk_hod_czk < 500000:
            st.caption("Do další úrovně ti chybí majetek.")
        else:
            st.success("Gratulace! Dosáhl jsi maximální úrovně Velryba 🐋")

        if AI_AVAILABLE:
            st.divider()
            st.subheader("🎲 DENNÍ LOGBOOK (AI Narrator)")

            denni_zmena_czk = (celk_hod_usd - celk_inv_usd) * kurzy.get("CZK", 21)
            if len(hist_vyvoje) > 1:
                denni_zmena_czk = (hist_vyvoje.iloc[-1]['TotalUSD'] - hist_vyvoje.iloc[-2]['TotalUSD']) * kurzy.get("CZK", 21)

            nalada_ikona = "💀" if denni_zmena_czk < 0 else "💰"

            if st.button("🎲 GENEROVAT PŘÍBĚH DNE", type="secondary"):
                with st.spinner("Dungeon Master hází kostkou..."):
                    sc, _ = ziskej_fear_greed()
                    actual_score = sc if sc else 50
                    rpg_res_text = generate_rpg_story(model, level_name, denni_zmena_czk, celk_hod_czk, actual_score)

                    st.markdown(f"""
                    <div style="background-color: #161B22; border-left: 5px solid {'#da3633' if denni_zmena_czk < 0 else '#238636'}; padding: 15px; border-radius: 5px;">
                        <h4 style="margin:0">{nalada_ikona} DENNÍ ZÁPIS</h4>
                        <p style="font-style: italic; color: #8B949E; margin-top: 10px;">"{rpg_res_text}"</p>
                    </div>
                    """, unsafe_allow_html=True)


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

        # ÚPRAVA: NOVÁ render_badge FUNKCE POUŽÍVAJÍCÍ CUSTOM CSS TŘÍDY
        def render_badge(col, title, desc, cond, icon, color):
            # Tady aplikujeme ty custom CSS třídy nadefinované ve styles.py
            css_class = "badge-earned" if cond else "badge-locked"
            status_text = "ZÍSKÁNO" if cond else "UZAMČENO"
            status_color = "#00FF99" if cond else "#8B949E" # Neon Green / Grey

            html = f"""
            <div class="badge-card {css_class}">
                <span class="badge-icon" style="color: {color};">{icon}</span>
                <div class="badge-title">{title}</div>
                <div class="badge-desc">{desc}</div>
                <hr style="margin: 10px 0; border-color: #30363D;">
                <div style="font-size: 0.7rem; color: {status_color}; font-weight: bold; letter-spacing: 1px;">
                    {status_text}
                </div>
            </div>
            """
            with col:
                st.markdown(html, unsafe_allow_html=True)

        render_badge(c1, "Začátečník", "Kup první akcii", has_first, "🥉", "#CD7F32")
        render_badge(c2, "Stratég", "Drž 3 různé firmy", cnt >= 3, "🥈", "#C0C0C0")
        render_badge(c3, "Boháč", "Portfolio > 100k", celk_hod_czk > 100000, "🥇", "#FFD700")
        render_badge(c4, "Rentiér", "Dividendy > 500 Kč", divi_total > 500, "💎", "#00BFFF")
        st.divider()
        st.subheader("💡 Moudro dne")
        if 'quote' not in st.session_state: st.session_state['quote'] = random.choice(CITATY)
        st.info(f"*{st.session_state['quote']}*")

    elif page == "📰 Zprávy":
        st.title("📰 BURZOVNÍ ZPRAVODAJSTVÍ")
        # --- MARKET WORD CLOUD (Mrak slov) ---
        try:
            from wordcloud import WordCloud
            import matplotlib.pyplot as plt

            # 1. Získáme texty
            raw_news_cloud = ziskej_zpravy()
            if raw_news_cloud:
                text_data = " ".join([n['title'] for n in raw_news_cloud]).upper()

                # 2. Definujeme slova, která nechceme (Stopwords)
                stop_words = ["A", "I", "O", "U", "V", "S", "K", "Z", "SE", "SI", "NA", "DO", "JE", "TO", "ŽE", "ALE", "PRO", "JAK", "TAK", "OD", "PO", "NEBO", "BUDE", "BYL", "MÁ", "JSOU", "KTERÝ", "KTERÁ", "ONLINE", "AKTUÁLNĚ", "CENA", "BURZA", "TRH", "AKCIE", "INVESTICE"]

                # 3. Nastavení mraku (Dark Mode Friendly)
                wc = WordCloud(
                    width=800, height=250,
                    background_color=None, # Průhledné pozadí
                    mode="RGBA",
                    stopwords=stop_words,
                    min_font_size=10,
                    colormap="GnBu" # Modro-zelená paleta (ladí s aplikací)
                ).generate(text_data)

                # 4. Vykreslení pomocí Matplotlib
                st.subheader("☁️ TÉMATA DNE (Co hýbe trhem)")
                fig_cloud, ax = plt.subplots(figsize=(10, 3))
                ax.imshow(wc, interpolation="bilinear")
                ax.axis("off") # Skryjeme osy

                # Nastavení průhlednosti grafu
                fig_cloud.patch.set_alpha(0)
                ax.patch.set_alpha(0)
                make_matplotlib_cyberpunk(fig_cloud, ax) # Používáme fig_cloud, ne jen fig
                st.pyplot(fig_cloud, use_container_width=True)
                st.divider()

        except ImportError:
            st.warning("⚠️ Pro zobrazení Mraku slov nainstaluj knihovnu: `pip install wordcloud`")
        except Exception as e:
            st.error(f"Chyba WordCloud: {e}")
        if AI_AVAILABLE:
            def analyze_news_with_ai(title, link):
                prompt_to_send = f"Analyzuj následující finanční zprávu V KONTEXTU MÉHO PORTFOLIA. Zpráva: {title} (Odkaz: {link}). Jaký by měla mít dopad na mé současné držby?"
                st.session_state["chat_messages"].append({"role": "user", "content": prompt_to_send})
                st.session_state['chat_expanded'] = True
                st.rerun()

            if st.button("🧠 SPUSTIT AI SENTIMENT 2.0", type="primary"):
                with st.spinner("AI analyzuje trh..."):
                    raw_news = ziskej_zpravy()
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

        news = ziskej_zpravy()
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

    elif page == "⚙️ Nastavení":
        st.title("⚙️ DATA & SPRÁVA")
        st.info("Zde můžeš editovat data natvrdo.")
        t1, t2 = st.tabs(["PORTFOLIO", "HISTORIE"])
        with t1:
            new_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Portfolio"): st.session_state['df'] = new_df; uloz_data_uzivatele(new_df, USER, SOUBOR_DATA); st.success("Uloženo")
        with t2:
            new_h = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True)
            if st.button("Uložit Historii"): st.session_state['df_hist'] = new_h; uloz_data_uzivatele(new_h, USER, SOUBOR_HISTORIE); st.success("Uloženo")
        st.divider(); st.subheader("📦 ZÁLOHA")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for n, d in [(SOUBOR_DATA, 'df'), (SOUBOR_HISTORIE, 'df_hist'), (SOUBOR_CASH, 'df_cash'), (SOUBOR_DIVIDENDY, 'df_div'), (SOUBOR_WATCHLIST, 'df_watch')]:
                if d in st.session_state: zf.writestr(n, st.session_state[d].to_csv(index=False))
        st.download_button("Stáhnout Data", buf.getvalue(), f"backup_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")

    with st.expander("🤖 AI ASISTENT", expanded=st.session_state.get('chat_expanded', False)):
        st.markdown('<span id="floating-bot-anchor"></span>', unsafe_allow_html=True)

        # --- NOVÉ: Tlačítko pro vymazání paměti ---
        c_clear, _ = st.columns([1, 2])
        with c_clear:
            if st.button("🧹 Nová konverzace", key="clear_chat"):
                st.session_state["chat_messages"] = [{"role": "assistant", "content": "Paměť vymazána. O čem se chceš bavit teď? 🧠"}]
                st.rerun()
        # ------------------------------------------

        if "chat_messages" not in st.session_state: st.session_state["chat_messages"] = [{"role": "assistant", "content": "Ahoj! Jsem tvůj AI průvodce. Co pro tebe mohu udělat?"}]
        for msg in st.session_state["chat_messages"]: st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("Zeptej se..."):
            if not AI_AVAILABLE: st.error("Chybí API klíč.")
            else: st.session_state["chat_messages"].append({"role": "user", "content": prompt}); st.rerun()
        # 👇👇👇 VLOŽ TOTO MÍSTO TOHO SMAZANÉHO 👇👇👇
        if st.session_state["chat_messages"][-1]["role"] == "user":
            with st.spinner("Přemýšlím..."):
                last_user_msg = st.session_state["chat_messages"][-1]["content"]

                # --- Příprava kontextu pro AI (zjednodušeno) ---
                # Sbíráme data o portfoliu, trhu a náladě, abychom je poslali do ai_brain
                portfolio_context = f"Uživatel má celkem {celk_hod_czk:,.0f} CZK. "
                if viz_data: portfolio_context += "Portfolio: " + ", ".join([f"{i['Ticker']} ({i['Sektor']})" for i in viz_data])

                # Fear & Greed
                fg_score, fg_rating = ziskej_fear_greed()
                if fg_score:
                    portfolio_context += f"\nTržní nálada: {fg_score} ({fg_rating})."

                # Sentiment zpráv
                ai_news = st.session_state.get('ai_news_analysis', {})
                if ai_news:
                    avg_s = sum([v['score'] for v in ai_news.values()]) / len(ai_news) if len(ai_news) > 0 else 50
                    portfolio_context += f"\nSentiment zpráv: {avg_s:.0f}/100."

                # --- VOLÁNÍ MOZKU (ai_brain.py) ---
                ai_reply = get_chat_response(model, last_user_msg, portfolio_context)

                # Uložení a refresh
                st.session_state["chat_messages"].append({"role": "assistant", "content": ai_reply})
                st.rerun()

if __name__ == "__main__":
    main()
