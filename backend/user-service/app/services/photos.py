"""Profile photo storage: JPEG or PNG up to 5 MB, saved as <media_root>/profiles/<role>s/<id>.<ext>."""
from pathlib import Path

from app.config import settings
from shared.errors import AppError

MAX_BYTES = 5 * 1024 * 1024
TYPES = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png"}
MAGIC = {"jpg": b"\xff\xd8\xff", "png": b"\x89PNG\r\n\x1a\n"}


def media_root() -> Path:
    return Path(settings.media_root).resolve()


def save_profile_photo(role: str, user_id: int, content_type: str | None, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise AppError(413, "FILE_TOO_LARGE", "Photo must be 5 MB or smaller.")
    ext = TYPES.get((content_type or "").lower())
    if ext is None:
        raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", "Photo must be a JPEG or PNG image.")
    if not data.startswith(MAGIC[ext]):
        raise AppError(422, "INVALID_IMAGE", "The file is not a valid image.")
    folder = media_root() / "profiles" / f"{role}s"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob(f"{user_id}.*"):
        old.unlink(missing_ok=True)
    (folder / f"{user_id}.{ext}").write_bytes(data)
    return f"/media/profiles/{role}s/{user_id}.{ext}"
