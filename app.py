# Flask 서버를 생성하기 위한 라이브러리 import
from flask import Flask, request, jsonify

# 우리가 만든 파이프라인 함수 import
from services.pipeline import process_image

# Flask 애플리케이션 객체 생성
app = Flask(__name__)


# /upload 경로로 POST 요청이 들어오면 실행되는 API
@app.route("/upload", methods=["POST"])
def upload():
    
    # 클라이언트가 업로드한 파일 가져오기
    # "image"는 프론트에서 보내는 key 이름
    file = request.files["image"]

    # 서버에 파일 저장 경로 지정
    # uploads 폴더에 파일 이름 그대로 저장
    path = f"uploads/{file.filename}"

    # 실제로 파일을 해당 경로에 저장
    file.save(path)

    # 저장된 이미지 경로를 파이프라인에 전달하여 처리
    result = process_image(path)

    # 처리 결과를 JSON 형태로 클라이언트에 반환
    return jsonify(result)