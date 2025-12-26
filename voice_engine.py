import streamlit as st
from gtts import gTTS
import io
import base64

# --- KONFIGURACE ---
# Můžeš změnit jazyk na 'en' pro angličtinu, 'sk' pro slovenštinu atd.
VOICE_LANG = 'cs' 

class VoiceAssistant:
    """
    Třída pro správu hlasových funkcí aplikace.
    Navržena tak, aby byla odolná proti chybám na serverech bez zvukové karty (Streamlit Cloud).
    """
    
    @staticmethod
    def speak(text):
        """
        Převede text na řeč a vrátí HTML audio přehrávač (autoplay).
        Používá Google TTS (online API).
        """
        if not text:
            return None
            
        try:
            # 1. Generování zvuku do paměti (neukládáme soubory na disk, abychom nezasvinili server)
            # slow=False znamená, že mluví normální rychlostí
            tts = gTTS(text=text, lang=VOICE_LANG, slow=False)
            
            # Použijeme BytesIO jako virtuální soubor v RAM
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            # 2. Kódování do Base64 pro HTML přehrávač
            # Prohlížeč neumí přečíst BytesIO přímo, musí to dostat jako textový řetězec
            audio_b64 = base64.b64encode(audio_buffer.read()).decode()
            audio_type = "audio/mp3"
            
            # 3. Vytvoření neviditelného přehrávače s autoplay
            # Pozor: Moderní prohlížeče blokují autoplay, pokud uživatel neinteragoval se stránkou.
            # Proto je dobré to spouštět až po stisku tlačítka.
            audio_html = f"""
                <audio autoplay="true" style="display:none;">
                    <source src="data:{audio_type};base64,{audio_b64}" type="{audio_type}">
                </audio>
            """
            return audio_html
            
        except Exception as e:
            # Pokud Google API selže nebo není net, aplikace nespadne, jen vypíše varování
            st.warning(f"⚠️ Hlasový modul (TTS) narazil na chybu: {e}")
            return None

    @staticmethod
    def render_voice_ui():
        """
        Zobrazí UI prvky pro ovládání hlasem (např. tlačítko mikrofonu).
        Zatím placeholder pro budoucí integraci STT (Speech-to-Text).
        """
        st.markdown("---")
        st.caption("🎙️ Hlasové ovládání (Beta)")
        # Zde později přidáme 'streamlit-mic-recorder'
        pass

# --- TEST (Pokud spustíme soubor přímo jako skript) ---
if __name__ == "__main__":
    st.write("Testování Voice Engine...")
    text = "Zdravím, veliteli. Systém je plně funkční a připraven k rozkazům."
    
    if st.button("🔊 Otestovat hlas"):
        html = VoiceAssistant.speak(text)
        if html:
            st.components.v1.html(html, height=0)
            st.success("Zvuk odeslán do prohlížeče.")
            st.write(f"Testovací text: {text}")
