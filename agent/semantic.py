from __future__ import annotations

from typing import Any, List, Dict

class SemanticAdapter:
    """Wraps a base adapter and ranks its results by embedding similarity.

    It requires `sentence-transformers` to be installed. The adapter calls the
    underlying adapter to fetch candidate documents, encodes them and the query,
    and returns the top-k items sorted by cosine similarity with `score` populated.
    """

    def __init__(self, base_adapter, model_name: str = "all-MiniLM-L6-v2"):
        self.base = base_adapter
        self.model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer, util
            self._model = SentenceTransformer(model_name)
            self._util = util
        except Exception:
            self._model = None
            self._util = None

    def search(self, perspective_name: str, query: str, top: int = 5) -> List[Dict[str, Any]]:
        candidates = self.base.search(perspective_name, query)
        if not candidates:
            return []
        texts = [c.get("text") or "" for c in candidates]

        if not self._model:
            # fallback: return candidates without scores
            return candidates[:top]

        # encode
        query_emb = self._model.encode(query, convert_to_tensor=True)
        doc_embs = self._model.encode(texts, convert_to_tensor=True)
        cos_scores = self._util.cos_sim(query_emb, doc_embs)[0]

        scored = []
        for idx, c in enumerate(candidates):
            score = float(cos_scores[idx].item())
            c_copy = dict(c)
            c_copy["score"] = score
            scored.append(c_copy)

        scored.sort(key=lambda d: d.get("score", 0.0), reverse=True)
        return scored[:top]
