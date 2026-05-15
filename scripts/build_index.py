import argparse
import json
from pathlib import Path

import faiss
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cosine-similarity FAISS index from embeddings.")
    parser.add_argument("--embeddings", required=True, help="Numpy .npy file with shape [N, D].")
    parser.add_argument("--cow-ids", required=True, help="JSON array of cow ids aligned with embeddings.")
    parser.add_argument("--out-index", default="data/cow_nose.faiss")
    parser.add_argument("--out-ids", default="data/cow_ids.json")
    args = parser.parse_args()

    embeddings = np.load(args.embeddings).astype("float32")
    if embeddings.ndim != 2:
        raise ValueError("Embeddings must be a 2D array.")
    faiss.normalize_L2(embeddings)

    cow_ids = json.loads(Path(args.cow_ids).read_text(encoding="utf-8"))
    if len(cow_ids) != embeddings.shape[0]:
        raise ValueError("cow id count must match embedding count.")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    Path(args.out_index).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, args.out_index)
    Path(args.out_ids).write_text(json.dumps(cow_ids, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
