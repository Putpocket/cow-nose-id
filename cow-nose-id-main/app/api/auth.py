# ==============================
# 인증 관련 API (로그인)
# ==============================

from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta

from app.db import get_connection
from app.core.security import verify_password


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ==============================
# 로그인 API
# ==============================
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "error": "username and password required"}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        # 사용자 조회
        cur.execute("""
            SELECT user_id, password_hash, role, status,
                   failed_attempts, locked_until, must_change_password
            FROM users
            WHERE username=%s
        """, (username,))

        user = cur.fetchone()

        # -----------------------------
        # 1. 사용자 없음
        # -----------------------------
        if not user:
            return jsonify({"error": "user not found"}), 404

        user_id = user[0]
        password_hash = user[1]
        role = user[2]
        status = user[3]
        failed_attempts = user[4]
        locked_until = user[5]
        must_change_password = user[6]

        # -----------------------------
        # 2. 계정 비활성화
        # -----------------------------
        if status != "active":
            return jsonify({"error": "account disabled"}), 403

        # -----------------------------
        # 3. 계정 잠금 확인
        # -----------------------------
        if locked_until and locked_until > datetime.now():
            return jsonify({"error": "account locked"}), 403

        # -----------------------------
        # 4. 비밀번호 검증 실패
        # -----------------------------
        if not verify_password(password, password_hash):

            failed_attempts += 1

            # 5회 이상 실패 → 계정 잠금 (예시)
            if failed_attempts >= 5:
                lock_time = datetime.now() + timedelta(minutes=15)

                cur.execute("""
                    UPDATE users
                    SET failed_attempts=%s, locked_until=%s
                    WHERE user_id=%s
                """, (failed_attempts, lock_time, user_id))

            else:
                cur.execute("""
                    UPDATE users
                    SET failed_attempts=%s
                    WHERE user_id=%s
                """, (failed_attempts, user_id))

            conn.commit()

            return jsonify({"error": "wrong password"}), 401

        # -----------------------------
        # 5. 로그인 성공
        # -----------------------------
        cur.execute("""
            UPDATE users
            SET failed_attempts=0,
                locked_until=NULL,
                last_login_at=NOW()
            WHERE user_id=%s
        """, (user_id,))
        conn.commit()

        # 세션 저장
        session["user_id"] = user_id
        session["username"] = username
        session["role"] = role

        # -----------------------------
        # 6. 비밀번호 변경 강제
        # -----------------------------
        if must_change_password:
            return jsonify({
                "success": True,
                "message": "must change password"
            })

        return jsonify({
            "success": True,
            "message": "login success",
            "user": {
                "user_id": user_id,
                "username": username,
                "role": role
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

# ==============================
# 현재 로그인 사용자 정보 조회 API
# ==============================
@auth_bp.route("/me", methods=["GET"])
def get_me():
    """
    현재 로그인된 사용자 정보를 반환하는 API
    """

    # -----------------------------
    # 1. 로그인 여부 확인
    # -----------------------------
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "not logged in"}), 401

    # -----------------------------
    # 2. DB 조회
    # -----------------------------
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT user_id, username, role, status
            FROM users
            WHERE user_id=%s
        """, (user_id,))

        user = cur.fetchone()

        if not user:
            return jsonify({"error": "user not found"}), 404

        # -----------------------------
        # 3. 결과 반환
        # -----------------------------
        return jsonify({
            "user_id": user[0],
            "username": user[1],
            "role": user[2],
            "status": user[3]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
