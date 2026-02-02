
import os
import sys
import logging
import tempfile
from PIL import Image, ImageDraw

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_ocr")

print("Checking environment...")
try:
    import pix2text
    print(f"Pix2Text version: {pix2text.__version__}")
except ImportError:
    print("CRITICAL: Pix2Text not installed!")

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

try:
    from app.services.ocr.ocr_service import ocr_service
    print("OCRService imported successfully.")
except Exception as e:
    print(f"Failed to import OCRService: {e}")
    sys.exit(1)

def test_ocr():
    print("\n--- Starting OCR Test ---")
    
    # 1. Create a dummy image
    img = Image.new('RGB', (300, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "x^2 + y^2 = 100", fill=(0, 0, 0))
    d.text((10, 50), "Solve for x.", fill=(0, 0, 0))
    
    tmp_img = os.path.join(tempfile.gettempdir(), "test_ocr_input.png")
    img.save(tmp_img)
    print(f"Created test image at: {tmp_img}")

    # 2. Read bytes
    with open(tmp_img, "rb") as f:
        image_bytes = f.read()

    # 3. Call recognize_region
    print("Calling recognize_region...")
    try:
        result = ocr_service.recognize_region(image_bytes, engine_name="local")
        print("\n--- Result ---")
        print(result)
        
        if not result.get("text"):
            print("FAILURE: returned empty text.")
        else:
            print("SUCCESS: Text extracted.")
            
    except Exception as e:
        print(f"EXCEPTION during recognition: {e}")

if __name__ == "__main__":
    test_ocr()
