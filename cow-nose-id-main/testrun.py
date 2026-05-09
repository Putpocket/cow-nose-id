import argparse
import os
from itertools import count

from flask import jsonify, request, session


TEST_ACCOUNTS = {
    1: {
        "user_id": 1,
        "username": "admin",
        "password": "admin",
        "role": "admin",
        "status": "active",
    },
    2: {
        "user_id": 2,
        "username": "user",
        "password": "user",
        "role": "user",
        "status": "active",
    },
}

TEST_COWS = {
    1: {
        "cow_id": 1,
        "ear_tag": "TEST-001",
        "name": "테스트 소",
        "breed": "한우",
        "sex": "암",
        "birth_date": "",
        "notes": "테스트 데이터",
        "owner_name": "테스트 목장",
    }
}

account_ids = count(3)
cow_ids = count(2)


def main():
    args = parse_args()
    configure_test_env()

    from app import create_app

    app = create_app()
    install_test_routes(app)

    print("")
    print("Starting Cow Nose ID test server")
    print(f"- URL: http://{args.host}:{args.port}")
    print("- Test admin: admin / admin")
    print("- Test user: user / user")
    print("- PostgreSQL is not required in this mode.")
    print("")

    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Cow Nose ID server with in-memory test data.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))
    parser.add_argument("--debug", action="store_true", default=os.getenv("FLASK_DEBUG", "1") == "1")
    return parser.parse_args()


def configure_test_env():
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("UPLOAD_DIR", "./data/test-uploads")
    os.environ.setdefault("LOG_FILE", "./data/test-logs/app.log")
    os.environ.setdefault("SESSION_COOKIE_SECURE", "false")


def install_test_routes(app):
    app.view_functions["auth.login"] = test_login
    app.view_functions["auth.get_me"] = test_me
    app.view_functions["auth.logout"] = test_logout
    app.view_functions["identify.identify"] = test_identify
    app.view_functions["admin.list_accounts"] = test_list_accounts
    app.view_functions["admin.create_account"] = test_create_account
    app.view_functions["admin.delete_account"] = test_delete_account
    app.view_functions["admin.list_cows"] = test_list_cows
    app.view_functions["admin.create_cow"] = test_create_cow
    app.view_functions["admin.update_cow"] = test_update_cow
    app.view_functions["admin.delete_cow"] = test_delete_cow


def test_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    account = next((item for item in TEST_ACCOUNTS.values() if item["username"] == username), None)
    if not account or account["password"] != password:
        return jsonify({"success": False, "error": "wrong username or password"}), 401

    session["user_id"] = account["user_id"]
    session["username"] = account["username"]
    session["role"] = account["role"]
    return jsonify({
        "success": True,
        "message": "test login success",
        "user": public_account(account),
    })


def test_me():
    user_id = session.get("user_id")
    if not user_id or user_id not in TEST_ACCOUNTS:
        return jsonify({"error": "not logged in"}), 401
    return jsonify(public_account(TEST_ACCOUNTS[user_id]))


def test_logout():
    session.clear()
    return jsonify({"success": True})


def test_identify():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "No selected file"}), 400
    return jsonify({
        "success": True,
        "data": {
            "cow_id": 1,
            "ear_tag": "TEST-001",
            "name": "테스트 소",
            "owner_name": "테스트 목장",
            "confidence": "0.99",
            "status": "테스트 식별 성공",
        },
    })


def test_list_accounts():
    if not require_admin():
        return admin_error()
    return jsonify({"success": True, "accounts": [public_account(item) for item in TEST_ACCOUNTS.values()]})


def test_create_account():
    if not require_admin():
        return admin_error()
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "user").strip().lower()

    if not username or not password:
        return jsonify({"success": False, "error": "username and password are required"}), 400
    if role not in ("user", "admin", "super"):
        return jsonify({"success": False, "error": "invalid role"}), 400
    if any(item["username"] == username for item in TEST_ACCOUNTS.values()):
        return jsonify({"success": False, "error": "username already exists"}), 400

    user_id = next(account_ids)
    TEST_ACCOUNTS[user_id] = {
        "user_id": user_id,
        "username": username,
        "password": password,
        "role": role,
        "status": "active",
    }
    return jsonify({"success": True, "user_id": user_id}), 201


def test_delete_account(user_id):
    if not require_admin():
        return admin_error()
    if user_id == session.get("user_id"):
        return jsonify({"success": False, "error": "cannot delete current account"}), 400
    if user_id not in TEST_ACCOUNTS:
        return jsonify({"success": False, "error": "account not found"}), 404
    TEST_ACCOUNTS.pop(user_id)
    return jsonify({"success": True})


def test_list_cows():
    if not require_admin():
        return admin_error()
    return jsonify({"success": True, "cows": list(TEST_COWS.values())})


def test_create_cow():
    if not require_admin():
        return admin_error()
    data = request.get_json(silent=True) or {}
    if not (data.get("ear_tag") or "").strip():
        return jsonify({"success": False, "error": "ear_tag is required"}), 400
    cow_id = next(cow_ids)
    TEST_COWS[cow_id] = cow_from_payload(cow_id, data)
    return jsonify({"success": True, "cow_id": cow_id}), 201


def test_update_cow(cow_id):
    if not require_admin():
        return admin_error()
    if cow_id not in TEST_COWS:
        return jsonify({"success": False, "error": "cow not found"}), 404
    data = request.get_json(silent=True) or {}
    if not (data.get("ear_tag") or "").strip():
        return jsonify({"success": False, "error": "ear_tag is required"}), 400
    TEST_COWS[cow_id] = cow_from_payload(cow_id, data)
    return jsonify({"success": True})


def test_delete_cow(cow_id):
    if not require_admin():
        return admin_error()
    if cow_id not in TEST_COWS:
        return jsonify({"success": False, "error": "cow not found"}), 404
    TEST_COWS.pop(cow_id)
    return jsonify({"success": True})


def public_account(account):
    return {
        "user_id": account["user_id"],
        "username": account["username"],
        "role": account["role"],
        "status": account["status"],
    }


def cow_from_payload(cow_id, data):
    return {
        "cow_id": cow_id,
        "ear_tag": (data.get("ear_tag") or "").strip(),
        "name": (data.get("name") or "").strip(),
        "breed": (data.get("breed") or "").strip(),
        "sex": (data.get("sex") or "").strip(),
        "birth_date": data.get("birth_date") or "",
        "notes": (data.get("notes") or "").strip(),
        "owner_name": (data.get("owner_name") or "").strip(),
    }


def require_admin():
    return session.get("role") in ("admin", "super")


def admin_error():
    return jsonify({"success": False, "error": "Admin access required"}), 403


if __name__ == "__main__":
    main()
