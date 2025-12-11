import streamlit as st
import pandas as pd
import time
import random
from . import bank_page

def simulace_pripojeni():
    """Simuluje připojení k bance a vrátí fiktivní token."""
    time.sleep(1.5) # Jakože to chvíli trvá
    # Simulace chyby občas (volitelné)
    # if random.random() < 0.1: return "Chyba: Banka neodpovídá (Timeout)"
    return "TOKEN_SECURE_12345"

def stahni_zustatky(token):
    """Vrátí DataFrame se zůstatky na účtech."""
    if not token or "Chyba" in token: return None
    
    data = [
        {"Název účtu": "Běžný účet", "Zůstatek": 12500.00, "Měna": "CZK"},
        {"Název účtu": "Spořicí účet", "Zůstatek": 50000.00, "Měna": "CZK"},
        {"Název účtu": "USD Wallet", "Zůstatek": 1250.00, "Měna": "USD"}
    ]
    return pd.DataFrame(data)

def stahni_data(token):
    """Vrátí DataFrame s historií transakcí."""
    if not token or "Chyba" in token: return None
    
    # Fiktivní transakce
    transakce = [
        {"Datum": "2023-12-10", "Částka": -250.0, "Měna": "CZK", "Druh": "Potraviny", "Popis": "Albert Supermarket"},
        {"Datum": "2023-12-09", "Částka": -1200.0, "Měna": "CZK", "Druh": "Nafta", "Popis": "Shell"},
        {"Datum": "2023-12-08", "Částka": 25000.0, "Měna": "CZK", "Druh": "Mzda", "Popis": "Výplata"},
        {"Datum": "2023-12-05", "Částka": -450.0, "Měna": "CZK", "Druh": "Zábava", "Popis": "Netflix"},
    ]
    return pd.DataFrame(transakce)
