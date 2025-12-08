# notification_engine.py
import streamlit as st
import requests

# ZAJISTÍME, ŽE SE TOTO NENAČÍTÁ PŘI IMPORTU (to zpusobuje chyby)

def _get_telegram_config():
    """Načte konfiguraci ze Streamlit Secrets."""
    try:
        token = st.secrets["telegram"]["TOKEN"]
        chat_id = st.secrets["telegram"]["CHAT_ID"]
        return token, chat_id
    except KeyError:
        return None, None

def poslat_zpravu(text_zpravy):
    """Odešle zprávu na Telegram."""
    TOKEN, CHAT_ID = _get_telegram_config()
    if not TOKEN or not CHAT_ID:
        return False, "❌ Chybí konfigurace Telegram (TOKEN nebo CHAT_ID v secrets)."

    # Použijeme HTML mód pro pěkné formátování (jako v tvém reportu)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': text_zpravy,
        'parse_mode': 'HTML' # Aby fungovalo <b> a <i>
    }

    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status() # Vyvolá HTTPError pro špatné stavy (4xx, 5xx)
        if response.json().get("ok"):
            return True, "✅ Zpráva úspěšně odeslána."
        else:
            return False, f"❌ Chyba Telegram API: {response.json().get('description', 'Neznámá chyba')}"

    except requests.exceptions.RequestException as e:
        return False, f"❌ Chyba připojení: {e}"

def otestovat_tlacitko():
    # Funkce pro stránku Nastavení
    if st.button("📲 ODESLAT TESTOVACÍ ZPRÁVU", use_container_width=True):
        ok, msg = poslat_zpravu("🤖 **TEST:** Spojení s Terminal Pro je aktivní!")
        if ok: st.success(msg)
        else: st.error(msg)
