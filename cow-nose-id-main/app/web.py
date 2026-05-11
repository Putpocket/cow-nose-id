import logging
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge

# pipeline import
from app.config import settings
from app.db import add_audit_log
from app.security import safe_log_value, save_secure_upload
from app.services.pipeline import process_image


def create_app():
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.secret_key = settings.secret_key
    app.permanent_session_lifetime = timedelta(minutes=settings.session_lifetime_minutes)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_mb * 1024 * 1024
    app.config["SESSION_COOKIE_SECURE"] = settings.session_cookie_secure
    app.config["SESSION_COOKIE_HTTPONLY"] = settings.session_cookie_httponly
    app.config["SESSION_COOKIE_SAMESITE"] = settings.session_cookie_samesite
    app.config["UPLOAD_DIR"] = settings.upload_dir
    configure_logging(app)
    register_blueprints(app)

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

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/")
    def index_page():
        return render_template("index.html")

    @app.route("/admin")
    def admin_page():
        if not session.get("user_id"):
            return redirect(url_for("login_page"))
        if session.get("role") not in ("admin", "super"):
            return render_template("block.html"), 403
        return render_template("admin.html")

    @app.route("/block")
    def block_page():
        return render_template("block.html"), 403

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


def register_blueprints(app: Flask) -> None:
    from app.api.admin import admin_bp
    from app.api.auth import auth_bp
    from app.api.identify import identify_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(identify_bp)
    app.register_blueprint(admin_bp)


def configure_logging(app: Flask) -> None:
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)
