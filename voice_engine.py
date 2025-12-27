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

# 1. BEZPEČNOST A NAČTENÍ KLÍČE
API_KEY = None
try:
    if "google" in st.secrets and "api_key" in st.secrets["google"]:
        API_KEY = st.secrets["google"]["api_key"]
    elif "GEMINI_API_KEY" in st.secrets:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    else:
        API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if API_KEY:
        genai.configure(api_key=API_KEY)
    else:
        st.warning("⚠️ VoiceEngine: Nebyl nalezen žádný API klíč. Zkontrolujte nastavení.")
except Exception as e:
    print(f"⚠️ VoiceEngine Config Error: {e}")

class VoiceAssistant:
    """
    Třída pro správu hlasových funkcí aplikace.
    V4.3: Smart Context Edition. Asistent už není "tupý", protože dostává briefing o datech.
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
            
            # HTML přehrávač s automatickým spuštěním (neviditelný pro čisté UI)
            audio_html = f"""
                <div style="display:none;">
                    <audio controls autoplay="true">
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
        Vrací text nebo chybové hlášení začínající na 'ERROR_'.
        """
        if not API_KEY:
            return "ERROR: Chybí API klíč pro přepis."

        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content([
                "Instrukce: Přepiš toto audio doslovně do textu v češtině. Zachovej tón mluvčího.",
                {
                    "mime_type": "audio/webm",
                    "data": audio_bytes
                }
            ])
            return response.text.strip()
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                return "ERROR_429: AI má teď pauzu, protože jsme vyčerpali limit zpráv. Zkus to prosím za chvilku."
            return f"ERROR_GENERIC: Chyba při přepisu: {error_msg}"

    @staticmethod
    def ask_gemini(prompt, context=""):
        """
        Zpracování textového dotazu s přihlédnutím k datům aplikace (context).
        """
        if not API_KEY:
            return "Chybí API klíč, nemohu odpovědět."

        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            
            # Tady definujeme "osobnost" a dáváme mu oči (kontext)
            system_instruction = (
                f"Jsi Attis AI, inteligentní finanční asistent integrovaný v aplikaci Terminal Pro. "
                f"Tvé aktuální vědomosti o portfoliu a stavu aplikace: {context}. "
                "Odpovídej stručně (max 2 věty), lidsky a česky. "
                "Pokud se uživatel ptá na svá data, využij informace v kontextu. "
                "Pokud se ptá na něco, co v datech nevidíš, slušně vysvětli, že k těmto informacím nemáš přístup."
            )
            
            full_prompt = f"{system_instruction}\n\nDotaz uživatele: {prompt}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                return "AI má teď pauzu, limit zpráv byl vyčerpán. Počkej prosím minutu."
            return f"Omlouvám se, došlo k chybě: {e}"

    @staticmethod
    def render_voice_ui(user_context=""):
        """
        Vykreslí UI komponenty a přijme briefing (user_context) z hlavní aplikace.
        """
        st.markdown("---")
        st.subheader("🎙️ Attis AI Hlasový Asistent (v4.3)")
        
        audio_input = mic_recorder(
            start_prompt="🎤 Začít mluvit",
            stop_prompt="⏹️ Dokončit",
            just_once=True,
            key='recorder_gemini_v43_smart'
        )
        
        if audio_input:
            with st.spinner("Poslouchám..."):
                user_text = VoiceAssistant.transcribe_audio_with_gemini(audio_input['bytes'])
                
                if user_text:
                    if user_text.startswith("ERROR_"):
                        clean_error = user_text.split(": ", 1)[1] if ": " in user_text else user_text
                        st.warning(clean_error)
                        audio_html = VoiceAssistant.speak(clean_error)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                    else:
                        st.write(f"🗣️ **Ty:** {user_text}")
                        
                        with st.spinner("Přemýšlím..."):
                            # Tady posíláme briefing do mozku
                            ai_response = VoiceAssistant.ask_gemini(user_text, context=user_context)
                        
                        st.write(f"🤖 **Attis AI:** {ai_response}")
                        
                        audio_html = VoiceAssistant.speak(ai_response)
                        if audio_html:
                            st.components.v1.html(audio_html, height=0)
                else:
                    st.warning("Nebylo nic slyšet. Zkuste to znovu.")
