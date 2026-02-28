import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
import time
from pypdf import PdfReader
from PIL import Image, ImageDraw
import io

# --- 1. SETUP & MODELL-CHECK ---
st.set_page_config(page_title="KI Interview-Coach", page_icon="🎙️", layout="wide")

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("Bitte GOOGLE_API_KEY in den Secrets hinterlegen!")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

def get_chat_model():
    for name in ["models/gemini-1.5-flash", "gemini-1.5-flash"]:
        try:
            return genai.GenerativeModel(name)
        except: continue
    st.stop()

model = get_chat_model()

# --- 2. SESSION STATE (DAS GEDÄCHTNIS) ---
if "messages" not in st.session_state: st.session_state.messages = []
if "q_count" not in st.session_state: st.session_state.q_count = 0
if "interview_active" not in st.session_state: st.session_state.interview_active = False
if "start_time" not in st.session_state: st.session_state.start_time = None

MAX_QUESTIONS = 5

# --- 3. HILFSFUNKTIONEN ---
def speak(text, gender):
    """Lässt die KI im Browser sprechen."""
    if text:
        pitch = 1.3 if gender == "Weiblich" else 0.8
        clean_text = text.replace("'", "\\'").replace("\n", " ")
        st.components.v1.html(f"""
            <script>
                var m = new SpeechSynthesisUtterance('{clean_text}');
                m.lang = 'de-DE'; m.pitch = {pitch};
                window.speechSynthesis.speak(m);
            </script>
        """, height=0)

def extract_pdf(file):
    reader = PdfReader(file)
    return " ".join([p.extract_text() for p in reader.pages if p.extract_text()])

# --- 4. SIDEBAR (EINSTELLUNGEN) ---
with st.sidebar:
    st.title("👤 Recruiter Setup")
    voice = st.radio("Interviewer:", ["👩 Julia", "👨 Stefan"])
    gender = "Weiblich" if "Julia" in voice else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Job-Profil (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Gespräch jetzt starten", use_container_width=True):
        if up_job and up_cv:
            # Initialisierung
            job_txt = extract_pdf(up_job)
            cv_txt = extract_pdf(up_cv)
            st.session_state.messages = [{
                "role": "system", 
                "parts": [f"Du bist ein Recruiter. Job: {job_txt}. Bewerber-CV: {cv_txt}. Ziel: Führe ein rundenbasiertes Gespräch. Stelle genau eine Frage nach der anderen. Warte immer auf die Antwort. Sei professionell."]
            }]
            st.session_state.q_count = 1
            st.session_state.interview_active = True
            st.session_state.start_time = time.time()
            
            # Die Begrüßung + erste Frage
            res = model.generate_content(st.session_state.messages + [{"role": "user", "parts": ["Begrüße mich kurz und stelle die erste Frage."]}])
            st.session_state.messages.append({"role": "model", "parts": [res.text]})
            st.rerun()

    if st.button("🗑️ Alles zurücksetzen"):
        st.session_state.clear()
        st.rerun()

# --- 5. HAUPTFENSTER (INTERVIEW) ---
st.title("📞 Live-Interview Simulation")

if st.session_state.interview_active:
    col_av, col_chat = st.columns([1, 2])
    
    with col_av:
        img_url = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png" if gender == "Weiblich" else "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
        st.image(img_url, width=150)
        st.write(f"**Status:** Frage {st.session_state.q_count} von {MAX_QUESTIONS}")
        st.progress(st.session_state.q_count / MAX_QUESTIONS)
        
        # Automatische Sprachausgabe der letzten KI-Nachricht
        if st.session_state.messages[-1]["role"] == "model":
            speak(st.session_state.messages[-1]["parts"][0], gender)

    with col_chat:
        # Chat-Historie anzeigen
        for m in st.session_state.messages:
            if m["role"] != "system":
                with st.chat_message("assistant" if m["role"] == "model" else "user"):
                    st.write(m["parts"][0])

        # EINGABE: Sprache oder Text
        st.divider()
        audio_bytes = audio_recorder(text="Antwort einsprechen...", icon_size="2x", neutral_color="#0068c9")
        user_text = st.chat_input("Oder hier tippen...")

        # LOGIK: Antwort verarbeiten
        if (audio_bytes or user_text) and st.session_state.q_count <= MAX_QUESTIONS:
            if audio_bytes:
                # Sprache direkt an Gemini senden
                with st.spinner("KI hört zu..."):
                    user_msg = {"role": "user", "parts": [{"mime_type": "audio/wav", "data": audio_bytes}]}
                    st.session_state.messages.append({"role": "user", "parts": ["(Audio-Antwort gesendet)"]})
            else:
                user_msg = {"role": "user", "parts": [user_text]}
                st.session_state.messages.append(user_msg)

            # Nächster Schritt
            if st.session_state.q_count < MAX_QUESTIONS:
                st.session_state.q_count += 1
                response = model.generate_content(st.session_state.messages + [user_msg])
                st.session_state.messages.append({"role": "model", "parts": [response.text]})
                st.rerun()
            else:
                # FINALE ANALYSE
                st.session_state.interview_active = False
                with st.spinner("Analyse wird erstellt..."):
                    res = model.generate_content(st.session_state.messages + [{"role": "user", "parts": ["Das Interview ist beendet. Gib mir ein detailliertes Feedback zu meinen Antworten (Stärken/Schwächen)."]}])
                    st.session_state.analysis = res.text
                st.rerun()

elif "analysis" in st.session_state:
    st.balloons()
    st.header("🎯 Dein Feedback")
    st.markdown(st.session_state.analysis)
else:
    st.info("👈 Lade links deine PDFs hoch und klicke auf 'Start'.")
