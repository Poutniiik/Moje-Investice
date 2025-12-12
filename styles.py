import streamlit as st

# --- STYLY & THEMES ---
def get_css(theme):
    # =========================================================================
    # 1. ZÁKLAD (LÉTAJÍCÍ BOT) - TOTO NECHÁVÁME PŮVODNÍ
    # =========================================================================
    base_css = """
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {margin-top: -30px;}

    /* --- MAGIE PRO LÉTAJÍCÍHO BOTA (CSS HACK) --- */
    div[data-testid="stExpander"]:has(#floating-bot-anchor) {
        position: fixed !important; bottom: 20px !important; right: 20px !important; 
        width: 380px !important; max-width: 85vw !important; z-index: 99999 !important; 
        background-color: transparent !important; border: none !important; box-shadow: none !important;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary {
        background-color: transparent !important; color: transparent !important;
        height: 70px !important; width: 70px !important; border-radius: 50% !important;
        padding: 0 !important; margin-left: auto !important;
        /* FOTKA PSÍKA ZŮSTÁVÁ ZDE: */
        background-image: url('https://i.postimg.cc/cK5DmzZv/1000001805.jpg');
        background-size: cover; background-position: center;
        border: 3px solid #238636 !important;
        box-shadow: 0 0 15px rgba(35, 134, 54, 0.5);
        animation: float 6s ease-in-out infinite;
        transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55), box-shadow 0.3s;
    }

    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary:hover {
        transform: scale(1.1) rotate(10deg);
        box-shadow: 0 0 30px rgba(35, 134, 54, 0.9);
        cursor: pointer;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) summary svg {display: none !important;}

    div[data-testid="stExpander"]:has(#floating-bot-anchor) details {
        border-radius: 20px !important;
        background-color: #161B22 !important;
        border: 1px solid #30363D !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.8) !important;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary {
        width: 100% !important; height: 40px !important;
        border-radius: 15px 15px 0 0 !important;
        background-image: none !important;
        background-color: #238636 !important;
        color: white !important;
        display: flex; align-items: center; justify-content: center;
        animation: none !important;
        border: none !important; margin: 0 !important;
    }
    
    div[data-testid="stExpander"]:has(#floating-bot-anchor) details[open] summary::after {
        content: "❌ ZAVŘÍT CHAT";
        font-weight: bold; font-size: 0.9rem; color: white;
    }

    div[data-testid="stExpander"]:has(#floating-bot-anchor) div[data-testid="stExpanderDetails"] {
        max-height: 400px; overflow-y: auto;
        background-color: #0d1117;
        border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;
        border-top: 1px solid #30363D;
        padding: 15px;
    }

    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
        100% { transform: translateY(0px); }
    }
    """

    # =========================================================================
    # 2. THEMES (SKINY)
    # =========================================================================
    theme_css = ""
    
    if theme == "🔮 Glassmorphism (Modern)":
        theme_css = """
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
        
    elif theme == "💼 Wall Street (Classic)":
        theme_css = """
        .stApp { background-color: #f0f2f6; color: #1f2937; }
        div[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e7eb; }
        h1, h2, h3 { color: #111827; font-family: 'Georgia', serif; }
        div[data-testid="stMetricValue"] { color: #059669; }
        .stButton>button { background-color: #2563eb; color: white; border-radius: 5px; }
        """
        
    else: # 🌌 Cyberpunk (Default)
        theme_css = """
        /* Cyberpunk je defaultní tmavý režim Streamlitu, jen přidáme neony */
        div[data-testid="stMetric"] {
            background-color: #161b22; border: 1px solid #30363d;
            box-shadow: 0 0 10px rgba(0, 255, 153, 0.1); border-radius: 10px; padding: 10px;
        }
        div[data-testid="stMetricLabel"] { color: #8b949e; }
        div[data-testid="stMetricValue"] { color: #00ff99; text-shadow: 0 0 5px rgba(0,255,153,0.5); }
        """

    # SPOJENÍ A ZABALENÍ DO <style> TAGŮ (TO JE TA OPRAVA)
    return f"<style>{base_css}\n{theme_css}</style>"
