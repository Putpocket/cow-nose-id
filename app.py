# Flask 서버 생성 및 실행 파일

from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os

# .env 환경변수 로드
load_dotenv()

# pipeline 함수 import
from services.pipeline import process_image

app = Flask(__name__)

# 업로드 폴더 설정
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# 이미지 업로드 API
@app.route("/upload", methods=["POST"])
def upload():
    # 요청에서 파일 가져오기
    file = request.files.get("file")

    if not file:
        return jsonify({"error": "No file uploaded"})

    # 파일 저장 경로
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    # 파일 저장
    file.save(file_path)

    # pipeline 실행
    result = process_image(file_path)

    # 결과 반환
    return jsonify(result)


# 서버 실행
if __name__ == "__main__":
    app.run(debug=True)