import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
import magic  # MIME 타입 검사용 (pip install python-magic 필요)

# 조장님 피드백 반영: 허용 확장자 및 최대 용량 설정
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB

def allowed_file(filename):
    """확장자 검증"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image(file_stream):
    """
    Pillow와 magic을 이용한 실제 이미지 및 MIME 타입 검증
    """
    # 1. MIME 타입 체크 (파일 헤더 분석)
    file_stream.seek(0)
    mime = magic.from_buffer(file_stream.read(2048), mime=True)
    file_stream.seek(0)
    
    if mime not in ['image/jpeg', 'image/png', 'image/webp']:
        return False, f"허용되지 않는 파일 형식입니다 (MIME: {mime})"

    # 2. Pillow를 이용한 이미지 손상 여부 확인
    try:
        with Image.open(file_stream) as img:
            img.verify()  # 이미지 파일이 깨졌는지 검증
        file_stream.seek(0)
        return True, None
    except Exception:
        return False, "유효하지 않거나 손상된 이미지 파일입니다."

def save_secure_image(file, upload_dir):
    """
    안전한 파일명으로 변환하여 이미지 저장
    """
    if not file or not allowed_file(file.filename):
        return None, "허용되지 않는 확장자입니다."

    # 조장님 요건: UUID 기반 파일명 저장 (경로 조작 방지)
    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_filename = f"{uuid.uuid4().hex}.{ext}"
    
    # 저장 경로 생성 및 검증
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, mode=0o755, exist_ok=True)
    
    file_path = os.path.join(upload_dir, safe_filename)
    
    # 실제 이미지 검증 실행
    is_valid, error_msg = validate_image(file.stream)
    if not is_valid:
        return None, error_msg

    # 파일 저장 (권한 제한 포함)
    file.save(file_path)
    os.chmod(file_path, 0o640) # 조장님 요구 권한 0o640 적용
    
    return safe_filename, None