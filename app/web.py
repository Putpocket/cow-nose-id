# app/web.py
from flask import Flask
from app.config import settings
from app.api.auth import auth_bp
from app.api.identify import identify_bp

def create_app():
    """
    Flask 애플리케이션 팩토리: 보안 설정 및 블루프린트 등록
    """
    app = Flask(__name__)

    # 1. 팀원분이 정의한 보안 설정 적용 (조장님 피드백 9번 반영)
    app.secret_key = settings.secret_key
    app.config['SESSION_COOKIE_HTTPONLY'] = settings.session_cookie_httponly
    app.config['SESSION_COOKIE_SECURE'] = settings.session_cookie_secure
    app.config['SESSION_COOKIE_SAMESITE'] = settings.session_cookie_samesite
    app.config['PERMANENT_SESSION_LIFETIME'] = settings.session_lifetime_minutes * 60
    app.config['MAX_CONTENT_LENGTH'] = settings.max_upload_mb * 1024 * 1024 # 업로드 용량 제한

    # 2. 보안 헤더 설정 (조장님 피드백 9번: CSP, X-Frame-Options 등)
    @app.after_request
    def set_security_headers(response):
        response.headers['Content-Security-Policy'] = settings.content_security_policy
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = settings.referrer_policy
        return response

    # 3. 시스템 헬스 체크 API
    @app.route("/health")
    def health():
        return {
            "status": "ok", 
            "message": "VibeCoding Backend is running with security settings"
        }

    # 4. 기능별 Blueprint 등록
    app.register_blueprint(auth_bp)
    app.register_blueprint(identify_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)