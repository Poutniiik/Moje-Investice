import streamlit as st
import pandas as pd
import time
import zipfile
import io
from datetime import datetime, timedelta
import random
from streamlit_lottie import st_lottie
import extra_streamlit_components as stx

# Internal Imports
from styles import get_css
from src.config import (
    REPO_NAZEV, SOUBOR_DATA, SOUBOR_UZIVATELE, SOUBOR_HISTORIE,
    SOUBOR_CASH, SOUBOR_VYVOJ, SOUBOR_WATCHLIST, SOUBOR_DIVIDENDY,
    CITATY
)
from data_manager import (
    nacti_csv, uloz_csv, zasifruj, nacti_uzivatele
)
from src.services.market_data import (
    ziskej_fear_greed, ziskej_zpravy, cached_detail_akcie,
    cached_ceny_hromadne, cached_kurzy, ziskej_info
)
from src.services.portfolio_service import (
    calculate_all_data, proved_nakup, proved_prodej, get_zustatky, invalidate_data_core, aktualizuj_graf_vyvoje
)
from src.services.reporting import vytvor_pdf_report
from src.ui.components.widgets import render_ticker_tape
from ai_brain import (
    init_ai, ask_ai_guard, get_chat_response
)
import notification_engine as notify
import bank_engine as bank # Needed for bank lab render logic if it was inline, but we moved it. Kept if used here.
# Actually we moved bank render logic to src/ui/pages/bank.py, but that file imports bank_engine.
# src/app.py might not need bank_engine directly unless for sidebar info?
# Sidebar info (market times) uses zjisti_stav_trhu from market_data (originally utils).
from src.services.market_data import zjisti_stav_trhu

# Import Pages
from src.ui.pages.dashboard import render_prehled_page
from src.ui.pages.watchlist import render_sledovani_page
from src.ui.pages.analysis import render_analysis_page
from src.ui.pages.news import render_news_page
from src.ui.pages.trading import render_trading_page
from src.ui.pages.dividends import render_dividendy_page
from src.ui.pages.gamification import render_gamifikace_page
from src.ui.pages.settings import render_settings_page
from src.ui.pages.bank import render_bank_lab_page

# --- KONFIGURACE ---
st.set_page_config(
    page_title="Terminal Pro",
    layout="wide",
    page_icon="💹",
    initial_sidebar_state="expanded"
)

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
    import requests
    r = requests.get(url)
    if r.status_code != 200: return None
    return r.json()

# --- AI CACHE ---
@st.cache_resource(show_spinner="Připojuji neurální sítě...")
def get_cached_ai_connection():
    try:
        return init_ai()
    except Exception as e:
        print(f"Chyba init_ai: {e}")
        return None, False

# --- CLI CALLBACK ---
if 'cli_msg' not in st.session_state: st.session_state['cli_msg'] = None

def process_cli_command(USER, AI_AVAILABLE, model):
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
            elif 'data_core' not in st.session_state:
                msg_text = "❌ Datové jádro není inicializováno. Zkus obnovit stránku."
                msg_icon = "⚠️"
            else:
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
                                msg_text = f"❌ Fundamentální data pro {target_ticker} nebyla nalezena."
                                msg_icon = "⚠️"
                        except Exception as e:
                            msg_text = f"❌ Chyba při získávání dat pro {target_ticker}: {e}"
                            msg_icon = "⚠️"

                    if not msg_text:
                        current_price = LIVE_DATA.get(target_ticker, {}).get('price', 'N/A')
                        pe_ratio = fund_info.get('trailingPE', 'N/A')
                        divi_yield_raw = fund_info.get('dividendYield', 'N/A')
                        vdf = core['vdf']
                        if not vdf.empty and target_ticker in vdf['Ticker'].values:
                            portfolio_row = vdf[vdf['Ticker'] == target_ticker].iloc[0]
                            if pd.notna(portfolio_row.get('Divi')):
                                divi_yield_raw = portfolio_row['Divi']

                        divi_yield_for_ai = divi_yield_raw if isinstance(divi_yield_raw, (float, int)) and pd.notna(divi_yield_raw) else 'N/A'
                        divi_yield_display = f"{divi_yield_raw * 100:.2f}%" if isinstance(divi_yield_raw, (float, int)) and pd.notna(divi_yield_raw) else 'N/A'

                        ai_prompt = (
                            f"Jsi finanční analytik. Analyzuj akcii {target_ticker} na základě jejích fundamentálních dat:\n"
                            f"Aktuální P/E: {pe_ratio}. Dividendový výnos (jako desetinne cislo, napr. 0.03): {divi_yield_for_ai}.\n"
                            "Poskytni stručné shrnutí (max 3 věty) o tom, zda je akcie drahá, levná, nebo neutrální, a jaké je její hlavní riziko/příležitost."
                        )

                        try:
                            with st.spinner(f"AI provádí analýzu pro {target_ticker}..."):
                                ai_response = model.generate_content(ai_prompt).text
                            summary_text = (
                                f"## 🕵️ Analýza: {target_ticker}\n"
                                f"- Cena: {current_price}\n"
                                f"- P/E Ratio: {pe_ratio}\n"
                                f"- Dividend Yield: {divi_yield_display}\n"
                                "---"
                            )
                            msg_text = f"🛡️ **HLÁŠENÍ PRO {target_ticker}:**\n{summary_text}\n🤖 **AI Verdikt:** {ai_response}"
                            msg_icon = "🔬"
                        except Exception as e:
                            msg_text = f"❌ Chyba AI ({target_ticker}): {e}" if "429" not in str(e) else "❌ Chyba kvóty (429)."
                            msg_icon = "⚠️"

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
                        msg_text = f"🛡️ **HLÁŠENÍ STRÁŽCE:**\n{guard_res_text}"
                        msg_icon = "👮"
                    except Exception as e:
                        msg_text = f"❌ Chyba AI: {e}"
                        msg_icon = "⚠️"

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

def send_daily_telegram_report(USER, data_core, alerts, kurzy):
    try:
        celk_hod_czk = data_core['celk_hod_usd'] * kurzy.get("CZK", 20.85)
        pct_24h = data_core['pct_24h']
        cash_usd = data_core['cash_usd']
        vdf = data_core['vdf']
        score, rating = ziskej_fear_greed()

        summary_text = f"<b>💸 DENNÍ REPORT: {USER.upper()}</b>\n"
        summary_text += f"📅 {datetime.now().strftime('%d.%m.%Y')}\n"
        summary_text += "--------------------------------------\n"
        summary_text += f"Celkové jmění: <b>{celk_hod_czk:,.0f} CZK</b>\n"

        zmena_emoji = '🟢' if pct_24h >= 0 else '🔴'
        summary_text += f"24h Změna: {zmena_emoji} <b>{pct_24h:+.2f}%</b>\n"
        summary_text += f"Volná hotovost: ${cash_usd:,.0f}\n"
        summary_text += f"Nálada trhu: <b>{rating}</b> ({score}/100)\n"
        summary_text += "--------------------------------------\n"

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

        if alerts:
            summary_text += "<b>🚨 AKTIVNÍ ALERTY:</b>\n" + "\n".join(alerts) + "\n"
            summary_text += "--------------------------------------\n"

        summary_text += "<i>Mějte úspěšný investiční den!</i>"
        return notify.poslat_zpravu(summary_text)
    except Exception as e:
        return False, f"❌ Chyba generování reportu: {e}"

# --- MAIN FUNCTION ---
def main():
    model, AI_AVAILABLE = get_cached_ai_connection()
    cookie_manager = get_manager()

    if 'prihlasen' not in st.session_state:
        st.session_state['prihlasen'] = False
        st.session_state['user'] = ""

    time.sleep(0.3)

    if 'chat_expanded' not in st.session_state:
        st.session_state['chat_expanded'] = False

    if not st.session_state['prihlasen']:
        cookie_user = cookie_manager.get("invest_user")
        if cookie_user:
            st.session_state['prihlasen'] = True
            st.session_state['user'] = cookie_user
            st.rerun()

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
                        df_u = nacti_uzivatele(); row = df_u[df_u['username'] == ru] # Fixed var usage u->ru
                        if not row.empty and row.iloc[0]['recovery_key'] == zasifruj(rk): # Fixed logic
                            df_u.at[row.index[0], 'password'] = zasifruj(rnp); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}"); st.success("Hotovo!")
                        else: st.error("Chyba údajů.")
        return

    USER = st.session_state['user']

    if 'boot_completed' not in st.session_state:
        st.session_state['boot_completed'] = False

    if not st.session_state['boot_completed']:
        boot_placeholder = st.empty()
        with boot_placeholder.container():
            st.markdown("""<style>.stApp {background-color: black !important;}</style>""", unsafe_allow_html=True)
            st.markdown("## 🖥️ TERMINAL PRO v4.0", unsafe_allow_html=True)
            steps = ["Initializing...", "Loading weights...", "Accessing market...", "Decrypting...", "ACCESS GRANTED"]
            bar = st.progress(0)
            status_text = st.empty()
            for i, step in enumerate(steps):
                status_text.markdown(f"```bash\n> {step}\n```")
                bar.progress((i + 1) * (100 // len(steps)))
                time.sleep(0.2)
            st.success("SYSTEM ONLINE")
            time.sleep(0.5)
        boot_placeholder.empty()
        st.session_state['boot_completed'] = True

    # LOAD DATA
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

    cache_timeout = timedelta(minutes=5)
    if ('data_core' not in st.session_state or
        (datetime.now() - st.session_state['data_core']['timestamp']) > cache_timeout):
        with st.spinner("🔄 Aktualizuji datové jádro (LIVE data)..."):
            data_core = calculate_all_data(USER, df, df_watch, zustatky, kurzy)
    else:
        data_core = st.session_state['data_core']

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

    alerts = []
    if not df_watch.empty:
        for _, r in df_watch.iterrows():
            tk = r['Ticker']; buy_trg = r['TargetBuy']; sell_trg = r['TargetSell']
            if buy_trg > 0 or sell_trg > 0:
                inf = LIVE_DATA.get(tk, {})
                price = inf.get('price')
                if not price: price, _, _ = ziskej_info(tk)
                if price:
                    if buy_trg > 0 and price <= buy_trg:
                        alerts.append(f"{tk}: KUPNÍ ALERT! Cena {price:.2f} <= {buy_trg:.2f}")
                        st.toast(f"🔔 {tk} je ve slevě! ({price:.2f})", icon="🔥")
                    if sell_trg > 0 and price >= sell_trg:
                        alerts.append(f"💰 PRODEJ: {tk} za {price:.2f} >= {sell_trg:.2f}")
                        st.toast(f"🔔 {tk} dosáhl cíle! ({price:.2f})", icon="💰")

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

    with st.sidebar:
        lottie_url = "https://lottie.host/02092823-3932-4467-9d7e-976934440263/3q5XJg2Z2W.json"
        lottie_json = load_lottieurl(lottie_url)
        if lottie_json:
            st_lottie(lottie_json, height=120, key="sidebar_anim")

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
        page = st.radio("Jít na:", ["🏠 Přehled", "👀 Sledování", "📈 Analýza", "📰 Zprávy", "💸 Obchod", "💎 Dividendy", "🎮 Gamifikace", "⚙️ Nastavení", "🧪 Banka"], label_visibility="collapsed")
        st.divider()

        level_name = "Novic"
        level_progress = 0.0
        if celk_hod_czk < 10000:
            level_name = "Novic 🧒"; level_progress = min(celk_hod_czk / 10000, 1.0)
        elif celk_hod_czk < 50000:
            level_name = "Učeň 🧑‍🎓"; level_progress = min((celk_hod_czk - 10000) / 40000, 1.0)
        elif celk_hod_czk < 100000:
            level_name = "Trader 💼"; level_progress = min((celk_hod_czk - 50000) / 50000, 1.0)
        elif celk_hod_czk < 500000:
            level_name = "Profi 🎩"; level_progress = min((celk_hod_czk - 100000) / 400000, 1.0)
        else:
            level_name = "Velryba 🐋"; level_progress = 1.0

        st.caption(f"Úroveň: **{level_name}**")
        st.progress(level_progress)

        with st.expander("🌍 SVĚTOVÉ TRHY", expanded=False):
            ny_time, ny_open = zjisti_stav_trhu("America/New_York", 9, 16)
            ln_time, ln_open = zjisti_stav_trhu("Europe/London", 8, 16)
            jp_time, jp_open = zjisti_stav_trhu("Asia/Tokyo", 9, 15)
            c_m1, c_m2 = st.columns([3, 1]); c_m1.caption("🇺🇸 New York"); c_m2.markdown(f"**{ny_time}** {'🟢' if ny_open else '🔴'}")
            c_m1, c_m2 = st.columns([3, 1]); c_m1.caption("🇬🇧 Londýn"); c_m2.markdown(f"**{ln_time}** {'🟢' if ln_open else '🔴'}")
            c_m1, c_m2 = st.columns([3, 1]); c_m1.caption("🇯🇵 Tokio"); c_m2.markdown(f"**{jp_time}** {'🟢' if jp_open else '🔴'}")

        with st.expander("💰 STAV PENĚŽENKY", expanded=False):
            for mena in ["USD", "CZK", "EUR"]:
                castka = zustatky.get(mena, 0.0)
                sym = "$" if mena == "USD" else ("Kč" if mena == "CZK" else "€")
                st.markdown(f"""<div style="background-color: #0D1117; padding: 10px; border-radius: 5px; margin-bottom: 5px; border: 1px solid #30363D;"><span style="color: #8B949E;">{mena}:</span> <span style="color: #00FF99; font-weight: bold; float: right;">{castka:,.2f} {sym}</span></div>""", unsafe_allow_html=True)

        if alerts:
            st.error("🔔 CENOVÉ ALERTY!", icon="🔥")
            for a in alerts: st.markdown(f"- **{a}**")

        st.divider()
        with st.expander("💻 TERMINÁL", expanded=False):
            if st.session_state.get('cli_msg'):
                txt, ic = st.session_state['cli_msg']
                if ic in ["🔬", "👮"]:
                    st.toast(f"{ic} Nové hlášení od AI strážce!", icon=ic)
                    st.markdown(f"<div style='font-size: 10px;'>{txt}</div>", unsafe_allow_html=True)
                else:
                    st.info(f"{ic} {txt}")
                st.session_state['cli_msg'] = None
            st.text_input(">", key="cli_cmd", placeholder="/help", on_change=process_cli_command, args=(USER, AI_AVAILABLE, model))

        st.divider()
        c_act1, c_act2 = st.columns(2)
        with c_act2:
            pdf_data = vytvor_pdf_report(USER, celk_hod_czk, cash_usd, (celk_hod_czk - celk_inv_czk), viz_data_list)
            st.download_button(label="📄 PDF", data=pdf_data, file_name=f"report.pdf", mime="application/pdf", use_container_width=True)

        with st.expander("🔐 Účet"):
            with st.form("pass_change_main"):
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

    if page not in ["🎮 Gamifikace", "⚙️ Nastavení"]:
        render_ticker_tape(LIVE_DATA)

    if page == "🏠 Přehled":
        render_prehled_page(USER, vdf, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, zmena_24h, pct_24h, cash_usd, AI_AVAILABLE, model, df_watch, fundament_data, LIVE_DATA)
    elif page == "👀 Sledování":
        render_sledovani_page(USER, df_watch, LIVE_DATA, kurzy, df, SOUBOR_WATCHLIST)
    elif page == "📈 Analýza":
        render_analysis_page(df, df_watch, vdf, model, AI_AVAILABLE, hist_vyvoje, kurzy, celk_hod_usd, celk_inv_usd, celk_hod_czk, viz_data_list, LIVE_DATA)
    elif page == "📰 Zprávy":
        render_news_page(celk_hod_czk, viz_data_list, AI_AVAILABLE, model)
    elif page == "💸 Obchod":
        render_trading_page(USER, LIVE_DATA, df, zustatky)
    elif page == "💎 Dividendy":
        render_dividendy_page(USER, df, df_div, kurzy, viz_data_list)
    elif page == "🎮 Gamifikace":
        render_gamifikace_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky)
    elif page == "⚙️ Nastavení":
        render_settings_page(USER, df, AI_AVAILABLE)
    elif page == "🧪 Banka":
        render_bank_lab_page()

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
