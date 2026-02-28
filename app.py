import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder # Für die Spracheingabe

# --- KONFIGURATION ---
st.set_page_config(page_title="KI Interview Coach", page_icon="📞")
st.title("📞 Dein Telefon-Interview Simulator")

# API Key sicher laden (über Streamlit Secrets)
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# Session State initialisieren
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False

# --- SIDEBAR: INPUT ---
with st.sidebar:
    st.header("Unterlagen")
    job_desc = st.text_area("Stellenbeschreibung hier rein:")
    cv_text = st.text_area("Dein Lebenslauf (Text-Kopie):")
    
    if st.button("Interview starten") and job_desc and cv_text:
        st.session_state.interview_started = True
        system_prompt = f"Du bist ein Recruiter. Interviewe mich für diesen Job: {job_desc}. Mein CV: {cv_text}. Stelle EINE kurze Frage nach der anderen. Warte auf Antwort. Sei professionell."
        st.session_state.messages = [{"role": "system", "content": system_prompt}]
        # Erste Frage generieren
        response = model.generate_content(system_prompt + " Beginne das Gespräch mit einer Begrüßung und der ersten Frage.")
        st.session_state.messages.append({"role": "assistant", "content": response.text})

# --- HAUPTTEIL: DAS GESPRÄCH ---
if st.session_state.interview_started:
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    # Spracheingabe-Tool
    st.write("---")
    audio_bytes = audio_recorder(text="Klicke zum Sprechen", pause_threshold=2.0)

    if audio_bytes:
        # Hier könnte man noch Whisper API für Audio-to-Text einbauen.
        # Einfachheitshalber nutzen wir hier Text-Eingabe als Fallback 
        # oder du nutzt die Browser-Diktierfunktion.
        user_input = st.chat_input("Oder tippe deine Antwort hier...")
        
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            # KI Antwort generieren
            chat_history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            response = model.generate_content(chat_history)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()