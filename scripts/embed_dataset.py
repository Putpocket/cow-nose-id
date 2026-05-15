import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings
from app.services.detector import NoseDetector
from app.services.embedder import DinoEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(description="Create embeddings from registered cow images.")
    parser.add_argument("--out-embeddings", default="data/embeddings.npy")
    parser.add_argument("--out-cow-ids", default="data/cow_ids_source.json")
    args = parser.parse_args()

    settings = get_settings()
    detector = NoseDetector(settings.yolo_weights_path, settings.device, settings.yolo_conf_threshold)
    embedder = DinoEmbedder(settings.dino_model_name, settings.device)

    pool = ConnectionPool(settings.database_url, kwargs={"row_factory": dict_row}, min_size=0, max_size=10)
    rows = []
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT cow_id, image_path
            FROM cow_images
            ORDER BY cow_id, id
            """
        ).fetchall()
    pool.close()

    if not rows:
        raise ValueError("No cow_images rows found.")

    embeddings = []
    cow_ids = []
    for row in rows:
        image_path = Path(row["image_path"])
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        image = Image.open(image_path).convert("RGB")
        crop, _ = detector.crop(image)
        embeddings.append(embedder.embed(crop)[0])
        cow_ids.append(int(row["cow_id"]))

    Path(args.out_embeddings).parent.mkdir(parents=True, exist_ok=True)
    np.save(args.out_embeddings, np.vstack(embeddings).astype("float32"))
    Path(args.out_cow_ids).write_text(json.dumps(cow_ids, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
