import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
import time
from pypdf import PdfReader
from PIL import Image, ImageDraw
import io

# --- 1. SETUP ---
st.set_page_config(page_title="KI Interview-Coach 2026", page_icon="🎙️", layout="wide")

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ Bitte 'GOOGLE_API_KEY' in den Streamlit Secrets hinterlegen.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Laut deinen PDFs ist Gemini 2.5 Flash für dich verfügbar
@st.cache_resource
def load_model():
    try:
        # Wir priorisieren 2.5 Flash, da es in deinem Dashboard steht
        m = genai.GenerativeModel('models/gemini-2.5-flash')
        m.generate_content("test") 
        return m
    except:
        # Fallback auf die Liste (Detektiv-Modus)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in models if "2.5-flash" in m or "1.5-flash" in m), models[0])
        return genai.GenerativeModel(target)

model = load_model()

# --- 2. HILFSFUNKTIONEN ---
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    return " ".join([p.extract_text() or "" for p in reader.pages])

def speak(text, gender):
    if text:
        p = 1.3 if gender == "Weiblich" else 0.8
        t = text.replace("'", "\\'").replace("\n", " ")
        st.components.v1.html(f"<script>var u=new SpeechSynthesisUtterance('{t}');u.lang='de-DE';u.pitch={p};window.speechSynthesis.speak(u);</script>", height=0)

# --- 3. SESSION STATE ---
if "history" not in st.session_state: st.session_state.history = []
if "interview_active" not in st.session_state: st.session_state.interview_active = False
if "q_num" not in st.session_state: st.session_state.q_num = 0
if "start_time" not in st.session_state: st.session_state.start_time = None

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("👤 Interview-Setup")
    voice = st.radio("Interviewer:", ["👩 Julia", "👨 Stefan"])
    gender = "Weiblich" if "Julia" in voice else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Stellenanzeige (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Simulation starten", use_container_width=True):
        if up_job and up_cv:
            job_txt = extract_text_from_pdf(up_job)
            cv_txt = extract_text_from_pdf(up_cv)
            
            # Reset & System Prompt
            st.session_state.history = [
                {"role": "user", "parts": [f"Du bist Recruiter. Job: {job_txt}. CV: {cv_txt}. Ziel: 5 kurze Fragen nacheinander. Antworte IMMER nur mit EINER Frage/Begrüßung. Warte auf Antwort."]}
            ]
            
            # Erste Aktion: Begrüßung
            res = model.generate_content(st.session_state.history + [{"role": "user", "parts": ["Starte das Interview. Begrüße mich kurz und stelle Frage 1."]}])
            st.session_state.history.append({"role": "model", "parts": [res.text]})
            
            st.session_state.interview_active = True
            st.session_state.q_num = 1
            st.session_state.start_time = time.time()
            st.rerun()

    if st.button("🗑️ Reset"):
        st.session_state.clear()
        st.rerun()

# --- 5. HAUPTFENSTER ---
st.title("📞 Live-Interview Coach")

if st.session_state.interview_active:
    col_av, col_chat = st.columns([1, 2])
    
    with col_av:
        img = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png" if gender == "Weiblich" else "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
        st.image(img, width=150)
        st.write(f"**Frage {st.session_state.q_num} / 5**")
        st.progress(st.session_state.q_num / 5)
        
        # Audio-Trigger
        if st.session_state.history[-1]["role"] == "model":
            speak(st.session_state.history[-1]["parts"][0], gender)

    with col_chat:
        # Nur das eigentliche Gespräch anzeigen (kein System-Prompt)
        for m in st.session_state.history:
            if "Du bist Recruiter" not in m["parts"][0]:
                with st.chat_message("assistant" if m["role"] == "model" else "user"):
                    st.write(m["parts"][0])

        st.divider()
        audio = audio_recorder(text="Antwort sprechen", icon_size="2x")
        text_input = st.chat_input("Tippen...")

        if (audio or text_input) and st.session_state.q_num <= 5:
            # Antwort hinzufügen
            user_msg = text_input if text_input else "(Audio-Antwort gesendet)"
            st.session_state.history.append({"role": "user", "parts": [user_msg]})
            
            if st.session_state.q_num < 5:
                st.session_state.q_num += 1
                # KI holt nächste Frage
                res = model.generate_content(st.session_state.history)
                st.session_state.history.append({"role": "model", "parts": [res.text]})
                st.rerun()
            else:
                # Analyse-Modus aktivieren
                st.session_state.interview_active = False
                st.session_state.show_analysis = True
                st.rerun()

elif st.session_state.get("show_analysis"):
    st.header("🏁 Dein Feedback")
    with st.spinner("Analysiere Gespräch..."):
        full_h = "\n".join([p["parts"][0] for p in st.session_state.history if isinstance(p["parts"][0], str)])
        analysis = model.generate_content(f"Gib kurzes, konstruktives Feedback: {full_h}")
        st.markdown(analysis.text)
        st.balloons()
        if st.button("Neues Training"):
            st.session_state.clear()
            st.rerun()
else:
    st.info("Willkommen! Lade links deine PDFs hoch, um das Training mit Gemini 2.5 Flash zu starten.")
