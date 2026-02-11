import os
import hashlib
import uuid

import pytest
from sqlmodel import Session

from app.services.ocr.upload_service import UploadService
from app.models import Upload, User
from app.auth import get_password_hash


@pytest.mark.asyncio
async def test_save_upload_replaces_stale_existing_record(tmp_path, session: Session):
    service = UploadService(storage_dir=str(tmp_path / "uploads"))
    os.makedirs(service.storage_dir, exist_ok=True)
    user = User(
        email=f"stale-upload-test-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Stale Upload Test",
        password_hash=get_password_hash("password123"),
        role="student",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    payload = b"\x89PNG\r\n\x1a\nfake"
    stale = Upload(
        user_id=user.id,
        storage_url=str(tmp_path / "missing" / "stale.png"),
        file_hash=hashlib.sha256(payload).hexdigest(),
        content_type="image/png",
    )
    session.add(stale)
    session.commit()

    class FakeUploadFile:
        filename = "img.png"
        content_type = "image/png"

        def __init__(self, content: bytes):
            self._content = content

        async def read(self):
            return self._content

    file_obj = FakeUploadFile(payload)
    created = await service.save_upload(user_id=user.id, file=file_obj, session=session)

    assert created.id is not None
    assert os.path.exists(created.storage_url)
    # stale row should have been replaced
    assert session.get(Upload, stale.id) is None
