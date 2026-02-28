import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
from PIL import Image, ImageDraw
import io
from pypdf import PdfReader

# 1. Seiteneinstellungen
st.set_page_config(page_title="KI Interview-Coach Pro", page_icon="👤", layout="wide")

# 2. API Key Prüfung
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key fehlt! Bitte in den Streamlit Secrets hinterlegen.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# 3. Hilfsfunktionen
def extract_text_from_pdf(pdf_file):
    """Liest Text aus einer hochgeladenen PDF-Datei."""
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
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
    img = Image.new('RGB', (800, 600), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 800, 80], fill=(0, 104, 201))
    d.text((30, 25), "Mein KI-Interview Feedback", fill=(255, 255, 255))
    y_pos = 120
    for line in text.split('\n')[:20]:
        d.text((30, y_pos), line[:80], fill=(40, 40, 40))
        y_pos += 22
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# 4. Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "q_count" not in st.session_state:
    st.session_state.q_count = 0
if "job_text" not in st.session_state:
    st.session_state.job_text = ""
if "cv_text" not in st.session_state:
    st.session_state.cv_text = ""

MAX_QUESTIONS = 5

# Avatare (Beispiel-URLs für professionelle AI-Porträts)
AVATAR_FEMALE = "https://raw.githubusercontent.com/Ashwin-S-Kurup/streamlit-chat-avatar/main/avatar_female.png"
AVATAR_MALE = "https://raw.githubusercontent.com/Ashwin-S-Kurup/streamlit-chat-avatar/main/avatar_male.png"

# --- SIDEBAR ---
with st.sidebar:
    st.title("📂 Unterlagen & Setup")
    voice_option = st.radio("Dein Gegenüber:", ["👩 Recruiterin (Julia)", "👨 Recruiter (Stefan)"])
    gender = "Weiblich" if "👩" in voice_option else "Männlich"
    avatar_url = AVATAR_FEMALE if gender == "Weiblich" else AVATAR_MALE
    
    st.divider()
    
    # PDF Uploads
    uploaded_job = st.file_uploader("Stellenbeschreibung (PDF)", type="pdf")
    uploaded_cv = st.file_uploader("Dein Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Simulation starten", use_container_width=True):
        if uploaded_job and uploaded_cv:
            with st.spinner("Lese Dokumente..."):
                st.session_state.job_text = extract_text_from_pdf(uploaded_job)
                st.session_state.cv_text = extract_text_from_pdf(uploaded_cv)
                
                st.session_state.messages = []
                st.session_state.q_count = 1
                st.session_state.interview_started = True
                st.session_state.analysis_done = False
                
                prompt = f"Du bist ein Recruiter. Job: {st.session_state.job_text}. CV: {st.session_state.cv_text}. Führe ein kurzes Interview mit genau {MAX_QUESTIONS} Fragen."
                st.session_state.messages = [{"role": "system", "content": prompt}]
                
                response = model.generate_content(prompt + " Begrüße mich kurz und stelle Frage 1.")
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                speak(response.text, gender)
                st.rerun()
        else:
            st.warning("Bitte beide PDFs hochladen!")

    if st.session_state.interview_started:
        if st.button("🗑️ Abbruch / Reset", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# --- HAUPTFENSTER ---
if st.session_state.analysis_done:
    st.header("🏁 Deine Analyse")
    history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
    analysis = model.generate_content(f"Gib detailliertes Feedback zum Interview: {history}")
    st.markdown(analysis.text)
    st.download_button("🖼️ Analyse als Bild speichern", create_feedback_image(analysis.text), "feedback.png", "image/png")
    st.balloons()

elif st.session_state.interview_started:
    # Layout mit Avatar
    col_av, col_chat = st.columns([1, 2])
    
    with col_av:
        st.image(avatar_url, caption=f"Dein Interviewer: {'Julia' if gender == 'Weiblich' else 'Stefan'}")
        st.progress(st.session_state.q_count / MAX_QUESTIONS, text=f"Frage {st.session_state.q_count}/{MAX_QUESTIONS}")
        st.info("💡 Tipp: Nutze die Diktierfunktion am Handy zum Antworten!")

    with col_chat:
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        if st.session_state.q_count <= MAX_QUESTIONS:
            user_input = st.chat_input("Deine Antwort...")
            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                if st.session_state.q_count < MAX_QUESTIONS:
                    st.session_state.q_count += 1
                    chat_history = [{"role": "user" if m["role"] in ["user", "system"] else "model", "parts": [m["content"]]} for m in st.session_state.messages]
                    response = model.generate_content(chat_history)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    speak(response.text, gender)
                    st.rerun()
                else:
                    st.session_state.analysis_done = True
                    st.rerun()
else:
    st.title("👤 KI-Interview Training")
    st.markdown("""
    ### So funktioniert's:
    1. Lade die **Stellenbeschreibung** und deinen **Lebenslauf** als PDF hoch.
    2. Wähle eine Stimme aus.
    3. Beantworte die 5 Fragen der KI (am besten laut sprechend).
    4. Erhalte eine Profi-Analyse deiner Antworten.
    """)
    st.image("https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=800&q=80", caption="Bereit für dein nächstes Level?")
