import streamlit as st
import requests  # <--- Tohle je ta knihovna, kterou už máš :)

def init_telegram():
    """
    Načte klíče pro Telegram ze secrets.toml.
    """
    try:
        if "telegram" not in st.secrets:
            return None, None
        
        token = st.secrets["telegram"]["bot_token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        return token, chat_id
    except Exception:
        return None, None

def poslat_zpravu(text):
    """
    Odešle zprávu přes Telegram Bota pomocí obyčejného HTTP požadavku.
    """
    token, chat_id = init_telegram()
    
    if not token or not chat_id:
        return False, "❌ Chybí konfigurace Telegramu v secrets.toml"
        
    # Tady se skládá ta 'webová adresa', na kterou Python 'zaklepe'
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Data zprávy
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML" 
    }
    
    try:
        # Tady 'requests' odešle dopis na server Telegramu
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            return True, "✅ Zpráva odeslána na Telegram!"
        else:
            return False, f"❌ Chyba Telegramu: {response.text}"
    except Exception as e:
        return False, f"❌ Chyba spojení: {str(e)}"

def otestovat_tlacitko():
    """
    Tlačítko pro Settings.
    """
    if st.button("📲 Odeslat testovací notifikaci"):
        with st.spinner("Odesílám..."):
            zprava = "🚀 <b>Terminal Pro:</b> Zkouška spojení.\nVše funguje bez instalace knihoven! 😎"
            ok, msg = poslat_zpravu(zprava)
            
            if ok:
                st.success(msg)
            else:
                st.error(msg)
