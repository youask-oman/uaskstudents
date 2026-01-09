from pix2text import Pix2Text
import os
import logging

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        self._p2t = None

    @property
    def p2t(self):
        if self._p2t is None:
            # Lazy load the model to avoid startup overhead
            # languages=['en', 'zh'] by default, can configure as needed
            logger.info("Initializing Pix2Text model...")
            self._p2t = Pix2Text.from_config()
            logger.info("Pix2Text Initialized.")
        return self._p2t

    def process_image_sync(self, image_path: str) -> str:
        """
        Synchronous OCR processing using Pix2Text.
        To be called from Celery worker.
        """
        try:
            # check if file exists
            if not os.path.exists(image_path):
                return f"Error: File not found at {image_path}"
            
            # recognize_page returns markdown
            # Depending on p2t version, it might return a dict or string.
            # examples suggest recognize_page returns a specific object or markdown.
            # Using recognize_page which seems to be the high level API for mixed content.
            
            result = self.p2t.recognize_page(image_path)
            
            if hasattr(result, 'to_markdown'):
                return result.to_markdown("ocr_output")
            return str(result)
            
        except Exception as e:
            logger.error(f"OCR Error: {e}")
            raise e

    async def process_image(self, image_path: str) -> str:
        """
        Async wrapper. Note: Pix2Text is CPU/GPU bound, 
        so calling this directly in async loop might block.
        Prefer using the Celery worker via process_image_sync.
        """
        # For simple dev/testing without worker:
        return self.process_image_sync(image_path)

ocr_service = OCRService()
