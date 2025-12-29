import pandas as pd
from datetime import datetime

# POZNÁMKA: Importuj si věci z data_manager (dm), které funkce potřebuje
# Předpokládám, že máš přístup k funkcím pohyb_penez a uloz_data_uzivatele

def proved_nakup_engine(ticker, kusy, cena, user, df_portfolio, df_cash, zustatky, ziskej_info_funkce, uloz_funkce, soubor_data, soubor_cash):
    """
    Logika nákupu oddělená od Streamlitu.
    Všechna data dostává zvenčí, aby byla nezávislá.
    """
    # 1. Zjistíme info o měně (použijeme funkci, kterou jsme dostali v argumentu)
    _, mena, _ = ziskej_info_funkce(ticker)
    cost = kusy * cena

    # 2. Kontrola zůstatku
    if zustatky.get(mena, 0) < cost:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {zustatky.get(mena, 0):,.2f})", None, None

    # 3. Výpočty (lokálně v paměti)
    # Vytvoříme kopie, abychom neupravovali původní data, dokud si nejsme jistí
    df_p_new = df_portfolio.copy()
    df_cash_new = df_cash.copy()

    # Pomocná funkce pohyb_penez (musí být dostupná nebo importovaná)
    from data_manager import pohyb_penez 
    df_cash_new = pohyb_penez(-cost, mena, "Nákup", ticker, user, df_cash_new)
    
    # Připsání akcií
    nova_transakce = pd.DataFrame([{
        "Ticker": ticker, 
        "Pocet": kusy, 
        "Cena": cena, 
        "Datum": datetime.now(), 
        "Owner": user, 
        "Sektor": "Doplnit", 
        "Poznamka": "Obchod"
    }])
    df_p_new = pd.concat([df_p_new, nova_transakce], ignore_index=True)

    # 4. Zápis do souborů (všechno najednou)
    try:
        uloz_funkce(df_p_new, user, soubor_data)
        uloz_funkce(df_cash_new, user, soubor_cash)
        # Pokud se to povedlo, vrátíme True a nová data
        return True, f"✅ Koupeno: {kusy}x {ticker}", df_p_new, df_cash_new
    except Exception as e:
        return False, f"❌ Chyba zápisu na disk: {e}", None, None
