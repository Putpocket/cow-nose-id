import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    db_host: str = os.getenv("DB_HOST", "").strip()
    db_name: str = os.getenv("DB_NAME", "").strip()
    db_user: str = os.getenv("DB_USER", "").strip()
    db_password: str = os.getenv("DB_PASSWORD", "").strip()
    db_port: str = os.getenv("DB_PORT", "5432").strip()

    secret_key: str = os.getenv("SECRET_KEY", "change-me")

    upload_dir: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "8"))
    allowed_image_extensions: str = os.getenv("ALLOWED_IMAGE_EXTENSIONS", "jpg,jpeg,png,webp")
    upload_file_mode: str = os.getenv("UPLOAD_FILE_MODE", "0o640")

    password_min_length: int = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    login_max_attempts: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    login_lockout_seconds: int = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))

    session_lifetime_minutes: int = int(os.getenv("SESSION_LIFETIME_MINUTES", "60"))
    session_cookie_secure: bool = env_bool("SESSION_COOKIE_SECURE")
    session_cookie_httponly: bool = env_bool("SESSION_COOKIE_HTTPONLY", "true")
    session_cookie_samesite: str = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    log_file: str = os.getenv("LOG_FILE", "./data/logs/app.log")
    backup_dir: str = os.getenv("BACKUP_DIR", "./data/backups")
    backup_enabled: bool = env_bool("BACKUP_ENABLED", "true")
    backup_interval_seconds: int = int(os.getenv("BACKUP_INTERVAL_SECONDS", "86400"))

    content_security_policy: str = os.getenv(
        "CONTENT_SECURITY_POLICY",
        "default-src 'self'; img-src 'self' blob: data:; script-src 'self'; "
        "style-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
    )
    referrer_policy: str = os.getenv("REFERRER_POLICY", "same-origin")


settings = Settings()
