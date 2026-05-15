from pathlib import Path

from PIL import Image
from ultralytics import YOLO


class NoseDetector:
    def __init__(self, weights_path: str, device: str, conf_threshold: float = 0.25) -> None:
        path = Path(weights_path)
        if not path.exists():
            raise FileNotFoundError(f"YOLO weights not found: {path}")
        self._model = YOLO(str(path))
        self._device = device
        self._conf_threshold = conf_threshold

    def crop(self, image: Image.Image) -> tuple[Image.Image, list[int]]:
        results = self._model.predict(
            image,
            device=self._device,
            conf=self._conf_threshold,
            verbose=False,
        )
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            raise ValueError("No cow nose region was detected.")

        best_index = int(boxes.conf.argmax().item())
        xyxy = boxes.xyxy[best_index].detach().cpu().numpy().round().astype(int).tolist()
        width, height = image.size
        x1, y1, x2, y2 = xyxy
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(x1 + 1, min(x2, width))
        y2 = max(y1 + 1, min(y2, height))
        return image.crop((x1, y1, x2, y2)), [x1, y1, x2, y2]
