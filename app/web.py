import logging
from datetime import timedelta
from pathlib import Path

from flask import Flask, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

# pipeline import
from app.config import settings
from app.db import add_audit_log
from app.security import safe_log_value, save_secure_upload
from app.services.pipeline import process_image


def create_app():
    app = Flask(__name__)
    app.secret_key = settings.secret_key
    app.permanent_session_lifetime = timedelta(minutes=settings.session_lifetime_minutes)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_mb * 1024 * 1024
    app.config["SESSION_COOKIE_SECURE"] = settings.session_cookie_secure
    app.config["SESSION_COOKIE_HTTPONLY"] = settings.session_cookie_httponly
    app.config["SESSION_COOKIE_SAMESITE"] = settings.session_cookie_samesite
    configure_logging(app)

    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = settings.content_security_policy
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = settings.referrer_policy
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        return response

    # =========================
    # health check API
    # =========================
    @app.route("/health")
    def health():
        return {"status": "ok"}

    # =========================
    # 이미지 업로드 API
    # =========================
    @app.route("/upload", methods=["POST"])
    def upload():
        try:
            file = request.files.get("file")
            file_path = save_secure_upload(file)
            add_audit_log(
                action="upload_received",
                ip_address=safe_log_value(request.headers.get("X-Forwarded-For", request.remote_addr), 128),
                user_agent=safe_log_value(request.headers.get("User-Agent"), 256),
                detail="secure upload accepted",
            )
            result = process_image(file_path)
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("Upload processing failed.")
            return jsonify({"error": "Server error occurred."}), 500

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        return jsonify({"error": "Uploaded file is too large."}), 413

    return app


def configure_logging(app: Flask) -> None:
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)
