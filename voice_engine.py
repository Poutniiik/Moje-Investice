import streamlit as st
from gtts import gTTS
import io
import base64

# --- KONFIGURACE ---
# Jazyk hlasu (cs = čeština, en = angličtina)
VOICE_LANG = 'cs' 

class VoiceAssistant:
    """
    Třída pro správu hlasových funkcí aplikace.
    Navržena tak, aby byla odolná proti chybám na serverech bez zvukové karty (GitHub Actions, Streamlit Cloud).
    Používá gTTS (Google Text-to-Speech) pro generování MP3, které se přehrají v prohlížeči.
    """
    
    @staticmethod
    def speak(text):
        """
        Převede text na řeč a vrátí HTML audio přehrávač s autoplay.
        """
        # Kontrola, zda je hlas povolen v session_state (pokud existuje)
        if 'voice_enabled' in st.session_state and not st.session_state['voice_enabled']:
            return None

        if not text:
            return None
            
        try:
            # 1. Generování zvuku do paměti (neukládáme soubory na disk)
            # slow=False znamená normální rychlost
            tts = gTTS(text=text, lang=VOICE_LANG, slow=False)
            
            # Použijeme BytesIO jako virtuální soubor v RAM
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            # 2. Kódování do Base64 pro HTML přehrávač
            # Prohlížeč potřebuje data v textové podobě
            audio_b64 = base64.b64encode(audio_buffer.read()).decode()
            audio_type = "audio/mp3"
            
            # 3. Vytvoření neviditelného přehrávače s autoplay
            # Používáme HTML5 <audio> tag s atributem autoplay
            audio_html = f"""
                <audio autoplay="true" style="display:none;">
                    <source src="data:{audio_type};base64,{audio_b64}" type="{audio_type}">
                </audio>
                <div style="
                    padding: 10px; 
                    background-color: rgba(0, 255, 153, 0.1); 
                    border-left: 3px solid #00FF99; 
                    border-radius: 5px; 
                    margin-bottom: 10px;
                    color: #00FF99;
                    font-size: 0.8em;">
                    🔊 Přehrávám audio...
                </div>
            """
            return audio_html
            
        except Exception as e:
            # Nevypisujeme chybu uživateli příliš agresivně, jen do konzole/logu
            print(f"⚠️ Hlasový modul (TTS) narazil na chybu: {e}")
            return None

    @staticmethod
    def render_settings_toggle():
        """
        Vykreslí přepínač v nastavení.
        """
        if 'voice_enabled' not in st.session_state:
            st.session_state['voice_enabled'] = True
            
        is_on = st.toggle("🔊 Povolit hlasový výstup", value=st.session_state['voice_enabled'])
        if is_on != st.session_state['voice_enabled']:
            st.session_state['voice_enabled'] = is_on
            st.rerun()

# --- TEST (Pokud spustíme soubor přímo) ---
if __name__ == "__main__":
    st.write("Testování Voice Engine...")
    st.session_state['voice_enabled'] = True # Force enable pro test
    html = VoiceAssistant.speak("Zdravím, veliteli. Zkouška hlasového modulu jedna dva tři.")
    if html:
        st.components.v1.html(html, height=100)
        st.success("Audio odesláno.")
