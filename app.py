import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
import time
from pypdf import PdfReader

# --- 1. SETUP ---
st.set_page_config(page_title="KI Interview-Coach Pro", page_icon="🎙️", layout="wide")

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ Bitte 'GOOGLE_API_KEY' in den Secrets hinterlegen.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

@st.cache_resource
def load_model():
    # Wir nutzen das Modell aus deinem Dashboard [cite: 26, 30, 124]
    return genai.GenerativeModel('models/gemini-2.5-flash')

model = load_model()

# --- 2. HILFSFUNKTIONEN ---
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    return " ".join([p.extract_text() or "" for p in reader.pages])

def speak(text, gender):
    if text:
        p = 1.2 if gender == "Weiblich" else 0.8
        t = text.replace("'", "\\'").replace("\n", " ")
        st.components.v1.html(f"<script>var u=new SpeechSynthesisUtterance('{t}');u.lang='de-DE';u.pitch={p};window.speechSynthesis.speak(u);</script>", height=0)

# --- 3. SESSION STATE (STABILISIERUNG) ---
# Wir nutzen Flags, um zu verhindern, dass die KI ohne User-Input weitermacht
if "history" not in st.session_state: st.session_state.history = []
if "interview_active" not in st.session_state: st.session_state.interview_active = False
if "q_num" not in st.session_state: st.session_state.q_num = 0
if "waiting_for_ai" not in st.session_state: st.session_state.waiting_for_ai = False

MAX_QUESTIONS = 5

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("👤 Recruiter Setup")
    voice = st.radio("Interviewer:", ["👩 Julia", "👨 Stefan"])
    gender = "Weiblich" if "Julia" in voice else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Job-Anzeige (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Simulation starten", use_container_width=True):
        if up_job and up_cv:
            job_txt = extract_text_from_pdf(up_job)
            cv_txt = extract_text_from_pdf(up_cv)
            
            # WICHTIG: Explizite Rollenzuweisung
            st.session_state.history = [{
                "role": "user", 
                "parts": [f"SYSTEM-ANWEISUNG: Du bist der Recruiter. ICH BIN DER BEWERBER. Interviewe MICH basierend auf Job: {job_txt} und meinem CV: {cv_txt}. Stelle EINE Frage und WARTE auf meine Antwort. Wiederhole diesen Prozess für insgesamt 5 Fragen."]
            }]
            
            # Erste Frage generieren
            res = model.generate_content(st.session_state.history + [{"role": "user", "parts": ["Hallo, ich bin bereit für das Interview. Bitte stelle die erste Frage."]}])
            st.session_state.history.append({"role": "model", "parts": [res.text]})
            
            st.session_state.interview_active = True
            st.session_state.q_num = 1
            st.session_state.waiting_for_ai = False
            st.rerun()

    if st.button("🗑️ Reset"):
        st.session_state.clear()
        st.rerun()

# --- 5. HAUPTFENSTER ---
st.title("📞 Telefoninterview Coach (v2.5)")

if st.session_state.interview_active:
    col_av, col_chat = st.columns([1, 2])
    
    with col_av:
        img = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png" if gender == "Weiblich" else "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
        st.image(img, width=150)
        st.metric("Fortschritt", f"{st.session_state.q_num} / {MAX_QUESTIONS}")
        
        if st.session_state.history[-1]["role"] == "model" and not st.session_state.waiting_for_ai:
            speak(st.session_state.history[-1]["parts"][0], gender)

    with col_chat:
        # Chat anzeigen (ohne technische Anweisungen)
        for m in st.session_state.history:
            if "SYSTEM-ANWEISUNG" not in str(m["parts"][0]):
                with st.chat_message("assistant" if m["role"] == "model" else "user"):
                    st.write(m["parts"][0])

        st.divider()
        
        # Eingabe-Logik
        # Wichtig: Der Key verhindert doppeltes Triggern
        audio = audio_recorder(text="Antwort sprechen", icon_size="2x", key=f"audio_{st.session_state.q_num}")
        text_input = st.chat_input("Oder hier tippen...")

        # Nur verarbeiten, wenn wirklich Input da ist UND wir nicht schon auf die KI warten
        if (audio or text_input) and not st.session_state.waiting_for_ai:
            user_msg = text_input if text_input else "(Audio-Antwort empfangen)"
            st.session_state.history.append({"role": "user", "parts": [user_msg]})
            st.session_state.waiting_for_ai = True # Blocke weitere Eingaben
            
            if st.session_state.q_num < MAX_QUESTIONS:
                st.session_state.q_num += 1
                res = model.generate_content(st.session_state.history)
                st.session_state.history.append({"role": "model", "parts": [res.text]})
                st.session_state.waiting_for_ai = False
                st.rerun()
            else:
                st.session_state.interview_active = False
                st.session_state.show_analysis = True
                st.rerun()

elif st.session_state.get("show_analysis"):
    st.header("🏁 Analyse deiner Performance")
    with st.spinner("Bewerbung wird ausgewertet..."):
        # Spezifischer Prompt für das Feedback an den BEWERBER
        history_str = "\n".join([f"{m['role']}: {m['parts'][0]}" for m in st.session_state.history])
        analysis_prompt = f"Analysiere die Antworten des BEWERBERS (user) in diesem Gespräch: {history_str}. Gib Tipps, was er/sie inhaltlich oder rhetorisch besser machen kann."
        analysis = model.generate_content(analysis_prompt)
        st.markdown(analysis.text)
        st.balloons()
