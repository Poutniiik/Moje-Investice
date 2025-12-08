import requests
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 👇 ZDE VLOŽ SVÉ KLÍČE (Uvnitř uvozovek!) 👇
# ==========================================
PLAID_CLIENT_ID = "6936237b139fbf00216fb766"
PLAID_SECRET = "05377cff894a1c4d86e5d3ea1caea2"
# ==========================================

# Používáme čisté API volání (bez instalace knihoven)
BASE_URL = "https://sandbox.plaid.com"

def simulace_pripojeni():
    """Vytvoří fiktivní připojení k bance v Sandboxu (přes Requests)."""
    try:
        # 1. Vytvoření veřejného tokenu (Simulace loginu)
        url_pt = f"{BASE_URL}/sandbox/public_token/create"
        payload_pt = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "institution_id": "ins_109508", # First Platypus Bank (Sandbox)
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
