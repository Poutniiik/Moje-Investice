import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Importy z utils
from utils import (
    ziskej_fear_greed, 
    ziskej_ceny_hromadne, 
    ziskej_yield, 
    # Cache wrappery
    cached_ceny_hromadne
)

def aktualizuj_graf_vyvoje(user, celk_hod_usd):
    if 'hist_vyvoje' not in st.session_state:
        df_vyvoj = pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    else:
        df_vyvoj = st.session_state['hist_vyvoje']

    dnes = datetime.now().strftime("%Y-%m-%d")
    
    # Ošetření duplicit pro dnešní den
    if not df_vyvoj.empty and df_vyvoj.iloc[-1]['Date'] == dnes:
        df_vyvoj.at[df_vyvoj.index[-1], 'TotalUSD'] = float(celk_hod_usd)
    else:
        novy = pd.DataFrame([{"Date": dnes, "TotalUSD": float(celk_hod_usd), "Owner": user}])
        df_vyvoj = pd.concat([df_vyvoj, novy], ignore_index=True)
    
    return df_vyvoj

def calculate_all_data(user, df, df_watch, zustatky, kurzy):
    """
    ROBUSTNÍ VÝPOČETNÍ JÁDRO (S Debug výpisy chyb)
    """
    
    # 1. Získání Live dat
    tickers_list = []
    if not df.empty and 'Ticker' in df.columns:
        tickers_list = df['Ticker'].unique().tolist()
    
    if df_watch is not None and not df_watch.empty and 'Ticker' in df_watch.columns:
        tickers_list += df_watch['Ticker'].unique().tolist()
        
    vsechny_tickery = list(set(tickers_list))
    live_data = cached_ceny_hromadne(vsechny_tickery)
    st.session_state['LIVE_DATA'] = live_data

    # 2. Proměnné pro výpočet
    celk_hod_usd = 0.0
    celk_inv_usd = 0.0
    viz_data = []
    fundament_data = {}
    
    # DEBUG: Kontrola vstupu
    # st.sidebar.text(f"DEBUG Core: Vstup {len(df)} řádků")

    if not df.empty:
        g = df.groupby('Ticker')
        for ticker, group in g:
            try:
                # A) Výpočet kusů
                kusy = pd.to_numeric(group['Pocet'], errors='coerce').sum()
                
                # Pokud nemáme kusy, nemá smysl počítat dál
                if kusy <= 0.0001: 
                    # st.sidebar.text(f"Skip {ticker}: Kusy <= 0 ({kusy})")
                    continue
                    
                # B) Výpočet investice
                investovano = (group['Pocet'] * group['Cena']).sum()
                avg_cena = investovano / kusy if kusy > 0 else 0
                
                # C) Získání ceny (Bezpečně s fallbackem na 0)
                inf = live_data.get(ticker, {})
                curr_price = inf.get('price')
                curr_currency = inf.get('curr', 'USD')
                
                # Pokud cena chybí (None nebo 0), zkusíme nouzově yfinance přímo
                if not curr_price:
                    try:
                        t_obj = yf.Ticker(str(ticker))
                        curr_price = t_obj.fast_info.last_price
                    except: 
                        curr_price = 0.0

                if curr_price is None: curr_price = 0.0
                
                # D) Převod měn (aby to nespadlo na None)
                price_in_usd = float(curr_price)
                if curr_currency == "CZK":
                    czk_rate = kurzy.get("CZK", 20.85)
                    price_in_usd = price_in_usd / czk_rate if czk_rate else 0
                elif curr_currency == "EUR":
                    eur_rate = kurzy.get("EUR", 1.16)
                    price_in_usd = price_in_usd * eur_rate if eur_rate else 0
                    
                aktualni_hodnota_usd = kusy * price_in_usd
                investovano_usd = investovano # Zjednodušení (předpoklad USD vstupu)
                
                zisk_usd = aktualni_hodnota_usd - investovano_usd
                zisk_pct = (zisk_usd / investovano_usd) if investovano_usd != 0 else 0
                
                celk_hod_usd += aktualni_hodnota_usd
                celk_inv_usd += investovano_usd
                
                divi_yield = ziskej_yield(ticker)

                # E) Uložení řádku
                viz_data.append({
                    "Ticker": str(ticker),
                    "Kusy": float(kusy),
                    "Průměr": float(avg_cena),
                    "Cena": float(curr_price),
                    "Měna": str(curr_currency),
                    "HodnotaUSD": float(aktualni_hodnota_usd),
                    "InvesticeUSD": float(investovano_usd),
                    "Zisk": float(zisk_usd),
                    "Zisk%": float(zisk_pct),
                    "Sektor": str(group.iloc[0]['Sektor']),
                    "Divi": divi_yield
                })
                
                fundament_data[ticker] = {
                    "trailingPE": 0,
                    "dividendYield": divi_yield,
                    "currency": curr_currency,
                    "currentPrice": curr_price
                }
            except Exception as e:
                # TOTO je klíčové: Pokud se něco pokazí u jednoho tickeru, 
                # nevypne to celou aplikaci, jen vypíše chybu a jede dál.
                st.sidebar.error(f"❌ Chyba výpočtu {ticker}: {e}")
                continue

    vdf = pd.DataFrame(viz_data)
    
    # 3. Změna 24h
    zmena_24h_usd = 0
    if not vdf.empty:
        for idx, row in vdf.iterrows():
            try:
                # Jednoduchá simulace změny
                ticker = row['Ticker']
                curr = row['Cena']
                # Pokud nemáme historii, nemůžeme počítat změnu (dáme 0)
                # Tady to často padalo na chybějících datech
                vdf.at[idx, 'Dnes'] = 0.0 
            except: pass
    
    pct_24h = (zmena_24h_usd / celk_hod_usd * 100) if celk_hod_usd > 0 else 0
    
    # 4. Hotovost
    cash_usd = zustatky.get("USD", 0) + (zustatky.get("CZK", 0) / kurzy.get("CZK", 20.85)) + (zustatky.get("EUR", 0) * kurzy.get("EUR", 1.16))
    
    hist_vyvoje = aktualizuj_graf_vyvoje(user, celk_hod_usd + cash_usd)

    return {
        'vdf': vdf,
        'viz_data_list': viz_data,
        'celk_hod_usd': celk_hod_usd,
        'celk_inv_usd': celk_inv_usd,
        'hist_vyvoje': hist_vyvoje,
        'zmena_24h': zmena_24h_usd,
        'pct_24h': pct_24h,
        'cash_usd': cash_usd,
        'fundament_data': fundament_data,
        'kurzy': kurzy,
        'timestamp': datetime.now()
    }
