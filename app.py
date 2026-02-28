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
    return genai.GenerativeModel('models/gemini-2.5-flash')

model = load_model()

# --- 2. HILFSFUNKTIONEN ---
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    return " ".join([p.extract_text() or "" for p in reader.pages])

def speak(text, gender):
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
    voice = st.radio("Interviewer auswählen:", ["👩 Julia", "👨 Stefan"])
    recruiter_name = "Julia" if "Julia" in voice else "Stefan"
    gender = "Weiblich" if "Julia" in voice else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Stellenanzeige (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Gespräch jetzt starten", use_container_width=True):
        if up_job and up_cv:
            job_txt = extract_text_from_pdf(up_job)
            cv_txt = extract_text_from_pdf(up_cv)
            
            # WICHTIG: Name wird hier fest in den System-Prompt geschrieben
            st.session_state.history = [{
                "role": "user", 
                "parts": [f"SYSTEM-ORDER: Dein Name ist {recruiter_name} von van Hekk Spedition. "
                          f"Du interviewst den Bewerber für den Job: {job_txt}. Sein CV: {cv_txt}. "
                          f"REGELN: 1. Benutze NIEMALS '[Ihr Name]'. Du BIST {recruiter_name}. "
                          "2. Stelle NUR EINE Frage pro Runde. 3. Wenn die Antwort des Bewerbers "
                          "keinen Sinn ergibt oder nach Hintergrundgeräuschen klingt, bitte ihn höflich, "
                          "es zu wiederholen, statt darauf einzugehen."]
            }]
            
            res = model.generate_content(st.session_state.history + [{"role": "user", "parts": [f"Stelle dich als {recruiter_name} vor und beginne mit Frage 1."]}])
            st.session_state.history.append({"role": "model", "parts": [res.text]})
            
            st.session_state.interview_active = True
            st.session_state.q_num = 1
            st.rerun()

# --- 5. HAUPTFENSTER ---

st.title("📞 Live-Interview Coach")

if st.session_state.interview_active:
    col_av, col_chat = st.columns([1, 2])
    
    with col_av:
        img = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png" if gender == "Weiblich" else "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
        st.image(img, width=150)
        st.write(f"**Interviewer:** {recruiter_name}")
        st.write(f"**Frage:** {st.session_state.q_num} / {MAX_QUESTIONS}")
        
        if st.session_state.history[-1]["role"] == "model":
            speak(st.session_state.history[-1]["parts"][0], gender)

    with col_chat:
        for m in st.session_state.history:
            if "SYSTEM-ORDER:" not in str(m["parts"][0]):
                with st.chat_message("assistant" if m["role"] == "model" else "user"):
                    st.write(m["parts"][0])

        st.divider()
        # Mikrofon-Button
        audio_bytes = audio_recorder(text="Klicken, sprechen, dann erneut klicken zum Stoppen", icon_size="2x", key=f"rec_{st.session_state.q_num}")
        text_input = st.chat_input("Oder hier tippen...")

        if (audio_bytes or text_input) and not st.session_state.processing:
            st.session_state.processing = True
            
            if audio_bytes:
                with st.spinner("Verarbeite Audio..."):
                    # Spezieller Prompt für die Transkription, um Müll zu filtern
                    trans_res = model.generate_content([
                        {"mime_type": "audio/wav", "data": audio_bytes},
                        "Transkribiere dieses Interview-Audio. Wenn nur Rauschen oder "
                        "Hintergrundgespräche zu hören sind, antworte NUR mit dem Wort: [UNVERSTÄNDLICH]."
                    ])
                    user_text = trans_res.text
            else:
                user_text = text_input

            # Wenn die Transkription Müll war, fordern wir eine Wiederholung an
            if "[UNVERSTÄNDLICH]" in user_text:
                st.session_state.history.append({"role": "user", "parts": ["(Rauschen/Hintergrundgeräusche)"]})
                st.session_state.history.append({"role": "model", "parts": ["Entschuldigung, das habe ich akustisch nicht verstanden. Könnten Sie das bitte wiederholen?"]})
                st.session_state.processing = False
                st.rerun()
            else:
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
