# Cow Nose ID Backend

## Run
```bash
pip install -r requirements.txt
flask --app app.web:create_app run
```

## Core APIs
- GET /health
- POST /auth/login
- POST /auth/logout
- POST /auth/change-password
- GET /auth/me
- GET /me
- GET /api/csrf-token
- POST /api/identify

## Admin APIs
- GET /admin/users
- POST /admin/users
- POST /admin/users/{user_id}/password
- POST /admin/users/{user_id}/disable
- POST /admin/users/{user_id}/enable
- GET /admin/cows
- POST /admin/cows
- GET /admin/cows/{cow_id}
- PUT /admin/cows/{cow_id}
- DELETE /admin/cows/{cow_id}

## Notes
- Bootstrap admin is created from `BOOTSTRAP_ADMIN_USERNAME`/`BOOTSTRAP_ADMIN_PASSWORD` if missing.
- Passwords are hashed with Werkzeug and stored in DB only.
- Upload validation uses extension allowlist + header sniff + Pillow verify.
- Pipeline wiring follows detect->crop->embed->search->DB lookup with current service stubs.
