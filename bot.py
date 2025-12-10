import pandas as pd
import yfinance as yf
from datetime import datetime
import data_manager as dm
# import notification_engine as notify # Starý engine už nepotřebujeme, nahradíme ho přímým voláním
import math
import os
import random
import matplotlib.pyplot as plt
import io
import requests

# --- KONFIGURACE ROBOTA ---
TARGET_USER = "Filip"
BOT_NAME = "Alex"

# --- POMOCNÉ FUNKCE PRO TELEGRAM A GRAFIKU ---
def get_telegram_creds():
    """Získá token a chat ID z prostředí GitHub Actions."""
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not token or not chat_id:
        print("❌ CHYBA: Chybí TG_BOT_TOKEN nebo TG_CHAT_ID v Secrets!")
        return None, None
    return token, chat_id

def poslat_zpravu_telegram(text):
    """Odešle textovou zprávu."""
    token, chat_id = get_telegram_creds()
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data)
        print("✅ Textová zpráva odeslána.")
    except Exception as e:
        print(f"❌ Chyba odesílání textu: {e}")

def poslat_obrazek_telegram(img_buffer, caption=""):
    """Odešle obrázek (PNG) z paměti."""
    token, chat_id = get_telegram_creds()
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    img_buffer.seek(0) # Vrátíme se na začátek souboru v paměti
    files = {'photo': ('chart.png', img_buffer, 'image/png')}
    data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
    try:
        requests.post(url, files=files, data=data)
        print("🖼️ Obrázek odeslán.")
    except Exception as e:
        print(f"❌ Chyba odesílání obrázku: {e}")

def generate_portfolio_chart(stocks_val_czk, cash_val_czk, total_val_czk):
    """Vytvoří 'Donut Chart' rozložení portfolia."""
    print("🎨 Kreslím graf...")
    
    # Data
    labels = ['Akcie', 'Hotovost']
    sizes = [stocks_val_czk, cash_val_czk]
    # Barvy: Zelená pro akcie, Modrá pro cash (Cyberpunk styl)
    colors = ['#00CC96', '#636EFA']
    
    # Pokud je vše nula, nemá smysl kreslit
    if total_val_czk <= 0: return None

    # Nastavení stylu (Tmavý režim)
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(aspect="equal"))
    
    # Barva pozadí (aby ladila s Telegramem)
    fig.patch.set_facecolor('#161B22')
    ax.set_facecolor('#161B22')

    # Kreslení Donutu
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.0f%%',
                                      startangle=90, colors=colors,
                                      textprops=dict(color="white", fontsize=12, weight='bold'),
                                      wedgeprops=dict(width=0.4, edgecolor='#161B22', linewidth=2),
                                      pctdistance=0.80)
    
    # Text uprostřed (Celkové jmění)
    center_text = f"JMĚNÍ\n{total_val_czk:,.0f} Kč"
    ax.text(0, 0, center_text, ha='center', va='center', fontsize=14, weight='bold', color='white')

    # Titulek
    ax.set_title("Rozložení Portfolia", fontsize=16, color='white', pad=20, weight='bold')
    
    plt.tight_layout()

    # Uložení do paměti (ne na disk)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig) # Úklid paměti
    return buf

# --- HLAVNÍ LOGIKA ROBOTA ---

def safe_float(val, fallback=0.0):
    try:
        f = float(val)
        if math.isnan(f): return fallback
        return f
    except:
        return fallback

def run_bot():
    # 1. NAČTENÍ PARAMETRŮ
    rezim = os.environ.get("INPUT_TYP", "Standardní Report")
    vzkaz_od_sefa = os.environ.get("INPUT_VZKAZ", "")

    print(f"🤖 {BOT_NAME}: Startuji v režimu '{rezim}' (v5.0 Visual)...")

    if rezim == "Jenom Vtip":
        vtipy = [
            "Investování je jako sledování schnoucí barvy nebo rostoucí trávy. Pokud chcete vzrušení, vezměte 20 tisíc a jeďte do Las Vegas.",
            "Burza je místo, kde lidé, kteří vědí, prodávají lidem, kteří nevědí.",
            "Proč je diverzifikace důležitá? Aby když jedna vaše loď půjde ke dnu, nemuseli jste plavat."
        ]
        poslat_zpravu_telegram(f"🤡 <b>Burzovní vtip:</b>\n\n{random.choice(vtipy)}")
        return

    if rezim == "Test Spojení":
        poslat_zpravu_telegram("📡 <b>Test spojení:</b> Alex v5.0 (Visual) je online!")
        return

    # 2. NAČTENÍ DAT
    try:
        raw_df = dm.nacti_csv(dm.SOUBOR_DATA)
        raw_cash = dm.nacti_csv(dm.SOUBOR_CASH)
        
        df = raw_df[raw_df['Owner'] == TARGET_USER].copy()
        df_cash = raw_cash[raw_cash['Owner'] == TARGET_USER].copy()
        
        if df.empty and df_cash.empty:
            poslat_zpravu_telegram("⚠️ <b>Alex:</b> Nemám data. Nahraj CSV na GitHub.")
            return

    except Exception as e:
        print(f"❌ Chyba dat: {e}")
        return

    # 3. PŘÍPRAVA TICKERŮ
    my_tickers = df['Ticker'].unique().tolist()
    market_tickers = ["^GSPC", "BTC-USD"]
    all_tickers = list(set(my_tickers + market_tickers))

    # 4. STAŽENÍ DAT
    kurz_czk = 24.0
    kurz_eur = 1.05
    live_prices = {}; open_prices = {}; market_data = {}; divi_yields = {}

    try:
        print(f"🌍 Stahuji data pro {len(all_tickers)} tickerů...")
        data_obj = yf.Tickers(" ".join(all_tickers + ["CZK=X", "EURUSD=X"]))
        
        try:
            h_czk = data_obj.tickers["CZK=X"].history(period="1d")
            if not h_czk.empty: kurz_czk = float(h_czk['Close'].iloc[-1])
            h_eur = data_obj.tickers["EURUSD=X"].history(period="1d")
            if not h_eur.empty: kurz_eur = float(h_eur['Close'].iloc[-1])
        except: pass

        for t in all_tickers:
            try:
                ticker_obj = data_obj.tickers[t]
                hist = ticker_obj.history(period="1d")
                if hist.empty: continue
                price = float(hist['Close'].iloc[-1])
                open_p = float(hist['Open'].iloc[-1])
                live_prices[t] = price
                open_prices[t] = open_p
                if t in my_tickers:
                    dy = ticker_obj.info.get('dividendYield', 0)
                    divi_yields[t] = safe_float(dy)
                if t in market_tickers:
                    pct_change = ((price - open_p) / open_p) * 100 if open_p > 0 else 0
                    market_data[t] = pct_change
            except: pass

    except Exception as e:
        print(f"⚠️ Chyba stahování: {e}")

    # 5. VÝPOČTY
    total_cash_usd = 0; portfolio_val_usd = 0; portfolio_cost_usd = 0; daily_gain_usd = 0; annual_divi_usd = 0
    
    # A) Hotovost
    try:
        df_cash['Castka'] = pd.to_numeric(df_cash['Castka'], errors='coerce').fillna(0)
        for mena, castka in df_cash.groupby('Mena')['Castka'].sum().items():
            if castka > 1:
                if mena == 'USD': total_cash_usd += castka
                elif mena == 'CZK': total_cash_usd += castka / kurz_czk
                elif mena == 'EUR': total_cash_usd += castka * kurz_eur
    except: pass

    # B) Akcie
    movers = []
    for t in my_tickers:
        if t not in live_prices: continue
        curr = "USD"; koef = 1.0
        if ".PR" in t: curr = "CZK"; koef = 1.0 / kurz_czk
        elif ".DE" in t: curr = "EUR"; koef = kurz_eur
        
        row = df[df['Ticker'] == t]
        kusy = row['Pocet'].sum()
        avg_buy = row['Cena'].mean()
        val_usd = kusy * live_prices[t] * koef
        cost_usd = kusy * avg_buy * koef
        
        portfolio_val_usd += val_usd
        portfolio_cost_usd += cost_usd
        daily_gain_usd += (live_prices[t] - open_prices[t]) * kusy * koef
        
        if open_prices[t] > 0:
            pct = ((live_prices[t] - open_prices[t]) / open_prices[t])
            movers.append((t, pct))
            
        yield_val = divi_yields.get(t, 0)
        if yield_val > 0: annual_divi_usd += (val_usd * yield_val)

    # 6. FINÁLNÍ ČÍSLA (CZK)
    total_net_worth_czk = (portfolio_val_usd + total_cash_usd) * kurz_czk
    portfolio_val_czk = portfolio_val_usd * kurz_czk
    total_cash_czk = total_cash_usd * kurz_czk

    total_profit_czk = (portfolio_val_usd - portfolio_cost_usd) * kurz_czk
    total_profit_pct = (portfolio_val_usd - portfolio_cost_usd) / portfolio_cost_usd * 100 if portfolio_cost_usd > 0 else 0
    annual_divi_czk = annual_divi_usd * kurz_czk
    
    my_daily_pct = 0.0
    if portfolio_val_usd > 0:
        my_daily_pct = (daily_gain_usd / (portfolio_val_usd - daily_gain_usd)) * 100

    sp500_pct = market_data.get("^GSPC", 0.0)
    btc_pct = market_data.get("BTC-USD", 0.0)

    # 7. SESTAVENÍ REPORTU (TEXT)
    emoji_main = "🟢" if total_profit_czk >= 0 else "🔴"
    emoji_daily = "📈" if my_daily_pct >= 0 else "📉"
    beat_market = my_daily_pct > sp500_pct
    market_msg = "🏆 <b>Porazil jsi trh!</b>" if beat_market else "🐢 <b>Trh byl dnes rychlejší.</b>"

    msg = f"<b>🎩 CEO REPORT: {datetime.now().strftime('%d.%m.')}</b>\n"
    msg += f"<i>Rentier & Visual Edition ❄️🎨</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    msg += f"💰 <b>JMĚNÍ: {total_net_worth_czk:,.0f} Kč</b>\n"
    msg += f"📊 Zisk: {emoji_main} {total_profit_czk:+,.0f} Kč ({total_profit_pct:+.1f}%)\n"
    if annual_divi_czk > 10:
        msg += f"❄️ <b>Dividenda (rok): {annual_divi_czk:,.0f} Kč</b>\n"
    
    msg += f"{emoji_daily} Dnes: {my_daily_pct:+.2f}% (S&P: {sp500_pct:+.2f}%)\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    msg += f"{market_msg}\n"
    if btc_pct != 0: msg += f"🪙 Bitcoin: {btc_pct:+.2f}%\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    if movers:
        movers.sort(key=lambda x: x[1], reverse=True)
        b = movers[0]; w = movers[-1]
        msg += f"🚀 {b[0]} ({b[1]*100:+.1f}%)\n"
        msg += f"💀 {w[0]} ({w[1]*100:+.1f}%)\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
    
    msg += "💳 <b>Stav hotovosti:</b>\n"
    found_cash = False
    try:
        sums = df_cash.groupby('Mena')['Castka'].sum()
        for mena in ['CZK', 'USD', 'EUR']:
            if mena in sums and sums[mena] > 1:
                amount = sums[mena]
                if mena == 'CZK': txt = f"{amount:,.0f} Kč"
                elif mena == 'USD': txt = f"${amount:,.0f}"
                elif mena == 'EUR': txt = f"€{amount:,.0f}"
                else: txt = f"{amount:,.0f} {mena}"
                msg += f"• {txt}\n"
                found_cash = True
    except: pass
    if not found_cash: msg += "• <i>Prázdno</i>\n"

    if vzkaz_od_sefa:
        msg += f"\n✍️ <b>Poznámka:</b> {vzkaz_od_sefa}"

    print(f"📤 Odesílám textový report...")
    poslat_zpravu_telegram(msg)

    # --- 8. GENERIVÁNÍ A ODESLÁNÍ GRAFU (NOVINKA) ---
    try:
        # Vygenerujeme obrázek do paměti
        chart_buffer = generate_portfolio_chart(portfolio_val_czk, total_cash_czk, total_net_worth_czk)
        
        if chart_buffer:
            print(f"📤 Odesílám graf...")
            # Odešleme obrázek s krátkým popiskem
            poslat_obrazek_telegram(chart_buffer, caption="📊 <i>Vizuální přehled portfolia</i>")
        else:
            print("⚠️ Graf nebyl vygenerován (nulové hodnoty).")

    except Exception as e:
        print(f"❌ Chyba při generování/odesílání grafu: {e}")
        # Pošleme aspoň info o chybě do Telegramu, ať víme, co se děje
        poslat_zpravu_telegram(f"⚠️ <b>Alex Error:</b> Nepodařilo se vykreslit graf.\n{e}")

if __name__ == "__main__":
    run_bot()
