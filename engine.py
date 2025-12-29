import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

# Importujeme potřebné věci z tvých existujících modulů
from data_manager import (
    uloz_data_uzivatele, SOUBOR_DATA, SOUBOR_CASH, 
    SOUBOR_HISTORIE, SOUBOR_DIVIDENDY, SOUBOR_WATCHLIST
)
from utils import ziskej_info

def invalidate_data_core():
    """Vynucený refresh: Zneplatní vypočtené jádro a donutí aplikaci načíst čerstvá data."""
    if 'data_core' in st.session_state:
        st.session_state['data_core']['timestamp'] = datetime.now() - timedelta(minutes=6)
    
    raw_data_keys = ['df', 'df_hist', 'df_cash', 'df_div', 'df_watch']
    for key in raw_data_keys:
        if key in st.session_state:
            del st.session_state[key]

def pohyb_penez(castka, mena, typ, poznamka, user, df_cash_temp):
    """Provede pohyb peněz v paměťovém DataFrame."""
    novy = pd.DataFrame([{
        "Typ": typ, 
        "Castka": float(castka), 
        "Mena": mena, 
        "Poznamka": poznamka, 
        "Datum": datetime.now(), 
        "Owner": user
    }])
    return pd.concat([df_cash_temp, novy], ignore_index=True)

#def proved_nakup(ticker, kusy, cena, user, current_df, current_cash_df, zustatky, add_xp_fn):
    """Logika provedení nákupu akcie."""
    _, mena, _ = ziskej_info(ticker)
    cost = kusy * cena
    
    if zustatky.get(mena, 0) >= cost:
        # 1. Úprava hotovosti
        new_cash_df = pohyb_penez(-cost, mena, "Nákup", ticker, user, current_cash_df)
        
        # 2. Úprava akcií
        new_row = pd.DataFrame([{
            "Ticker": ticker, "Pocet": kusy, "Cena": cena, 
            "Datum": datetime.now(), "Owner": user, 
            "Sektor": "Doplnit", "Poznamka": "CLI/Auto"
        }])
        new_portfolio_df = pd.concat([current_df, new_row], ignore_index=True)
        
        try:
            # 3. Zápis na GitHub
            uloz_data_uzivatele(new_portfolio_df, user, SOUBOR_DATA)
            uloz_data_uzivatele(new_cash_df, user, SOUBOR_CASH)
            
            # 4. Odměna XP přes funkci z main
            add_xp_fn(user, 50)
            invalidate_data_core()
            return True, f"✅ Koupeno: {kusy}x {ticker} za {cena:,.2f} {mena}"
        except Exception as e:
            return False, f"❌ Chyba zápisu na GitHub: {e}"
    else:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {zustatky.get(mena, 0):,.2f})"

def proved_prodej(ticker, kusy, cena, user, current_df, current_hist_df, current_cash_df, mena_input, invalidate_fn):
    """Logika provedení prodeje akcie."""
    df_t = current_df[current_df['Ticker'] == ticker].sort_values('Datum')

    if df_t.empty or df_t['Pocet'].sum() < kusy:
        return False, "Nedostatek kusů k prodeji."

    zbyva, zisk, trzba = kusy, 0, kusy * cena
    df_p_novy = current_df.copy()
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

    # Záznam historie a hotovosti
    new_h = pd.DataFrame([{
        "Ticker": ticker, "Kusu": kusy, "Prodejka": cena, 
        "Zisk": zisk, "Mena": mena_input, "Datum": datetime.now(), "Owner": user
    }])
    df_h_updated = pd.concat([current_hist_df, new_h], ignore_index=True)
    df_cash_updated = pohyb_penez(trzba, mena_input, "Prodej", f"Prodej {ticker}", user, current_cash_df)

    try:
        uloz_data_uzivatele(df_p_novy, user, SOUBOR_DATA)
        uloz_data_uzivatele(df_h_updated, user, SOUBOR_HISTORIE)
        uloz_data_uzivatele(df_cash_updated, user, SOUBOR_CASH)
        invalidate_fn()
        return True, f"Prodáno! +{trzba:,.2f} {mena_input} (Zisk: {zisk:,.2f})"
    except Exception as e:
        return False, f"❌ Chyba zápisu prodeje: {e}"

def pridat_dividendu(ticker, castka, mena, user, current_div_df, current_cash_df, add_xp_fn):
    """Zaznamená dividendu a připíše hotovost."""
    new_div = pd.DataFrame([{
        "Ticker": ticker, "Castka": float(castka), 
        "Mena": mena, "Datum": datetime.now(), "Owner": user
    }])
    updated_div_df = pd.concat([current_div_df, new_div], ignore_index=True)
    updated_cash_df = pohyb_penez(castka, mena, "Dividenda", f"Divi {ticker}", user, current_cash_df)
    
    try:
        uloz_data_uzivatele(updated_div_df, user, SOUBOR_DIVIDENDY)
        uloz_data_uzivatele(updated_cash_df, user, SOUBOR_CASH)
        add_xp_fn(user, 30)
        invalidate_data_core()
        return True, f"✅ Připsána dividenda {castka} {mena} od {ticker}"
    except Exception as e:
        return False, f"❌ Chyba zápisu dividendy: {e}"
