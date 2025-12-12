import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import notification_engine as notify
from data_manager import (
    SOUBOR_DATA, SOUBOR_CASH, SOUBOR_HISTORIE, SOUBOR_WATCHLIST, SOUBOR_DIVIDENDY, SOUBOR_VYVOJ,
    uloz_data_uzivatele, nacti_csv, uloz_csv
)


# --- POMOCNÉ FUNKCE PRO CACHE ---
def invalidate_data_core():
    """Vynutí opětovný přepočet datového jádra."""
    if 'data_core' in st.session_state:
        st.session_state['data_core']['timestamp'] = datetime.now() - timedelta(minutes=6)

def get_zustatky(user):
    df_cash = st.session_state.get('df_cash', pd.DataFrame())
    if df_cash.empty: return {}
    return df_cash.groupby('Mena')['Castka'].sum().to_dict()

# --- ATOMICKÉ FUNKCE (Transakce) ---

# Toto je ta funkce, kterou definujeme ZDE, takže ji nemusíme importovat
def pohyb_penez(castka, mena, typ, poznamka, user, df_cash_temp):
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash_temp = pd.concat([df_cash_temp, novy], ignore_index=True)
    return df_cash_temp

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

def pridat_dividendu(ticker, castka, mena, user):
    df_div = st.session_state['df_div']
    df_cash_temp = st.session_state['df_cash'].copy()
    
    # Krok 1: Záznam dividendy
    novy = pd.DataFrame([{"Ticker": ticker, "Castka": float(castka), "Mena": mena, "Datum": datetime.now(), "Owner": user}])
    df_div = pd.concat([df_div, novy], ignore_index=True)
    
    # Krok 2: Pohyb peněz
    df_cash_temp = pohyb_penez(castka, mena, "Dividenda", f"Divi {ticker}", user, df_cash_temp)
    
    try:
        uloz_data_uzivatele(df_div, user, SOUBOR_DIVIDENDY)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        st.session_state['df_div'] = df_div
        st.session_state['df_cash'] = df_cash_temp
        invalidate_data_core()
        return True, f"✅ Připsáno {castka:,.2f} {mena} od {ticker}"
    except Exception as e:
        return False, f"❌ Chyba zápisu (DIVI): {e}"

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
            return True, f"✅ Koupeno: {kusy}x {ticker} za {cena:,.2f} {mena}"
        except Exception as e:
            return False, f"❌ Chyba zápisu (NÁKUP): {e}"
    else:
        return False, f"❌ Nedostatek {mena}"

def proved_prodej(ticker, kusy, cena, user, mena_input):
    df_p = st.session_state['df'].copy()
    df_h = st.session_state['df_hist'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')

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
        return True, f"Prodáno! +{trzba:,.2f} {final_mena} (Zisk: {zisk:,.2f})"
    except Exception as e:
        return False, f"❌ Chyba zápisu (PRODEJ): {e}"

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
    except Exception as e:
        return False, f"❌ Chyba zápisu (SMĚNA): {e}"

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

# --- VÝPOČETNÍ JÁDRO ---
def calculate_all_data(USER, df, df_watch, zustatky, kurzy):
    all_tickers = []
    if not df.empty: all_tickers.extend(df['Ticker'].unique().tolist())
    if not df_watch.empty: all_tickers.extend(df_watch['Ticker'].unique().tolist())
    
    LIVE_DATA = cached_ceny_hromadne(list(set(all_tickers)))
    if LIVE_DATA:
        if "CZK=X" in LIVE_DATA: kurzy["CZK"] = LIVE_DATA["CZK=X"]["price"]
        if "EURUSD=X" in LIVE_DATA: kurzy["EUR"] = LIVE_DATA["EURUSD=X"]["price"]
    
    st.session_state['LIVE_DATA'] = LIVE_DATA if LIVE_DATA else {} 
    
    fundament_data = {}
    if not df.empty:
        tickers_in_portfolio = df['Ticker'].unique().tolist()
        for tkr in tickers_in_portfolio:
            info, _ = cached_detail_akcie(tkr)
            fundament_data[tkr] = info

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
                "Země": country, "P/E": pe_ratio, "Kapitalizace": market_cap / 1e9 if market_cap else 0
            })

    vdf = pd.DataFrame(viz_data) if viz_data else pd.DataFrame()
    hist_vyvoje = aktualizuj_graf_vyvoje(USER, celk_hod_usd)
    zmena_24h = 0
    pct_24h = 0
    if len(hist_vyvoje) > 1:
        vcera = hist_vyvoje.iloc[-2]['TotalUSD']
        if pd.notnull(vcera) and vcera > 0:
            zmena_24h = celk_hod_usd - vcera
            pct_24h = (zmena_24h / vcera * 100)

    cash_usd = (zustatky.get('USD', 0)) + (zustatky.get('CZK', 0)/kurzy.get("CZK", 20.85)) + (zustatky.get('EUR', 0)*kurzy.get("EUR", 1.16))

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

# --- RPG LOGIKA & TASKS ---
RPG_TASKS = [
    {"title": "První průzkum", "desc": "Přidej do Watchlistu akcii, kterou nemáš v portfoliu.", 
     "check_fn": lambda df, df_w, zustatky, vdf: not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique())},
    
    {"title": "Diverzifikace: Sektor", "desc": "Drž akcie ve 3 různých sektorech.", 
     "check_fn": lambda df, df_w, zustatky, vdf: df['Sektor'].nunique() >= 3 and df.shape[0] >= 3},
    
    {"title": "Měnová rovnováha", "desc": "Drž hotovost alespoň ve 2 měnách.", 
     "check_fn": lambda df, df_w, zustatky, vdf: sum(1 for v in zustatky.values() if v > 100) >= 2},
    
    {"title": "Mód Rentiera", "desc": "Drž 3 akcie s dividendovým výnosem > 1%.", 
     "check_fn": lambda df, df_w, zustatky, vdf: len([i for i in (vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf) if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01]) >= 3},
      
    {"title": "Cílovací expert", "desc": "Nastav cílovou nákupní i prodejní cenu.", 
     "check_fn": lambda df, df_w, zustatky, vdf: (df_w['TargetBuy'] > 0).any() and (df_w['TargetSell'] > 0).any()},
    
    {"title": "Pohotovostní fond", "desc": "Drž alespoň 5 000 Kč v hotovosti (Měna CZK).", 
     "check_fn": lambda df, df_w, zustatky, vdf: zustatky.get('CZK', 0) >= 5000},
]

def get_task_progress(task_id, df, df_w, zustatky, vdf):
    if task_id == 0:
        target = 1; current = 1 if not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique()) else 0
        return current, target, f"Sledované (mimo portfolio): {current}/{target}"
    elif task_id == 1:
        target = 3; current = df['Sektor'].nunique() if not df.empty else 0
        return current, target, f"Sektorů: {current}/{target}"
    elif task_id == 2:
        target = 2; current = sum(1 for v in zustatky.values() if v > 100)
        return current, target, f"Aktivních měn: {current}/{target}"
    elif task_id == 3:
        target = 3; safe_vdf = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
        current = len([i for i in safe_vdf if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01])
        return current, target, f"Dividendových akcií: {current}/{target}"
    elif task_id == 4:
        target = 2; has_buy = (df_w['TargetBuy'] > 0).any(); has_sell = (df_w['TargetSell'] > 0).any()
        current = (1 if has_buy else 0) + (1 if has_sell else 0)
        return current, target, f"Nastavené cíle (Buy + Sell): {current}/{target}"
    elif task_id == 5:
        target = 5000; current = zustatky.get('CZK', 0)
        return min(current, target), target, f"CZK hotovost: {current:,.0f}/{target:,.0f} Kč"
    return 0, 1, "N/A"

def send_daily_telegram_report(USER, data_core, alerts, kurzy):
    try:
        celk_hod_czk = data_core['celk_hod_usd'] * kurzy.get("CZK", 20.85)
        pct_24h = data_core['pct_24h']
        cash_usd = data_core['cash_usd']
        vdf = data_core['vdf']
        score, rating = ziskej_fear_greed()
        
        summary_text = f"<b>💸 DENNÍ REPORT: {USER.upper()}</b>\n📅 {datetime.now().strftime('%d.%m.%Y')}\n"
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
        return False, f"❌ Chyba reportu: {e}"
