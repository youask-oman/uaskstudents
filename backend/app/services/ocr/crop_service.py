import os
import hashlib
from PIL import Image
from sqlmodel import Session
from app.models import Crop, Upload

STORAGE_DIR = "storage/crops"

class CropService:
    def __init__(self, storage_dir: str = STORAGE_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    async def create_crop(self, upload: Upload, crop_rect: dict, rotation: int, margin_pct: int, session: Session) -> Crop:
        """
        crop_rect: {x, y, w, h} normalized 0..1
        """
        # Load original image; tolerate stale/moved relative paths.
        source_path = self._resolve_upload_path(upload.storage_url)
        if not source_path:
            raise FileNotFoundError(f"Upload file not found for upload_id={upload.id}: {upload.storage_url}")
        img = Image.open(source_path)
        width, height = img.size

        # Apply rotation to original image if needed
        if rotation:
            img = img.rotate(-rotation, expand=True)
            width, height = img.size

        # Convert normalized coordinates to pixel coordinates
        left = crop_rect['x'] * width
        top = crop_rect['y'] * height
        right = (crop_rect['x'] + crop_rect['w']) * width
        bottom = (crop_rect['y'] + crop_rect['h']) * height

        # Apply margin
        margin_x = (right - left) * (margin_pct / 100)
        margin_y = (bottom - top) * (margin_pct / 100)
        
        left = max(0, left - margin_x)
        top = max(0, top - margin_y)
        right = min(width, right + margin_x)
        bottom = min(height, bottom + margin_y)

        # Crop
        cropped_img = img.crop((left, top, right, bottom))
        
        # Compute crop hash (of the content)
        import io
        img_byte_arr = io.BytesIO()
        cropped_img.save(img_byte_arr, format='PNG')
        content = img_byte_arr.getvalue()
        crop_hash = hashlib.sha256(content).hexdigest()

        # Check deduplication
        from sqlmodel import select
        existing = session.exec(select(Crop).where(Crop.crop_image_hash == crop_hash)).first()
        if existing:
            return existing

        # Save cropped image
        filename = f"crop_{crop_hash[:16]}.png"
        file_path = os.path.join(self.storage_dir, filename)
        cropped_img.save(file_path, "PNG")

        # Create DB record
        new_crop = Crop(
            upload_id=upload.id,
            crop_rect=crop_rect,
            rotation=rotation,
            margin_pct=margin_pct,
            crop_image_hash=crop_hash,
            cropped_storage_url=file_path
        )
        session.add(new_crop)
        session.commit()
        session.refresh(new_crop)
        
        return new_crop

    @staticmethod
    def _resolve_upload_path(storage_url: str | None) -> str | None:
        if not storage_url:
            return None
        candidate = os.path.normpath(storage_url)
        if os.path.exists(candidate):
            return candidate
        # Fallback if app cwd differs (e.g., backend/ vs repo root).
        backend_relative = os.path.normpath(os.path.join("backend", storage_url))
        if os.path.exists(backend_relative):
            return backend_relative
        return None

crop_service = CropService()
