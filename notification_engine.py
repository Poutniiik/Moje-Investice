# Soubor: notification_engine.py

import streamlit as st
import requests
import os # <--- PŘIDEJ TENTO IMPORT NAHORNÍ ČÁST SOUBORU

def init_telegram():
    """
    Načte klíče pro Telegram. 
    Priorita: 1. Systémové proměnné (pro GHA bota) 2. st.secrets (pro Streamlit).
    """
    # 1. Zkusíme načíst ze systémových proměnných (pro bota GHA/Cron)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") 
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        return token, chat_id # Načteno z prostředí (GHA)

    # 2. Fallback pro Streamlit (pro aplikaci)
    try:
        # Používáme tvé původní názvy z secrets.toml
        if "telegram" in st.secrets:
            token = st.secrets["telegram"]["bot_token"]
            chat_id = st.secrets["telegram"]["chat_id"]
            return token, chat_id
    except Exception:
        # st.secrets není dostupné
        pass
        
    return None, None
def poslat_zpravu(text):
    """
    Odešle zprávu přes Telegram Bota pomocí obyčejného HTTP požadavku.
    Používá HTML formátování.
    """
    token, chat_id = init_telegram()
    
    if not token or not chat_id:
        return False, "❌ Chybí konfigurace Telegramu v secrets.toml"
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Payload pro odeslání zprávy
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML" 
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            return True, "✅ Zpráva odeslána na Telegram!"
        else:
            # Zahrneme jen část response.text, aby to nebylo moc dlouhé
            error_detail = response.json().get("description", response.text[:100])
            return False, f"❌ Chyba Telegram API: {error_detail}"
            
    except Exception as e:
        return False, f"❌ Chyba spojení: {str(e)}"

# Ponecháme starou funkci jen pro snadné testování v Nastavení
def otestovat_tlacitko():
    """Tlačítko pro otestování spojení v Nastavení."""
    if st.button("📲 Odeslat testovací notifikaci"):
        with st.spinner("Odesílám..."):
            zprava = "🚀 <b>Terminal Pro:</b> Zkouška spojení.\nVše funguje! 😎"
            ok, msg = poslat_zpravu(zprava)
            
            if ok:
                st.success(msg)
            else:
                st.error(msg)
