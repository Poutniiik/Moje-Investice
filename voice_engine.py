import streamlit as st
from gtts import gTTS
import io
import base64
import os

# --- NOVÉ IMPORTY PRO AI A MIKROFON ---
# Zabaleno do try-except pro stabilitu, kdyby chyběly knihovny
try:
    import google.generativeai as genai
    from streamlit_mic_recorder import mic_recorder
    import speech_recognition as sr
except ImportError as e:
    st.error(f"⚠️ Chybí kritické moduly v voice_engine.py! ({e})")
    st.info("💡 Řešení: Spusť v terminálu: pip install google-generativeai streamlit-mic-recorder SpeechRecognition")
    st.stop()

# --- KONFIGURACE ---
VOICE_LANG = 'cs' 

# Pokus o načtení API klíče
try:
    API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if API_KEY:
        genai.configure(api_key=API_KEY)
    else:
        # Jen logujeme do konzole, nebudeme spamovat UI varováním hned po startu
        print("⚠️ VoiceEngine: Není nastaven GOOGLE_API_KEY. AI funkce nepojedou.")
except Exception as e:
    print(f"⚠️ VoiceEngine Config Error: {e}")

class VoiceAssistant:
    """
    Třída pro správu hlasových funkcí aplikace.
    Obsahuje: TTS (Mluvení), STT (Poslouchání), LLM (Gemini).
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
                <audio autoplay="true" style="display:none;">
                    <source src="data:{audio_type};base64,{audio_b64}" type="{audio_type}">
                </audio>
            """
            return audio_html
        except Exception as e:
            st.warning(f"⚠️ Chyba TTS: {e}")
            return None

    @staticmethod
    def transcribe_audio(audio_bytes):
        """
        Převede audio bytes na text.
        """
        r = sr.Recognizer()
        audio_file = io.BytesIO(audio_bytes)
        
        try:
            with sr.AudioFile(audio_file) as source:
                audio_data = r.record(source)
            text = r.recognize_google(audio_data, language=VOICE_LANG)
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            st.error(f"Chyba služby Speech API: {e}")
            return None
        except Exception as e:
            st.error(f"Chyba přepisu: {e}")
            return None

    @staticmethod
    def ask_gemini(prompt):
        """
        Komunikace s Google Gemini.
        """
        if not API_KEY:
            return "Chybí mi API klíč, nemohu odpovídat."
            
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            full_prompt = f"Odpověz stručně, česky a k věci jako finanční asistent: {prompt}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Chyba AI: {e}"

    @staticmethod
    def render_voice_ui():
        """
        Zobrazí widget pro hlasové ovládání.
        """
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎙️ Hlasový Asistent")
        
        # Nahrávání
        audio_input = mic_recorder(
            start_prompt="🎤 Mluvit",
            stop_prompt="⏹️ Stop",
            just_once=True,
            key='recorder_sidebar'
        )
        
        if audio_input:
            st.sidebar.info("Zpracovávám...")
            user_text = VoiceAssistant.transcribe_audio(audio_input['bytes'])
            
            if user_text:
                st.sidebar.write(f"🗣️ **Vy:** {user_text}")
                
                ai_response = VoiceAssistant.ask_gemini(user_text)
                st.sidebar.write(f"🤖 **AI:** {ai_response}")
                
                audio_html = VoiceAssistant.speak(ai_response)
                if audio_html:
                    st.sidebar.components.v1.html(audio_html, height=0)
            else:
                st.sidebar.warning("Nerozuměl jsem.")

# Testovací blok - spustí se jen když zapneš přímo tento soubor
if __name__ == "__main__":
    st.title("Test Voice Engine")
    VoiceAssistant.render_voice_ui()
