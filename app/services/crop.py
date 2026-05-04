# 이미지 처리를 위한 라이브러리 import
from PIL import Image

# 이미지에서 특정 영역을 자르는 함수
def crop_image(image_path, bbox):
    # image_path: 원본 이미지 경로
    # bbox: [x1, y1, x2, y2]

    # 이미지 열기
    img = Image.open(image_path)

    # bbox 기준으로 이미지 자르기
    cropped = img.crop(bbox)

    # 잘린 이미지 반환
    return cropped