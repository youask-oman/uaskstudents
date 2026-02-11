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
        # 1. Validate File Size (10MB limit)
        MAX_SIZE = 10 * 1024 * 1024 # 10MB
        content = await file.read()
        if len(content) > MAX_SIZE:
            from fastapi import HTTPException
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")
        
        # 2. Validate Extension
        ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf', '.webp'}
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".png"
        if ext not in ALLOWED_EXTENSIONS:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {list(ALLOWED_EXTENSIONS)}")

        # Read file content for hashing
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check for existing upload with same hash
        from sqlmodel import select
        existing = session.exec(select(Upload).where(Upload.file_hash == file_hash, Upload.user_id == user_id)).first()
        if existing:
            # Stale row can exist if file was removed on disk; refresh it by re-saving.
            if existing.storage_url and os.path.exists(existing.storage_url):
                return existing
            ext_existing = os.path.splitext(file.filename)[1] or ".png"
            timestamp_existing = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            refreshed_filename = f"{user_id}_{timestamp_existing}_{file_hash[:8]}{ext_existing}"
            refreshed_path = os.path.join(self.storage_dir, refreshed_filename)
            async with aiofiles.open(refreshed_path, "wb") as f:
                await f.write(content)
            # Keep same Upload row to avoid FK issues with existing Crop children.
            existing.storage_url = refreshed_path
            existing.content_type = file.content_type or existing.content_type or "image/png"
            session.add(existing)
            session.commit()
            session.refresh(existing)
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
