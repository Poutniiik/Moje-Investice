import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# ==========================================
# 👇 NASTAVENÍ PROSTŘEDÍ (Sandbox vs. Development) 👇
# ==========================================

# 1. Vyber prostředí: "sandbox" (testovací) nebo "development" (reálné banky)
PLAID_ENV = "sandbox"

# 2. Nastavení URL podle prostředí
if PLAID_ENV == "sandbox":
    BASE_URL = "https://sandbox.plaid.com"
    INSTITUTION_ID = "ins_109508" 
elif PLAID_ENV == "development":
    BASE_URL = "https://development.plaid.com"
    INSTITUTION_ID = "ins_109508" # Zde pak bude reálná banka

# 3. Načtení klíčů (BEZPEČNÁ IMPLEMENTACE Z SECRETS)
# Klíče se načtou s prázdným řetězcem jako fallback, aby se zabránilo chybám.
PLAID_CLIENT_ID = st.secrets.get("plaid", {}).get("client_id", "")
PLAID_SECRET = st.secrets.get("plaid", {}).get(f"secret_{PLAID_ENV}", "")

# ==========================================

def simulace_pripojeni():
    """
    Vytvoří připojení k bance a vymění Public Token za Access Token (Sandbox).
    Vrací Access Token nebo chybovou zprávu.
    """
    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        return "Chyba: Chybí Plaid API klíče v secrets.toml."

    if PLAID_ENV == "development":
        return "⚠️ Pro Development režim je potřeba Plaid Link (Frontend) a skutečná banka."

    try:
        # 1. Vytvoření veřejného tokenu (Public Token)
        url_pt = f"{BASE_URL}/sandbox/public_token/create"
        payload_pt = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "institution_id": INSTITUTION_ID, 
            "initial_products": ["transactions"]
        }
        
        r_pt = requests.post(url_pt, json=payload_pt)
        if r_pt.status_code != 200: 
            return f"Chyba Public Token (krok 1): {r_pt.text}"
        
        public_token = r_pt.json()['public_token']
        
        # 2. Výměna za Access Token
        url_ex = f"{BASE_URL}/item/public_token/exchange"
        payload_ex = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "public_token": public_token
        }
        
        r_ex = requests.post(url_ex, json=payload_ex)
        if r_ex.status_code != 200: 
            return f"Chyba Access Token (krok 2): {r_ex.text}"
        
        return r_ex.json()['access_token']

    except Exception as e:
        return f"Kritická chyba simulace: {str(e)}"

def stahni_data(access_token):
    """
    Stáhne transakce za posledních 90 dní.
    POZN: Plaid vrací výdaje jako KLADNÉ částky.
    """
    if not PLAID_CLIENT_ID or not PLAID_SECRET: return None

    try:
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        url_tr = f"{BASE_URL}/transactions/get"
        payload_tr = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "access_token": access_token,
            "start_date": start_date,
            "end_date": end_date,
            "options": {"count": 100}
        }
        
        r = requests.post(url_tr, json=payload_tr)
        if r.status_code != 200: return None
        
        data_json = r.json()
        data_list = []
        for t in data_json['transactions']:
            # Převedeme KLADNÉ Plaid částky na KLASICKÉ finanční (Výdaje jako záporné)
            # Protože Plaid vrací amount jako 'user-facing value'
            amount_klasicke_finance = -t['amount'] 
            
            # Získání kategorie
            cat = t['category'][0] if 'category' in t and t['category'] else "Ostatní"
            
            data_list.append({
                "Datum": t['date'],
                "Obchodník": t['name'],
                "Částka": amount_klasicke_finance,
                "Měna": t['iso_currency_code'],
                "Kategorie": cat,
                "Druh": "Výdaj" if amount_klasicke_finance < 0 else "Příjem"
            })
        return pd.DataFrame(data_list)
    except Exception:
        return None

# --- NOVÁ FUNKCE: ZŮSTATKY 💰 ---
def stahni_zustatky(access_token):
    """Zjistí aktuální zůstatek na účtech (Available/Current)."""
    if not PLAID_CLIENT_ID or not PLAID_SECRET: return None

    try:
        url_bal = f"{BASE_URL}/accounts/balance/get"
        payload_bal = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "access_token": access_token
        }
        
        r = requests.post(url_bal, json=payload_bal)
        if r.status_code != 200: return None
        
        accounts = r.json()['accounts']
        results = []
        
        for acc in accounts:
            # Preferujeme "available" (disponibilní) před "current" (účetní)
            bal = acc['balances']['available'] if acc['balances']['available'] is not None else acc['balances']['current']
            
            results.append({
                "Název účtu": acc['name'],
                "Zůstatek": bal,
                "Měna": acc['balances']['iso_currency_code'],
                "Typ": acc['subtype']
            })
            
        return pd.DataFrame(results)
        
    except Exception:
        return None
