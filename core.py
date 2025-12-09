import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import notification_engine as notify
import bank_engine as bank
from utils import (
    ziskej_info, ziskej_yield, cached_ceny_hromadne, cached_kurzy, 
    cached_detail_akcie, aktualizuj_graf_vyvoje, ziskej_fear_greed
)
from data_manager import (
    SOUBOR_DATA, SOUBOR_CASH, SOUBOR_HISTORIE, SOUBOR_WATCHLIST, SOUBOR_DIVIDENDY,
    nacti_csv, uloz_data_uzivatele, uloz_csv, get_repo
)

# --- ŘÍZENÍ STAVU DAT ---
def invalidate_data_core():
    """Vynutí opětovný přepočet datového jádra."""
    if 'data_core' in st.session_state:
        st.session_state['data_core']['timestamp'] = datetime.now() - timedelta(minutes=6)

# --- TRANSAKČNÍ LOGIKA (ATOMICKÉ OPERACE) ---

def pohyb_penez(castka, mena, typ, poznamka, user, df_cash_temp):
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    return pd.concat([df_cash_temp, novy], ignore_index=True)

def proved_nakup(ticker, kusy, cena, user):
    df_p = st.session_state['df'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    
    _, mena, _ = ziskej_info(ticker)
    cost = kusy * cena
    
    # Rychlý výpočet zůstatku lokálně
    aktualni_cash = df_cash_temp[df_cash_temp['Mena'] == mena]['Castka'].sum() if not df_cash_temp.empty else 0
    
    # Pokud nemáme data v session, zkusíme je dopočítat (fallback)
    if 'data_core' in st.session_state:
        # Zde by byla logika pro čtení z cache, ale pro bezpečnost počítáme přímo z DF
        pass

    # Zjednodušený check zůstatku (vylepšit dle potřeby)
    zustatky = df_cash_temp.groupby('Mena')['Castka'].sum().to_dict()
    
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
            return True, f"✅ Koupeno: {kusy}x {ticker} za {cena:,.2f} {mena}"
        except Exception as e:
            return False, f"❌ Chyba zápisu: {e}"
    else:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {zustatky.get(mena, 0):,.2f})"

def proved_prodej(ticker, kusy, cena, user, mena_input):
    df_p = st.session_state['df'].copy()
    df_h = st.session_state['df_hist'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')
    final_mena = mena_input if mena_input and mena_input != "N/A" else "USD"

    if df_t.empty or df_t['Pocet'].sum() < kusy:
        return False, "Nedostatek kusů."

    zbyva, zisk, trzba = kusy, 0, kusy * cena
    df_p_novy = df_p.copy()
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
        return True, f"Prodáno! +{trzba:,.2f} {final_mena} (Zisk: {zisk:,.2f})"
    except Exception as e:
        return False, f"❌ Chyba zápisu: {e}"

# --- HLAVNÍ VÝPOČETNÍ JÁDRO ---
def calculate_all_data(USER, df, df_watch, zustatky, kurzy):
    """Provede kompletní přepočet portfolia a vrátí data_core dictionary."""
    
    # 1. Live Data
    all_tickers = []
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    
    LIVE_DATA = cached_ceny_hromadne(list(set(all_tickers)))
    st.session_state['LIVE_DATA'] = LIVE_DATA if LIVE_DATA else {}

    if LIVE_DATA:
        if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
        if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]

    # 2. Fundamenty
    fundament_data = {}
    if not df.empty:
        for tkr in df['Ticker'].unique():
            info, _ = cached_detail_akcie(tkr)
            fundament_data[tkr] = info

    # 3. Portfolio
    viz_data = []
    celk_hod_usd = 0
    celk_inv_usd = 0

    if not df.empty:
        df_g = df.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        df_g['Investice'] = df.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        
        for _, row in df_g.iterrows():
            tkr = row['Ticker']
            p, m, d_zmena = ziskej_info(tkr)
            if p is None: p = row['Cena']
            if m is None or m == "N/A": m = "USD"
            
            fundamenty = fundament_data.get(tkr, {})
            # ... (logika výpočtu jako v původním souboru) ...
            
            # Zjednodušený převod měn pro výpočet hodnoty
            k = 1.0
            if m == "CZK": k = 1.0 / kurzy.get("CZK", 20.85)
            elif m == "EUR": k = kurzy.get("EUR", 1.16)
            
            hod = row['Pocet'] * p
            inv = row['Investice']
            
            celk_hod_usd += hod * k
            celk_inv_usd += inv * k
            
            viz_data.append({
                "Ticker": tkr, "Sektor": df[df['Ticker']==tkr]['Sektor'].iloc[0] if 'Sektor' in df.columns else "Doplnit",
                "HodnotaUSD": hod*k, "Zisk": hod-inv, "Měna": m, "Hodnota": hod, "Cena": p,
                "Kusy": row['Pocet'], "Průměr": (row['Investice']/row['Pocet']), "Divi": ziskej_yield(tkr),
                "Dnes": d_zmena, "P/E": fundamenty.get('trailingPE', 0),
                "Země": "N/A" # Zjednodušeno pro Core
            })

    vdf = pd.DataFrame(viz_data) if viz_data else pd.DataFrame()
    
    # 4. Historie a Hotovost
    hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))
    
    zmena_24h = 0
    pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if pd.notnull(vcera) and vcera > 0:
            zmena_24h = celk_hod_usd - vcera
            pct_24h = (zmena_24h / vcera * 100)

    return {
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

# --- AUTOMATICKÝ REPORTÉR ---
def check_and_send_daily_report(USER, data_core):
    """
    Automatický hlídač, který se spustí při načtení stránky.
    Pokud je po 18:00 a report nebyl odeslán, pošle ho.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Kdy posílat? (Např. po 18. hodině)
    REPORT_HOUR = 18
    
    # Stav v Session State (pro tento běh)
    if 'last_telegram_report' not in st.session_state:
        st.session_state['last_telegram_report'] = "2000-01-01" # Default
    
    # Podmínky: Je po 18:00? A nebyl už dnes poslán?
    if now.hour >= REPORT_HOUR and st.session_state['last_telegram_report'] != today_str:
        
        # 1. Sestavení zprávy
        celk_hod_czk = data_core['celk_hod_usd'] * data_core['kurzy'].get("CZK", 21)
        zmena = data_core['pct_24h']
        emoji = "🟢" if zmena >= 0 else "🔴"
        
        msg = f"<b>🔔 DENNÍ UPDATE: {USER}</b>\n"
        msg += f"📅 {today_str}\n"
        msg += f"💰 Jmění: <b>{celk_hod_czk:,.0f} Kč</b>\n"
        msg += f"📊 Změna: {emoji} <b>{zmena:+.2f}%</b>\n"
        
        # Top Movers
        vdf = data_core['vdf']
        if not vdf.empty and 'Dnes' in vdf.columns:
            best = vdf.sort_values('Dnes', ascending=False).iloc[0]
            msg += f"🚀 Top: {best['Ticker']} ({best['Dnes']*100:+.1f}%)\n"
        
        # 2. Odeslání
        success, info = notify.poslat_zpravu(msg)
        
        if success:
            st.session_state['last_telegram_report'] = today_str
            return True, "Report odeslán."
        else:
            return False, f"Chyba odeslání: {info}"
            
    return None, "Čekám na čas..."
