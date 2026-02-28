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
    # Wir nutzen Gemini 2.5 Flash für maximale Geschwindigkeit
    return genai.GenerativeModel('models/gemini-2.5-flash')

model = load_model()

# --- 2. HILFSFUNKTIONEN ---
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    return " ".join([p.extract_text() or "" for p in reader.pages])

def speak(text, gender):
    """Lässt den Recruiter sprechen."""
    if text:
        p = 1.1 if gender == "Weiblich" else 0.8
        t = text.replace("'", "\\'").replace("\n", " ")
        st.components.v1.html(f"""
            <script>
                window.speechSynthesis.cancel();
                var u = new SpeechSynthesisUtterance('{t}');
                u.lang = 'de-DE'; u.pitch = {p};
                window.speechSynthesis.speak(u);
            </script>
        """, height=0)

# --- 3. SESSION STATE ---
if "history" not in st.session_state: st.session_state.history = []
if "interview_active" not in st.session_state: st.session_state.interview_active = False
if "q_num" not in st.session_state: st.session_state.q_num = 0
if "processing" not in st.session_state: st.session_state.processing = False

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
            
            # System-Regeln: Strenges Interview-Verhalten
            st.session_state.history = [{
                "role": "user", 
                "parts": [f"SYSTEM: Du bist Recruiter. Job: {job_txt}. CV: {cv_txt}. "
                          "REGELN: 1. Du bist ein MENSCH am Telefon. 2. Stelle NUR EINE Frage. "
                          "3. Sage NIEMALS, dass du eine KI bist. 4. Warte auf die Antwort."]
            }]
            
            # Erste Aktion: Begrüßung
            res = model.generate_content(st.session_state.history + [{"role": "user", "parts": ["Beginne das Interview mit einer Begrüßung und Frage 1."]}])
            st.session_state.history.append({"role": "model", "parts": [res.text]})
            
            st.session_state.interview_active = True
            st.session_state.q_num = 1
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
        st.write(f"**Frage {st.session_state.q_num} / {MAX_QUESTIONS}**")
        
        # Audio-Trigger (nur wenn die KI gerade geantwortet hat)
        if st.session_state.history[-1]["role"] == "model":
            speak(st.session_state.history[-1]["parts"][0], gender)

    with col_chat:
        for m in st.session_state.history:
            if "SYSTEM:" not in str(m["parts"][0]):
                with st.chat_message("assistant" if m["role"] == "model" else "user"):
                    st.write(m["parts"][0])

        st.divider()
        
        # Audio-Recorder mit automatischer Verarbeitung
        audio_bytes = audio_recorder(text="Antwort einsprechen (Klick zum Stoppen)", icon_size="3x", key=f"rec_{st.session_state.q_num}")
        text_input = st.chat_input("Oder hier tippen...")

        if (audio_bytes or text_input) and not st.session_state.processing:
            st.session_state.processing = True
            
            # 1. Schritt: Audio zu Text (falls nötig)
            if audio_bytes:
                with st.spinner("Ich höre zu..."):
                    # Wir nutzen Gemini selbst zur Transkription
                    response = model.generate_content([
                        {"mime_type": "audio/wav", "data": audio_bytes},
                        "Transkribiere dieses Audio exakt in Text. Antworte NUR mit dem transkribierten Text."
                    ])
                    user_text = response.text
            else:
                user_text = text_input

            # 2. Schritt: Gespräch fortführen
            st.session_state.history.append({"role": "user", "parts": [user_text]})
            
            if st.session_state.q_num < MAX_QUESTIONS:
                st.session_state.q_num += 1
                res = model.generate_content(st.session_state.history)
                st.session_state.history.append({"role": "model", "parts": [res.text]})
                st.session_state.processing = False
                st.rerun()
            else:
                st.session_state.interview_active = False
                st.session_state.show_analysis = True
                st.session_state.processing = False
                st.rerun()

elif st.session_state.get("show_analysis"):
    st.header("🏁 Dein Feedback")
    history_str = "\n".join([f"{m['role']}: {m['parts'][0]}" for m in st.session_state.history if "SYSTEM:" not in str(m['parts'][0])])
    analysis = model.generate_content(f"Analysiere die Antworten des Bewerbers (user): {history_str}. Gib konkrete Tipps.")
    st.markdown(analysis.text)
    if st.button("Neustart"):
        st.session_state.clear()
        st.rerun()
