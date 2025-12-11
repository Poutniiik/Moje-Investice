import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Importy z utils (protože portfolio engine potřebuje pomocné funkce)
from utils import (
    ziskej_fear_greed, 
    ziskej_ceny_hromadne, 
    ziskej_yield, 
    calculate_sharpe_ratio,
    # Cache wrappery
    cached_fear_greed,
    cached_ceny_hromadne
)

def aktualizuj_graf_vyvoje(user, celk_hod_usd):
    """
    Pomocná funkce pro sledování historie hodnoty portfolia.
    """
    # Použijeme data z session state nebo vytvoříme nová
    if 'hist_vyvoje' not in st.session_state:
        df_vyvoj = pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    else:
        df_vyvoj = st.session_state['hist_vyvoje']

    dnes = datetime.now().strftime("%Y-%m-%d")
    
    # Pokud už máme záznam pro dnešek, aktualizujeme ho
    if not df_vyvoj.empty and df_vyvoj.iloc[-1]['Date'] == dnes:
        df_vyvoj.at[df_vyvoj.index[-1], 'TotalUSD'] = float(celk_hod_usd)
    else:
        # Jinak přidáme nový řádek
        novy = pd.DataFrame([{"Date": dnes, "TotalUSD": float(celk_hod_usd), "Owner": user}])
        df_vyvoj = pd.concat([df_vyvoj, novy], ignore_index=True)
    
    return df_vyvoj

def calculate_all_data(user, df, df_watch, zustatky, kurzy):
    """
    HLAVNÍ VÝPOČETNÍ MOZEK (DATA CORE).
    Počítá hodnotu portfolia, zisky, stahuje live data.
    """
    
    # 1. ZÍSKÁNÍ LIVE DAT (Hromadně pro rychlost)
    tickers_list = df['Ticker'].unique().tolist()
    watch_list = df_watch['Ticker'].unique().tolist()
    vsechny_tickery = list(set(tickers_list + watch_list))
    
    # Tady už NENÍ st.spinner (řeší ho main.py)
    live_data = cached_ceny_hromadne(vsechny_tickery)
    
    # Uložíme live data do session state pro ostatní stránky
    st.session_state['LIVE_DATA'] = live_data

    # 2. VÝPOČET HODNOTY PORTFOLIA
    celk_hod_usd = 0.0
    celk_inv_usd = 0.0
    viz_data = []
    fundament_data = {} # Cache pro fundamenty
    
    if not df.empty:
        # Seskupení podle tickerů
        g = df.groupby('Ticker')
        for ticker, group in g:
            kusy = group['Pocet'].sum()
            
            # Pokud už nemáme žádné kusy, přeskočíme
            if kusy <= 0: continue
                
            investovano = (group['Pocet'] * group['Cena']).sum()
            avg_cena = investovano / kusy if kusy > 0 else 0
            
            # Získání aktuální ceny
            inf = live_data.get(ticker, {})
            curr_price = inf.get('price')
            curr_currency = inf.get('curr', 'USD')
            
            if not curr_price:
                # Fallback, pokud hromadné stažení selhalo
                t_obj = yf.Ticker(ticker)
                curr_price = t_obj.fast_info.last_price
                
            # Převod měn (zjednodušený)
            # Pokud je akcie v CZK, převedeme cenu na USD pro sčítání
            price_in_usd = curr_price
            if curr_currency == "CZK":
                price_in_usd = curr_price / kurzy.get("CZK", 20.85)
            elif curr_currency == "EUR":
                price_in_usd = curr_price * kurzy.get("EUR", 1.16)
                
            aktualni_hodnota_usd = kusy * price_in_usd
            investovano_usd = investovano # Předpokládáme vstup v USD nebo přepočet při nákupu (zjednodušení)
            
            # Pokud byla investice v jiné měně, museli bychom to přepočítat, 
            # ale pro zachování logiky starého kódu to držíme takto.
            
            zisk_usd = aktualni_hodnota_usd - investovano_usd
            zisk_pct = (zisk_usd / investovano_usd) if investovano_usd != 0 else 0
            
            celk_hod_usd += aktualni_hodnota_usd
            celk_inv_usd += investovano_usd
            
            # Získání Divi Yield (pro analýzu) - jen pokud je to potřeba
            divi_yield = ziskej_yield(ticker)

            viz_data.append({
                "Ticker": ticker,
                "Kusy": kusy,
                "Průměr": avg_cena,
                "Cena": curr_price,
                "Měna": curr_currency,
                "HodnotaUSD": aktualni_hodnota_usd,
                "InvesticeUSD": investovano_usd,
                "Zisk": zisk_usd,
                "Zisk%": zisk_pct,
                "Sektor": group.iloc[0]['Sektor'], # Bereme sektor z prvního záznamu
                "Divi": divi_yield
            })
            
            # Uložení fundamentů pro cache
            fundament_data[ticker] = {
                "trailingPE": 0, # Placeholder, v reálu by se stahovalo asynchronně
                "dividendYield": divi_yield,
                "currency": curr_currency,
                "currentPrice": curr_price
            }

    vdf = pd.DataFrame(viz_data)
    
    # 3. VÝPOČET ZMĚNY 24H (Zjednodušený odhad podle denní změny ceny akcií)
    zmena_24h_usd = 0
    if not vdf.empty:
        # Simulace denní změny (protože yfinance fast_info nemá vždy pct change hned)
        # Ve starém kódu se to počítalo přes last_price vs previous_close
        for _, row in vdf.iterrows():
            ticker = row['Ticker']
            try:
                # Zkusíme získat změnu z live dat, pokud tam není, stáhneme
                t_obj = yf.Ticker(ticker)
                prev = t_obj.fast_info.previous_close
                curr = row['Cena']
                if prev and prev > 0:
                    day_change_usd = (curr - prev) * row['Kusy']
                    
                    # Převod na USD pokud je to CZK/EUR
                    if row['Měna'] == "CZK": day_change_usd /= kurzy.get("CZK", 20.85)
                    elif row['Měna'] == "EUR": day_change_usd *= kurzy.get("EUR", 1.16)
                    
                    zmena_24h_usd += day_change_usd
                    
                    # Přidáme info o denní změně do VDF pro řazení (Top Movers)
                    row_idx = vdf[vdf['Ticker'] == ticker].index[0]
                    vdf.at[row_idx, 'Dnes'] = (curr / prev) - 1
                else:
                    row_idx = vdf[vdf['Ticker'] == ticker].index[0]
                    vdf.at[row_idx, 'Dnes'] = 0.0
            except:
                pass
    
    pct_24h = (zmena_24h_usd / celk_hod_usd * 100) if celk_hod_usd > 0 else 0
    
    # 4. HOTOVOST
    cash_usd = zustatky.get("USD", 0) + (zustatky.get("CZK", 0) / kurzy.get("CZK", 20.85)) + (zustatky.get("EUR", 0) * kurzy.get("EUR", 1.16))
    
    # 5. AKTUALIZACE GRAFU VÝVOJE
    hist_vyvoje = aktualizuj_graf_vyvoje(user, celk_hod_usd + cash_usd) # Graf sleduje Net Worth (Akcie + Cash)

    # 6. RETURN BALÍČEK (DATA CORE)
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
        'kurzy': kurzy, # Vracíme kurzy, aby byly dostupné globálně
        'timestamp': datetime.now() # Pro kontrolu stáří cache
    }
