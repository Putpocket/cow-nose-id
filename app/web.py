from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os

# pipeline import
from app.services.pipeline import process_image


def create_app():
    # .env 로드
    load_dotenv()

    app = Flask(__name__)

    # 업로드 폴더 설정
    UPLOAD_FOLDER = "uploads"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # =========================
    # health check API
    # =========================
    @app.route("/health")
    def health():
        return {"status": "ok"}

    # =========================
    # 이미지 업로드 API
    # =========================
    @app.route("/upload", methods=["POST"])
    def upload():
        file = request.files.get("file")

        if not file:
            return jsonify({"error": "No file uploaded"})

        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        result = process_image(file_path)

        return jsonify(result)

    return app