from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from psycopg import errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._pool = ConnectionPool(
            settings.database_url,
            kwargs={"row_factory": dict_row},
            min_size=0,
            max_size=10,
            open=False,
        )
        self._is_open = False

    def open(self) -> None:
        if self._is_open:
            return
        self._pool.open()
        self._is_open = True

    def close(self) -> None:
        if not self._is_open:
            return
        self._pool.close()
        self._is_open = False

    @contextmanager
    def connection(self) -> Iterator:
        with self._pool.connection() as conn:
            yield conn

    def ensure_schema(self) -> None:
        schema_path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
        statements = [
            statement.strip()
            for statement in schema_path.read_text(encoding="utf-8").split(";")
            if statement.strip()
        ]
        with self.connection() as conn:
            for statement in statements:
                conn.execute(statement)

    def ensure_security_schema(self) -> None:
        with self.connection() as conn:
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'")
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false")
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0")
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ")
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ")
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS password_history (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id BIGSERIAL PRIMARY KEY,
                    actor_user_id BIGINT REFERENCES users(id),
                    actor_username TEXT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    detail TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs(actor_user_id)")

    def bootstrap_admin(self, username: str, password: str) -> None:
        with self.connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            if count > 0:
                return
            password_hash = generate_password_hash(password)
            row = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, must_change_password, password_changed_at)
                VALUES (%s, %s, 'admin', true, now())
                RETURNING id
                """,
                (username, password_hash),
            ).fetchone()
            conn.execute(
                "INSERT INTO password_history (user_id, password_hash) VALUES (%s, %s)",
                (row["id"], password_hash),
            )

    def get_login_user(self, username: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    username,
                    password_hash,
                    role,
                    status,
                    must_change_password,
                    failed_attempts,
                    locked_until
                FROM users
                WHERE username = %s
                """,
                (username,),
            ).fetchone()
        return dict(row) if row is not None else None

    def authenticate_user(self, username: str, password: str) -> dict | None:
        row = self.get_login_user(username)
        if row is None or row["status"] != "active" or not check_password_hash(row["password_hash"], password):
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "must_change_password": row["must_change_password"],
        }

    def get_user(self, user_id: int) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT id, username, role, status, must_change_password
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "status": row["status"],
            "must_change_password": row["must_change_password"],
        }

    def create_user(self, username: str, password: str, role: str = "user") -> int:
        password_hash = generate_password_hash(password)
        try:
            with self.connection() as conn:
                row = conn.execute(
                    """
                    INSERT INTO users (username, password_hash, role, must_change_password, password_changed_at)
                    VALUES (%s, %s, %s, true, now())
                    RETURNING id
                    """,
                    (username, password_hash, role),
                ).fetchone()
                conn.execute(
                    "INSERT INTO password_history (user_id, password_hash) VALUES (%s, %s)",
                    (row["id"], password_hash),
                )
        except errors.UniqueViolation as exc:
            raise ValueError("이미 사용 중인 아이디입니다.") from exc
        return int(row["id"])

    def update_user_password(self, user_id: int, password: str, force_change: bool = False) -> None:
        self._reject_reused_password(user_id, password)
        password_hash = generate_password_hash(password)
        with self.connection() as conn:
            result = conn.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    must_change_password = %s,
                    failed_attempts = 0,
                    locked_until = NULL,
                    password_changed_at = now()
                WHERE id = %s
                """,
                (password_hash, force_change, user_id),
            )
            if result.rowcount != 0:
                conn.execute(
                    "INSERT INTO password_history (user_id, password_hash) VALUES (%s, %s)",
                    (user_id, password_hash),
                )
        if result.rowcount == 0:
            raise ValueError("계정을 찾을 수 없습니다.")

    def change_own_password(self, user_id: int, current_password: str, new_password: str) -> None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], current_password):
            raise ValueError("현재 비밀번호가 올바르지 않습니다.")
        self.update_user_password(user_id, new_password, force_change=False)

    def disable_user(self, user_id: int, current_user_id: int | None) -> None:
        if current_user_id == user_id:
            raise ValueError("현재 로그인한 계정은 비활성화할 수 없습니다.")
        with self.connection() as conn:
            user = conn.execute(
                "SELECT id, role, status FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
            if user is None:
                raise ValueError("계정을 찾을 수 없습니다.")
            if user["role"] == "admin" and user["status"] == "active":
                admin_count = conn.execute(
                    "SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND status = 'active'"
                ).fetchone()["count"]
                if admin_count <= 1:
                    raise ValueError("마지막 활성 관리자 계정은 비활성화할 수 없습니다.")
            conn.execute(
                """
                UPDATE users
                SET status = 'disabled', locked_until = NULL
                WHERE id = %s
                """,
                (user_id,),
            )

    def enable_user(self, user_id: int) -> None:
        with self.connection() as conn:
            result = conn.execute(
                """
                UPDATE users
                SET status = 'active', failed_attempts = 0, locked_until = NULL
                WHERE id = %s
                """,
                (user_id,),
            )
        if result.rowcount == 0:
            raise ValueError("계정을 찾을 수 없습니다.")

    def delete_user(self, user_id: int, current_user_id: int | None) -> None:
        self.disable_user(user_id, current_user_id)

    def list_users(self) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    username,
                    role,
                    status,
                    must_change_password,
                    failed_attempts,
                    locked_until::text AS locked_until,
                    last_login_at::text AS last_login_at,
                    created_at::text AS created_at
                FROM users
                ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_login_failure(self, username: str, max_attempts: int, lockout_seconds: int) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, failed_attempts FROM users WHERE username = %s",
                (username,),
            ).fetchone()
            if row is None:
                return False
            attempts = int(row["failed_attempts"]) + 1
            locked = attempts >= max_attempts
            conn.execute(
                """
                UPDATE users
                SET failed_attempts = %s,
                    locked_until = CASE WHEN %s THEN now() + make_interval(secs => %s) ELSE locked_until END
                WHERE id = %s
                """,
                (attempts, locked, lockout_seconds, row["id"]),
            )
        return locked

    def clear_login_failures(self, user_id: int) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE users
                SET failed_attempts = 0,
                    locked_until = NULL,
                    last_login_at = now()
                WHERE id = %s
                """,
                (user_id,),
            )

    def add_audit_log(
        self,
        actor_user_id: int | None,
        actor_username: str | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        detail: str | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    actor_user_id,
                    actor_username,
                    action,
                    target_type,
                    target_id,
                    ip_address,
                    user_agent,
                    detail
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (actor_user_id, actor_username, action, target_type, target_id, ip_address, user_agent, detail),
            )

    def list_audit_logs(self, limit: int = 200) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    created_at::text AS created_at,
                    actor_username,
                    action,
                    target_type,
                    target_id,
                    ip_address,
                    detail
                FROM audit_logs
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _reject_reused_password(self, user_id: int, password: str, history_limit: int = 3) -> None:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT password_hash
                FROM password_history
                WHERE user_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, history_limit),
            ).fetchall()
        for row in rows:
            if check_password_hash(row["password_hash"], password):
                raise ValueError("최근 사용한 비밀번호는 다시 사용할 수 없습니다.")

    def list_cows(self) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id,
                    c.ear_tag,
                    c.name,
                    c.breed,
                    c.sex,
                    c.birth_date::text AS birth_date,
                    o.name AS owner_name,
                    o.farm_name
                FROM cows c
                JOIN owners o ON o.id = c.owner_id
                ORDER BY c.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_cow_record(self, cow_id: int) -> dict | None:
        query = """
            SELECT
                c.id,
                c.owner_id,
                c.ear_tag,
                c.name AS cow_name,
                c.breed,
                c.sex,
                c.birth_date::text AS birth_date,
                c.notes,
                o.name AS owner_name,
                o.phone AS owner_phone,
                o.farm_name,
                o.farm_address
            FROM cows c
            JOIN owners o ON o.id = c.owner_id
            WHERE c.id = %s
        """
        with self.connection() as conn:
            row = conn.execute(query, (cow_id,)).fetchone()
        return dict(row) if row is not None else None

    def update_cow_with_owner(
        self,
        cow_id: int,
        owner_name: str,
        owner_phone: str | None,
        farm_name: str | None,
        farm_address: str | None,
        ear_tag: str,
        cow_name: str | None,
        breed: str | None,
        sex: str | None,
        birth_date: str | None,
        notes: str | None,
    ) -> None:
        try:
            with self.connection() as conn:
                row = conn.execute(
                    "SELECT owner_id FROM cows WHERE id = %s",
                    (cow_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("소 정보를 찾을 수 없습니다.")
                conn.execute(
                    """
                    UPDATE owners
                    SET name = %s, phone = %s, farm_name = %s, farm_address = %s
                    WHERE id = %s
                    """,
                    (owner_name, owner_phone, farm_name, farm_address, row["owner_id"]),
                )
                conn.execute(
                    """
                    UPDATE cows
                    SET ear_tag = %s,
                        name = %s,
                        breed = %s,
                        sex = %s,
                        birth_date = NULLIF(%s, '')::date,
                        notes = %s
                    WHERE id = %s
                    """,
                    (ear_tag, cow_name, breed, sex, birth_date, notes, cow_id),
                )
        except errors.UniqueViolation as exc:
            raise ValueError("이미 등록된 개체번호입니다.") from exc

    def replace_cow_images(self, cow_id: int, image_paths: list[str]) -> list[str]:
        with self.connection() as conn:
            exists = conn.execute("SELECT id FROM cows WHERE id = %s", (cow_id,)).fetchone()
            if exists is None:
                raise ValueError("소 정보를 찾을 수 없습니다.")
            old_rows = conn.execute(
                "SELECT image_path FROM cow_images WHERE cow_id = %s",
                (cow_id,),
            ).fetchall()
            conn.execute("DELETE FROM cow_images WHERE cow_id = %s", (cow_id,))
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO cow_images (cow_id, image_path)
                    VALUES (%s, %s)
                    """,
                    [(cow_id, image_path) for image_path in image_paths],
                )
        return [row["image_path"] for row in old_rows]

    def replace_cow_image(self, cow_id: int, image_path: str) -> list[str]:
        return self.replace_cow_images(cow_id, [image_path])

    def delete_cow(self, cow_id: int) -> list[str]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT owner_id FROM cows WHERE id = %s",
                (cow_id,),
            ).fetchone()
            if row is None:
                raise ValueError("소 정보를 찾을 수 없습니다.")
            image_rows = conn.execute(
                "SELECT image_path FROM cow_images WHERE cow_id = %s",
                (cow_id,),
            ).fetchall()
            conn.execute("DELETE FROM cow_images WHERE cow_id = %s", (cow_id,))
            conn.execute("DELETE FROM cows WHERE id = %s", (cow_id,))
            remaining = conn.execute(
                "SELECT COUNT(*) AS count FROM cows WHERE owner_id = %s",
                (row["owner_id"],),
            ).fetchone()["count"]
            if remaining == 0:
                conn.execute("DELETE FROM owners WHERE id = %s", (row["owner_id"],))
        return [image["image_path"] for image in image_rows]

    def create_cow_with_owner(
        self,
        owner_name: str,
        owner_phone: str | None,
        farm_name: str | None,
        farm_address: str | None,
        ear_tag: str,
        cow_name: str | None,
        breed: str | None,
        sex: str | None,
        birth_date: str | None,
        notes: str | None,
        image_paths: list[str],
    ) -> int:
        try:
            with self.connection() as conn:
                owner = conn.execute(
                    """
                    INSERT INTO owners (name, phone, farm_name, farm_address)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (owner_name, owner_phone, farm_name, farm_address),
                ).fetchone()
                cow = conn.execute(
                    """
                    INSERT INTO cows (owner_id, ear_tag, name, breed, sex, birth_date, notes)
                    VALUES (%s, %s, %s, %s, %s, NULLIF(%s, '')::date, %s)
                    RETURNING id
                    """,
                    (owner["id"], ear_tag, cow_name, breed, sex, birth_date, notes),
                ).fetchone()
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO cow_images (cow_id, image_path)
                        VALUES (%s, %s)
                        """,
                        [(cow["id"], image_path) for image_path in image_paths],
                    )
        except errors.UniqueViolation as exc:
            raise ValueError("이미 등록된 개체번호입니다.") from exc
        return int(cow["id"])

    def get_cow_with_owner(self, cow_id: int) -> dict | None:
        query = """
            SELECT
                c.id AS cow_id,
                c.ear_tag,
                c.name AS cow_name,
                c.breed,
                c.sex,
                c.birth_date::text AS birth_date,
                c.notes,
                o.id AS owner_id,
                o.name AS owner_name,
                o.phone,
                o.farm_name,
                o.farm_address
            FROM cows c
            JOIN owners o ON o.id = c.owner_id
            WHERE c.id = %s
        """
        with self.connection() as conn:
            row = conn.execute(query, (cow_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["cow_id"],
            "ear_tag": row["ear_tag"],
            "name": row["cow_name"],
            "breed": row["breed"],
            "sex": row["sex"],
            "birth_date": row["birth_date"],
            "notes": row["notes"],
            "owner": {
                "id": row["owner_id"],
                "name": row["owner_name"],
                "phone": row["phone"],
                "farm_name": row["farm_name"],
                "farm_address": row["farm_address"],
            },
        }
