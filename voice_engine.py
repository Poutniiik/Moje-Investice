import streamlit as st
from gtts import gTTS
import io
import base64
import os

# --- NOVÉ IMPORTY PRO AI A MIKROFON ---
# Zabaleno do try-except pro stabilitu
try:
    import google.generativeai as genai
    from streamlit_mic_recorder import mic_recorder
    # SpeechRecognition už nepotřebujeme, Gemini má lepší uši!
except ImportError as e:
    st.error(f"⚠️ Chybí kritické moduly v voice_engine.py! ({e})")
    st.info("💡 Řešení: Spusť v terminálu: pip install google-generativeai streamlit-mic-recorder")
    st.stop()

# --- KONFIGURACE ---
VOICE_LANG = 'cs' 

# 1. BEZPEČNOST: Inicializace
API_KEY = None

# Pokus o načtení API klíče
try:
    possible_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if possible_key:
        API_KEY = possible_key
        genai.configure(api_key=API_KEY)
    else:
        print("⚠️ VoiceEngine: Není nastaven GOOGLE_API_KEY.")
except Exception as e:
    print(f"⚠️ VoiceEngine Config Error: {e}")

class VoiceAssistant:
    """
    Třída pro správu hlasových funkcí aplikace.
    V3.0 Update: Pure Gemini Edition (odstraněna závislost na SpeechRecognition).
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
            
            # Viditelný přehrávač pro jistotu
            audio_html = f"""
                <audio controls autoplay="true" style="width: 100%;">
                    <source src="data:{audio_type};base64,{audio_b64}" type="{audio_type}">
                </audio>
            """
            return audio_html
        except Exception as e:
            st.warning(f"⚠️ Chyba TTS: {e}")
            return None

    @staticmethod
    def transcribe_audio_with_gemini(audio_bytes):
        """
        Převede audio na text pomocí Gemini (Uši).
        Je to robustnější než staré SpeechRecognition, protože Gemini bere i WebM.
        """
        if not API_KEY:
            st.error("Chybí API klíč pro přepis zvuku.")
            return None

        try:
            # Použijeme Gemini Flash - je rychlý a levný
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Gemini umí přijmout přímo raw data (blob)
            # Webové prohlížeče obvykle posílají audio/webm
            response = model.generate_content([
                "Přepiš přesně a doslovně toto audio do textu. Nepřidávej žádné úvody ani závěry. Pokud je audio ticho nebo šum, vrať jen prázdný řetězec.",
                {
                    "mime_type": "audio/webm",
                    "data": audio_bytes
                }
            ])
            return response.text.strip()
        except Exception as e:
            st.error(f"Chyba při přepisu přes AI: {e}")
            return None

    @staticmethod
    def ask_gemini(prompt):
        """
        Komunikace s Google Gemini (Mozek).
        """
        if not API_KEY:
            return "Chybí mi API klíč."
            
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            full_prompt = f"Odpověz stručně (max 2 věty), česky a k věci jako finanční asistent na tento dotaz: {prompt}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Omlouvám se, chyba AI: {e}"

    @staticmethod
    def render_voice_ui():
        """
        Zobrazí widget pro hlasové ovládání.
        """
        st.markdown("---")
        st.subheader("🎙️ Hlasový Asistent")
        
        audio_input = mic_recorder(
            start_prompt="🎤 Mluvit",
            stop_prompt="⏹️ Stop",
            just_once=True,
            key='recorder_gemini_pure'
        )
        
        if audio_input:
            st.info("Posílám zvuk do AI...")
            
            # 1. PŘEPIS (Gemini Uši)
            # Posíláme bytes přímo Geminimu, neřešíme konverzi WAV/WebM!
            user_text = VoiceAssistant.transcribe_audio_with_gemini(audio_input['bytes'])
            
            if user_text:
                st.write(f"🗣️ **Vy:** {user_text}")
                
                # 2. ODPOVĚĎ (Gemini Mozek)
                # Tady už posíláme text
                with st.spinner("Přemýšlím..."):
                    ai_response = VoiceAssistant.ask_gemini(user_text)
                
                st.write(f"🤖 **AI:** {ai_response}")
                
                # 3. MLUVENÍ (TTS Ústa)
                audio_html = VoiceAssistant.speak(ai_response)
                if audio_html:
                    st.components.v1.html(audio_html, height=45)
            else:
                st.warning("Nerozuměl jsem (nebo bylo ticho).")
