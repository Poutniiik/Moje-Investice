import streamlit as st
import requests
import os

def init_telegram():
    """
    Načte klíče pro Telegram.
    1. Zkusí Streamlit secrets (pro web).
    2. Zkusí Environment Variables (pro robota/GitHub Actions).
    """
    token, chat_id = None, None

    # 1. Zkusíme Streamlit Secrets (pokud běžíme v appce)
    try:
        if "telegram" in st.secrets:
            token = st.secrets["telegram"]["bot_token"]
            chat_id = st.secrets["telegram"]["chat_id"]
    except FileNotFoundError:
        pass # Nejsme ve Streamlitu nebo chybí secrets.toml
    except Exception:
        pass

    # 2. Pokud stále nemáme, zkusíme Environment Variables (pro Robota)
    if not token:
        token = os.environ.get("TG_BOT_TOKEN")
    if not chat_id:
        chat_id = os.environ.get("TG_CHAT_ID")

    return token, chat_id

def poslat_zpravu(text):
    """
    Odešle zprávu přes Telegram Bota.
    """
    token, chat_id = init_telegram()
    
    if not token or not chat_id:
        print("❌ CHYBA: Chybí konfigurace Telegramu (secrets nebo ENV).")
        return False, "Chybí konfigurace Telegramu"
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML" 
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
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
