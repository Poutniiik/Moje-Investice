import requests
import pandas as pd
import streamlit as st  # Přidán import pro přístup k trezoru
from datetime import datetime, timedelta

# ==========================================
# 👇 BEZPEČNÉ NAČTENÍ KLÍČŮ Z TREZORU 👇
# Už žádné klíče natvrdo v kódu!
# ==========================================

try:
    PLAID_CLIENT_ID = st.secrets["plaid"]["client_id"]
    PLAID_SECRET = st.secrets["plaid"]["secret"]
except Exception:
    # Fallback pro případ, že klíče v trezoru chybí (aby aplikace nespadla hned)
    PLAID_CLIENT_ID = ""
    PLAID_SECRET = ""

# ==========================================

# Používáme čisté API volání
BASE_URL = "https://sandbox.plaid.com"

def simulace_pripojeni():
    """Vytvoří fiktivní připojení k bance v Sandboxu (přes Requests)."""
    
    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        return "Chyba: Chybí API klíče v nastavení (Secrets)."

    try:
        # 1. Vytvoření veřejného tokenu (Simulace loginu)
        url_pt = f"{BASE_URL}/sandbox/public_token/create"
        payload_pt = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "institution_id": "ins_109508", # Platypus Bank
            "initial_products": ["transactions"]
        }
        
        r_pt = requests.post(url_pt, json=payload_pt)
        if r_pt.status_code != 200: return f"Chyba Public Token: {r_pt.text}"
        
        public_token = r_pt.json()['public_token']
        
        # 2. Výměna za Access Token (Klíč k datům)
        url_ex = f"{BASE_URL}/item/public_token/exchange"
        payload_ex = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "public_token": public_token
        }
        
        r_ex = requests.post(url_ex, json=payload_ex)
        if r_ex.status_code != 200: return f"Chyba Access Token: {r_ex.text}"
        
        return r_ex.json()['access_token']

    except Exception as e:
        return f"Kritická chyba: {str(e)}"

def stahni_data(access_token):
    """Stáhne transakce za posledních 90 dní (přes Requests)."""
    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        return None

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
        
        # Zpracování do tabulky
        data_list = []
        for t in data_json['transactions']:
            amount = -t['amount'] 
            cat = t['category'][0] if 'category' in t and t['category'] else "Ostatní"
            
            data_list.append({
                "Datum": t['date'],
                "Obchodník": t['name'],
                "Částka": amount,
                "Měna": t['iso_currency_code'],
                "Kategorie": cat,
                "Druh": "Výdaj" if amount < 0 else "Příjem"
            })
            
        return pd.DataFrame(data_list)
    except Exception as e:
        return None
