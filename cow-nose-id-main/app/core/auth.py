# app/core/auth.py

from app.core.security import verify_password
from app.db import get_connection

def login_user(username, password):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT user_id, password_hash, role, status FROM users WHERE username=%s",
            (username,)
        )
        user = cur.fetchone()

        if not user:
            return None

        user_id, password_hash, role, status = user

        # 비활성 계정 차단
        if status != "active":
            return None

        # 비밀번호 검증
        if not verify_password(password, password_hash):
            return None

        return {
            "user_id": user_id,
            "username": username,
            "role": role
        }

    finally:
        cur.close()
        conn.close()