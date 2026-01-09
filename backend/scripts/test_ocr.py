import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ocr import ocr_service

def main():
    # Default to a test image if provided, otherwise check specific paths
    image_path = "tests/sample_math.png"
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    
    print(f"Testing OCR on {image_path}...")
    
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        print("Please provide an absolute path to an image file.")
        return

    try:
        print("Initializing OCR Service (this may take time to download models)...")
        result = ocr_service.process_image_sync(image_path)
        print("\n--- OCR Result ---")
        print(result)
        print("------------------")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
