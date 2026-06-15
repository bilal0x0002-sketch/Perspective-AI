from __future__ import annotations

import threading
from typing import Dict


class Telemetry:
    def __init__(self):
        self._lock = threading.Lock()
        self.stats: Dict[str, int] = {
            "retrieval_calls": 0,
            "citations_returned": 0,
            "fallbacks": 0,
        }

    def incr(self, key: str, amount: int = 1) -> None:
        with self._lock:
            if key not in self.stats:
                self.stats[key] = 0
            self.stats[key] += amount

    def get(self, key: str) -> int:
        with self._lock:
            return int(self.stats.get(key, 0))


# singleton telemetry instance used across agents
telemetry = Telemetry()
