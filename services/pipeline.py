# ==============================
# DB 조회 함수 import
# ==============================
from services.db.postgres import get_cow_info


# ==============================
# 전체 이미지 처리 파이프라인
# ==============================
def process_image(image_path):
    """
    이미지 처리 전체 파이프라인 (현재는 더미 기반)

    Args:
        image_path (str): 업로드된 이미지 경로

    Returns:
        dict: 소 정보
    """

    # ======================
    # 1. YOLO (더미)
    # ======================
    # 실제로는 detect_nose(image_path)
    bbox = [10, 10, 100, 100]

    # ======================
    # 2. Crop (더미)
    # ======================
    # 실제로는 crop_image(image_path, bbox)
    cropped = image_path

    # ======================
    # 3. DINO (더미 벡터)
    # ======================
    # 실제로는 extract_vector(cropped)
    vector = [0.1, 0.2, 0.3]

    # ======================
    # 4. FAISS (더미 결과)
    # ======================
    # 실제로는 search_similar(vector)
    cow_id = 1

    # ======================
    # 5. DB 조회
    # ======================
    cow_info = get_cow_info(cow_id)

    return cow_info