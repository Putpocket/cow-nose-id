import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel


class DinoEmbedder:
    def __init__(self, model_name: str, device: str) -> None:
        self._device = torch.device(device)
        self._processor = AutoImageProcessor.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name).to(self._device)
        self._model.eval()

    @torch.inference_mode()
    def embed(self, image: Image.Image) -> np.ndarray:
        inputs = self._processor(images=image.convert("RGB"), return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        outputs = self._model(**inputs)
        vector = outputs.pooler_output if outputs.pooler_output is not None else outputs.last_hidden_state[:, 0]
        vector = torch.nn.functional.normalize(vector, p=2, dim=1)
        return vector.detach().cpu().numpy().astype("float32")
