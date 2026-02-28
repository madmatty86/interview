import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder

# 1. Seiteneinstellungen
st.set_page_config(
    page_title="KI Interview-Coach", 
    page_icon="🎙️", 
    layout="centered"
)

# 2. Absturzsicherung: API Key Prüfung
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key nicht gefunden! Bitte füge 'GOOGLE_API_KEY' in den Streamlit Secrets hinzu.")
    st.info("Gehe zu: Settings -> Secrets und gib ein: GOOGLE_API_KEY = 'dein_key'")
    st.stop()

# 3. KI-Modell Initialisierung
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# 4. Hilfsfunktion: Sprachausgabe (Text-to-Speech)
def speak(text):
    if text:
        # Bereinigt den Text für JavaScript (entfernt Zeilenumbrüche und einfache Anstriche)
        clean_text = text.replace("'", "\\'").replace("\n", " ")
        html_code = f"""
            <script>
                var msg = new SpeechSynthesisUtterance('{clean_text}');
                msg.lang = 'de-DE';
                msg.rate = 1.0; 
                window.speechSynthesis.speak(msg);
            </script>
        """
        st.components.v1.html(html_code, height=0)

# 5. Session State (Speicher des Gesprächsverlaufs)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False

# --- SIDEBAR: KONFIGURATION ---
with st.sidebar:
    st.title("⚙️ Einstellungen")
    job_desc = st.text_area("Stellenbeschreibung:", placeholder="Kopiere hier die Anzeige rein...", height=200)
    cv_text = st.text_area("Dein Lebenslauf:", placeholder="Kopiere hier deinen CV rein...", height=200)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Start"):
            if job_desc and cv_text:
                st.session_state.interview_started = True
                # System-Anweisung für die KI
                system_prompt = (
                    f"Du bist ein professioneller Recruiter. Interviewe den Bewerber für diesen Job: {job_desc}. "
                    f"Nutze diesen Lebenslauf als Basis: {cv_text}. "
                    "Regeln: Stelle nur EINE kurze Frage auf einmal. Warte auf die Antwort. "
                    "Sei realistisch, hake bei Lücken im Lebenslauf nach. Sprich Deutsch."
                )
                st.session_state.messages = [{"role": "system", "content": system_prompt}]
                
                # Erste Frage generieren
                first_response = model.generate_content(system_prompt + " Begrüße mich kurz und stelle die erste Frage.")
                st.session_state.messages.append({"role": "assistant", "content": first_response.text})
                st.rerun()
            else:
                st.warning("Bitte fülle beide Felder aus!")
    
    with col2:
        if st.button("🗑️ Reset"):
            st.session_state.messages = []
            st.session_state.interview_started = False
            st.rerun()

# --- HAUPTFENSTER: INTERVIEW ---
st.title("📞 Telefoninterview Simulator")

if not st.session_state.interview_started:
    st.info("Willkommen! Gib links deine Daten ein und klicke auf 'Start', um das Training zu beginnen.")
else:
    # Chat-Verlauf anzeigen
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    # Eingabe-Bereich
    st.write("---")
    
    # Spracheingabe (Audio Recorder)
    audio_data = audio_recorder(text="Antwort einsprechen", pause_threshold=2.0, icon_size="2x")
    
    # Texteingabe als Backup/Ergänzung
    user_input = st.chat_input("Oder tippe hier deine Antwort...")

    # Logik: Wenn der User antwortet
    if user_input:
        # Nachricht speichern
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # KI-Antwort generieren (gesamte Historie mitsenden)
        chat_history = []
        for m in st.session_state.messages:
            chat_history.append({"role": "user" if m["role"] == "user" or m["role"] == "system" else "model", "parts": [m["content"]]})
        
        response = model.generate_content(chat_history)
        
        # Antwort speichern und vorlesen
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
        # Trigger für Sprache und Refresh
        speak(response.text)
        st.rerun()

    # Falls Audio aufgenommen wurde, aber die Umwandlung fehlt (Hinweis für User)
    if audio_data:
        st.info("Audio empfangen! (Hinweis: Um Audio direkt in Text umzuwandeln, müsste noch ein 'Whisper'-Modell integriert werden. Nutze aktuell das Textfeld für die Antwort.)")
