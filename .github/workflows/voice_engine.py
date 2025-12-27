import streamlit as st
from gtts import gTTS
import io
import base64
import os

# --- IMPORTY PRO AI A MIKROFON ---
try:
    import google.generativeai as genai
    from streamlit_mic_recorder import mic_recorder
except ImportError as e:
    st.error(f"⚠️ Chybí kritické moduly v voice_engine.py! ({e})")
    st.info("💡 Řešení: Spusť v terminálu: pip install google-generativeai streamlit-mic-recorder")
    st.stop()

# --- KONFIGURACE ---
VOICE_LANG = 'cs' 
GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"

# 1. BEZPEČNOST A NAČTENÍ KLÍČE (OPRAVENO)
API_KEY = None

try:
    # A. Kontrola vnořeného klíče v secrets [google] api_key = "..."
    if "google" in st.secrets and "api_key" in st.secrets["google"]:
        API_KEY = st.secrets["google"]["api_key"]
    
    # B. Kontrola přímého klíče GEMINI_API_KEY (pro Actions / Env)
    elif "GEMINI_API_KEY" in st.secrets:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    
    # C. Kontrola environmentálních proměnných (Fallback)
    else:
        API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    # Konfigurace modelu, pokud jsme klíč našli
    if API_KEY:
        genai.configure(api_key=API_KEY)
    else:
        st.warning("⚠️ VoiceEngine: Nebyl nalezen žádný API klíč. Zkontrolujte nastavení v secrets nebo env.")
except Exception as e:
    print(f"⚠️ VoiceEngine Config Error: {e}")

class VoiceAssistant:
    """
    Třída pro správu hlasových funkcí aplikace.
    V4.1: Opravena detekce API klíčů a multimodální přepis přes Gemini 2.5 Flash.
    """
    
    @staticmethod
    def speak(text):
        """
        Převede text na řeč a vrátí HTML audio přehrávač.
        """
        if not text:
            return None
            
        try:
            tts = gTTS(text=text, lang=VOICE_LANG, slow=False)
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            audio_b64 = base64.b64encode(audio_buffer.read()).decode()
            audio_type = "audio/mp3"
            
            audio_html = f"""
                <div style="margin-top: 10px;">
                    <audio controls autoplay="true" style="width: 100%; height: 40px; border-radius: 5px;">
                        <source src="data:{audio_type};base64,{audio_b64}" type="{audio_type}">
                    </audio>
                </div>
            """
            return audio_html
        except Exception as e:
            st.warning(f"⚠️ Chyba při generování řeči (TTS): {e}")
            return None

    @staticmethod
    def transcribe_audio_with_gemini(audio_bytes):
        """
        Multimodální přepis zvuku pomocí Gemini 2.5 Flash.
        """
        if not API_KEY:
            return None

        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            
            response = model.generate_content([
                "Instrukce: Přepiš toto audio doslovně do textu. Zachovej jazyk mluvčího. "
                "Pokud je v audiu ticho, vrať prázdný řetězec. Ignoruj šumy.",
                {
                    "mime_type": "audio/webm",
                    "data": audio_bytes
                }
            ])
            return response.text.strip()
        except Exception as e:
            st.error(f"⚠️ AI chyba při přepisu: {e}")
            return None

    @staticmethod
    def ask_gemini(prompt):
        """
        Zpracování textového dotazu mozkem AI (Gemini 2.5).
        """
        if not API_KEY:
            return "Chybí API klíč, nemohu odpovědět."

        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            context_prompt = (
                "Jsi profesionální finanční asistent. Odpovídej stručně, maximálně dvě věty, česky. "
                "Dotaz uživatele: "
            )
            response = model.generate_content(f"{context_prompt} {prompt}")
            return response.text
        except Exception as e:
            return f"Omlouvám se, došlo k chybě mozků: {e}"

    @staticmethod
    def render_voice_ui():
        """
        Vykreslí UI komponenty v aplikaci bez vynucování sidebaru.
        """
        st.markdown("---")
        st.subheader("🎙️ AI Hlasový Asistent (v2.5)")
        
        audio_input = mic_recorder(
            start_prompt="🎤 Začít mluvit",
            stop_prompt="⏹️ Dokončit",
            just_once=True,
            key='recorder_gemini_v25_fixed'
        )
        
        if audio_input:
            st.info("Analyzuji zvuk přes Gemini 2.5...")
            
            user_text = VoiceAssistant.transcribe_audio_with_gemini(audio_input['bytes'])
            
            if user_text:
                st.write(f"🗣️ **Slyšel jsem:** {user_text}")
                
                with st.spinner("Generuji odpověď..."):
                    ai_response = VoiceAssistant.ask_gemini(user_text)
                
                st.write(f"🤖 **Asistent:** {ai_response}")
                
                audio_html = VoiceAssistant.speak(ai_response)
                if audio_html:
                    st.components.v1.html(audio_html, height=60)
            else:
                st.warning("Nebylo nic slyšet. Zkuste to znovu.")
