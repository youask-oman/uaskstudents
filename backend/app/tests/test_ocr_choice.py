import sys
import os
import asyncio
import io
from PIL import Image

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_pix2text_extract():
    print("Testing Pix2Text extraction helper...")
    from app.api import _call_extract_questions
    
    # Create a small dummy image for testing
    img = Image.new('RGB', (100, 30), color = (255, 255, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    image_bytes = img_byte_arr.getvalue()
    
    try:
        # Note: This requires Pix2Text to be installed/available on the system
        # If it's not, it will raise an ImportError or fail inside.
        # We can at least check if the logic flow handles it.
        result = await _call_extract_questions(image_bytes, 1000, engine_choice="pix2text")
        print("Result keys:", result.keys())
        if "payload" in result:
            payload = result["payload"]
            print("Payload OK:", payload.get("ok"))
            print("Notes:", payload.get("notes"))
            print("Questions count:", len(payload.get("questions", [])))
            if payload.get("questions"):
                print("First question text:", payload["questions"][0].get("text"))
    except Exception as e:
        print(f"Error during Pix2Text test: {e}")

if __name__ == "__main__":
    asyncio.run(test_pix2text_extract())
