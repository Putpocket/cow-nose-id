from functools import wraps

from flask import Blueprint, jsonify, request, session

from app.db import add_audit_log, get_connection
from app.security import hash_password


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        if session.get("role") not in ("admin", "super"):
            add_audit_log(
                action="admin_access_denied",
                user_id=session.get("user_id"),
                username=session.get("username"),
                detail=request.path,
            )
            return jsonify({"success": False, "error": "Admin access required"}), 403
        return handler(*args, **kwargs)

    return wrapper


@admin_bp.route("/accounts", methods=["GET"])
@admin_required
def list_accounts():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, username, role, status, last_login_at, created_at
            FROM users
            ORDER BY user_id
            """
        )
        accounts = [
            {
                "user_id": row[0],
                "username": row[1],
                "role": row[2],
                "status": row[3],
                "last_login_at": row[4].isoformat() if row[4] else None,
                "created_at": row[5].isoformat() if row[5] else None,
            }
            for row in cur.fetchall()
        ]
        return jsonify({"success": True, "accounts": accounts})
    finally:
        cur.close()
        conn.close()


@admin_bp.route("/accounts", methods=["POST"])
@admin_required
def create_account():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "user").strip().lower()

    if not username or not password:
        return jsonify({"success": False, "error": "username and password are required"}), 400
    if role not in ("user", "admin", "super"):
        return jsonify({"success": False, "error": "invalid role"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role, status, must_change_password)
            VALUES (%s, %s, %s, 'active', TRUE)
            RETURNING user_id
            """,
            (username, hash_password(password), role),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        add_audit_log(
            action="account_created",
            user_id=session.get("user_id"),
            username=session.get("username"),
            target_type="user",
            target_id=str(user_id),
            detail=f"created username={username} role={role}",
        )
        return jsonify({"success": True, "user_id": user_id}), 201
    except Exception as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        cur.close()
        conn.close()


@admin_bp.route("/accounts/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_account(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"success": False, "error": "cannot delete current account"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE user_id=%s RETURNING username", (user_id,))
        deleted = cur.fetchone()
        if not deleted:
            conn.rollback()
            return jsonify({"success": False, "error": "account not found"}), 404
        conn.commit()
        add_audit_log(
            action="account_deleted",
            user_id=session.get("user_id"),
            username=session.get("username"),
            target_type="user",
            target_id=str(user_id),
            detail=f"deleted username={deleted[0]}",
        )
        return jsonify({"success": True})
    except Exception as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        cur.close()
        conn.close()


@admin_bp.route("/cows", methods=["GET"])
@admin_required
def list_cows():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT c.cow_id, c.ear_tag, c.name, c.breed, c.sex, c.birth_date,
                   c.notes, c.created_at, o.name AS owner_name
            FROM cows c
            LEFT JOIN owners o ON c.owner_id = o.owner_id
            ORDER BY c.cow_id DESC
            """
        )
        cows = [
            {
                "cow_id": row[0],
                "ear_tag": row[1],
                "name": row[2],
                "breed": row[3],
                "sex": row[4],
                "birth_date": row[5].isoformat() if row[5] else None,
                "notes": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
                "owner_name": row[8],
            }
            for row in cur.fetchall()
        ]
        return jsonify({"success": True, "cows": cows})
    finally:
        cur.close()
        conn.close()


@admin_bp.route("/cows", methods=["POST"])
@admin_required
def create_cow():
    data = request.get_json(silent=True) or {}
    ear_tag = (data.get("ear_tag") or "").strip()
    if not ear_tag:
        return jsonify({"success": False, "error": "ear_tag is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        owner_id = upsert_owner(cur, data.get("owner_name"))
        cur.execute(
            """
            INSERT INTO cows (owner_id, ear_tag, name, breed, sex, birth_date, notes)
            VALUES (%s, %s, %s, %s, %s, NULLIF(%s, '')::date, %s)
            RETURNING cow_id
            """,
            (
                owner_id,
                ear_tag,
                empty_to_none(data.get("name")),
                empty_to_none(data.get("breed")),
                empty_to_none(data.get("sex")),
                data.get("birth_date") or "",
                empty_to_none(data.get("notes")),
            ),
        )
        cow_id = cur.fetchone()[0]
        conn.commit()
        add_audit_log(
            action="cow_created",
            user_id=session.get("user_id"),
            username=session.get("username"),
            target_type="cow",
            target_id=str(cow_id),
            detail=f"created ear_tag={ear_tag}",
        )
        return jsonify({"success": True, "cow_id": cow_id}), 201
    except Exception as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        cur.close()
        conn.close()


@admin_bp.route("/cows/<int:cow_id>", methods=["PUT"])
@admin_required
def update_cow(cow_id):
    data = request.get_json(silent=True) or {}
    ear_tag = (data.get("ear_tag") or "").strip()
    if not ear_tag:
        return jsonify({"success": False, "error": "ear_tag is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        owner_id = upsert_owner(cur, data.get("owner_name"))
        cur.execute(
            """
            UPDATE cows
            SET owner_id=%s,
                ear_tag=%s,
                name=%s,
                breed=%s,
                sex=%s,
                birth_date=NULLIF(%s, '')::date,
                notes=%s
            WHERE cow_id=%s
            RETURNING cow_id
            """,
            (
                owner_id,
                ear_tag,
                empty_to_none(data.get("name")),
                empty_to_none(data.get("breed")),
                empty_to_none(data.get("sex")),
                data.get("birth_date") or "",
                empty_to_none(data.get("notes")),
                cow_id,
            ),
        )
        if not cur.fetchone():
            conn.rollback()
            return jsonify({"success": False, "error": "cow not found"}), 404
        conn.commit()
        add_audit_log(
            action="cow_updated",
            user_id=session.get("user_id"),
            username=session.get("username"),
            target_type="cow",
            target_id=str(cow_id),
            detail=f"updated ear_tag={ear_tag}",
        )
        return jsonify({"success": True})
    except Exception as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        cur.close()
        conn.close()


@admin_bp.route("/cows/<int:cow_id>", methods=["DELETE"])
@admin_required
def delete_cow(cow_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM cow_images WHERE cow_id=%s", (cow_id,))
        cur.execute("DELETE FROM cows WHERE cow_id=%s RETURNING ear_tag", (cow_id,))
        deleted = cur.fetchone()
        if not deleted:
            conn.rollback()
            return jsonify({"success": False, "error": "cow not found"}), 404
        conn.commit()
        add_audit_log(
            action="cow_deleted",
            user_id=session.get("user_id"),
            username=session.get("username"),
            target_type="cow",
            target_id=str(cow_id),
            detail=f"deleted ear_tag={deleted[0]}",
        )
        return jsonify({"success": True})
    except Exception as exc:
        conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        cur.close()
        conn.close()


def upsert_owner(cur, owner_name):
    owner_name = (owner_name or "").strip()
    if not owner_name:
        return None
    cur.execute("SELECT owner_id FROM owners WHERE name=%s ORDER BY owner_id LIMIT 1", (owner_name,))
    existing = cur.fetchone()
    if existing:
        return existing[0]
    cur.execute("INSERT INTO owners (name) VALUES (%s) RETURNING owner_id", (owner_name,))
    return cur.fetchone()[0]


def empty_to_none(value):
    value = (value or "").strip()
    return value or None
