from flask import Blueprint, request, jsonify, session
from app.models import db, User, Cow, AuditLog
from app.utils.upload import save_secure_image
from functools import wraps

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# 관리자 확인용 데코레이터 (피드백 5번: 권한 분리)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"success": False, "error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# 소 등록 API (피드백 6, 7, 8번 통합)
@admin_bp.route("/cows", methods=["POST"])
@admin_required
def register_cow():
    # 1. 이미지 업로드 처리 (utils/upload.py 활용)
    file = request.files.get("file")
    safe_filename, error = save_secure_image(file, current_app.config['UPLOAD_DIR'])
    if error:
        return jsonify({"success": False, "error": error}), 400

    # 2. DB 저장 (PostgreSQL)
    new_cow = Cow(name=request.form.get("name"), ear_tag=request.form.get("ear_tag"))
    db.session.add(new_cow)
    db.session.commit()

    # 3. FAISS 갱신 로직 호출 (생략)
    
    # 4. 감사 로그 남기기 (피드백 10번)
    log = AuditLog(user_id=session.get("user_id"), action="COW_REGISTERED", detail=f"Cow ID: {new_cow.cow_id}")
    db.session.add(log)
    db.session.commit()

    return jsonify({"success": True, "cow_id": new_cow.cow_id})