from io import BytesIO
import threading

from PIL import Image
import torch

from app.config import Settings
from app.db import Database
from app.models import IdentifyResponse
from app.services.detector import NoseDetector
from app.services.embedder import DinoEmbedder
from app.services.vector_store import VectorStore


class IdentificationPipeline:
    def __init__(self, settings: Settings, database: Database) -> None:
        self._lock = threading.Lock()
        self._settings = settings
        self._database = database
        self._detector = NoseDetector(
            settings.yolo_weights_path,
            settings.device,
            settings.yolo_conf_threshold,
        )
        self._embedder = DinoEmbedder(settings.dino_model_name, settings.device)
        self._vectors = VectorStore(settings.faiss_index_path, settings.faiss_ids_path)

    def identify(self, image_bytes: bytes) -> IdentifyResponse:
        with self._lock:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            crop, crop_box = self._detector.crop(image)
            vector = self._embedder.embed(crop)
            matches = self._vectors.search(vector)
            best = matches[0] if matches else None
            if best is None:
                return IdentifyResponse(
                    matched=False,
                    best_similarity=0.0,
                    threshold=self._settings.similarity_threshold,
                    cow=None,
                    matches=[],
                    crop_box=crop_box,
                )

            cow = self._database.get_cow_with_owner(best.cow_id)
            matched = best.similarity >= self._settings.similarity_threshold and cow is not None
            return IdentifyResponse(
                matched=matched,
                best_similarity=best.similarity,
                threshold=self._settings.similarity_threshold,
                cow=cow if matched else None,
                matches=matches,
                crop_box=crop_box,
            )

    def close(self) -> None:
        self._detector = None
        self._embedder = None
        self._vectors = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
