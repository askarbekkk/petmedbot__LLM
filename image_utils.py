import os
from PIL import Image
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploaded_images")

def save_uploaded_image(uploaded_file):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{timestamp}_{uploaded_file.name}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return save_path

def analyze_image(image_path):
    try:
        image = Image.open(image_path)
        return {
            "format": image.format,
            "mode": image.mode,
            "size": image.size,
            "path": image_path
        }
    except Exception as e:
        return {"error": str(e), "path": image_path}
