import uuid
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from flask import Flask, current_app, g, has_request_context, jsonify, request, session
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app.services.pipeline import process_image


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _db_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "").strip(),
        database=os.getenv("DB_NAME", "").strip(),
        user=os.getenv("DB_USER", "").strip(),
        password=os.getenv("DB_PASSWORD", "").strip(),
        port=os.getenv("DB_PORT", "5432").strip(),
    )




def _table_columns(conn, table_name: str):
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table_name,))
        return {r[0] for r in cur.fetchall()}


def _user_columns(conn):
    if has_request_context() and getattr(g, "_users_cols", None) is not None:
        return g._users_cols
    cols = _table_columns(conn, "users")
    if has_request_context():
        g._users_cols = cols
    return cols


def _audit_columns(conn):
    if has_request_context() and getattr(g, "_audit_cols", None) is not None:
        return g._audit_cols
    cols = _table_columns(conn, "audit_logs")
    if has_request_context():
        g._audit_cols = cols
    return cols


def _lock_state_from_row(row: dict):
    status = str(row.get("status") or "").lower()
    is_active = status == "active"
    attempts = row.get("failed_attempts", 0)
    return is_active, int(attempts or 0)

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=_int_env("SESSION_LIFETIME_MINUTES", 60))
    app.config["SESSION_COOKIE_HTTPONLY"] = _bool_env("SESSION_COOKIE_HTTPONLY", True)
    app.config["SESSION_COOKIE_SECURE"] = _bool_env("SESSION_COOKIE_SECURE", False)
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    app.config["MAX_CONTENT_LENGTH"] = _int_env("MAX_UPLOAD_MB", 8) * 1024 * 1024

    upload_dir = Path(os.getenv("UPLOAD_DIR", "./data/uploads")).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"] = upload_dir
    app.config["ALLOWED_EXTENSIONS"] = {
        ext.strip().lower() for ext in os.getenv("ALLOWED_IMAGE_EXTENSIONS", "jpg,jpeg,png,webp").split(",") if ext.strip()
    }

    log_file = os.getenv("LOG_FILE", "./data/logs/app.log")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_file, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    def audit(action: str, target: str = "", ok: bool = True, detail: str = ""):
        user_id = session.get("user_id")
        username = session.get("username")
        status = "ok" if ok else "fail"
        message = f"{action} {status} target={target} user_id={user_id} {detail}".strip()
        app.logger.info(message)
        try:
            with _db_connection() as conn:
                cols = _audit_columns(conn)
                payload = {}
                if "user_id" in cols:
                    payload["user_id"] = user_id
                if "username" in cols:
                    payload["username"] = username
                if "action" in cols:
                    payload["action"] = action
                if "target_type" in cols:
                    payload["target_type"] = "api"
                if "target_id" in cols:
                    payload["target_id"] = target
                if "ip_address" in cols:
                    payload["ip_address"] = request.remote_addr if has_request_context() else None
                if "user_agent" in cols:
                    payload["user_agent"] = request.headers.get("User-Agent", "") if has_request_context() else ""
                if "detail" in cols:
                    payload["detail"] = message
                if payload:
                    keys = list(payload.keys())
                    sql = f"INSERT INTO audit_logs ({', '.join(keys)}) VALUES ({', '.join(['%s']*len(keys))})"
                    with conn.cursor() as cur:
                        cur.execute(sql, [payload[k] for k in keys])
        except Exception:
            app.logger.exception("audit_log_insert_failed")

    def require_login():
        if not session.get("user_id"):
            audit("auth_required", ok=False)
            return jsonify({"error": "login required"}), 401

    def require_admin():
        if session.get("role") not in {"admin", "super"}:
            audit("admin_required", ok=False)
            return jsonify({"error": "admin required"}), 403

    def require_csrf():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not token or token != session.get("csrf_token"):
                audit("csrf_rejected", ok=False)
                return jsonify({"error": "invalid csrf token"}), 400

    @app.before_request
    def _security_headers_and_csrf():
        csrf_err = require_csrf()
        if csrf_err:
            return csrf_err

    @app.after_request
    def add_headers(response):
        response.headers["Content-Security-Policy"] = os.getenv("CONTENT_SECURITY_POLICY", "default-src 'self'")
        response.headers["Referrer-Policy"] = os.getenv("REFERRER_POLICY", "same-origin")
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Permissions-Policy"] = os.getenv("PERMISSIONS_POLICY", "geolocation=(), microphone=(), camera=()")
        return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/csrf-token")
    def csrf_token():
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify({"csrf_token": session["csrf_token"]})

    @app.post("/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        with _db_connection() as conn, conn.cursor() as cur:
            select_cols = ["user_id", "password_hash", "role", "status", "failed_attempts", "locked_until"]
            cur.execute("SELECT user_id, password_hash, role, status, failed_attempts, locked_until FROM users WHERE username=%s", (username,))
            row = cur.fetchone()
            if not row:
                audit("login", target=username, ok=False, detail="no_user")
                return jsonify({"error": "invalid credentials"}), 401
            data = dict(zip(select_cols, row))
            user_id = data["user_id"]
            password_hash = data["password_hash"]
            role = data.get("role", "user")
            locked_until = data.get("locked_until")
            is_active, attempts = _lock_state_from_row(data)
            now = datetime.now(timezone.utc)
            if locked_until and locked_until.replace(tzinfo=timezone.utc) > now:
                audit("login", target=username, ok=False, detail="locked")
                return jsonify({"error": "account locked"}), 423
            if (not is_active) or (not check_password_hash(password_hash, password)):
                max_attempts = _int_env("LOGIN_MAX_ATTEMPTS", 5)
                lock_seconds = _int_env("LOGIN_LOCKOUT_SECONDS", 900)
                attempts += 1
                lock_until = now + timedelta(seconds=lock_seconds) if attempts >= max_attempts else None
                cur.execute("UPDATE users SET failed_attempts=%s, locked_until=%s WHERE user_id=%s", (attempts, lock_until, user_id))
                audit("login", target=username, ok=False, detail="bad_password_or_inactive")
                return jsonify({"error": "invalid credentials"}), 401

            cur.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE user_id=%s", (user_id,))
            session.clear()
            session["user_id"] = user_id
            session["username"] = username
            session["role"] = role
            session["is_admin"] = role in {"admin", "super"}
            session.permanent = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            audit("login", target=username, ok=True)
            return jsonify({"message": "ok", "csrf_token": session["csrf_token"], "role": role, "is_admin": session["is_admin"]})


    @app.get("/auth/me")
    def me():
        require = require_login()
        if require:
            return require
        return jsonify({"user_id": session.get("user_id"), "username": session.get("username"), "role": session.get("role", "user")})

    @app.get("/me")
    def me_alias():
        return me()

    @app.post("/auth/logout")
    def logout():
        require = require_login()
        if require:
            return require
        audit("logout", target=session.get("username", ""), ok=True)
        session.clear()
        return jsonify({"message": "ok"})


    @app.post("/auth/change-password")
    def change_password():
        require = require_login()
        if require:
            return require
        payload = request.get_json(silent=True) or {}
        old_password = payload.get("old_password") or ""
        new_password = payload.get("new_password") or ""
        min_len = _int_env("PASSWORD_MIN_LENGTH", 8)
        if len(new_password) < min_len:
            return jsonify({"error": f"password min length {min_len}"}), 400

        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE user_id=%s", (session["user_id"],))
            row = cur.fetchone()
            if not row or not check_password_hash(row[0], old_password):
                audit("change_password", target=str(session.get("user_id")), ok=False, detail="bad_old")
                return jsonify({"error": "invalid password"}), 401
            new_hash = generate_password_hash(new_password)
            cur.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (new_hash, session["user_id"]))
            cur.execute("INSERT INTO password_history (user_id, password_hash) VALUES (%s, %s)", (session["user_id"], new_hash))
        audit("change_password", target=str(session.get("user_id")), ok=True)
        return jsonify({"message": "password updated"})

    @app.get("/admin/accounts")
    def list_accounts():
        for check in (require_login(), require_admin()):
            if check:
                return check
        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT user_id, username, role, (status='active') AS is_active, created_at FROM users ORDER BY user_id DESC")
            rows = cur.fetchall()
        return jsonify([{"user_id": r[0], "username": r[1], "role": r[2], "is_active": bool(r[3]), "created_at": r[4].isoformat() if r[4] else None} for r in rows])

    @app.get("/api/admin/accounts")
    def list_accounts_api_alias():
        return list_accounts()

    @app.post("/api/admin/accounts")
    def create_account_api_alias():
        return create_account()

    @app.post("/admin/accounts")
    def create_account():
        for check in (require_login(), require_admin()):
            if check:
                return check
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        role = (payload.get("role") or "user").strip()
        min_len = _int_env("PASSWORD_MIN_LENGTH", 8)
        if len(password) < min_len:
            return jsonify({"error": f"password min length {min_len}"}), 400

        try:
            with _db_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (username, generate_password_hash(password), role),
                )
            audit("account_create", target=username, ok=True)
            return jsonify({"message": "created"}), 201
        except Exception as exc:
            audit("account_create", target=username, ok=False, detail=str(exc))
            return jsonify({"error": "create failed"}), 400

    @app.delete("/api/admin/accounts/<int:user_id>")
    def delete_account_api_alias(user_id: int):
        return delete_account(user_id)

    @app.delete("/admin/accounts/<int:user_id>")
    def delete_account(user_id: int):
        for check in (require_login(), require_admin()):
            if check:
                return check
        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
            deleted = cur.rowcount
        audit("account_delete", target=str(user_id), ok=bool(deleted))
        return jsonify({"deleted": deleted})


    @app.get("/admin/users")
    def list_users():
        return list_accounts()

    @app.post("/admin/users")
    def create_user():
        return create_account()

    @app.post("/admin/users/<int:user_id>/password")
    def admin_set_user_password(user_id: int):
        for check in (require_login(), require_admin()):
            if check:
                return check
        payload = request.get_json(silent=True) or {}
        new_password = payload.get("new_password") or ""
        min_len = _int_env("PASSWORD_MIN_LENGTH", 8)
        if len(new_password) < min_len:
            return jsonify({"error": f"password min length {min_len}"}), 400
        new_hash = generate_password_hash(new_password)
        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (new_hash, user_id))
            cur.execute("INSERT INTO password_history (user_id, password_hash) VALUES (%s, %s)", (user_id, new_hash))
        audit("admin_password_reset", target=str(user_id), ok=True)
        return jsonify({"message": "updated"})

    @app.post("/admin/users/<int:user_id>/disable")
    def disable_user(user_id: int):
        for check in (require_login(), require_admin()):
            if check:
                return check
        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET status='disabled' WHERE user_id=%s", (user_id,))
        audit("user_disable", target=str(user_id), ok=True)
        return jsonify({"message": "disabled"})

    @app.post("/admin/users/<int:user_id>/enable")
    def enable_user(user_id: int):
        for check in (require_login(), require_admin()):
            if check:
                return check
        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET status='active' WHERE user_id=%s", (user_id,))
        audit("user_enable", target=str(user_id), ok=True)
        return jsonify({"message": "enabled"})

    @app.route("/api/admin/cattle", methods=["GET", "POST"])
    def cattle_collection_api_alias():
        return cattle_collection()

    @app.route("/admin/cows", methods=["GET", "POST"])
    def cattle_collection():
        for check in (require_login(), require_admin()):
            if check:
                return check
        if request.method == "GET":
            with _db_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT cow_id, owner_id, name, created_at FROM cows ORDER BY cow_id DESC")
                data = cur.fetchall()
            return jsonify([{"cow_id": r[0], "owner_id": r[1], "name": r[2], "created_at": r[3].isoformat() if r[3] else None} for r in data])

        payload = request.get_json(silent=True) or {}
        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO cows (owner_id, name) VALUES (%s, %s) RETURNING cow_id", (payload.get("owner_id"), payload.get("name")))
            cow_id = cur.fetchone()[0]
        audit("cattle_create", target=str(cow_id), ok=True)
        return jsonify({"cow_id": cow_id}), 201

    @app.route("/api/admin/cattle/<int:cow_id>", methods=["GET", "PUT", "DELETE"])
    def cattle_item_api_alias(cow_id: int):
        return cattle_item(cow_id)

    @app.route("/admin/cows/<int:cow_id>", methods=["GET", "PUT", "DELETE"])
    def cattle_item(cow_id: int):
        for check in (require_login(), require_admin()):
            if check:
                return check
        if request.method == "GET":
            with _db_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT cow_id, owner_id, name, created_at FROM cows WHERE cow_id=%s", (cow_id,))
                r = cur.fetchone()
            if not r:
                return jsonify({"error": "not found"}), 404
            return jsonify({"cow_id": r[0], "owner_id": r[1], "name": r[2], "created_at": r[3].isoformat() if r[3] else None})
        if request.method == "PUT":
            payload = request.get_json(silent=True) or {}
            with _db_connection() as conn, conn.cursor() as cur:
                cur.execute("UPDATE cows SET owner_id=%s, name=%s WHERE cow_id=%s", (payload.get("owner_id"), payload.get("name"), cow_id))
                updated = cur.rowcount
            audit("cattle_update", target=str(cow_id), ok=bool(updated))
            return jsonify({"updated": updated})
        with _db_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM cows WHERE cow_id=%s", (cow_id,))
            deleted = cur.rowcount
        audit("cattle_delete", target=str(cow_id), ok=bool(deleted))
        return jsonify({"deleted": deleted})

    @app.post("/api/identify")
    def upload():
        login_err = require_login()
        if login_err:
            return login_err
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "No file uploaded"}), 400

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in app.config["ALLOWED_EXTENSIONS"]:
            return jsonify({"error": "unsupported extension"}), 400

        safe_name = secure_filename(file.filename)
        file.stream.seek(0)
        try:
            img = Image.open(file.stream)
            img.verify()
            format_name = (img.format or "").lower()
            if format_name not in {"jpeg", "png", "webp"}:
                return jsonify({"error": "invalid image type"}), 400
        except Exception:
            return jsonify({"error": "invalid image content"}), 400
        file.stream.seek(0)
        ext = safe_name.rsplit(".", 1)[-1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        target = (app.config["UPLOAD_DIR"] / filename).resolve()
        if app.config["UPLOAD_DIR"] not in target.parents:
            audit("upload", target=file.filename, ok=False, detail="path_traversal")
            return jsonify({"error": "invalid path"}), 400

        file.save(target)
        os.chmod(target, int(os.getenv("UPLOAD_FILE_MODE", "0o640"), 8))
        audit("upload", target=str(target), ok=True)
        try:
            result = process_image(str(target))
        except Exception as exc:
            current_app.logger.exception("identify_pipeline_failed")
            audit("identify", target=str(target), ok=False, detail=str(exc))
            return jsonify({"error": "identify failed"}), 500
        return jsonify(result)


    # bootstrap admin account
    try:
        with _db_connection() as conn, conn.cursor() as cur:
            admin_user = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
            admin_pw = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
            if not admin_user or not admin_pw:
                return app
            cur.execute("SELECT user_id FROM users WHERE username=%s", (admin_user,))
            if not cur.fetchone():
                pw_hash = generate_password_hash(admin_pw)
                cur.execute("INSERT INTO users (username, password_hash, role, status) VALUES (%s, %s, 'admin', 'active')", (admin_user, pw_hash))
                cur.execute("INSERT INTO password_history (user_id, password_hash) SELECT user_id, password_hash FROM users WHERE username=%s", (admin_user,))
                app.logger.info("bootstrap admin created")
    except Exception:
        app.logger.exception("bootstrap_admin_failed")

    return app
