# YOLO에서 비문 위치를 찾는 함수 import
from services.yolo import detect_nose

# 이미지에서 특정 영역을 잘라내는 함수 import
from services.crop import crop_image

# DINO 모델로 이미지 → 벡터 변환 함수 import
from services.dino import extract_vector

# FAISS에서 유사 벡터를 찾는 함수 import
from services.faiss_search import search_similar

# PostgreSQL에서 소 정보를 조회하는 함수 import
from db.postgres import get_cow_info


# 전체 이미지 처리 파이프라인 함수 정의
def process_image(image_path):
    # image_path: 업로드된 이미지 파일 경로

    # 1. YOLO 모델을 사용하여 비문(nose) 위치 bounding box 검출
    # bbox는 [x1, y1, x2, y2] 형태라고 가정
    bbox = detect_nose(image_path)

    # 2. 원본 이미지에서 비문 영역만 잘라냄
    cropped = crop_image(image_path, bbox)

    # 3. 잘라낸 비문 이미지를 DINO 모델로 벡터화
    # 결과는 숫자 리스트(embedding vector)
    vector = extract_vector(cropped)

    # 4. FAISS를 사용하여 가장 유사한 벡터를 검색
    # 결과는 가장 유사한 소의 ID
    cow_id = search_similar(vector)

    # 5. PostgreSQL에서 해당 cow_id에 대한 정보 조회
    cow_info = get_cow_info(cow_id)

    # 최종 결과 반환 (프론트로 전달됨)
    return cow_info