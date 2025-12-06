import streamlit as st

# --- STYLY & THEMES ---
def get_css(theme):
    # 1. ZÁKLAD + LOGIKA PRO LÉTAJÍCÍHO BOTA (To, co chybělo)
    base_css = """
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {margin-top: -30px;}

    /* --- MAGIE PRO LÉTAJÍCÍHO BOTA (CSS HACK) --- */
    /* 1. Pozice celého okna fixně vpravo dole */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) {
        position: fixed !important; bottom: 20px !important; right: 20px !important; 
        width: 380px !important; max-width: 85vw !important; z-index: 99999 !important; 
        background-color: transparent !important; border: none !important; box-shadow: none !important;
    }
    
    /* 2. Styl zavřeného tlačítka (KULIČKA S FOTKOU) */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary {
        background-color: transparent !important; color: transparent !important;
        height: 70px !important; width: 70px !important; border-radius: 50% !important;
        padding: 0 !important; margin-left: auto !important;
        /* 👇👇👇 TADY SI VRÁTÍŠ FOTKU SVÉHO PSÍKA 👇👇👇 */
        background-image: url('https://i.postimg.cc/cK5DmzZv/1000001805.jpg'); 
        background-size: cover; background-position: center;
        border: 3px solid #238636 !important;
        box-shadow: 0 0 15px rgba(35, 134, 54, 0.5);
        animation: float 6s ease-in-out infinite;
        transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55), box-shadow 0.3s;
    }
    
    /* 3. Hover efekt (když na to najedeš myší) */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary:hover {
        transform: scale(1.1) rotate(10deg);
        box-shadow: 0 0 30px rgba(35, 134, 54, 0.9);
        cursor: pointer;
    }
    
    /* 4. Schování té malé šipky defaultního expandéru */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary svg {display: none !important;}
    
    /* 5. Styl OTEVŘENÉHO okna (Chat) */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details {
        border-radius: 20px !important; background-color: #161B22 !important; 
        border: 1px solid #30363D !important; box-shadow: 0 10px 30px rgba(0,0,0,0.8) !important;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary {
        width: 100% !important; height: 40px !important; 
        border-radius: 15px 15px 0 0 !important; 
        background-image: none !important; 
        background-color: #238636 !important; 
        color: white !important; 
        display: flex; align-items: center; justify-content: center; 
        animation: none !important; border: none !important; margin: 0 !important;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary::after {
        content: "❌ ZAVŘÍT CHAT"; font-weight: bold; font-size: 0.9rem; color: white;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) div[data-testid="stExpanderDetails"] {
        max-height: 400px; overflow-y: auto; background-color: #0d1117; 
        border-bottom-left-radius: 20px; border-bottom-right-radius: 20px; 
        border-top: 1px solid #30363D; padding: 15px;
    }
    
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
        100% { transform: translateY(0px); }
    }
    """
    
    # 2. PŘIDÁNÍ TÉMAT (Barvičky)
    if theme == "🕹️ Cyberpunk (Retro)":
        return base_css + """
        @keyframes gradient { 0% {background-position: 0% 50%;} 50% {background-position: 100% 50%;} 100% {background-position: 0% 50%;} }
        .stApp {
            background: linear-gradient(-45deg, #05070a, #0E1117, #161b22, #0d1117);
            background-size: 400% 400%; animation: gradient 20s ease infinite;
            font-family: 'Roboto Mono', monospace;
        }
        .stApp::before {
            content: " "; display: block; position: absolute; top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.1) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.03), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.03));
            z-index: 2; background-size: 100% 2px, 3px 100%; pointer-events: none;
        }
        div[data-testid="stMetric"] {
            background-color: rgba(22, 27, 34, 0.8); border: 1px solid #30363D; padding: 15px; border-radius: 8px;
            color: #E6EDF3; box-shadow: 0 0 10px rgba(0, 255, 0, 0.1);
        }
        """
        
    elif theme == "💎 Glassmorphism (Modern)":
        return base_css + """
        .stApp {
            background-image: url("https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop");
            background-size: cover; background-attachment: fixed; font-family: 'Inter', sans-serif;
        }
        div[data-testid="stMetric"], div[data-testid="stExpander"], div.stDataFrame, div[data-testid="stForm"] {
            background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 15px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        h1, h2, h3 { text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .stButton>button { border-radius: 20px; background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%); border: none; }
        """
        
    elif theme == "💼 Wall Street (Profi)":
        return base_css + """
        .stApp { background-color: #0e1117; font-family: 'Helvetica Neue', sans-serif; }
        div[data-testid="stMetric"] {
            background-color: #161b22; border-left: 5px solid #238636; border-radius: 4px;
            padding: 10px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
        }
        h1, h2, h3 { font-weight: 300; letter-spacing: 1px; color: #ffffff; }
        .stProgress > div > div > div > div { background-color: #238636; }
        """
    return base_css
