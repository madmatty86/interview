import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
from pypdf import PdfReader
import time

# --- 1. SETUP & ERWEITERTES CSS ---
st.set_page_config(page_title="KI Interview-Coach Pro", page_icon="🎙️", layout="wide")

st.markdown("""
    <style>
    .on-air {
        height: 15px; width: 15px; background-color: #ff4b4b;
        border-radius: 50%; display: inline-block;
        animation: blink 1s infinite; vertical-align: middle; margin-right: 8px;
    }
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
    .sentiment-box {
        padding: 20px; border-radius: 10px; text-align: center;
        background-color: #f0f2f6; border: 2px solid #dfe1e6;
    }
    .emoji-large { font-size: 50px; }
    </style>
""", unsafe_allow_html=True)

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key fehlt!")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('models/gemini-2.5-flash')

# --- 2. HILFSFUNKTIONEN ---
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    return " ".join([p.extract_text() or "" for p in reader.pages])

def speak(text, gender):
    if text:
        p = 1.1 if gender == "Weiblich" else 0.8
        t = text.replace("'", "\\'").replace("\n", " ")
        st.components.v1.html(f"<script>window.speechSynthesis.cancel(); var u = new SpeechSynthesisUtterance('{t}'); u.lang = 'de-DE'; u.pitch = {p}; window.speechSynthesis.speak(u);</script>", height=0)

def safe_generate(content):
    try:
        return model.generate_content(content)
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ Rate-Limit! Bitte 30 Sek. warten...")
        else:
            st.error(f"Fehler: {e}")
        return None

def get_sentiment_emoji(score):
    if score >= 80: return "😍", "Absolut überzeugt!"
    if score >= 60: return "🙂", "Gute Antwort."
    if score >= 40: return "😐", "Okay, aber hake nach."
    return "🧐", "Konnte noch nicht ganz überzeugen."

# --- 3. SESSION STATE ---
for key in ["history", "interview_active", "q_num", "processing", "current_score"]:
    if key not in st.session_state:
        if key == "history": st.session_state[key] = []
        elif key == "q_num": st.session_state[key] = 0
        elif key == "current_score": st.session_state[key] = 50
        else: st.session_state[key] = False

MAX_QUESTIONS = 5

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("👤 Recruiter Setup")
    voice = st.radio("Interviewer:", ["👩 Julia", "👨 Stefan"])
    rec_name = "Julia" if "Julia" in voice else "Stefan"
    gender = "Weiblich" if "Julia" in voice else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Job-Anzeige (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Simulation starten", use_container_width=True):
        if up_job and up_cv:
            st.session_state.history = [{
                "role": "user", 
                "parts": [f"SYSTEM: Dein Name ist {rec_name}. Job-Anforderung: {extract_text_from_pdf(up_job)}. CV: {extract_text_from_pdf(up_cv)}. REGELN: Sei {rec_name}. Antworte kurz."]
            }]
            res = safe_generate(st.session_state.history + [{"role": "user", "parts": ["Begrüße mich und stelle Frage 1."]}])
            if res:
                st.session_state.history.append({"role": "model", "parts": [res.text]})
                st.session_state.interview_active = True
                st.session_state.q_num = 1
                st.rerun()

# --- 5. HAUPTFENSTER ---
st.title("📞 KI-Interview mit Live-Gefühl")



if st.session_state.interview_active:
    col_av, col_chat = st.columns([1, 2])
    
    with col_av:
        img = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png" if gender == "Weiblich" else "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
        st.image(img, width=150)
        
        # --- DAS NEUE STIMMUNGS-BAROMETER ---
        st.divider()
        emoji, label = get_sentiment_emoji(st.session_state.current_score)
        st.markdown(f"<div class='sentiment-box'><div class='emoji-large'>{emoji}</div><br><b>{rec_name} denkt:</b><br>{label}</div>", unsafe_allow_html=True)
        st.progress(st.session_state.current_score / 100)
        
        if st.session_state.history[-1]["role"] == "model":
            speak(st.session_state.history[-1]["parts"][0], gender)

    with col_chat:
        for m in st.session_state.history:
            if "SYSTEM:" not in str(m["parts"][0]):
                with st.chat_message("assistant" if m["role"] == "model" else "user"):
                    st.write(m["parts"][0])

        st.divider()
        if not st.session_state.processing:
            st.markdown('<div><span class="on-air"></span> Julia hört zu... Bitte jetzt antworten.</div>', unsafe_allow_html=True)
        
        audio = audio_recorder(text="Antwort sprechen", icon_size="3x", key=f"rec_{st.session_state.q_num}")
        u_text = st.chat_input("Oder tippen...")

        if (audio or u_text) and not st.session_state.processing:
            st.session_state.processing = True
            
            # Wir machen alles in EINEM Aufruf für weniger Rate-Limit-Stress
            with st.spinner("Analysiere Antwort..."):
                input_data = []
                if audio:
                    input_data.append({"mime_type": "audio/wav", "data": audio})
                
                input_data.append(f"""
                1. Transkribiere meine Antwort (falls Audio). 
                2. Bewerte die Qualität dieser Antwort für den Job auf einer Skala von 0 bis 100.
                3. Antworte im Format: SCORE: [Zahl] | TEXT: [Deine Transkription]
                """)
                
                analysis_res = safe_generate(input_data)
                
                if analysis_res:
                    try:
                        # Extrahiere Score und Text
                        parts = analysis_res.text.split("|")
                        new_score = int(parts[0].replace("SCORE:", "").strip())
                        actual_text = parts[1].replace("TEXT:", "").strip()
                        
                        st.session_state.current_score = new_score
                        st.session_state.history.append({"role": "user", "parts": [actual_text]})
                        
                        # Nächste Frage holen
                        if st.session_state.q_num < MAX_QUESTIONS:
                            st.session_state.q_num += 1
                            res = safe_generate(st.session_state.history)
                            if res: st.session_state.history.append({"role": "model", "parts": [res.text]})
                        else:
                            st.session_state.interview_active = False
                            st.session_state.show_analysis = True
                    except:
                        st.error("Fehler bei der Verarbeitung. Bitte noch einmal versuchen.")
            
            st.session_state.processing = False
            st.rerun()

elif st.session_state.get("show_analysis"):
    st.header("🏁 Abschluss-Bericht")
    st.balloons()
    # Hier kommt die finale Analyse...
