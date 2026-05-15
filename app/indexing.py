from __future__ import annotations

import json
import logging
from pathlib import Path

import faiss
import numpy as np
from PIL import Image
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import Settings
from app.services.detector import NoseDetector
from app.services.embedder import DinoEmbedder


def rebuild_faiss_index(settings: Settings, logger: logging.Logger) -> int:
    detector = NoseDetector(settings.yolo_weights_path, settings.device, settings.yolo_conf_threshold)
    embedder = DinoEmbedder(settings.dino_model_name, settings.device)

    pool = ConnectionPool(settings.database_url, kwargs={"row_factory": dict_row}, min_size=0, max_size=10)
    try:
        with pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT cow_id, image_path
                FROM cow_images
                ORDER BY cow_id, id
                """
            ).fetchall()
    finally:
        pool.close()

    if not rows:
        logger.warning("FAISS rebuild skipped because no cow_images rows exist.")
        raise ValueError("No registered cow images found.")

    embeddings = []
    cow_ids = []
    for row in rows:
        image_path = Path(row["image_path"])
        if not image_path.exists():
            logger.warning("Skipping missing cow image during FAISS rebuild: %s", image_path)
            continue
        try:
            image = Image.open(image_path).convert("RGB")
            crop, _ = detector.crop(image)
            embedding = embedder.embed(crop)[0]
        except Exception as exc:
            logger.warning("Skipping cow image during FAISS rebuild: %s (%s)", image_path, exc)
            continue
        embeddings.append(embedding)
        cow_ids.append(int(row["cow_id"]))

    if not embeddings:
        logger.warning("FAISS rebuild skipped because no readable cow images exist.")
        raise ValueError("No cow images could be indexed. Check image paths and YOLO detection logs.")

    vectors = np.vstack(embeddings).astype("float32")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    index_path = Path(settings.faiss_index_path)
    ids_path = Path(settings.faiss_ids_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.parent.mkdir(parents=True, exist_ok=True)

    temp_index = index_path.with_suffix(index_path.suffix + ".tmp")
    temp_ids = ids_path.with_suffix(ids_path.suffix + ".tmp")
    faiss.write_index(index, str(temp_index))
    temp_ids.write_text(json.dumps(cow_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_index.replace(index_path)
    temp_ids.replace(ids_path)
    return len(cow_ids)
