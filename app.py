import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
from PIL import Image, ImageDraw
import io
from pypdf import PdfReader
import time

# 1. Seiteneinstellungen
st.set_page_config(page_title="KI Interview-Coach Pro", page_icon="👤", layout="wide")

# 2. Absturzsicherung & API Initialisierung
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key fehlt! Bitte in den Streamlit Secrets hinterlegen (GOOGLE_API_KEY).")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# FIX: Wir nutzen hier den expliziten Pfad 'models/gemini-1.5-flash'
try:
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"Fehler beim Laden des Modells: {e}")
    st.stop()

# 3. Hilfsfunktionen
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def speak(text, gender="Weiblich"):
    if text:
        clean_text = text.replace("'", "\\'").replace("\n", " ")
        pitch = 1.3 if gender == "Weiblich" else 0.8
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
    img = Image.new('RGB', (800, 800), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 800, 80], fill=(0, 104, 201))
    d.text((30, 25), "Mein KI-Interview Feedback", fill=(255, 255, 255))
    y_pos = 120
    for line in text.split('\n')[:30]:
        d.text((30, y_pos), line[:85], fill=(40, 40, 40))
        y_pos += 20
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# 4. Session State initialisieren
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "q_count" not in st.session_state:
    st.session_state.q_count = 0
if "start_time" not in st.session_state:
    st.session_state.start_time = None

MAX_QUESTIONS = 5
AVATAR_FEMALE = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png"
AVATAR_MALE = "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"

# --- SIDEBAR ---
with st.sidebar:
    st.title("📂 Setup")
    voice_option = st.radio("Interviewer:", ["👩 Julia (Recruiterin)", "👨 Stefan (Recruiter)"])
    gender = "Weiblich" if "👩" in voice_option else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Job-Beschreibung (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Simulation starten", use_container_width=True):
        if up_job and up_cv:
            job_txt = extract_text_from_pdf(up_job)
            cv_txt = extract_text_from_pdf(up_cv)
            
            st.session_state.messages = []
            st.session_state.q_count = 1
            st.session_state.interview_started = True
            st.session_state.analysis_done = False
            st.session_state.start_time = time.time()
            
            system_prompt = f"Du bist Recruiter. Job: {job_txt}. CV: {cv_txt}. Stelle 5 kurze Fragen nacheinander."
            st.session_state.messages = [{"role": "system", "content": system_prompt}]
            
            # Erste Frage
            resp = model.generate_content(system_prompt + " Begrüße mich kurz und stelle Frage 1.")
            st.session_state.messages.append({"role": "assistant", "content": resp.text})
            speak(resp.text, gender)
            st.rerun()
        else:
            st.warning("Bitte beide PDFs hochladen!")

    if st.session_state.interview_started:
        if st.button("🗑️ Reset", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# --- HAUPTFENSTER ---
if st.session_state.analysis_done:
    st.header("🏁 Deine Analyse")
    history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
    with st.spinner("Erstelle Auswertung..."):
        analysis = model.generate_content(f"Analysiere dieses Interview detailliert: {history}")
        st.markdown(analysis.text)
        st.download_button("🖼️ Als Bild teilen", create_feedback_image(analysis.text), "feedback.png", "image/png")
    st.balloons()

elif st.session_state.interview_started:
    col_av, col_chat = st.columns([1, 2])
    
    with col_av:
        st.image(AVATAR_FEMALE if gender == "Weiblich" else AVATAR_MALE, width=200)
        st.subheader(f"Frage {st.session_state.q_count} von {MAX_QUESTIONS}")
        st.progress(st.session_state.q_count / MAX_QUESTIONS)
        
        # Stoppuhr
        elapsed = int(time.time() - st.session_state.start_time)
        st.metric("Dauer", f"{elapsed // 60:02d}:{elapsed % 60:02d}")

    with col_chat:
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        user_input = st.chat_input("Deine Antwort...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            if st.session_state.q_count < MAX_QUESTIONS:
                st.session_state.q_count += 1
                # Verlauf für die KI aufbereiten
                history = []
                for m in st.session_state.messages:
                    role = "user" if m["role"] in ["user", "system"] else "model"
                    history.append({"role": role, "parts": [m["content"]]})
                
                resp = model.generate_content(history)
                st.session_state.messages.append({"role": "assistant", "content": resp.text})
                speak(resp.text, gender)
                st.rerun()
            else:
                st.session_state.analysis_done = True
                st.rerun()
else:
    st.title("👤 KI-Interview Training")
    st.info("Lade links deine Dokumente hoch und starte die Simulation!")
