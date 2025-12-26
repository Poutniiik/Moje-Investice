import streamlit as st
import google.generativeai as genai

# --- KONSTANTY & MANUÁL ---
APP_MANUAL = """
Jsi inteligentní asistent v aplikaci 'Terminal Pro'.
Tvá role: Radit s investicemi, vysvětlovat finanční pojmy a analyzovat portfolio uživatele.

PRAVIDLA CHOVÁNÍ:
1. Odpovídej stručně a k věci (jsi burzovní nástroj, ne spisovatel).
2. Pokud se uživatel ptá na jeho data, použij poskytnutý KONTEXT.
3. Pokud data nemáš, řekni to na rovinu.
4. Udržuj kontext konverzace (pamatuj si, o čem jsme mluvili).

MAPA APLIKACE:
1. '🏠 Přehled': Dashboard, Jmění, Hotovost, Síň slávy.
2. '📈 Analýza': Rentgen akcie, Mapa trhu, Srovnání s S&P 500.
3. '📰 Zprávy': Čtečka novinek + AI analýza.
4. '💸 Obchod': Nákup/Prodej, Banka.
5. '💎 Dividendy': Kalendář a grafy.
"""

# --- INICIALIZACE ---
def init_ai():
    """
    Pokusí se připojit k Google Gemini.
    Vrací: (model, True) pokud ok, jinak (None, False)
    """
    try:
        if "google" in st.secrets:
            key = st.secrets["google"]["api_key"]
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash') 
            return model, True
        else:
            return None, False
    except Exception:
        return None, False

# --- FUNKCE PRO JEDNOTLIVÉ ÚKOLY ---

def ask_ai_guard(model, pct_24h, cash_usd, top_mover, flop_mover):
    """Generuje hlášení osobního strážce."""
    prompt = f"""
    Jsi "Osobní strážce portfolia". Stručně (max 2 věty) zhodnoť situaci pro velitele.
    DATA:
    - Celková změna portfolia: {pct_24h:+.2f}%
    - Hotovost k dispozici: {cash_usd:,.0f} USD
    - Nejlepší akcie dne: {top_mover}
    - Nejhorší akcie dne: {flop_mover}
    
    INSTRUKCE:
    - Pokud je trh dole a je hotovost > 1000 USD -> Navrhni nákup.
    - Pokud je trh nahoře -> Pochval strategii.
    - Pokud je velký propad -> Uklidni velitele.
    - Mluv stručně, vojensky/profesionálně, česky.
    """
    try:
        return model.generate_content(prompt).text
    except: return "Strážce je momentálně nedostupný."

def audit_portfolio(model, total_val, cash_usd, port_summary):
    """Provede hloubkový audit portfolia."""
    prompt = f"""
    Jsi profesionální portfolio manažer (Hedge Fund). Udělej tvrdý a upřímný audit tohoto portfolia:
    
    Celkové jmění: {total_val:,.0f} USD
    Hotovost: {cash_usd:,.0f} USD
    
    POZICE:
    {port_summary}
    
    ÚKOL:
    1. Zhodnoť diverzifikaci (sektory, jednotlivé akcie).
    2. Identifikuj největší riziko (koncentrace, měna, sektor).
    3. Navrhni 1 konkrétní krok pro vylepšení (co prodat/koupit/změnit).
    
    Odpověz stručně, profesionálně a česky. Používej formátování (body, tučné písmo).
    """
    try:
        return model.generate_content(prompt).text
    except Exception as e: return f"Chyba auditu: {e}"

def get_tech_analysis(model, ticker, last_row):
    """Generuje technickou analýzu na základě indikátorů."""
    prompt = f"""
    Jsi expert na technickou analýzu akcií. Analyzuj následující TVRDÁ DATA pro {ticker}:
    
    CENA: {last_row['Close']:.2f}
    RSI (14): {last_row['RSI']:.2f} (Nad 70=Překoupeno, Pod 30=Přeprodáno)
    SMA 20: {last_row['SMA20']:.2f}
    SMA 50: {last_row['SMA50']:.2f}
    Bollinger Upper: {last_row['BB_Upper']:.2f}
    Bollinger Lower: {last_row['BB_Lower']:.2f}
    MACD: {last_row['MACD']:.4f} (Signal: {last_row['Signal']:.4f})
    
    ÚKOL:
    1. Urči trend (Je cena nad SMA50?).
    2. Zhodnoť RSI (Je bezpečné teď nakupovat?).
    3. MACD signál (Blíží se překřížení?).
    4. Dej finální verdikt: BÝČÍ (Růst) / MEDVĚDÍ (Pokles) / NEUTRÁLNÍ.
    
    Odpověz stručně, profesionálně, česky a použij formátování (tučné písmo).
    """
    try:
        return model.generate_content(prompt).text
    except Exception as e: return f"Chyba analýzy: {e}"

def generate_rpg_story(model, level_name, denni_zmena, celk_hod, score):
    """Generuje herní příběh pro gamifikaci."""
    prompt = f"""
    Jsi cynický vypravěč (Dungeon Master) ve sci-fi cyberpunk hře. Hráč je "Trader".
    
    AKTUÁLNÍ STAV MISIE:
    - Úroveň hráče: {level_name}
    - Dnešní výsledek: {denni_zmena:,.0f} CZK
    - Celkové jmění: {celk_hod:,.0f} CZK
    - Nálada trhu (Fear/Greed): {score}
    
    ÚKOL:
    Napiš krátký "Zápis z kapitánského deníku" (max 3 věty).
    Pokud je výsledek mínusový, popiš to jako poškození lodi, útok hackerů nebo krvácení. Buď drsný.
    Pokud je výsledek plusový, popiš to jako úspěšný raid, nalezení lootu nebo upgrade systému. Buď oslavný.
    Používej herní/kyberpunkový slang.
    """
    try:
        return model.generate_content(prompt).text
    except Exception as e: return f"Chyba příběhu: {e}"

def analyze_headlines_sentiment(model, headlines_list):
    """Analyzuje sentiment seznamu titulků."""
    titles_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(headlines_list)])
    prompt = f"""Jsi finanční analytik. Analyzuj tyto novinové titulky a urči jejich sentiment.\nTITULKY:\n{titles_str}\nPro každý titulek vrať přesně tento formát na jeden řádek (bez odrážek):\nINDEX|SKÓRE(0-100)|VYSVĚTLENÍ (česky, max 1 věta)"""
    try:
        return model.generate_content(prompt).text
    except Exception as e: return ""

# --- NOVINKA: CHATBOT S PAMĚTÍ ---
def get_chat_response(model, history_messages, context_data):
    """
    Generuje odpověď chatbota s využitím historie konverzace.
    history_messages: list slovníků [{'role': 'user', 'parts': ['text']}, ...]
    """
    try:
        # 1. Start chatu s historií
        chat = model.start_chat(history=history_messages[:-1]) # Poslední zprávu pošleme zvlášť
        
        # 2. Příprava aktuální zprávy s kontextem
        last_user_msg = history_messages[-1]['parts'][0]
        full_msg_with_context = f"KONTEXT APLIKACE:\n{context_data}\n\nDOTAZ UŽIVATELE: {last_user_msg}"
        
        # 3. Odeslání
        response = chat.send_message(full_msg_with_context)
        return response.text
        
    except Exception as e:
        return f"Omlouvám se, došlo k chybě spojení: {e}"
