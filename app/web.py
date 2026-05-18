from __future__ import annotations

import atexit
import logging
import os
import secrets
import threading
from datetime import datetime, timedelta
from io import BytesIO
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from app.backup import run_backup, start_backup_scheduler
from app.config import get_settings
from app.db import Database
from app.indexing import rebuild_faiss_index
from app.services.pipeline import IdentificationPipeline


settings = get_settings()
Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
database = Database(settings)
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.rate_limit_storage_uri)
pipeline: IdentificationPipeline | None = None
pipeline_lock = threading.Lock()
backup_lock = threading.Lock()
backup_status = {
    "state": "idle",
    "message": "대기 중",
    "updated_at": None,
}
index_rebuild_lock = threading.Lock()
index_rebuild_status = {
    "state": "idle",
    "message": "대기 중",
    "updated_at": None,
    "pending": False,
}
atexit.register(database.close)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    if settings.proxy_fix_enabled:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=settings.proxy_fix_x_for,
            x_proto=settings.proxy_fix_x_proto,
            x_host=settings.proxy_fix_x_host,
            x_port=settings.proxy_fix_x_port,
            x_prefix=settings.proxy_fix_x_prefix,
        )
    app.secret_key = settings.secret_key
    app.permanent_session_lifetime = timedelta(minutes=settings.session_lifetime_minutes)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_request_mb * 1024 * 1024
    app.config["SESSION_COOKIE_SECURE"] = settings.session_cookie_secure
    app.config["SESSION_COOKIE_HTTPONLY"] = settings.session_cookie_httponly
    app.config["SESSION_COOKIE_SAMESITE"] = settings.session_cookie_samesite
    app.config["RATELIMIT_ENABLED"] = settings.rate_limit_enabled
    app.config["BOOTSTRAPPED_ADMIN"] = False
    configure_logging(app)
    limiter.init_app(app)
    initialize_database(app)
    start_backup_scheduler(settings, app.logger)

    @app.context_processor
    def inject_security_helpers():
        return {"csrf_token": csrf_token}

    @app.before_request
    def prepare_request() -> None:
        validate_csrf()

    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = settings.content_security_policy
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = settings.referrer_policy
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        return response

    @app.get("/")
    @login_required
    def index():
        return render_template("index.html", result=None, error=None, current_user=current_user())

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/csrf")
    def api_csrf():
        return jsonify({"csrf_token": csrf_token()})

    @app.get("/api/me")
    @api_login_required
    def api_me():
        return jsonify({"user": serialize_user(current_user()), "csrf_token": csrf_token()})

    @app.get("/login")
    def login_page():
        if current_user() is not None:
            return redirect(url_for("index"))
        return render_template("login.html", error=None)

    @app.post("/login")
    @limiter.limit(lambda: settings.login_rate_limit)
    def login():
        try:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            login_user = database.get_login_user(username)
            if login_user is None:
                audit("login_failed", target_type="user", target_id=username, detail="unknown user")
                return render_template("login.html", error="아이디 또는 비밀번호가 올바르지 않습니다."), 400
            if login_user["status"] != "active":
                audit("login_blocked", target_type="user", target_id=username, detail="disabled account")
                return render_template("login.html", error="비활성화된 계정입니다."), 403
            if is_user_locked(login_user):
                audit("login_blocked", target_type="user", target_id=username, detail="locked account")
                return render_template("login.html", error="로그인 실패가 많아 잠시 잠겼습니다."), 429
            user = database.authenticate_user(username, password)
            if user is None:
                locked = database.record_login_failure(username, settings.login_max_attempts, settings.login_lockout_seconds)
                audit("login_failed", target_type="user", target_id=username, detail="locked" if locked else "bad password")
                return render_template("login.html", error="아이디 또는 비밀번호가 올바르지 않습니다."), 400
            database.clear_login_failures(user["id"])
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            csrf_token()
            audit("login_success", actor=user, target_type="user", target_id=str(user["id"]))
            if user["must_change_password"]:
                return redirect(url_for("change_password_page"))
            return redirect(url_for("index"))
        except Exception:
            app.logger.exception("Login failed with an unexpected error.")
            return render_template("login.html", error="로그인 처리 중 오류가 발생했습니다."), 500

    @app.post("/logout")
    def logout():
        audit("logout")
        session.clear()
        return redirect(url_for("login_page"))

    @app.get("/change-password")
    @login_required
    def change_password_page():
        return render_template("change_password.html", error=None, current_user=current_user())

    @app.post("/change-password")
    @login_required
    def change_password():
        try:
            user = current_user()
            current_password = required_form_value("current_password")
            new_password = required_form_value("new_password")
            validate_password_policy(new_password)
            database.change_own_password(user["id"], current_password, new_password)
            audit("password_changed", target_type="user", target_id=str(user["id"]))
            return redirect(url_for("index"))
        except ValueError as exc:
            return render_template("change_password.html", error=str(exc), current_user=current_user()), 400
        except Exception:
            app.logger.exception("Password change failed.")
            return render_template(
                "change_password.html",
                error="비밀번호 변경 중 서버 오류가 발생했습니다.",
                current_user=current_user(),
            ), 500

    @app.post("/identify")
    @login_required
    @limiter.limit(lambda: settings.upload_rate_limit)
    def identify_page():
        try:
            result = identify_uploaded_file()
            return render_template(
                "index.html",
                result=result.model_dump(),
                error=None,
                current_user=current_user(),
            )
        except ValueError as exc:
            return render_template(
                "index.html",
                result=None,
                error=str(exc),
                current_user=current_user(),
            ), 400
        except FileNotFoundError:
            app.logger.exception("Identify page is not ready because a required model or index file is missing.")
            return render_template(
                "index.html",
                result=None,
                error="식별에 필요한 모델 또는 FAISS 인덱스 파일이 없습니다. 관리자에게 문의하세요.",
                current_user=current_user(),
            ), 503
        except Exception:
            app.logger.exception("Identify page request failed.")
            return render_template(
                "index.html",
                result=None,
                error="식별 처리 중 서버 오류가 발생했습니다.",
                current_user=current_user(),
            ), 500

    @app.post("/api/auth/login")
    @limiter.limit(lambda: settings.login_rate_limit)
    def api_login():
        try:
            username = json_or_form_value("username", required=True)
            password = json_or_form_value("password", required=True)
            login_user = database.get_login_user(username)
            if login_user is None:
                audit("login_failed", target_type="user", target_id=username, detail="unknown user")
                return json_error("아이디 또는 비밀번호가 올바르지 않습니다.", 400)
            if login_user["status"] != "active":
                audit("login_blocked", target_type="user", target_id=username, detail="disabled account")
                return json_error("비활성화된 계정입니다.", 403)
            if is_user_locked(login_user):
                audit("login_blocked", target_type="user", target_id=username, detail="locked account")
                return json_error("로그인 실패가 많아 잠시 잠겼습니다.", 429)
            user = database.authenticate_user(username, password)
            if user is None:
                locked = database.record_login_failure(username, settings.login_max_attempts, settings.login_lockout_seconds)
                audit("login_failed", target_type="user", target_id=username, detail="locked" if locked else "bad password")
                return json_error("아이디 또는 비밀번호가 올바르지 않습니다.", 400)
            database.clear_login_failures(user["id"])
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            csrf = csrf_token()
            audit("login_success", actor=user, target_type="user", target_id=str(user["id"]))
            return jsonify({
                "user": serialize_user(database.get_user(user["id"])),
                "must_change_password": bool(user["must_change_password"]),
                "csrf_token": csrf,
            })
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception:
            app.logger.exception("Login API failed with an unexpected error.")
            return json_error("로그인 처리 중 오류가 발생했습니다.", 500)

    @app.post("/api/auth/logout")
    @api_login_required
    def api_logout():
        audit("logout")
        session.clear()
        return jsonify({"success": True})

    @app.post("/api/auth/change-password")
    @api_login_required
    def api_change_password():
        try:
            user = current_user()
            current_password = json_or_form_value("current_password", required=True)
            new_password = json_or_form_value("new_password", required=True)
            validate_password_policy(new_password)
            database.change_own_password(user["id"], current_password, new_password)
            audit("password_changed", target_type="user", target_id=str(user["id"]))
            return jsonify({"success": True})
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception:
            app.logger.exception("Password change API failed.")
            return json_error("비밀번호 변경 중 서버 오류가 발생했습니다.", 500)

    @app.post("/api/identify")
    @api_login_required
    @limiter.limit(lambda: settings.upload_rate_limit)
    def identify_api():
        try:
            result = identify_uploaded_file()
            return jsonify(result.model_dump())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except FileNotFoundError:
            app.logger.exception("Identify API is not ready because a required model or index file is missing.")
            return jsonify({"error": "식별에 필요한 모델 또는 FAISS 인덱스 파일이 없습니다."}), 503
        except Exception:
            app.logger.exception("Identify API request failed.")
            return jsonify({"error": "식별 처리 중 서버 오류가 발생했습니다."}), 500

    @app.get("/api/admin/users")
    @api_admin_required
    def api_list_users():
        return jsonify({"users": database.list_users()})

    @app.post("/api/admin/users")
    @api_admin_required
    def api_create_user():
        try:
            username = json_or_form_value("username", required=True)
            password = json_or_form_value("password", required=True)
            role = json_or_form_value("role", default="user")
            validate_password_policy(password)
            if role not in {"admin", "user"}:
                raise ValueError("권한 값이 올바르지 않습니다.")
            user_id = database.create_user(username, password, role)
            audit("user_created", target_type="user", target_id=str(user_id), detail=f"role={role}")
            return jsonify({"id": user_id, "success": True}), 201
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception:
            app.logger.exception("User creation API failed.")
            return json_error("계정 추가 처리 중 서버 오류가 발생했습니다.", 500)

    @app.patch("/api/admin/users/<int:user_id>")
    @api_admin_required
    def api_update_user(user_id: int):
        try:
            status = json_or_form_value("status", default=None)
            password = json_or_form_value("password", default=None)
            if status is None and password is None:
                raise ValueError("변경할 항목이 없습니다.")
            if password:
                validate_password_policy(password)
                database.update_user_password(user_id, password, force_change=True)
                audit("user_password_reset", target_type="user", target_id=str(user_id))
            if status:
                if status == "active":
                    database.enable_user(user_id)
                    audit("user_enabled", target_type="user", target_id=str(user_id))
                elif status == "disabled":
                    current = current_user()
                    database.disable_user(user_id, current["id"] if current else None)
                    audit("user_disabled", target_type="user", target_id=str(user_id))
                else:
                    raise ValueError("상태 값이 올바르지 않습니다.")
            return jsonify({"success": True})
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception:
            app.logger.exception("User update API failed.")
            return json_error("계정 변경 중 서버 오류가 발생했습니다.", 500)

    @app.delete("/api/admin/users/<int:user_id>")
    @api_admin_required
    def api_delete_user(user_id: int):
        try:
            current = current_user()
            database.disable_user(user_id, current["id"] if current else None)
            audit("user_disabled", target_type="user", target_id=str(user_id))
            return jsonify({"success": True})
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception:
            app.logger.exception("User deletion API failed.")
            return json_error("계정 삭제 중 서버 오류가 발생했습니다.", 500)

    @app.get("/api/admin/cows")
    @api_admin_required
    def api_list_cows():
        return jsonify({"cows": database.list_cows()})

    @app.get("/api/admin/cows/<int:cow_id>")
    @api_admin_required
    def api_get_cow(cow_id: int):
        cow = database.get_cow_record(cow_id)
        if cow is None:
            return json_error("소 정보를 찾을 수 없습니다.", 404)
        return jsonify({"cow": serialize_cow_record(cow)})

    @app.post("/api/admin/cows")
    @api_admin_required
    @limiter.limit(lambda: settings.upload_rate_limit)
    def api_create_cow():
        image_paths = []
        try:
            image_paths = save_uploaded_images(get_registration_uploads(required=True))
            cow_id = database.create_cow_with_owner(
                owner_name=json_or_form_value("owner_name", required=True),
                owner_phone=json_or_form_value("owner_phone", default=None),
                farm_name=json_or_form_value("farm_name", default=None),
                farm_address=json_or_form_value("farm_address", default=None),
                ear_tag=json_or_form_value("ear_tag", required=True),
                cow_name=json_or_form_value("cow_name", default=None),
                breed=json_or_form_value("breed", default=None),
                sex=json_or_form_value("sex", default=None),
                birth_date=json_or_form_value("birth_date", default=None),
                notes=json_or_form_value("notes", default=None),
                image_paths=image_paths,
            )
            image_paths = []
            audit("cow_created", target_type="cow", target_id=str(cow_id))
            trigger_index_rebuild("소 등록")
            return jsonify({"id": cow_id, "success": True, "index_status": index_rebuild_status}), 201
        except ValueError as exc:
            remove_uploaded_files(image_paths)
            return json_error(str(exc), 400)
        except Exception:
            remove_uploaded_files(image_paths)
            app.logger.exception("Cow creation API failed.")
            return json_error("소 등록 처리 중 서버 오류가 발생했습니다.", 500)

    @app.patch("/api/admin/cows/<int:cow_id>")
    @api_admin_required
    @limiter.limit(lambda: settings.upload_rate_limit)
    def api_update_cow(cow_id: int):
        image_paths = []
        try:
            existing = database.get_cow_record(cow_id)
            if existing is None:
                raise ValueError("소 정보를 찾을 수 없습니다.")
            uploads = get_registration_uploads(required=False)
            if uploads:
                image_paths = save_uploaded_images(uploads)
            old_image_paths = database.update_cow_with_owner(
                cow_id=cow_id,
                owner_name=json_or_form_value("owner_name", default=existing["owner_name"]),
                owner_phone=json_or_form_value("owner_phone", default=existing["owner_phone"]),
                farm_name=json_or_form_value("farm_name", default=existing["farm_name"]),
                farm_address=json_or_form_value("farm_address", default=existing["farm_address"]),
                ear_tag=json_or_form_value("ear_tag", default=existing["ear_tag"]),
                cow_name=json_or_form_value("cow_name", default=existing["cow_name"]),
                breed=json_or_form_value("breed", default=existing["breed"]),
                sex=json_or_form_value("sex", default=existing["sex"]),
                birth_date=json_or_form_value("birth_date", default=existing["birth_date"]),
                notes=json_or_form_value("notes", default=existing["notes"]),
                image_paths=image_paths if uploads else None,
            )
            if uploads:
                image_paths = []
                remove_uploaded_files(old_image_paths)
            audit("cow_updated", target_type="cow", target_id=str(cow_id))
            trigger_index_rebuild("소 정보 수정")
            return jsonify({"success": True, "index_status": index_rebuild_status})
        except ValueError as exc:
            remove_uploaded_files(image_paths)
            return json_error(str(exc), 400)
        except Exception:
            remove_uploaded_files(image_paths)
            app.logger.exception("Cow update API failed.")
            return json_error("소 정보 수정 중 서버 오류가 발생했습니다.", 500)

    @app.delete("/api/admin/cows/<int:cow_id>")
    @api_admin_required
    def api_delete_cow(cow_id: int):
        try:
            image_paths = database.delete_cow(cow_id)
            remove_uploaded_files(image_paths)
            audit("cow_deleted", target_type="cow", target_id=str(cow_id))
            trigger_index_rebuild("소 삭제")
            return jsonify({"success": True, "index_status": index_rebuild_status})
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception:
            app.logger.exception("Cow deletion API failed.")
            return json_error("소 정보 삭제 중 서버 오류가 발생했습니다.", 500)

    @app.get("/api/admin/system")
    @api_admin_required
    def api_system():
        return jsonify({
            "logs": read_log_tail(),
            "audit_logs": database.list_audit_logs(),
            "backups": list_backup_files(),
            "backup_status": backup_status,
            "index_status": index_rebuild_status,
        })

    @app.post("/api/admin/backups/run")
    @api_admin_required
    @limiter.limit(lambda: settings.admin_action_rate_limit)
    def api_run_backup_now():
        started = trigger_manual_backup("API 수동 실행")
        audit("backup_requested", detail="started" if started else "already running")
        return jsonify({"success": True, "started": started, "backup_status": backup_status}), 202

    @app.post("/api/admin/index/rebuild")
    @api_admin_required
    @limiter.limit(lambda: settings.admin_action_rate_limit)
    def api_rebuild_index_now():
        trigger_index_rebuild("수동 실행")
        audit("index_rebuild_requested")
        return jsonify({"success": True, "index_status": index_rebuild_status})

    @app.get("/admin/cows/new")
    @admin_required
    def new_cow_page():
        return render_template("admin_cow_form.html", error=None, saved=False, current_user=current_user())

    @app.post("/admin/cows")
    @admin_required
    @limiter.limit(lambda: settings.upload_rate_limit)
    def create_cow():
        image_paths = []
        try:
            image_paths = save_uploaded_images(get_registration_uploads(required=True))
            cow_id = database.create_cow_with_owner(
                owner_name=required_form_value("owner_name"),
                owner_phone=optional_form_value("owner_phone"),
                farm_name=optional_form_value("farm_name"),
                farm_address=optional_form_value("farm_address"),
                ear_tag=required_form_value("ear_tag"),
                cow_name=optional_form_value("cow_name"),
                breed=optional_form_value("breed"),
                sex=optional_form_value("sex"),
                birth_date=optional_form_value("birth_date"),
                notes=optional_form_value("notes"),
                image_paths=image_paths,
            )
            image_paths = []
            audit("cow_created", target_type="cow", target_id=str(cow_id))
            trigger_index_rebuild("소 등록")
            return render_template("admin_cow_form.html", error=None, saved=True, current_user=current_user())
        except ValueError as exc:
            remove_uploaded_files(image_paths)
            return render_template(
                "admin_cow_form.html",
                error=str(exc),
                saved=False,
                current_user=current_user(),
            ), 400
        except Exception:
            remove_uploaded_files(image_paths)
            app.logger.exception("Cow creation failed.")
            return render_template(
                "admin_cow_form.html",
                error="소 등록 처리 중 서버 오류가 발생했습니다.",
                saved=False,
                current_user=current_user(),
            ), 500

    @app.get("/admin/users")
    @admin_required
    def users_page():
        return render_template(
            "admin_users.html",
            users=database.list_users(),
            error=None,
            saved=False,
            current_user=current_user(),
        )

    @app.post("/admin/users")
    @admin_required
    def create_user():
        try:
            username = required_form_value("username")
            password = required_form_value("password")
            validate_password_policy(password)
            role = request.form.get("role", "user")
            if role not in {"admin", "user"}:
                raise ValueError("권한 값이 올바르지 않습니다.")
            user_id = database.create_user(username, password, role)
            audit("user_created", target_type="user", target_id=str(user_id), detail=f"role={role}")
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error=None,
                saved=True,
                current_user=current_user(),
            )
        except ValueError as exc:
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error=str(exc),
                saved=False,
                current_user=current_user(),
            ), 400
        except Exception:
            app.logger.exception("User creation failed.")
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error="계정 추가 처리 중 서버 오류가 발생했습니다.",
                saved=False,
                current_user=current_user(),
            ), 500

    @app.post("/admin/users/<int:user_id>/password")
    @admin_required
    def update_user_password(user_id: int):
        try:
            password = required_form_value("password")
            validate_password_policy(password)
            database.update_user_password(user_id, password, force_change=True)
            audit("user_password_reset", target_type="user", target_id=str(user_id))
            return redirect(url_for("users_page"))
        except ValueError as exc:
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error=str(exc),
                saved=False,
                current_user=current_user(),
            ), 400
        except Exception:
            app.logger.exception("User password update failed.")
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error="비밀번호 변경 중 서버 오류가 발생했습니다.",
                saved=False,
                current_user=current_user(),
            ), 500

    @app.post("/admin/users/<int:user_id>/delete")
    @admin_required
    def delete_user(user_id: int):
        try:
            current = current_user()
            database.disable_user(user_id, current["id"] if current else None)
            audit("user_disabled", target_type="user", target_id=str(user_id))
            return redirect(url_for("users_page"))
        except ValueError as exc:
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error=str(exc),
                saved=False,
                current_user=current_user(),
            ), 400
        except Exception:
            app.logger.exception("User deletion failed.")
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error="계정 삭제 중 서버 오류가 발생했습니다.",
                saved=False,
                current_user=current_user(),
            ), 500

    @app.post("/admin/users/<int:user_id>/enable")
    @admin_required
    def enable_user(user_id: int):
        try:
            database.enable_user(user_id)
            audit("user_enabled", target_type="user", target_id=str(user_id))
            return redirect(url_for("users_page"))
        except ValueError as exc:
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error=str(exc),
                saved=False,
                current_user=current_user(),
            ), 400
        except Exception:
            app.logger.exception("User enable failed.")
            return render_template(
                "admin_users.html",
                users=database.list_users(),
                error="계정 활성화 중 서버 오류가 발생했습니다.",
                saved=False,
                current_user=current_user(),
            ), 500

    @app.get("/admin/cows")
    @admin_required
    def cows_page():
        return render_template(
            "admin_cows.html",
            cows=database.list_cows(),
            error=None,
            current_user=current_user(),
        )

    @app.get("/admin/cows/<int:cow_id>/edit")
    @admin_required
    def edit_cow_page(cow_id: int):
        cow = database.get_cow_record(cow_id)
        if cow is None:
            return render_template(
                "admin_cows.html",
                cows=database.list_cows(),
                error="소 정보를 찾을 수 없습니다.",
                current_user=current_user(),
            ), 404
        return render_template("admin_cow_edit.html", cow=cow, error=None, saved=False, current_user=current_user())

    @app.post("/admin/cows/<int:cow_id>")
    @admin_required
    @limiter.limit(lambda: settings.upload_rate_limit)
    def update_cow(cow_id: int):
        image_paths = []
        try:
            uploads = get_registration_uploads(required=False)
            if uploads:
                image_paths = save_uploaded_images(uploads)
            old_image_paths = database.update_cow_with_owner(
                cow_id=cow_id,
                owner_name=required_form_value("owner_name"),
                owner_phone=optional_form_value("owner_phone"),
                farm_name=optional_form_value("farm_name"),
                farm_address=optional_form_value("farm_address"),
                ear_tag=required_form_value("ear_tag"),
                cow_name=optional_form_value("cow_name"),
                breed=optional_form_value("breed"),
                sex=optional_form_value("sex"),
                birth_date=optional_form_value("birth_date"),
                notes=optional_form_value("notes"),
                image_paths=image_paths if uploads else None,
            )
            if uploads:
                image_paths = []
                remove_uploaded_files(old_image_paths)
            audit("cow_updated", target_type="cow", target_id=str(cow_id))
            trigger_index_rebuild("소 정보 수정")
            cow = database.get_cow_record(cow_id)
            return render_template("admin_cow_edit.html", cow=cow, error=None, saved=True, current_user=current_user())
        except ValueError as exc:
            remove_uploaded_files(image_paths)
            cow = database.get_cow_record(cow_id)
            return render_template("admin_cow_edit.html", cow=cow, error=str(exc), saved=False, current_user=current_user()), 400
        except Exception:
            remove_uploaded_files(image_paths)
            app.logger.exception("Cow update failed.")
            cow = database.get_cow_record(cow_id)
            return render_template(
                "admin_cow_edit.html",
                cow=cow,
                error="소 정보 수정 중 서버 오류가 발생했습니다.",
                saved=False,
                current_user=current_user(),
            ), 500

    @app.post("/admin/cows/<int:cow_id>/delete")
    @admin_required
    def delete_cow(cow_id: int):
        try:
            image_paths = database.delete_cow(cow_id)
            remove_uploaded_files(image_paths)
            audit("cow_deleted", target_type="cow", target_id=str(cow_id))
            trigger_index_rebuild("소 삭제")
            return redirect(url_for("cows_page"))
        except ValueError as exc:
            return render_template(
                "admin_cows.html",
                cows=database.list_cows(),
                error=str(exc),
                current_user=current_user(),
            ), 400
        except Exception:
            app.logger.exception("Cow deletion failed.")
            return render_template(
                "admin_cows.html",
                cows=database.list_cows(),
                error="소 정보 삭제 중 서버 오류가 발생했습니다.",
                current_user=current_user(),
            ), 500

    @app.get("/admin/system")
    @admin_required
    def system_page():
        return render_template(
            "admin_system.html",
            logs=read_log_tail(),
            audit_logs=database.list_audit_logs(),
            backups=list_backup_files(),
            backup_status=backup_status,
            index_status=index_rebuild_status,
            error=None,
            saved=False,
            current_user=current_user(),
        )

    @app.post("/admin/backups/run")
    @admin_required
    @limiter.limit(lambda: settings.admin_action_rate_limit)
    def run_backup_now():
        started = trigger_manual_backup("수동 실행")
        audit("backup_requested", detail="started" if started else "already running")
        return render_template(
            "admin_system.html",
            logs=read_log_tail(),
            audit_logs=database.list_audit_logs(),
            backups=list_backup_files(),
            backup_status=backup_status,
            index_status=index_rebuild_status,
            error=None if started else "이미 백업이 실행 중입니다.",
            saved=started,
            current_user=current_user(),
        ), 202 if started else 409

    @app.post("/admin/index/rebuild")
    @admin_required
    @limiter.limit(lambda: settings.admin_action_rate_limit)
    def rebuild_index_now():
        trigger_index_rebuild("수동 실행")
        audit("index_rebuild_requested")
        return render_template(
            "admin_system.html",
            logs=read_log_tail(),
            audit_logs=database.list_audit_logs(),
            backups=list_backup_files(),
            backup_status=backup_status,
            index_status=index_rebuild_status,
            error=None,
            saved=False,
            current_user=current_user(),
        )

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        message = upload_too_large_message()
        if request.path.startswith("/api/"):
            return json_error(message, 413)
        if request.path == "/identify":
            return render_template(
                "index.html",
                result=None,
                error=message,
                current_user=current_user(),
            ), 413
        if request.path == "/admin/cows":
            return render_template(
                "admin_cow_form.html",
                error=message,
                saved=False,
                current_user=current_user(),
            ), 413
        if request.path.startswith("/admin/cows/"):
            cow_id = request.view_args.get("cow_id") if request.view_args else None
            cow = database.get_cow_record(int(cow_id)) if cow_id is not None else None
            if cow is not None:
                return render_template(
                    "admin_cow_edit.html",
                    cow=cow,
                    error=message,
                    saved=False,
                    current_user=current_user(),
                ), 413
        return render_template(
            "index.html",
            result=None,
            error=message,
            current_user=current_user(),
        ), 413

    @app.errorhandler(RateLimitExceeded)
    def rate_limit_exceeded(_error):
        message = "요청이 너무 많습니다. 잠시 후 다시 시도하세요."
        app.logger.warning("Rate limit exceeded: path=%s ip=%s", request.path, safe_log_value(request.remote_addr, 80))
        if request.path.startswith("/api/"):
            return json_error(message, 429)
        if request.path == "/login":
            return render_template("login.html", error=message), 429
        if request.path == "/identify":
            return render_template(
                "index.html",
                result=None,
                error=message,
                current_user=current_user(),
            ), 429
        if request.path == "/admin/cows":
            return render_template(
                "admin_cow_form.html",
                error=message,
                saved=False,
                current_user=current_user(),
            ), 429
        if request.path.startswith("/admin/cows/"):
            cow_id = request.view_args.get("cow_id") if request.view_args else None
            cow = database.get_cow_record(int(cow_id)) if cow_id is not None else None
            if cow is not None:
                return render_template(
                    "admin_cow_edit.html",
                    cow=cow,
                    error=message,
                    saved=False,
                    current_user=current_user(),
                ), 429
        return render_template(
            "index.html",
            result=None,
            error=message,
            current_user=current_user(),
        ), 429

    @app.errorhandler(ValueError)
    def bad_request(error):
        app.logger.info("Bad request: %s", error)
        if request.path.startswith("/api/"):
            return json_error(str(error), 400)
        return str(error), 400

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        if request.path.startswith("/api/"):
            return json_error("서버 오류가 발생했습니다. 로그를 확인하세요.", 500)
        return "서버 오류가 발생했습니다. 로그를 확인하세요.", 500

    @app.teardown_appcontext
    def close_database(_exception=None) -> None:
        pass

    return app


def get_pipeline() -> IdentificationPipeline:
    global pipeline
    if pipeline is None:
        with pipeline_lock:
            if pipeline is None:
                app.logger.info("Identification pipeline initialization started.")
                pipeline = IdentificationPipeline(settings, database)
                app.logger.info("Identification pipeline initialization completed.")
    return pipeline


def reset_pipeline() -> None:
    global pipeline
    with pipeline_lock:
        pipeline = None


def initialize_database(app: Flask) -> None:
    database.open()
    database.ensure_schema()
    database.ensure_security_schema()
    database.bootstrap_admin(settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    app.config["BOOTSTRAPPED_ADMIN"] = True
    app.logger.info("Database pool opened and schema verified.")


def upload_too_large_message() -> str:
    return f"업로드 파일 총 용량이 너무 큽니다. 한 번에 최대 {settings.max_request_mb}MB까지 업로드할 수 있습니다."


def trigger_manual_backup(reason: str) -> bool:
    if not backup_lock.acquire(blocking=False):
        update_backup_status("running", "백업 실행 중")
        return False
    thread = threading.Thread(target=run_manual_backup, args=(reason,), daemon=True)
    try:
        thread.start()
    except Exception:
        backup_lock.release()
        update_backup_status("failed", "백업 작업을 시작하지 못했습니다. 로그를 확인하세요.")
        app.logger.exception("Failed to start manual backup thread.")
        return False
    return True


def run_manual_backup(reason: str) -> None:
    try:
        update_backup_status("running", f"{reason}: 백업 실행 중")
        app.logger.info("Manual database backup started: reason=%s", safe_log_value(reason, 120))
        backup_path = run_backup(settings)
        update_backup_status("completed", f"백업 완료: {backup_path.name}")
        app.logger.info("Manual database backup completed: path=%s", backup_path)
    except Exception:
        app.logger.exception("Manual database backup failed.")
        update_backup_status("failed", "백업 실행 중 오류가 발생했습니다. 로그를 확인하세요.")
    finally:
        backup_lock.release()


def update_backup_status(state: str, message: str) -> None:
    backup_status["state"] = state
    backup_status["message"] = message
    backup_status["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def trigger_index_rebuild(reason: str) -> None:
    if not settings.auto_rebuild_index:
        update_index_status("disabled", "자동 갱신이 비활성화되어 있습니다.")
        return
    if not index_rebuild_lock.acquire(blocking=False):
        index_rebuild_status["pending"] = True
        update_index_status("queued", f"{reason}: 기존 갱신 작업 이후 한 번 더 갱신합니다.")
        return
    thread = threading.Thread(target=run_index_rebuild, args=(reason,), daemon=True)
    try:
        thread.start()
    except Exception:
        index_rebuild_lock.release()
        update_index_status("failed", "FAISS 인덱스 갱신 작업을 시작하지 못했습니다. 로그를 확인하세요.")
        app.logger.exception("Failed to start FAISS index rebuild thread.")


def run_index_rebuild(reason: str) -> None:
    try:
        next_reason = reason
        while next_reason:
            index_rebuild_status["pending"] = False
            update_index_status("running", f"{next_reason}: FAISS 인덱스 갱신 중")
            app.logger.info("FAISS index rebuild started: reason=%s", safe_log_value(next_reason, 120))
            try:
                count = rebuild_faiss_index(settings, app.logger)
                reset_pipeline()
                update_index_status("completed", f"FAISS 인덱스 갱신 완료: {count}개 이미지 반영")
                app.logger.info("FAISS index rebuild completed: indexed_images=%s", count)
            except Exception:
                app.logger.exception("FAISS index rebuild failed.")
                update_index_status("failed", "FAISS 인덱스 갱신 실패. 로그를 확인하세요.")
            next_reason = "대기 중인 변경사항" if index_rebuild_status["pending"] else None
    finally:
        index_rebuild_lock.release()


def update_index_status(state: str, message: str) -> None:
    index_rebuild_status["state"] = state
    index_rebuild_status["message"] = message
    index_rebuild_status["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def current_user() -> dict | None:
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return database.get_user(int(user_id))


def audit(
    action: str,
    actor: dict | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str | None = None,
) -> None:
    try:
        current = actor or current_user()
        app.logger.info(
            "audit action=%s actor=%s target_type=%s target_id=%s detail=%s",
            safe_log_value(action, 80),
            safe_log_value(current["username"] if current else None, 80),
            safe_log_value(target_type, 80),
            safe_log_value(target_id, 120),
            safe_log_value(detail, 200),
        )
        database.add_audit_log(
            actor_user_id=current["id"] if current else None,
            actor_username=current["username"] if current else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=safe_log_value(request.remote_addr, 128),
            user_agent=safe_log_value(request.headers.get("User-Agent"), 256),
            detail=safe_log_value(detail, 500),
        )
    except Exception:
        app.logger.exception("Audit log write failed: action=%s", safe_log_value(action, 80))


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf() -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    sent_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not sent_token or sent_token != session.get("_csrf_token"):
        raise ValueError("CSRF token is invalid.")


def validate_password_policy(password: str) -> None:
    if len(password) < settings.password_min_length:
        raise ValueError(f"비밀번호는 {settings.password_min_length}자 이상이어야 합니다.")
    if not any(character.isalpha() for character in password):
        raise ValueError("비밀번호에는 영문자가 포함되어야 합니다.")
    if not any(character.isdigit() for character in password):
        raise ValueError("비밀번호에는 숫자가 포함되어야 합니다.")


def is_user_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if locked_until is None:
        return False
    return datetime.now(locked_until.tzinfo) < locked_until


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("login_page"))
        if user["status"] != "active":
            session.clear()
            return redirect(url_for("login_page"))
        if user["must_change_password"] and request.endpoint not in {"change_password_page", "change_password", "logout", "static"}:
            return redirect(url_for("change_password_page"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("login_page"))
        if user["status"] != "active":
            session.clear()
            return redirect(url_for("login_page"))
        if user["must_change_password"] and request.endpoint not in {"change_password_page", "change_password", "logout", "static"}:
            return redirect(url_for("change_password_page"))
        if user["role"] != "admin":
            return "관리자 권한이 필요합니다.", 403
        return view(*args, **kwargs)

    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return json_error("인증이 필요합니다.", 401)
        if user["status"] != "active":
            session.clear()
            return json_error("비활성화된 계정입니다.", 403)
        if user["must_change_password"] and request.endpoint not in {"api_me", "api_change_password", "api_logout"}:
            return json_error("비밀번호 변경이 필요합니다.", 403)
        return view(*args, **kwargs)

    return wrapped


def api_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return json_error("인증이 필요합니다.", 401)
        if user["status"] != "active":
            session.clear()
            return json_error("비활성화된 계정입니다.", 403)
        if user["must_change_password"]:
            return json_error("비밀번호 변경이 필요합니다.", 403)
        if user["role"] != "admin":
            return json_error("관리자 권한이 필요합니다.", 403)
        return view(*args, **kwargs)

    return wrapped


def identify_uploaded_file():
    uploaded = request.files.get("file")
    image_bytes, _extension = read_validated_image(uploaded, "소 코 사진을 업로드하세요.")
    return get_pipeline().identify(image_bytes)


def save_uploaded_image(uploaded: FileStorage | None) -> str:
    image_bytes, extension = read_validated_image(uploaded, "등록할 소 코 사진을 업로드하세요.")

    upload_dir = Path(settings.upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(upload_dir, 0o750)
    target = (upload_dir / f"cow-upload-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex}.{extension}").resolve()
    if upload_dir not in target.parents:
        raise ValueError("업로드 저장 경로가 올바르지 않습니다.")
    temp_target = target.with_name(f".{target.name}.tmp")
    try:
        temp_target.write_bytes(image_bytes)
        os.chmod(temp_target, int(settings.upload_file_mode, 8))
        temp_target.replace(target)
    except Exception:
        temp_target.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    return str(target)


def get_registration_uploads(required: bool) -> list[FileStorage]:
    uploads = request.files.getlist("files") or request.files.getlist("file")
    uploads = [uploaded for uploaded in uploads if uploaded is not None and uploaded.filename]
    if required and not uploads:
        raise ValueError("등록할 소 코 사진을 업로드하세요.")
    if not uploads:
        return []
    if len(uploads) < settings.registration_min_images:
        raise ValueError(f"소 등록 이미지는 {settings.registration_min_images}장 이상 필요합니다.")
    if len(uploads) > settings.registration_max_images:
        raise ValueError(f"소 등록 이미지는 최대 {settings.registration_max_images}장까지 업로드할 수 있습니다.")
    return uploads


def save_uploaded_images(uploads: list[FileStorage]) -> list[str]:
    saved_paths = []
    try:
        for uploaded in uploads:
            saved_paths.append(save_uploaded_image(uploaded))
    except Exception:
        remove_uploaded_files(saved_paths)
        raise
    return saved_paths


def read_validated_image(uploaded: FileStorage | None, empty_message: str) -> tuple[bytes, str]:
    if uploaded is None or uploaded.filename == "":
        app.logger.warning("Upload rejected: missing file")
        raise ValueError(empty_message)

    suffix = validate_upload_extension(uploaded.filename)
    validate_upload_content_type(uploaded.mimetype)
    image_bytes = uploaded.read()
    if not image_bytes:
        app.logger.warning("Upload rejected: empty file")
        raise ValueError("빈 파일은 업로드할 수 없습니다.")
    if len(image_bytes) > settings.max_upload_mb * 1024 * 1024:
        app.logger.warning("Upload rejected: file too large size=%s", len(image_bytes))
        raise ValueError("업로드 파일 용량이 너무 큽니다.")

    detected_format = detect_image_format(image_bytes)
    detected_extension = extension_for_image_format(detected_format)
    if detected_extension not in allowed_image_extensions():
        raise ValueError("허용되지 않는 이미지 형식입니다.")
    if suffix != detected_extension and not (suffix == "jpg" and detected_extension == "jpeg"):
        app.logger.warning(
            "Upload rejected: extension mismatch supplied=%s detected=%s mimetype=%s",
            suffix,
            detected_extension,
            safe_log_value(uploaded.mimetype, 80),
        )
        raise ValueError("파일 확장자와 실제 이미지 형식이 일치하지 않습니다.")
    app.logger.debug(
        "Upload accepted: extension=%s mimetype=%s size=%s",
        detected_extension,
        safe_log_value(uploaded.mimetype, 80),
        len(image_bytes),
    )
    return normalize_image_bytes(image_bytes, detected_format), detected_extension


def validate_upload_extension(filename: str) -> str:
    if "\x00" in filename:
        app.logger.warning("Upload rejected: null byte in filename")
        raise ValueError("파일명이 올바르지 않습니다.")
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix == "jpg":
        suffix = "jpeg"
    if suffix == "":
        app.logger.warning("Upload rejected: missing extension")
        raise ValueError("파일 확장자가 없습니다.")
    if suffix not in allowed_image_extensions():
        app.logger.warning("Upload rejected: extension not allowed extension=%s", safe_log_value(suffix, 32))
        raise ValueError("허용되지 않는 이미지 확장자입니다.")
    return suffix


def validate_upload_content_type(mimetype: str | None) -> None:
    if mimetype not in allowed_image_mimetypes():
        app.logger.warning("Upload rejected: content type not allowed mimetype=%s", safe_log_value(mimetype, 80))
        raise ValueError("이미지 파일만 업로드할 수 있습니다.")


def allowed_image_extensions() -> set[str]:
    allowed = {value.strip().lower() for value in settings.allowed_image_extensions.split(",")}
    if "jpg" in allowed:
        allowed.add("jpeg")
    return allowed


def allowed_image_mimetypes() -> set[str]:
    return {
        f"image/{extension}"
        for extension in allowed_image_extensions()
        if extension != "jpg"
    } | {"image/jpg"}


def detect_image_format(image_bytes: bytes) -> str:
    if not has_allowed_image_signature(image_bytes):
        app.logger.warning("Upload rejected: image signature not allowed")
        raise ValueError("올바른 이미지 파일이 아닙니다.")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
            if image.format is None:
                raise ValueError("이미지 형식을 확인할 수 없습니다.")
            return image.format.upper()
    except (Image.DecompressionBombError, UnidentifiedImageError) as exc:
        raise ValueError("올바른 이미지 파일이 아닙니다.") from exc
    except Exception as exc:
        raise ValueError("올바른 이미지 파일이 아닙니다.") from exc


def has_allowed_image_signature(image_bytes: bytes) -> bool:
    return (
        image_bytes.startswith(b"\xff\xd8\xff")
        or image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        or (len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP")
    )


def extension_for_image_format(image_format: str) -> str:
    mapping = {
        "JPEG": "jpeg",
        "PNG": "png",
        "WEBP": "webp",
    }
    extension = mapping.get(image_format.upper())
    if extension is None:
        raise ValueError("허용되지 않는 이미지 형식입니다.")
    return extension


def normalize_image_bytes(image_bytes: bytes, image_format: str) -> bytes:
    extension = extension_for_image_format(image_format)
    with Image.open(BytesIO(image_bytes)) as image:
        image = image.convert("RGB") if extension == "jpeg" else image.copy()
        output = BytesIO()
        if extension == "jpeg":
            image.save(output, format="JPEG", quality=95, optimize=True)
        elif extension == "png":
            image.save(output, format="PNG", optimize=True)
        else:
            image.save(output, format="WEBP", quality=95, method=6)
        return output.getvalue()


def required_form_value(name: str) -> str:
    value = request.form.get(name, "").strip()
    if value == "":
        raise ValueError("필수 항목을 입력하세요.")
    return value


def optional_form_value(name: str) -> str | None:
    value = request.form.get(name, "").strip()
    return value or None


def json_or_form_value(name: str, required: bool = False, default=None):
    payload = request.get_json(silent=True) if request.is_json else None
    if payload is not None:
        value = payload.get(name, default)
    else:
        value = request.form.get(name, default)
    if isinstance(value, str):
        value = value.strip()
    if value == "":
        value = default
    if required and (value is None or value == ""):
        raise ValueError("필수 항목을 입력하세요.")
    return value


def json_error(message: str, status: int):
    return jsonify({"error": message}), status


def serialize_user(user: dict | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "status": user["status"],
        "must_change_password": user["must_change_password"],
    }


def serialize_cow_record(cow: dict) -> dict:
    return {
        "id": cow["id"],
        "ear_tag": cow["ear_tag"],
        "name": cow["cow_name"],
        "breed": cow["breed"],
        "sex": cow["sex"],
        "birth_date": cow["birth_date"],
        "notes": cow["notes"],
        "owner": {
            "id": cow["owner_id"],
            "name": cow["owner_name"],
            "phone": cow["owner_phone"],
            "farm_name": cow["farm_name"],
            "farm_address": cow["farm_address"],
        },
    }


def configure_logging(app: Flask) -> None:
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    error_log_path = Path(settings.error_log_file)
    error_log_path.parent.mkdir(parents=True, exist_ok=True)
    log_level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(log_level, int):
        log_level = logging.INFO

    for handler in list(app.logger.handlers):
        app.logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(log_level)
    handler.setFormatter(formatter)
    error_handler = logging.FileHandler(error_log_path, encoding="utf-8")
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)

    app.logger.setLevel(log_level)
    app.logger.addHandler(handler)
    app.logger.addHandler(error_handler)
    app.logger.info(
        "Logging initialized: level=%s file=%s error_file=%s",
        logging.getLevelName(log_level),
        log_path,
        error_log_path,
    )


def safe_log_value(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = "".join(character if character.isprintable() else " " for character in str(value))
    return cleaned[:max_length]


def read_log_tail(line_count: int = 200) -> str:
    log_path = Path(settings.log_file)
    if not log_path.exists():
        return ""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-line_count:])


def list_backup_files() -> list[dict]:
    backup_dir = Path(settings.backup_dir)
    if not backup_dir.exists():
        return []
    files = sorted(backup_dir.glob("*.dump"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [{"name": path.name, "size": path.stat().st_size} for path in files[:20]]


def remove_uploaded_files(paths: list[str]) -> None:
    upload_dir = Path(settings.upload_dir).resolve()
    for value in paths:
        path = Path(value).resolve()
        if upload_dir not in path.parents:
            app.logger.warning("Skipped deleting file outside upload dir: %s", path)
            continue
        try:
            path.unlink(missing_ok=True)
        except Exception:
            app.logger.exception("Failed to delete uploaded image: %s", path)


app = create_app()
