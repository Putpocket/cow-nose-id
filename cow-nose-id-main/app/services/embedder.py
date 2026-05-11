import torch
from PIL import Image
import torchvision.transforms as T

class DinoEmbedder:
    def __init__(self, model_name="facebook/dinov2-base"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # DINOv2는 공개 모델을 바로 다운로드해서 사용 가능
        self.model = torch.hub.load('facebook/dinov2', model_name).to(self.device)
        self.model.eval()

    def extract(self, image_path):
        """이미지를 넣으면 고차원 특징 벡터를 추출"""
        img = Image.open(image_path).convert('RGB')
        # ... 전처리 로직 ...
        with torch.no_grad():
            embedding = self.model(img) # 벡터 생성
        return embedding.cpu().numpy()