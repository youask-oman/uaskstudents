import os
import hashlib
import uuid

import pytest
from PIL import Image
from sqlmodel import Session

from app.services.ocr.crop_service import CropService
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
    stale_id = stale.id
    created = await service.save_upload(user_id=user.id, file=file_obj, session=session)

    assert created.id is not None
    assert os.path.exists(created.storage_url)
    # stale row should be refreshed in-place to preserve FK relationships.
    assert created.id == stale_id
    assert session.get(Upload, stale_id) is not None


@pytest.mark.asyncio
async def test_create_crop_rebuilds_stale_deduped_crop_file(tmp_path, session: Session):
    uploads_dir = tmp_path / "uploads"
    crops_dir = tmp_path / "crops"
    upload_service = UploadService(storage_dir=str(uploads_dir))
    crop_service = CropService(storage_dir=str(crops_dir))
    os.makedirs(uploads_dir, exist_ok=True)
    os.makedirs(crops_dir, exist_ok=True)

    user = User(
        email=f"stale-crop-test-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Stale Crop Test",
        password_hash=get_password_hash("password123"),
        role="student",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    source_path = uploads_dir / "source.png"
    Image.new("RGB", (20, 20), color="white").save(source_path)

    class FakeUploadFile:
        filename = "source.png"
        content_type = "image/png"

        def __init__(self, content: bytes):
            self._content = content

        async def read(self):
            return self._content

    upload = await upload_service.save_upload(
        user_id=user.id,
        file=FakeUploadFile(source_path.read_bytes()),
        session=session,
    )

    crop_1 = await crop_service.create_crop(
        upload=upload,
        crop_rect={"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
        rotation=0,
        margin_pct=0,
        session=session,
    )
    assert os.path.exists(crop_1.cropped_storage_url)
    os.remove(crop_1.cropped_storage_url)
    assert not os.path.exists(crop_1.cropped_storage_url)

    crop_2 = await crop_service.create_crop(
        upload=upload,
        crop_rect={"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
        rotation=0,
        margin_pct=0,
        session=session,
    )
    assert crop_2.id == crop_1.id
    assert os.path.exists(crop_2.cropped_storage_url)
