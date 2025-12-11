import streamlit as st
import requests
import os # NOVÝ IMPORT

def init_telegram():
    """Načte klíče pro Telegram ze secrets.toml nebo z ENV (pro GitHub Actions)."""
    
    # 1. Zkusíme Streamlit Secrets (pro Streamlit app)
    try:
        if "telegram" in st.secrets:
            token = st.secrets["telegram"]["bot_token"]
            chat_id = st.secrets["telegram"]["chat_id"]
            return token, chat_id
    except Exception:
        pass # Pokračujeme na ENV
        
    # 2. Zkusíme Environment Variables (pro GitHub Actions)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        return token, chat_id
    
    return None, None

# ... zbytek souboru (poslat_zpravu a otestovat_tlacitko) zůstane stejný.

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
            return False, f"❌ Chyba Telegramu: {response.text}"
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
