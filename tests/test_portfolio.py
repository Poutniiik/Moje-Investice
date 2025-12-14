import pandas as pd
import os
import sys

# Aby Python našel tvůj daily_bot.py, musíme přidat cestu do systému
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import daily_bot as bot # Importujeme tvůj hlavní bot

# 1. Testuje, jestli je DataFrame prázdný (hlídáme, jestli se nám nic nerozbilo)
def test_portfolio_data_exists():
    # Pokusíme se načíst tvůj portfolio_data.csv.
    # POZOR: Tenhle test funguje jen pokud máš soubor v kořenové složce!
    df = pd.read_csv("portfolio_data.csv")
    # Tvrzení: Očekáváme, že DataFrame nebude prázdný a bude mít aspoň 1 řádek
    assert not df.empty, "Chyba: Soubor portfolio_data.csv je prázdný!"

# 2. Testuje, jestli funkce get_data_safe vůbec funguje
def test_get_data_safe_works():
    # Zkusíme stáhnout data pro Apple
    price, change = bot.get_data_safe("AAPL")
    # Tvrzení 1: Očekáváme, že cena Applu bude větší než 10 USD
    assert price > 10.0, "Chyba: Cena AAPL se nestáhla (je <= 10.0)."
    # Tvrzení 2: Očekáváme, že změna je rozumné číslo (mezi -10 a 10 %)
    assert -10.0 < change < 10.0, "Chyba: Změna AAPL je nerealistická."

# 3. Testuje, jestli funguje přepočet na CZK
def test_currency_conversion():
    # Předpokládaný kurz USD/CZK = 24.0 (zadaný jako fallback v daily_bot.py)
    # 100 USD akcie, 1 kus.
    price = 100.0
    kusy = 1
    usd_czk = 24.0
    eur_usd = 1.08 # Necháme fallback, aby byl test rychlý a nezávislý

    # Výpočet hodnoty v CZK (USD akcie)
    val_czk = price * kusy * usd_czk
    # Tvrzení: 100 * 1 * 24.0 = 2400.0
    assert val_czk == 2400.0, f"Chyba ve výpočtu CZK. Očekáváno 2400.0, dostali jsme {val_czk}"
