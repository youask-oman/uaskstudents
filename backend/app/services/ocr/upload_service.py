import os
import hashlib
import aiofiles
from datetime import datetime
from fastapi import UploadFile
from sqlmodel import Session
from app.models import Upload

STORAGE_DIR = "storage/uploads"

class UploadService:
    def __init__(self, storage_dir: str = STORAGE_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    async def save_upload(self, user_id: int, file: UploadFile, session: Session) -> Upload:
        # Read file content for hashing
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check for existing upload with same hash
        from sqlmodel import select
        existing = session.exec(select(Upload).where(Upload.file_hash == file_hash, Upload.user_id == user_id)).first()
        if existing:
            return existing

        # Generate unique filename
        ext = os.path.splitext(file.filename)[1] or ".png"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{user_id}_{timestamp}_{file_hash[:8]}{ext}"
        file_path = os.path.join(self.storage_dir, filename)

        # Save to disk
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create DB record
        new_upload = Upload(
            user_id=user_id,
            storage_url=file_path,
            file_hash=file_hash,
            content_type=file.content_type or "image/png"
        )
        session.add(new_upload)
        session.commit()
        session.refresh(new_upload)
        
        return new_upload

upload_service = UploadService()
