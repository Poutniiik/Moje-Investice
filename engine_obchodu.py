import pandas as pd
from datetime import datetime

def proved_nakup_engine(ticker, kusy, cena, user, df_portfolio, df_cash, zustatky, ziskej_info_funkce, uloz_funkce, soubory):
    """
    LOGIKA NÁKUPU: Vypočítá náklady a přidá akcie.
    Nikoho neimportuje, vše dostává v argumentech.
    """
    # 1. Zjištění měny přes předanou funkci
    _, mena, _ = ziskej_info_funkce(ticker)
    cost = kusy * cena

    # 2. Kontrola peněz
    if zustatky.get(mena, 0) < cost:
        return False, f"❌ Nedostatek {mena} (Potřeba: {cost:,.2f})", None, None

    # 3. Příprava nových dat v paměti
    df_p_new = df_portfolio.copy()
    df_cash_new = df_cash.copy()

    # 4. Zápis pohybu peněz (náhrada za pohyb_penez)
    novy_pohyb = pd.DataFrame([{
        "Typ": "Nákup", 
        "Castka": -float(cost), 
        "Mena": mena, 
        "Poznamka": ticker, 
        "Datum": datetime.now(), 
        "Owner": user
    }])
    df_cash_new = pd.concat([df_cash_new, novy_pohyb], ignore_index=True)
    
    # 5. Zápis akcií
    nova_akcie = pd.DataFrame([{
        "Ticker": ticker, "Pocet": kusy, "Cena": cena, "Datum": datetime.now(), 
        "Owner": user, "Sektor": "Doplnit", "Poznamka": "Obchod"
    }])
    df_p_new = pd.concat([df_p_new, nova_akcie], ignore_index=True)

    # 6. Uložení přes předanou ukládací funkci
    try:
        uloz_funkce(df_p_new, user, soubory['data'])
        uloz_funkce(df_cash_new, user, soubory['cash'])
        return True, f"✅ Koupeno: {kusy}x {ticker}", df_p_new, df_cash_new
    except Exception as e:
        return False, f"❌ Chyba zápisu: {e}", None, None


def proved_prodej_engine(ticker, kusy, cena, user, mena_input, df_p, df_h, df_cash, live_data_context, uloz_funkce, soubory):
    """
    LOGIKA PRODEJE: FIFO odečtení akcií a připsání peněz.
    """
    df_t = df_p[df_p['Ticker'] == ticker].sort_values('Datum')

    # Zjištění měny (z vstupů nebo z kontextu živých dat)
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

    # FIFO Logika (vypůjčeno z tvého originálu)
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

    # Zápis historie
    new_h = pd.DataFrame([{
        "Ticker": ticker, "Kusu": kusy, "Prodejka": cena, "Zisk": zisk, 
        "Mena": final_mena, "Datum": datetime.now(), "Owner": user
    }])
    df_h_novy = pd.concat([df_h_novy, new_h], ignore_index=True)
    
    # Připsání peněz (náhrada za pohyb_penez)
    pohyb_trzba = pd.DataFrame([{
        "Typ": "Prodej", "Castka": float(trzba), "Mena": final_mena, 
        "Poznamka": f"Prodej {ticker}", "Datum": datetime.now(), "Owner": user
    }])
    df_cash_novy = pd.concat([df_cash_novy, pohyb_trzba], ignore_index=True)

    # Uložení
    try:
        uloz_funkce(df_p_novy, user, soubory['data'])
        uloz_funkce(df_h_novy, user, soubory['historie'])
        uloz_funkce(df_cash_novy, user, soubory['cash'])
        return True, f"Prodáno! +{trzba:,.2f} {final_mena}", df_p_novy, df_h_novy, df_cash_novy
    except Exception as e:
        return False, f"❌ Chyba zápisu: {e}", None, None, None

def proved_smenu_engine(castka, z_meny, do_meny, user, df_cash, kurzy, uloz_funkce, soubor_cash):
    """
    Logika směny peněz: Odečte jednu měnu, přičte druhou dle kurzu.
    """
    df_cash_new = df_cash.copy()
    
    # 1. Kalkulace směny (převod přes USD jako základ)
    # Kurz CZK je např. 25, Kurz EUR je např. 1.1 (vůči USD)
    if z_meny == "USD": castka_usd = castka
    elif z_meny == "CZK": castka_usd = castka / kurzy.get("CZK", 23.0)
    elif z_meny == "EUR": castka_usd = castka * kurzy.get("EUR", 1.08) # Zjednodušený převod EUR->USD

    if do_meny == "USD": vysledna = castka_usd
    elif do_meny == "CZK": vysledna = castka_usd * kurzy.get("CZK", 23.0)
    elif do_meny == "EUR": vysledna = castka_usd / kurzy.get("EUR", 1.08)

    # 2. Zápis pohybu - ODCHOD (mínus)
    odchod = pd.DataFrame([{
        "Typ": "Směna", "Castka": -float(castka), "Mena": z_meny, 
        "Poznamka": f"Směna na {do_meny}", "Datum": datetime.now(), "Owner": user
    }])
    
    # 3. Zápis pohybu - PŘÍCHOD (plus)
    prichod = pd.DataFrame([{
        "Typ": "Směna", "Castka": float(vysledna), "Mena": do_meny, 
        "Poznamka": f"Směna z {z_meny}", "Datum": datetime.now(), "Owner": user
    }])
    
    df_cash_new = pd.concat([df_cash_new, odchod, prichod], ignore_index=True)

    # 4. Uložení
    try:
        uloz_funkce(df_cash_new, user, soubor_cash)
        return True, f"Směněno: {vysledna:,.2f} {do_meny}", df_cash_new
    except Exception as e:
        return False, f"❌ Chyba zápisu směny: {e}", None
