from flask import Blueprint, jsonify, request

from app.security import save_secure_upload
from app.services.pipeline import process_image
# 감사 로그 기록을 위한 함수 (나중에 audit_logs 테이블에 저장용)
# from app.utils.logger import log_audit 

identify_bp = Blueprint("identify", __name__)

@identify_bp.route("/api/identify", methods=["POST"])
def identify():
    try:
        file_path = save_secure_upload(request.files.get("file"))
        result = process_image(file_path)

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

    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        # 에러 발생 시 로그 기록 및 응답
        # log_audit(action="IDENTIFY_FAILED", detail=str(e))
        return jsonify({"success": False, "error": "Internal Server Error"}), 500
