import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app.config import settings


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def validate_password_policy(password: str) -> None:
    if len(password) < settings.password_min_length:
        raise ValueError(f"Password must be at least {settings.password_min_length} characters.")
    if not any(character.isalpha() for character in password):
        raise ValueError("Password must contain at least one letter.")
    if not any(character.isdigit() for character in password):
        raise ValueError("Password must contain at least one number.")


def allowed_file(filename: str) -> bool:
    suffix = Path(filename).suffix.lower().lstrip(".")
    allowed = {value.strip().lower() for value in settings.allowed_image_extensions.split(",")}
    return suffix in allowed


def verify_image_bytes(image_bytes: bytes) -> None:
    try:
        Image.open(BytesIO(image_bytes)).verify()
    except Exception as exc:
        raise ValueError("Uploaded file is not a valid image.") from exc


def save_secure_upload(uploaded: FileStorage | None) -> str:
    if uploaded is None or uploaded.filename == "":
        raise ValueError("No file uploaded.")
    if not allowed_file(uploaded.filename):
        raise ValueError("Image extension is not allowed.")
    if uploaded.mimetype is None or not uploaded.mimetype.startswith("image/"):
        raise ValueError("Only image files are allowed.")

    image_bytes = uploaded.read()
    verify_image_bytes(image_bytes)

    upload_dir = Path(settings.upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(upload_dir, 0o750)

    original_name = secure_filename(uploaded.filename) or "image"
    target = (upload_dir / f"{uuid4().hex}-{original_name}").resolve()
    if upload_dir not in target.parents:
        raise ValueError("Invalid upload path.")

    target.write_bytes(image_bytes)
    os.chmod(target, int(settings.upload_file_mode, 8))
    return str(target)


def safe_log_value(value: str | None, max_length: int = 500) -> str | None:
    if value is None:
        return None
    cleaned = "".join(character if character.isprintable() else " " for character in str(value))
    return cleaned[:max_length]
