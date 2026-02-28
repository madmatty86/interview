import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
from PIL import Image, ImageDraw
import io
from pypdf import PdfReader
import time

# --- 1. INITIALISIERUNG & FEHLER-CHECK ---
st.set_page_config(page_title="KI Interview-Coach Pro", page_icon="🎙️", layout="wide")

if "GOOGLE_API_KEY" not in st.secrets:
    st.error("❌ API Key fehlt! Bitte in den Streamlit Secrets (GOOGLE_API_KEY) hinterlegen.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Modell-Suche: Wir fragen Google, welche Namen dein Key akzeptiert
@st.cache_resource
def load_robust_model():
    try:
        # Wir versuchen die gängigsten Namen nacheinander
        for m_name in ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-pro"]:
            try:
                m = genai.GenerativeModel(m_name)
                m.generate_content("test") # Kurzer Test-Aufruf
                return m
            except:
                continue
        st.error("Kein passendes Modell gefunden. Bitte API-Key im Google AI Studio prüfen.")
        st.stop()
    except Exception as e:
        st.error(f"Fehler beim Modell-Laden: {e}")
        st.stop()

model = load_robust_model()

# --- 2. HILFSFUNKTIONEN ---
def get_pdf_text(file):
    reader = PdfReader(file)
    return " ".join([p.extract_text() or "" for p in reader.pages])

def speak(text, gender):
    """Browser-Sprachausgabe via JavaScript"""
    if text:
        p = 1.3 if gender == "Weiblich" else 0.8
        t = text.replace("'", "\\'").replace("\n", " ")
        st.components.v1.html(f"""
            <script>
                var u = new SpeechSynthesisUtterance('{t}');
                u.lang = 'de-DE'; u.pitch = {p};
                window.speechSynthesis.speak(u);
            </script>
        """, height=0)

def make_feedback_img(text):
    img = Image.new('RGB', (800, 800), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,800,80], fill=(0,104,201))
    d.text((20,25), "Dein Interview-Ergebnis", fill=(255,255,255))
    y = 120
    for line in text.split('\n')[:35]:
        d.text((20, y), line[:85], fill=(50,50,50))
        y += 20
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

# --- 3. SESSION STATE (GEDÄCHTNIS) ---
if "history" not in st.session_state: st.session_state.history = []
if "step" not in st.session_state: st.session_state.step = 0 # 0=Setup, 1=Interview, 2=Analyse
if "q_num" not in st.session_state: st.session_state.q_num = 1
if "start_t" not in st.session_state: st.session_state.start_t = None

MAX_Q = 5

# --- 4. SIDEBAR SETUP ---
with st.sidebar:
    st.title("👤 Recruiter Setup")
    v_choice = st.radio("Interviewer:", ["👩 Julia", "👨 Stefan"])
    gender = "Weiblich" if "Julia" in v_choice else "Männlich"
    
    st.divider()
    up_job = st.file_uploader("Stellenanzeige (PDF)", type="pdf")
    up_cv = st.file_uploader("Lebenslauf (PDF)", type="pdf")
    
    if st.button("🚀 Gespräch starten", use_container_width=True):
        if up_job and up_cv:
            job_txt = get_pdf_text(up_job)
            cv_txt = get_pdf_text(up_cv)
            
            # Start-Prompt
            sys_msg = f"Du bist Recruiter. Job: {job_txt}. CV: {cv_txt}. Stelle 5 Fragen, eine nach der anderen. Warte auf Antwort."
            st.session_state.history = [{"role": "user", "parts": [sys_msg]}]
            
            # Begrüßung generieren
            res = model.generate_content(st.session_state.history + [{"role": "user", "parts": ["Begrüße mich kurz und stelle Frage 1."]}])
            st.session_state.history.append({"role": "model", "parts": [res.text]})
            
            st.session_state.step = 1
            st.session_state.q_num = 1
            st.session_state.start_t = time.time()
            st.rerun()
        else:
            st.warning("Bitte beide PDFs hochladen!")

    if st.button("🗑️ App zurücksetzen"):
        st.session_state.clear()
        st.rerun()

# --- 5. HAUPTFENSTER ---
st.title("📞 Telefoninterview Simulator")

if st.session_state.step == 1: # INTERVIEW LÄUFT
    col1, col2 = st.columns([1, 2])
    
    with col1:
        img = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png" if gender == "Weiblich" else "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
        st.image(img, width=180)
        st.metric("Fortschritt", f"{st.session_state.q_num} / {MAX_Q}")
        st.progress(st.session_state.q_num / MAX_Q)
        
        # Stoppuhr
        sec = int(time.time() - st.session_state.start_t)
        st.write(f"⏱️ Zeit: {sec//60:02d}:{sec%60:02d}")
        
        # Audio-Ausgabe der letzten Nachricht
        if st.session_state.history[-1]["role"] == "model":
            speak(st.session_state.history[-1]["parts"][0], gender)

    with col2:
        # Chat anzeigen
        for m in st.session_state.history:
            if m["role"] != "user" or "Du bist Recruiter" not in m["parts"][0]:
                with st.chat_message("assistant" if m["role"] == "model" else "user"):
                    st.write(m["parts"][0])

        # Eingabe
        st.divider()
        audio = audio_recorder(text="Antwort sprechen", icon_size="2x")
        u_text = st.chat_input("Oder hier tippen...")

        if (audio or u_text) and st.session_state.q_num <= MAX_Q:
            # Falls Audio kommt, schicken wir es als File zu Gemini
            if audio:
                with st.spinner("KI hört zu..."):
                    # Wir speichern das Audio kurz als part
                    user_part = {"mime_type": "audio/wav", "data": audio}
                    # Für die Anzeige im Chat nutzen wir Text
                    st.session_state.history.append({"role": "user", "parts": ["🎤 (Audio-Antwort)"]})
            else:
                user_part = u_text
                st.session_state.history.append({"role": "user", "parts": [u_text]})

            # Nächste Runde
            if st.session_state.q_num < MAX_Q:
                st.session_state.q_num += 1
                # KI Antwort holen
                res = model.generate_content(st.session_state.history + [{"role": "user", "parts": [user_part if audio else u_text]}])
                st.session_state.history.append({"role": "model", "parts": [res.text]})
                st.rerun()
            else:
                st.session_state.step = 2
                st.rerun()

elif st.session_state.step == 2: # ANALYSE
    st.balloons()
    st.header("🏁 Analyse deines Interviews")
    with st.spinner("Berechne Feedback..."):
        full_hist = "\n".join([p["parts"][0] for p in st.session_state.history if isinstance(p["parts"][0], str)])
        analysis = model.generate_content(f"Analysiere dieses Interview (Stärken/Schwächen): {full_hist}")
        st.markdown(analysis.text)
        
        btn_data = make_feedback_img(analysis.text)
        st.download_button("🖼️ Ergebnis als Bild speichern", btn_data, "feedback.png", "image/png")

else: # STARTSEITE
    st.info("Willkommen! Lade links deine PDFs hoch, um das Training zu starten.")
