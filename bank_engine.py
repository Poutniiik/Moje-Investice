import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from datetime import datetime, timedelta
import pandas as pd

# --- 1. KONFIGURACE (Tvoje klíče) ---
PLAID_CLIENT_ID = "6936237b139fbf00216fb766"
PLAID_SECRET = “05377cff894a1c4d86e5d3ea1caea2"
PLAID_ENV = plaid.Environment.Sandbox # Jsme na pískovišti

# --- 2. PŘIPOJENÍ K PLAIDU ---
configuration = plaid.Configuration(
    host=PLAID_ENV,
    api_key={
        'clientId': PLAID_CLIENT_ID,
        'secret': PLAID_SECRET,
    }
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

def simulace_pripojeni_banky():
    """
    V Sandboxu vytvoříme fiktivní připojení k bance (bez loginu uživatele),
    abychom získali ACCESS_TOKEN pro testování.
    """
    try:
        # A. Vytvoříme veřejný token (Jakože uživatel se přihlásil do 'Insomniac Bank')
        pt_request = SandboxPublicTokenCreateRequest(
            institution_id='ins_1', # ID testovací banky
            initial_products=[Products('transactions')]
        )
        pt_response = client.sandbox_public_token_create(pt_request)
        public_token = pt_response['public_token']
        
        # B. Vyměníme ho za ACCESS TOKEN (Klíč k datům)
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']
        
        return access_token
    except Exception as e:
        return f"Chyba při simulaci: {e}"

def stahni_transakce(access_token):
    """
    Stáhne historii transakcí pomocí Access Tokenu.
    """
    try:
        # Nastavíme okno (posledních 90 dní)
        start_date = (datetime.now() - timedelta(days=90)).date()
        end_date = datetime.now().date()
        
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
        )
        response = client.transactions_get(request)
        transactions = response['transactions']
        
        # Převedeme na hezkou tabulku (Pandas DataFrame)
        data = []
        for t in transactions:
            data.append({
                "Datum": t['date'],
                "Obchodník": t['name'],
                "Částka": t['amount'], # Pozor: Plaid má kladná čísla jako výdaje!
                "Měna": t['iso_currency_code'],
                "Kategorie": t['category'][0] if t['category'] else "Neznámé"
            })
            
        return pd.DataFrame(data)
    
    except Exception as e:
        return None
