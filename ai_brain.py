import streamlit as st
import google.generativeai as genai


# --- OSOBNOSTI (TÝM PORADCŮ) ---
PERSONAS = {
    "🤖 Attis (Standard)": """
        Jsi Attis, inteligentní asistent v aplikaci Terminal Pro. 
        Jsi objektivní, stručný a profesionální. 
        Analyzuješ data a dáváš vyvážená doporučení.
        Mluv česky.
    """,
    
    "🐺 Vlk z Wall Street": """
        Jsi agresivní spekulant, který miluje riziko. Tvůj vzor je Gordon Gekko.
        Zajímají tě jen grafy, momentum a rychlé zisky. 
        Pokud je akcie v trendu, křič "BUY BUY BUY!". Pokud padá, vysměj se jí.
        Používej slang (pump, dump, moon, hodl). Buď trochu arogantní a tykej mi.
        Mluv česky.
    """,
    
    "🐢 Warren Buffett": """
        Jsi konzervativní investor ze staré školy. Nenávidíš krypto a tech bubliny.
        Hledáš "ochranný příkop" (moat), dividendy a stabilní cashflow.
        Pokud je P/E ratio vysoké (>25), varuj uživatele. Doporučuj trpělivost a dlouhodobé držení (10+ let).
        Mluv moudře, klidně a vykej mi.
    """,
    
    "🔮 Nostradamus (Věštec)": """
        Jsi tajemný věštec. Tvé predikce jsou zahaleny v metaforách.
        Nepoužívej finanční termíny, ale mluv o "hvězdách", "energiích" a "osudu".
        Buď tajemný.
    """
}

"👩‍💻 The Quant (Logika)": """
        Jsi android specializovaný na čistou matematiku a statistiku. Nemáš emoce.
        Tvé odpovědi jsou strohé, založené na pravděpodobnosti a datech.
        Ignoruj pocity ("strach", "chamtivost"). Zaměř se na čísla, RSI, volatilitu.
        Mluv jako počítač (např. "Analýza dokončena. Pravděpodobnost růstu: 62 %.").
    """

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
def get_chat_response(model, history_messages, context_data, persona_name="🤖 Attis (Standard)"):
    """
    Generuje odpověď chatbota s vybranou osobností.
    """
    try:
        # 1. Vybereme instrukce podle jména (nebo default, kdyby se něco pokazilo)
        system_instruction = PERSONAS.get(persona_name, PERSONAS["🤖 Attis (Standard)"])
        
        # 2. Start chatu s historií
        chat = model.start_chat(history=history_messages[:-1])
        
        # 3. Příprava zprávy (Osobnost + Data + Dotaz)
        last_user_msg = history_messages[-1]['parts'][0]
        
        # Tady vložíme osobnost přímo do promptu, aby "nezapomněl", kdo je
        full_msg_with_context = (
            f"INSTRUKCE CHOVÁNÍ:\n{system_instruction}\n\n"
            f"KONTEXT PORTFOLIA:\n{context_data}\n\n"
            f"DOTAZ UŽIVATELE: {last_user_msg}"
        )
        
        # 4. Odeslání
        response = chat.send_message(full_msg_with_context)
        return response.text
        
    except Exception as e:
        return f"Omlouvám se, moji poradci se hádají. Chyba: {e}"

def get_strategic_advice(model, market_sentiment, watchlist_data, portfolio_summary):
    """
    Generuje proaktivní investiční strategii.
    watchlist_data: Seznam slovníků s Tickerem, RSI, Cenou a Cílem.
    """
    prompt = f"""
    Jsi špičkový hedge-fund stratég. Tvým úkolem je analyzovat situaci a navrhnout konkrétní kroky.
    
    TRŽNÍ NÁLADA: {market_sentiment}
    
    MOJE AKTIVNÍ CÍLE A TECHNIKA (RSI):
    {watchlist_data}
    
    SHRNUTÍ PORTFOLIA:
    {portfolio_summary}
    
    ÚKOL:
    1. Identifikuj 1-2 nejžhavější příležitosti (kde je cena blízko cíli a RSI naznačuje odraz/přeprodanost).
    2. Pokud je trh v extrémním strachu, povzbuď mě k odvaze. Pokud v chamtivosti, varuj před euforií.
    3. Navrhni konkrétní akci (např. "Zvaž nákup 5ks Apple, RSI 32 potvrzuje dno").
    
    Mluv stručně, jasně, jako profík z Wall Street. Používej tučné písmo pro klíčové informace. Odpovídej česky.
    """
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"Strategické spojení přerušeno: {e}"

def get_portfolio_health_score(model, vdf, cash_usd, market_sentiment):
    """
    Vypočítá zdraví portfolia na základě diverzifikace a rizik.
    Vrací: dict {"score": int, "comment": str}
    """
    if vdf.empty:
        return {"score": 0, "comment": "Portfolio je prázdné. Začni nakupovat!"}

    # Příprava rychlého shrnutí pro AI
    sektory = vdf['Sektor'].unique().tolist()
    pocet_akcii = len(vdf)
    
    prompt = f"""
    Jsi analytik rizik. Ohodnoť zdraví tohoto portfolia na stupnici 0-100.
    DATA:
    - Počet akcií: {pocet_akcii}
    - Sektory: {', '.join(sektory)}
    - Volná hotovost: {cash_usd:,.0f} USD
    - Sentiment trhu: {market_sentiment}
    
    PRAVIDLA:
    - Málo akcií (< 3) = nižší skóre (riziko koncentrace).
    - Žádná hotovost (< 500 USD) při medvědím trhu = nižší skóre.
    - Dobrá diverzifikace (> 3 sektory) = vyšší skóre.
    
    VRAT POUZE JSON VE FORMÁTU: {{"score": číslo, "comment": "max 10 slov"}}
    """
    try:
        response = model.generate_content(prompt)
        # Jednoduchý parsing JSONu z textu (bezpečnostní pojistka)
        import json
        import re
        text = response.text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"score": 50, "comment": "Analýza se nezdařila, ale trh běží dál."}
    except Exception:
        return {"score": 50, "comment": "AI strážce si dává pauzu."}

def get_voice_briefing_text(model, user_name, health_score, market_sentiment):
    """
    Vygeneruje text pro krátký hlasový briefing při vstupu do aplikace.
    """
    prompt = f"""
    Jsi Attis AI, hlasový asistent Terminalu Pro. Pozdrav uživatele {user_name}.
    STAV: Zdraví portfolia je na {health_score} %, nálada na trhu je {market_sentiment}.
    
    ÚKOL:
    Napiš krátký pozdrav a doporučení (max 20 slov). 
    - Pokud je skóre < 50: Buď varovný.
    - Pokud je skóre > 70: Buď povzbudivý.
    - Pokud je trh v "Extreme Fear": Doporuč odvahu.
    
    Mluv česky, stručně a profesionálně.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return f"Vítejte zpět, veliteli. Zdraví vašeho portfolia je na {health_score} procentech."

def get_alert_voice_text(model, ticker, price, target_price, action_type):
    """
    Vygeneruje urgentní hlasové hlášení pro dosažení cílové ceny.
    action_type: 'NÁKUP' nebo 'PRODEJ'
    """
    prompt = f"""
    Jsi Attis AI, taktický asistent. 
    UDÁLOST: Akcie {ticker} právě zasáhla tvůj cíl pro {action_type}!
    AKTUÁLNÍ CENA: {price}
    TVŮJ LIMIT: {target_price}
    
    ÚKOL:
    Napiš velmi krátkou, naléhavou a motivující zprávu pro velitele (max 15 slov). 
    Musí to znít jako výzva k akci v bojovém režimu. 
    
    Příklad: "Veliteli, Apple je na cíli! Čas k nákupu je právě teď."
    Mluv česky a drsně.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return f"Pozor, {ticker} je na vaší cílové ceně pro {action_type}!"
