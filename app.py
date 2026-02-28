import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
from PIL import Image, ImageDraw
import io
from pypdf import PdfReader
import time

# 1. Seiteneinstellungen
st.set_page_config(page_title="KI Interview-Coach Pro", page_icon="👤", layout="wide")

# 2. API Initialisierung mit Fallback-Logik
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key fehlt in den Streamlit Secrets (GOOGLE_API_KEY)!")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

def get_model():
    """Probiert verschiedene Modell-Bezeichnungen, um NotFound-Fehler zu vermeiden."""
    for model_name in ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-1.5-flash-latest"]:
        try:
            m = genai.GenerativeModel(model_name)
            # Test-Aufruf um Existenz zu prüfen
            m.generate_content("test")
            return m
        except Exception:
            continue
    st.error("❌ Kein verfügbares Gemini-Modell gefunden. Prüfe deinen API-Key!")
    st.stop()

model = get_model()

# 3. Hilfsfunktionen
def extract_text_from_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        return "".join([page.extract_text() or "" for page in reader.pages])
    except:
        return ""

def speak(text, gender="Weiblich"):
    if text:
        clean_text = text.replace("'", "\\'").replace("\n", " ")
        pitch = 1.3 if gender == "Weiblich" else 0.8
        html_code = f"""<script>
            var msg = new SpeechSynthesisUtterance('{clean_text}');
            msg.lang = 'de-DE'; msg.pitch = {pitch};
            window.speechSynthesis.speak(msg);
        </script>"""
        st.components.v1.html(html_code, height=0)

def create_feedback_image(text):
    img = Image.new('RGB', (800, 800), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 800, 80], fill=(0, 104, 201))
    d.text((30, 25), "KI-Interview Feedback", fill=(255, 255, 255))
    y = 120
    for line in text.split('\n')[:35]:
        d.text((30, y), line[:85], fill=(40, 40, 40))
        y += 18
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# 4. Session State
for key in ["messages", "job_txt", "cv_txt", "start_time"]:
    if key not in st.session_state: st.session_state[key] = None if key == "start_time" else []
if "q_count" not in st.session_state: st.session_state.q_count = 0
if "interview_started" not in st.session_state: st.session_state.interview_started = False
if "analysis_done" not in st.session_state: st.session_state.analysis_done = False

MAX_QUESTIONS = 5
AVATARS = {
    "Weiblich": "https://cdn-icons-png.flaticon.com/512/4140/4140047.png",
    "Männlich": "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
}

# --- SIDEBAR ---
with st.sidebar:
    st.title("📂 Interview Setup")
    voice = st.radio("Dein Interviewer:", ["👩 Julia", "👨 Stefan"])
    gender = "Weiblich" if "👩" in voice else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Job-Anzeige (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    salary_expectation = st.text_input("Gehaltswunsch (optional):", placeholder="z.B. 60.000€")
    
    if st.button("🚀 Simulation starten", use_container_width=True):
        if up_job and up_cv:
            st.session_state.job_txt = extract_text_from_pdf(up_job)
            st.session_state.cv_txt = extract_text_from_pdf(up_cv)
            st.session_state.messages = []
            st.session_state.q_count = 1
            st.session_state.interview_started = True
            st.session_state.analysis_done = False
            st.session_state.start_time = time.time()
            
            sys_p = f"Du bist Recruiter. Job: {st.session_state.job_txt}. CV: {st.session_state.cv_txt}. Ziel: 5 Fragen."
            st.session_state.messages = [{"role": "system", "content": sys_p}]
            
            res = model.generate_content(sys_p + " Begrüße mich und stelle Frage 1.")
            st.session_state.messages.append({"role": "assistant", "content": res.text})
            speak(res.text, gender)
            st.rerun()
        else:
            st.warning("Bitte beide PDFs hochladen!")

# --- HAUPTFENSTER ---
if st.session_state.analysis_done:
    st.header("🎯 Analyse & Gehalts-Check")
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
    with st.spinner("Werte Gespräch aus..."):
        prompt = f"Analysiere dieses Interview detailliert (Stärken/Schwächen). Gehaltswunsch war: {salary_expectation}. Gib einen Gehalts-Check basierend auf dem Jobprofil: {hist}"
        analysis = model.generate_content(prompt)
        st.markdown(analysis.text)
        st.download_button("🖼️ Als Bild teilen", create_feedback_image(analysis.text), "feedback.png", "image/png")
    st.balloons()

elif st.session_state.interview_started:
    col_l, col_r = st.columns([1, 2])
    with col_l:
        st.image(AVATARS[gender], width=150)
        st.subheader(f"Frage {st.session_state.q_count} / {MAX_QUESTIONS}")
        st.progress(st.session_state.q_count / MAX_QUESTIONS)
        elapsed = int(time.time() - st.session_state.start_time)
        st.metric("Dauer", f"{elapsed//60:02d}:{elapsed%60:02d}")

    with col_r:
        for m in st.session_state.messages:
            if m["role"] != "system":
                with st.chat_message(m["role"]): st.write(m["content"])

        u_input = st.chat_input("Deine Antwort...")
        if u_input:
            st.session_state.messages.append({"role": "user", "content": u_input})
            if st.session_state.q_count < MAX_QUESTIONS:
                st.session_state.q_count += 1
                history = [{"role": "user" if m["role"] in ["user", "system"] else "model", "parts": [m["content"]]} for m in st.session_state.messages]
                res = model.generate_content(history)
                st.session_state.messages.append({"role": "assistant", "content": res.text})
                speak(res.text, gender)
                st.rerun()
            else:
                st.session_state.analysis_done = True
                st.rerun()
else:
    st.title("👤 KI-Interview Training")
    st.image("https://images.unsplash.com/photo-1521737711867-e3b97375f902?auto=format&fit=crop&w=800&q=80")
    st.info("Lade PDFs hoch und wähle deinen Recruiter, um zu starten!")
