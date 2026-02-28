import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
from PIL import Image, ImageDraw
import io

# 1. Seiteneinstellungen
st.set_page_config(page_title="KI Interview-Coach Pro", page_icon="🎯", layout="wide")

# 2. Absturzsicherung: API Key Prüfung
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key fehlt! Bitte in den Streamlit Secrets hinterlegen.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# 3. Hilfsfunktionen
def speak(text, gender="Weiblich"):
    """Browser-basierte Sprachausgabe via JavaScript."""
    if text:
        clean_text = text.replace("'", "\\'").replace("\n", " ")
        pitch = 1.4 if gender == "Weiblich" else 0.8
        html_code = f"""
            <script>
                var msg = new SpeechSynthesisUtterance('{clean_text}');
                msg.lang = 'de-DE';
                msg.pitch = {pitch};
                window.speechSynthesis.speak(msg);
            </script>
        """
        st.components.v1.html(html_code, height=0)

def create_feedback_image(text):
    """Erstellt ein einfaches Bild der Analyse zum Teilen."""
    img = Image.new('RGB', (800, 600), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 800, 80], fill=(0, 104, 201))
    d.text((30, 25), "Mein KI-Interview Feedback", fill=(255, 255, 255))
    
    y_pos = 120
    for line in text.split('\n')[:20]: # Die ersten 20 Zeilen
        d.text((30, y_pos), line[:80], fill=(40, 40, 40))
        y_pos += 22
        
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# 4. Session State (Speicher)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "q_count" not in st.session_state:
    st.session_state.q_count = 0

MAX_QUESTIONS = 5

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Einstellungen")
    voice_option = st.radio("Stimme:", ["👩 Recruiterin", "👨 Recruiter"])
    gender = "Weiblich" if "👩" in voice_option else "Männlich"
    
    st.divider()
    job_desc = st.text_area("Stellenbeschreibung:", height=150)
    cv_text = st.text_area("Dein Lebenslauf:", height=150)
    
    if st.button("🚀 Interview starten", use_container_width=True):
        if job_desc and cv_text:
            st.session_state.messages = []
            st.session_state.q_count = 1
            st.session_state.interview_started = True
            st.session_state.analysis_done = False
            
            prompt = f"Du bist Recruiter. Job: {job_desc}. CV: {cv_text}. Stelle kurze Fragen. Wir machen genau {MAX_QUESTIONS} Fragen."
            st.session_state.messages = [{"role": "system", "content": prompt}]
            
            response = model.generate_content(prompt + " Begrüße mich kurz und stelle Frage 1.")
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            speak(response.text, gender)
            st.rerun()
        else:
            st.warning("Bitte erst Job & CV ausfüllen.")

    if st.session_state.interview_started:
        if st.button("🗑️ Reset", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# --- HAUPTFENSTER ---
st.title("📞 KI-Interview Simulator")

if st.session_state.analysis_done:
    # ANALYSE MODUS
    st.header("🎯 Deine Auswertung")
    with st.spinner("Analyse wird erstellt..."):
        history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
        analysis = model.generate_content(f"Analysiere das Interview (Stärken/Schwächen/Tipps): {history}")
        st.markdown(analysis.text)
        
        img_data = create_feedback_image(analysis.text)
        st.download_button("🖼️ Als Bild speichern (für WhatsApp/LinkedIn)", img_data, "feedback.png", "image/png", use_container_width=True)
        st.balloons()

elif st.session_state.interview_started:
    # INTERVIEW MODUS
    # Fortschrittsanzeige
    progress = st.session_state.q_count / MAX_QUESTIONS
    st.progress(progress, text=f"Frage {st.session_state.q_count} von {MAX_QUESTIONS}")
    
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    if st.session_state.q_count <= MAX_QUESTIONS:
        user_input = st.chat_input("Deine Antwort...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            if st.session_state.q_count < MAX_QUESTIONS:
                # Nächste Frage
                st.session_state.q_count += 1
                chat_history = [{"role": "user" if m["role"] in ["user", "system"] else "model", "parts": [m["content"]]} for m in st.session_state.messages]
                response = model.generate_content(chat_history)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                speak(response.text, gender)
                st.rerun()
            else:
                # Letzte Frage beantwortet -> Analyse
                st.session_state.analysis_done = True
                st.rerun()
    
    # Optionaler Abbruch-Button
    if st.button("Interview vorzeitig beenden & auswerten"):
        st.session_state.analysis_done = True
        st.rerun()

else:
    # WILLKOMMEN
    st.info("Gib links deine Daten ein und klicke auf Start. Viel Erfolg!")
    st.markdown("""
    ### Tipps für ein gutes Training:
    1. **Sprich laut:** Nutze die Diktierfunktion deiner Tastatur am Handy oder PC.
    2. **Bleib im Modus:** Antworte so, als hättest du den Personaler wirklich am Telefon.
    3. **Analyse:** Am Ende erhältst du ein detailliertes Feedback zu deinen Antworten.
    """)
