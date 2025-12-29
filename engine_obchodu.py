import pandas as pd
from datetime import datetime
from data_manager import pohyb_penez

def proved_nakup_engine(ticker, kusy, cena, user, df_portfolio, df_cash, zustatky, ziskej_info_funkce, uloz_funkce, soubory):
    """
    Logika nákupu. Všechny soubory bere z balíčku 'soubory'.
    """
    _, mena, _ = ziskej_info_funkce(ticker)
    cost = kusy * cena

    if zustatky.get(mena, 0) < cost:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f}, Máš: {zustatky.get(mena, 0):,.2f})", None, None

    df_p_new = df_portfolio.copy()
    df_cash_new = df_cash.copy()

    # Použijeme pohyb_penez (už importováno nahoře)
    df_cash_new = pohyb_penez(-cost, mena, "Nákup", ticker, user, df_cash_new)
    
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

    try:
        # TADY OPRAVA: Bereme názvy ze slovníku 'soubory'
        uloz_funkce(df_p_new, user, soubory['data'])
        uloz_funkce(df_cash_new, user, soubory['cash'])
        return True, f"✅ Koupeno: {kusy}x {ticker}", df_p_new, df_cash_new
    except Exception as e:
        return False, f"❌ Chyba zápisu na disk: {e}", None, None

def proved_prodej_engine(ticker, kusy, cena, user, mena_input, df_p, df_h, df_cash, live_data_context, uloz_funkce, soubory):
    """
    Logika prodeje: Vypočítá FIFO (First In First Out) zisk a upraví tabulky.
    """
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')

    final_mena = mena_input
    if final_mena is None or final_mena == "N/A":
        final_mena = "USD"
        if not df_t.empty and 'Měna' in df_p.columns:
            final_mena = df_p[df_p['Ticker'] == ticker].iloc[0].get('Měna', 'USD')
        else:
            final_mena = live_data_context.get(ticker, {}).get('curr', 'USD')

    if df_t.empty or df_t['Pocet'].sum() < kusy:
        return False, "Nedostatek kusů pro prodej.", None, None, None

    zbyva, zisk, trzba = kusy, 0, kusy * cena
    df_p_novy = df_p.copy()
    df_h_novy = df_h.copy()
    df_cash_novy = df_cash.copy()

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

    new_h = pd.DataFrame([{"Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, "Mena": final_mena, "Datum": datetime.now(), "Owner": user}])
    df_h_novy = pd.concat([df_h_novy, new_h], ignore_index=True)
    
    df_cash_novy = pohyb_penez(trzba, final_mena, "Prodej", f"Prodej {ticker}", user, df_cash_novy)

    try:
        uloz_funkce(df_p_novy, user, soubory['data'])
        uloz_funkce(df_h_novy, user, soubory['historie'])
        uloz_funkce(df_cash_novy, user, soubory['cash'])
        return True, f"Prodáno! +{trzba:,.2f} {final_mena}", df_p_novy, df_h_novy, df_cash_novy
    except Exception as e:
        return False, f"❌ Chyba zápisu: {e}", None, None, None
