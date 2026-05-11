from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import uuid
from app.services.pipeline import process_image
# 감사 로그 기록을 위한 함수 (나중에 audit_logs 테이블에 저장용)
# from app.utils.logger import log_audit 

identify_bp = Blueprint("identify", __name__)

# 조장님 피드백: .env 설정값 반영 및 확장자 제한
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@identify_bp.route("/api/identify", methods=["POST"])
def identify():
    # 1. 파일 존재 여부 확인
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
    
    file = request.files["file"]

    # 2. 파일명 및 확장자 검증 (보안 요건 8번 반영)
    if file.filename == "":
        return jsonify({"success": False, "error": "No selected file"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "File type not allowed"}), 400

    # 3. UUID 기반 안전한 파일명 생성 (보안 요건 8번 반영)
    # 조장님이 "filename 그대로 저장하면 위험하다"고 했으니 무조건 난수화해야 합니다.
    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_filename = f"{uuid.uuid4().hex}.{ext}"
    
    # 조장님이 지정한 업로드 디렉토리 사용 (없으면 생성)
    upload_dir = os.getenv("UPLOAD_DIR", "./data/uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, safe_filename)
    
    try:
        # 파일 저장
        file.save(file_path)

        # 4. 실제 파이프라인 실행
        result = process_image(file_path)

        # 5. 결과 반환 (조장님 요건: 매칭 안 되면 실패 처리)
        if not result:
            return jsonify({
                "success": False,
                "message": "식별된 소 정보가 없습니다."
            }), 404

        # 감사 로그 남기기 (보안 요건 10번 반영)
        # log_audit(action="IDENTIFY_SUCCESS", detail=f"File: {safe_filename}")

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        # 에러 발생 시 로그 기록 및 응답
        # log_audit(action="IDENTIFY_FAILED", detail=str(e))
        return jsonify({"success": False, "error": "Internal Server Error"}), 500