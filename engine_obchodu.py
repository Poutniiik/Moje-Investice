import pandas as pd
from datetime import datetime
import streamlit as st # Potřebujeme pro session state, pokud s ním pracujeme
from data_manager import (
    uloz_data_uzivatele, 
    SOUBOR_DATA, 
    SOUBOR_CASH, 
    SOUBOR_HISTORIE
)
# Funkce ziskej_info importujeme až uvnitř funkcí nebo si ji vyžádáme jako parametr, 
# abychom se vyhnuli kruhovým importům. Pro teď použijeme utils.
from utils import ziskej_info

# --- ATOMICKÁ FUNKCE: POHYB PENĚZ ---
def pohyb_penez(castka, mena, typ, poznamka, user, df_cash_temp):
    """
    Provede pohyb peněz a vrátí upravený DataFrame.
    """
    novy = pd.DataFrame([{"Typ": typ, "Castka": float(castka), "Mena": mena, "Poznamka": poznamka, "Datum": datetime.now(), "Owner": user}])
    df_cash_temp = pd.concat([df_cash_temp, novy], ignore_index=True)
    return df_cash_temp

# --- ATOMICKÁ FUNKCE: PROVEDENÍ NÁKUPU ---
def proved_nakup(ticker, kusy, cena, user):
    # Musíme načíst data ze Session State, protože funkce žije teď bokem
    df_p = st.session_state['df'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    
    # Zjistíme měnu (použijeme utils funkci)
    _, mena, _ = ziskej_info(ticker)
    
    cost = kusy * cena
    
    # Rychlý výpočet zůstatku pro kontrolu (zjednodušený get_zustatky)
    aktualni_zustatek = df_cash_temp[df_cash_temp['Mena'] == mena]['Castka'].sum()

    if aktualni_zustatek >= cost:
        # Krok 1: Odepsání hotovosti (lokálně)
        df_cash_temp = pohyb_penez(-cost, mena, "Nákup", ticker, user, df_cash_temp)
        
        # Krok 2: Připsání akcií (lokálně)
        d = pd.DataFrame([{"Ticker": ticker, "Pocet": kusy, "Cena": cena, "Datum": datetime.now(), "Owner": user, "Sektor": "Doplnit", "Poznamka": "CLI/Auto"}])
        df_p = pd.concat([df_p, d], ignore_index=True)
        
        # Krok 3: Uložení
        try:
            uloz_data_uzivatele(df_p, user, SOUBOR_DATA)
            uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
            
            # Aktualizace Session State
            st.session_state['df'] = df_p
            st.session_state['df_cash'] = df_cash_temp
            
            # Invalidace (nastavíme timestamp na starý, aby se při refresh přepočítalo)
            if 'data_core' in st.session_state:
                del st.session_state['data_core'] # Jednoduše smažeme cache
            
            return True, f"✅ Koupeno: {kusy}x {ticker} za {cena:,.2f} {mena}"
        except Exception as e:
            return False, f"❌ Chyba zápisu transakce (NÁKUP): {e}"
    else:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {aktualni_zustatek:,.2f})"

# --- ATOMICKÁ FUNKCE: PROVEDENÍ PRODEJE ---
def proved_prodej(ticker, kusy, cena, user, mena_input):
    df_p = st.session_state['df'].copy()
    df_h = st.session_state['df_hist'].copy()
    df_cash_temp = st.session_state['df_cash'].copy()
    
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')

    final_mena = mena_input
    if final_mena is None or final_mena == "N/A":
        final_mena = "USD" # Fallback

    if df_t.empty or df_t['Pocet'].sum() < kusy:
        return False, "Nedostatek kusů."

    zbyva, zisk, trzba = kusy, 0, kusy * cena
    df_p_novy = df_p.copy()

    # Logika odebrání kusů (FIFO)
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

    # Krok 1: Záznam do historie
    new_h = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, "Mena": final_mena, "Datum": datetime.now(), "Owner": user}])
    df_h = pd.concat([df_h, new_h], ignore_index=True)
    
    # Krok 2: Připsání hotovosti
    df_cash_temp = pohyb_penez(trzba, final_mena, "Prodej", f"Prodej {ticker}", user, df_cash_temp)
    
    # Krok 3: Uložení
    try:
        uloz_data_uzivatele(df_p_novy, user, SOUBOR_DATA)
        uloz_data_uzivatele(df_h, user, SOUBOR_HISTORIE)
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        
        st.session_state['df'] = df_p_novy
        st.session_state['df_hist'] = df_h
        st.session_state['df_cash'] = df_cash_temp
        
        if 'data_core' in st.session_state: del st.session_state['data_core']
        
        return True, f"Prodáno! +{trzba:,.2f} {final_mena} (Zisk: {zisk:,.2f})"
    except Exception as e:
        return False, f"❌ Chyba zápisu transakce (PRODEJ): {e}"

# --- ATOMICKÁ FUNKCE: PROVEDENÍ SMĚNY ---
def proved_smenu(castka, z_meny, do_meny, user):
    # Potřebujeme kurzy. Zkusíme je vzít z cache, jinak default
    kurzy = {"CZK": 20.85, "EUR": 1.16} 
    if 'data_core' in st.session_state:
        kurzy = st.session_state['data_core'].get('kurzy', kurzy)

    df_cash_temp = st.session_state['df_cash'].copy()
    
    # Kalkulace směny
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy.get("CZK", 20.85)
    elif z_meny == "EUR": castka_usd = castka / kurzy.get("EUR", 1.16) * kurzy.get("CZK", 20.85) / kurzy.get("CZK", 20.85) # Zjednodušeno

    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurzy.get("CZK", 20.85)
    elif do_meny == "EUR": vysledna = castka_usd / kurzy.get("EUR", 1.16)

    # Krok 1: Odepsání a připsání
    df_cash_temp = pohyb_penez(-castka, z_meny, "Směna", f"Směna na {do_meny}", user, df_cash_temp)
    df_cash_temp = pohyb_penez(vysledna, do_meny, "Směna", f"Směna z {z_meny}", user, df_cash_temp)
    
    # Krok 2: Uložení
    try:
        uloz_data_uzivatele(df_cash_temp, user, SOUBOR_CASH)
        st.session_state['df_cash'] = df_cash_temp
        if 'data_core' in st.session_state: del st.session_state['data_core']
        return True, f"Směněno: {vysledna:,.2f} {do_meny}"
    except Exception as e:
        return False, f"❌ Chyba zápisu transakce (SMĚNA): {e}"
