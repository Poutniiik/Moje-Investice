# =======================================================
# SOUBOR: bot_utils.py (Pouze pro GHA bota)
# =======================================================
import pandas as pd
import yfinance as yf
import requests
import numpy as np
import pytz
from datetime import datetime
import time
# NEimportujeme STREAMLIT ani dekorátory!

# --- ZÍSKÁNÍ FEAR & GREED (Kopírováno z utils.py) ---
def ziskej_fear_greed():
    """Získá Fear & Greed Index z CNN."""
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status() 
        data = r.json()
        score = int(data['fear_and_greed']['score'])
        rating = data['fear_and_greed']['rating']
        return score, rating
    except Exception: return None, None

# --- ZÍSKÁNÍ KURZŮ (Kopírováno z utils.py) ---
def ziskej_kurzy(): 
    """Získá výchozí kurzy."""
    return {"USD": 1.0, "CZK": 20.85, "EUR": 1.16} # Fallback pro kurz

# --- ZÍSKÁNÍ CEN PORTFOLIA (Kopírováno z utils.py) ---
def ziskej_ceny_portfolia_bot(list_tickeru):
    """Získá aktuální ceny a včerejší close pro seznam tickerů (Robustní pro GHA)."""
    ceny = {}
    vcer_close = {}
    if not list_tickeru:
        return ceny, vcer_close

    for tkr in list_tickeru:
        try:
            # Nová hlavička pro stabilnější API přístup v Cloudu (GHA)
            ticker_obj = yf.Ticker(tkr)
            
            # Historická data pro aktuální cenu
            ticker_data = ticker_obj.history(period="1d", interval="1m", prepost=True)
            
            # Získání aktuální ceny (poslední dostupná)
            if not ticker_data.empty:
                ceny[tkr] = ticker_data['Close'].iloc[-1]
                
            # Získání včerejší Close ceny pro porovnání z .info
            # Použijeme info, ale s ošetřením, aby to nepadlo tichou chybou
            info = ticker_obj.info
            if info and info.get('previousClose'):
                vcer_close[tkr] = info['previousClose']
            
        except Exception as e:
            # Tiché selhání s logem (uvidíme v GHA logu, co se stalo, i když report dorazí)
            print(f"❌ Chyba YFinance pro {tkr}: {e}") # <--- TENTO ŘÁDEK ZAJISTÍ LOGOVÁNÍ
            ceny[tkr] = 0.0
            vcer_close[tkr] = 0.0
            
    return ceny, vcer_close
