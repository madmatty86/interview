import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder

# 1. Seiteneinstellungen
st.set_page_config(page_title="KI Interview-Coach", page_icon="🎙️")

# 2. API Key Prüfung
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key fehlt in den Streamlit Secrets!")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# 3. Erweiterte Sprachausgabe (mit Pitch-Steuerung)
def speak(text, gender="Weiblich"):
    if text:
        clean_text = text.replace("'", "\\'").replace("\n", " ")
        # Pitch: 1.0 ist Standard, 0.5 ist tief (männlich), 1.5 ist hoch (weiblich)
        pitch = 1.4 if gender == "Weiblich" else 0.8
        
        html_code = f"""
            <script>
                var msg = new SpeechSynthesisUtterance('{clean_text}');
                msg.lang = 'de-DE';
                msg.pitch = {pitch};
                msg.rate = 1.0;
                window.speechSynthesis.speak(msg);
            </script>
        """
        st.components.v1.html(html_code, height=0)

# 4. Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Setup")
    
    # NEU: Stimmauswahl
    voice_option = st.radio("Stimme des Recruiters:", ["👩 Recruiterin (Heller)", "👨 Recruiter (Tiefer)"])
    gender = "Weiblich" if "👩" in voice_option else "Männlich"
    
    st.divider()
    job_desc = st.text_area("Stellenbeschreibung:", height=150)
    cv_text = st.text_area("Lebenslauf:", height=150)
    
    if st.button("🚀 Interview starten"):
        if job_desc and cv_text:
            st.session_state.interview_started = True
            system_prompt = f"Du bist ein Recruiter. Interviewe mich für: {job_desc}. Mein CV: {cv_text}. Nur eine kurze Frage pro Antwort!"
            st.session_state.messages = [{"role": "system", "content": system_prompt}]
            
            first_response = model.generate_content(system_prompt + " Begrüße mich und stelle die erste Frage.")
            st.session_state.messages.append({"role": "assistant", "content": first_response.text})
            speak(first_response.text, gender)
            st.rerun()

# --- HAUPTFENSTER ---
st.title("📞 Interview Simulator")

if st.session_state.interview_started:
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    st.write("---")
    # Eingabe
    user_input = st.chat_input("Deine Antwort...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Historie für Gemini aufbereiten
        chat_history = []
        for m in st.session_state.messages:
            role = "user" if m["role"] in ["user", "system"] else "model"
            chat_history.append({"role": role, "parts": [m["content"]]})
        
        response = model.generate_content(chat_history)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
        speak(response.text, gender)
        st.rerun()
else:
    st.info("👈 Bitte links Daten eingeben und Stimme wählen.")
