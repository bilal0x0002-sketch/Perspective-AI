from __future__ import annotations

from typing import Any, Dict, List
from .knowledge import KnowledgeBaseAdapter
import concurrent.futures


class KnowledgeBaseManager:
    """Manage named knowledge bases composed of one or more adapters.

    Usage:
      manager = KnowledgeBaseManager()
      manager.register_kb("default", [adapter1, adapter2])
      results = manager.search("default", perspective, query)
    """

    def __init__(self):
        self.kbs: Dict[str, List[KnowledgeBaseAdapter]] = {}

    def register_kb(self, name: str, adapters: List[KnowledgeBaseAdapter]) -> None:
        self.kbs[name] = adapters

    def search(self, kb_name: str, perspective_name: str, query: str, top: int = 5) -> List[Dict[str, Any]]:
        adapters = self.kbs.get(kb_name) or []
        if not adapters:
            return []

        results: List[Dict[str, Any]] = []

        # Query adapters in parallel
        def _call(adapter):
            try:
                return adapter.search(perspective_name, query)
            except Exception:
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(adapters))) as ex:
            futures = [ex.submit(_call, a) for a in adapters]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res:
                    results.extend(res)

        # simple dedupe by id (preserve order)
        seen = set()
        merged: List[Dict[str, Any]] = []
        for item in results:
            item_id = item.get("id") or item.get("source") or str(hash(item.get("text")))
            if item_id in seen:
                continue
            seen.add(item_id)
            merged.append(item)

        # return top N
        return merged[:top]
