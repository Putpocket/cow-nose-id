import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
REQUIREMENTS_PATH = ROOT / "requirements.txt"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"


def main():
    args = parse_args()
    os.chdir(ROOT)

    ensure_env_file()
    env = load_env_file(ENV_PATH)
    apply_env(env)

    if not args.skip_install:
        ensure_requirements()

    ensure_runtime_dirs(env)

    if not args.skip_db:
        prepare_database(env)

    print("")
    print("Starting Cow Nose ID server")
    print(f"- URL: http://{args.host}:{args.port}")
    print("- Login page: /login")
    print("- Admin page: /admin")
    print("")

    from app import create_app

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Cow Nose ID Flask server.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))
    parser.add_argument("--debug", action="store_true", default=os.getenv("FLASK_DEBUG", "1") == "1")
    parser.add_argument("--skip-install", action="store_true", help="Skip pip install -r requirements.txt.")
    parser.add_argument("--skip-db", action="store_true", help="Skip schema setup and admin bootstrap.")
    return parser.parse_args()


def ensure_env_file():
    if ENV_PATH.exists():
        return
    if not ENV_EXAMPLE_PATH.exists():
        print("Warning: .env and .env.example are missing. Continuing with process environment.")
        return
    shutil.copyfile(ENV_EXAMPLE_PATH, ENV_PATH)
    print("Created .env from .env.example. Check DB and secret settings when you can.")


def load_env_file(path):
    values = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def apply_env(values):
    for key, value in values.items():
        os.environ.setdefault(key, value)


def ensure_requirements():
    missing = missing_required_modules()
    if not missing:
        print("Python packages are already available.")
        return
    if not REQUIREMENTS_PATH.exists():
        print(f"Warning: requirements.txt not found. Missing modules: {', '.join(missing)}")
        return
    print(f"Installing Python packages because these modules are missing: {', '.join(missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)])


def missing_required_modules():
    checks = {
        "flask": "flask",
        "dotenv": "python-dotenv",
        "psycopg2": "psycopg2-binary",
        "PIL": "Pillow",
        "werkzeug": "Werkzeug",
    }
    missing = []
    for module_name, package_name in checks.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(package_name)
    return missing


def ensure_runtime_dirs(env):
    for key in ("UPLOAD_DIR", "BACKUP_DIR"):
        value = env.get(key) or os.getenv(key)
        if value:
            Path(value).mkdir(parents=True, exist_ok=True)

    log_file = env.get("LOG_FILE") or os.getenv("LOG_FILE")
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)


def prepare_database(env):
    database_url = env.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print("Warning: DATABASE_URL is empty. Skipping DB setup.")
        return

    try:
        import psycopg2
    except ImportError:
        print("Warning: psycopg2 is not installed. Skipping DB setup.")
        return

    try:
        conn = psycopg2.connect(database_url)
    except Exception as exc:
        print("Warning: could not connect to PostgreSQL.")
        print(f"- DATABASE_URL: {database_url}")
        print(f"- Reason: {exc}")
        print("Server will start, but login/admin/identify DB features may fail until DB is ready.")
        return

    try:
        apply_schema(conn)
        bootstrap_admin(conn, env)
    finally:
        conn.close()


def apply_schema(conn):
    if not SCHEMA_PATH.exists():
        print("Warning: sql/schema.sql not found. Skipping schema setup.")
        return
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Database schema is ready.")


def bootstrap_admin(conn, env):
    username = env.get("BOOTSTRAP_ADMIN_USERNAME") or os.getenv("BOOTSTRAP_ADMIN_USERNAME") or "admin"
    password = env.get("BOOTSTRAP_ADMIN_PASSWORD") or os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or "admin"
    if not username or not password:
        print("Skipping admin bootstrap because username or password is empty.")
        return

    from app.security import hash_password

    with conn.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE username=%s", (username,))
        existing = cur.fetchone()
        if existing:
            print(f"Admin account already exists: {username}")
            return
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role, status, must_change_password)
            VALUES (%s, %s, 'admin', 'active', FALSE)
            """,
            (username, hash_password(password)),
        )
    conn.commit()
    print(f"Created bootstrap admin account: {username}")


if __name__ == "__main__":
    main()
