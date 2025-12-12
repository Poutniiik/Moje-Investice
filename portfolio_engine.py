import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Importy z utils
from utils import (
    ziskej_fear_greed, 
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
    if not df_vyvoj.empty and 'Date' in df_vyvoj.columns and df_vyvoj.iloc[-1]['Date'] == dnes:
        df_vyvoj.at[df_vyvoj.index[-1], 'TotalUSD'] = float(celk_hod_usd)
    else:
        novy = pd.DataFrame([{"Date": dnes, "TotalUSD": float(celk_hod_usd), "Owner": user}])
        df_vyvoj = pd.concat([df_vyvoj, novy], ignore_index=True)
    
    return df_vyvoj

def calculate_all_data(user, df, df_watch, zustatky, kurzy):
    """
    ROBUSTNÍ VÝPOČETNÍ JÁDRO (Anti-Crash verze)
    """
    celk_hod_usd = 0.0
    celk_inv_usd = 0.0
    viz_data_list = []
    
    # 1. Kontrola, zda máme data
    if df.empty:
        # Pokud je portfolio prázdné, vrátíme jen hotovost
        cash_usd = zustatky.get("USD", 0) + (zustatky.get("CZK", 0) / kurzy.get("CZK", 20.85)) + (zustatky.get("EUR", 0) * kurzy.get("EUR", 1.16))
        return 0.0, 0.0, cash_usd, []

    tickers = df['Ticker'].unique().tolist()
    
    # 2. Hromadné stažení cen (s ošetřením chyb)
    ceny = {}
    try:
        if tickers:
            ceny = cached_ceny_hromadne(tickers)
    except Exception as e:
        st.sidebar.warning(f"⚠️ Problém s připojením k burze: {e}")
        # Pokračujeme s prázdným slovníkem cen -> vše bude mít hodnotu 0

    # 3. Iterace přes portfolio
    for index, row in df.iterrows():
        try:
            ticker = row['Ticker']
            pocet = float(row['Pocet'])
            nakup_cena = float(row['Cena'])
            
            # Získání aktuální ceny (bezpečně)
            curr_price = ceny.get(ticker, nakup_cena) # Fallback na nákupku, pokud selže API
            if curr_price is None or curr_price == 0:
                curr_price = nakup_cena
                
            hodnota = pocet * curr_price
            investice = pocet * nakup_cena
            
            celk_hod_usd += hodnota
            celk_inv_usd += investice
            
            # Výpočet zisku
            zisk_abs = hodnota - investice
            zisk_pct = (zisk_abs / investice * 100) if investice > 0 else 0
            
            viz_data_list.append({
                "Ticker": ticker,
                "Sektor": row.get('Sektor', 'Jiny'),
                "Kusy": pocet,
                "Cena": curr_price,
                "HodnotaUSD": hodnota,
                "Zisk": zisk_abs,
                "Dnes": 0.0, # Změna 24h zatím vypnuta pro stabilitu
                "Divi": 0.0,
                "P/E": 0.0
            })
            
        except Exception as e:
            # Pokud jeden řádek selže, přeskočíme ho, ale neshodíme celou appku
            print(f"Chyba u řádku {index}: {e}")
            continue

    # 4. Hotovost
    try:
        cash_usd = zustatky.get("USD", 0) + (zustatky.get("CZK", 0) / kurzy.get("CZK", 24.50)) + (zustatky.get("EUR", 0) * kurzy.get("EUR", 1.08))
    except Exception:
        cash_usd = 0.0

    return celk_hod_usd, celk_inv_usd, cash_usd, viz_data_list
