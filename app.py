from PIL import Image, ImageDraw, ImageFont
import io

def create_feedback_image(text):
    # Wir erstellen ein Bild mit 800x1000 Pixeln und blauem Farbverlauf-Stil
    img = Image.new('RGB', (800, 1000), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    
    # Header zeichnen
    d.rectangle([0, 0, 800, 100], fill=(0, 104, 201))
    d.text((40, 30), "Mein Interview-Feedback", fill=(255, 255, 255))
    
    # Text-Wrapping (ganz simpel)
    lines = text.split('\n')
    y_text = 150
    for line in lines:
        # Wir zeichnen jede Zeile einzeln (Pillow kann standardmäßig kein Auto-Wrap)
        if len(line) > 70: # Zeile zu lang? Kürzen für das Bild
            line = line[:67] + "..."
        d.text((40, y_text), line, fill=(50, 50, 50))
        y_text += 25
        if y_text > 950: break # Bildende erreicht
            
    # In einen Byte-Stream speichern, damit Streamlit es zum Download anbieten kann
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    byte_im = buf.getvalue()
    return byte_im
