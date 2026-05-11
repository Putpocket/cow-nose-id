import cv2
import numpy as np

class NoseDetector:
    def __init__(self, model_path=None):
        self.model_path = model_path
        # TODO: 모델 학습 완료 시 실제 YOLO 로드 로직 추가
        # self.model = YOLO(model_path) 
        pass

    def detect(self, image_path):
        """소의 비문 영역을 찾아 좌표(bbox)를 반환"""
        # 임시로 이미지 크기에 맞춘 가짜 bbox 반환 (학습 전까지)
        return [50, 50, 200, 200]