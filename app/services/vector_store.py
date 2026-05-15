import json
from pathlib import Path

import faiss
import numpy as np

from app.models import SearchMatch


class VectorStore:
    def __init__(self, index_path: str, ids_path: str) -> None:
        index_file = Path(index_path)
        ids_file = Path(ids_path)
        if not index_file.exists():
            raise FileNotFoundError(f"FAISS index not found: {index_file}")
        if not ids_file.exists():
            raise FileNotFoundError(f"FAISS id map not found: {ids_file}")

        self._index = faiss.read_index(str(index_file))
        self._cow_ids = [int(value) for value in json.loads(ids_file.read_text(encoding="utf-8"))]
        if self._index.ntotal != len(self._cow_ids):
            raise ValueError("FAISS index size does not match cow id map size.")

    def search(self, vector: np.ndarray, limit: int = 5) -> list[SearchMatch]:
        scores, indices = self._index.search(vector.astype("float32"), limit)
        matches: list[SearchMatch] = []
        for rank, (score, index) in enumerate(zip(scores[0], indices[0]), start=1):
            if index < 0:
                continue
            matches.append(SearchMatch(rank=rank, cow_id=self._cow_ids[int(index)], similarity=float(score)))
        return matches
