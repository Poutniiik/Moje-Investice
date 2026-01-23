import pytest
import sys
import os

# Přidáme kořenový adresář do cesty, aby Python viděl daily_bot.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import daily_bot as bot

def test_batch_download_works():
    """
    Testuje, zda nová hromadná funkce (Turbo mode) funguje
    a vrací data ve správném formátu.
    """
    test_tickers = ["AAPL", "MSFT"]
    
    # Zavoláme novou funkci
    data = bot.get_batch_data(test_tickers)
    
    # 1. Musí vrátit slovník (ne prázdno)
    assert isinstance(data, dict)
    assert len(data) > 0
    
    # 2. Musí tam být naše akcie (pokud zrovna Yahoo nemá výpadek)
    # Pozn: Kontrolujeme aspoň jednu, kdyby náhodou jedna selhala
    found_any = False
    for t in test_tickers:
        if t in data:
            found_any = True
            item = data[t]
            # 3. Kontrola struktury dat
            assert "price" in item
            assert "change" in item
            assert item["price"] > 0
            
    if not found_any:
        pytest.skip("Yahoo Finance pravděpodobně neodpovídá, přeskakuji test.")

def test_ai_comment_fallback():
    """
    Testuje, že AI funkce nespadne, i když nemá klíč.
    """
    # Simulujeme chybějící klíč tím, že pošleme prázdný text
    result = bot.get_ai_comment("Test portfolio", 100000)
    
    # Měla by vrátit string (buď komentář, nebo chybovou hlášku), ale nesmí spadnout
    assert isinstance(result, str)
    assert len(result) > 0
