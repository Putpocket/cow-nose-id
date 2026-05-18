from __future__ import annotations

from urllib.parse import urlparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from app.config import get_settings
    from app.db import Database
    from app.services.detector import NoseDetector
    from app.services.embedder import DinoEmbedder

    settings = get_settings()
    errors = []
    warnings = []

    if settings.secret_key in {"change-me", "change-this-to-a-random-secret"}:
        errors.append("SECRET_KEY를 운영용 랜덤 값으로 바꿔야 합니다.")
    if settings.log_level.upper() == "DEBUG":
        warnings.append("LOG_LEVEL=DEBUG는 운영에서 사용하지 않는 것이 좋습니다.")
    if not settings.rate_limit_enabled:
        errors.append("RATE_LIMIT_ENABLED=true로 요청 제한을 활성화해야 합니다.")
    if settings.rate_limit_storage_uri == "memory://":
        warnings.append("운영 다중 프로세스/다중 서버 환경에서는 RATE_LIMIT_STORAGE_URI를 Redis 등 공유 저장소로 바꾸는 것이 좋습니다.")

    database_url = urlparse(settings.database_url)
    if database_url.username in {"postgres", "root"}:
        warnings.append("DATABASE_URL은 postgres/root 같은 슈퍼유저 대신 앱 전용 DB 계정을 사용해야 합니다.")

    weights_path = Path(settings.yolo_weights_path)
    if not weights_path.exists():
        errors.append(f"YOLO_WEIGHTS_PATH 파일을 찾을 수 없습니다: {weights_path}")

    if settings.registration_min_images < 1:
        errors.append("REGISTRATION_MIN_IMAGES는 1 이상이어야 합니다.")
    if settings.registration_max_images < settings.registration_min_images:
        errors.append("REGISTRATION_MAX_IMAGES는 REGISTRATION_MIN_IMAGES 이상이어야 합니다.")
    if settings.max_request_mb < settings.max_upload_mb * settings.registration_max_images:
        warnings.append("MAX_REQUEST_MB가 등록 최대 이미지 수와 개별 파일 제한을 감당하기에 작습니다.")
    if settings.proxy_fix_enabled:
        warnings.append("PROXY_FIX_ENABLED=true일 때는 신뢰할 수 있는 프록시만 X-Forwarded-* 헤더를 전달하도록 제한해야 합니다.")
    if not Path(settings.upload_dir).is_absolute():
        warnings.append("UPLOAD_DIR은 운영에서 앱 루트 밖 절대 경로를 권장합니다. 예: /var/lib/cow-muzzle/uploads")
    if not Path(settings.backup_dir).is_absolute():
        warnings.append("BACKUP_DIR은 운영에서 앱 루트 밖 절대 경로를 권장합니다. 예: /var/backups/cow-muzzle")

    try:
        database = Database(settings)
        database.open()
        database.ensure_schema()
        database.ensure_security_schema()
        database.close()
    except Exception as exc:
        errors.append(f"DB 연결 또는 스키마 확인 실패: {exc}")

    if weights_path.exists():
        try:
            NoseDetector(settings.yolo_weights_path, settings.device, settings.yolo_conf_threshold)
        except Exception as exc:
            errors.append(f"YOLO 모델 로드 실패: {exc}")

    try:
        DinoEmbedder(settings.dino_model_name, settings.device)
    except Exception as exc:
        errors.append(f"Embedding 모델 로드 실패({settings.dino_model_name}): {exc}")

    if errors:
        print("Runtime check failed:")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("Runtime check warnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print("Runtime check passed.")
    if warnings:
        print("Runtime check warnings:")
        for warning in warnings:
            print(f"- {warning}")
    print(f"- YOLO: {settings.yolo_weights_path}")
    print(f"- Embedding: {settings.dino_model_name}")
    print(f"- Device: {settings.device}")
    print(f"- Registration images: {settings.registration_min_images}~{settings.registration_max_images}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
