from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/cow_nose_id"
    faiss_index_path: str = "./data/cow_nose.faiss"
    faiss_ids_path: str = "./data/cow_ids.json"
    yolo_weights_path: str = "./models/yolov8m-cow-nose.pt"
    yolo_conf_threshold: float = 0.25
    dino_model_name: str = "facebook/dinov2-base"
    device: str = "cpu"
    similarity_threshold: float = 0.72
    secret_key: str = "change-me"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 8
    max_image_pixels: int = 20_000_000
    rate_limit_enabled: bool = True
    rate_limit_storage_uri: str = "memory://"
    login_rate_limit: str = "5 per minute"
    upload_rate_limit: str = "20 per hour"
    admin_action_rate_limit: str = "30 per hour"
    registration_min_images: int = 3
    registration_max_images: int = 10
    allowed_image_extensions: str = "jpg,jpeg,png,webp"
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin"
    backup_enabled: bool = True
    backup_dir: str = "./data/backups"
    backup_interval_seconds: int = 86400
    log_file: str = "./data/logs/app.log"
    error_log_file: str = "./data/logs/error.log"
    log_level: str = "INFO"
    auto_rebuild_index: bool = True
    password_min_length: int = 8
    login_max_attempts: int = 5
    login_lockout_seconds: int = 900
    session_lifetime_minutes: int = 60
    session_cookie_secure: bool = False
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "Lax"
    content_security_policy: str = "default-src 'self'; img-src 'self' blob: data:; script-src 'self'; style-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    referrer_policy: str = "same-origin"
    upload_file_mode: str = "0o640"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
