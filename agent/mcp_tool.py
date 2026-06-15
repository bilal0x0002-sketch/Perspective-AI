from __future__ import annotations

from typing import Any, Dict


class MCPTool:
    """Lightweight MCPTool representation for connecting agents to knowledge bases.

    This is a small helper to build a tool descriptor that could be passed to an
    external agent framework. It does not implement a network server — it only
    captures the configuration and provides a `call` helper used by agents in-process.
    """

    def __init__(self, server_label: str, server_url: str, kb_name: str = "default"):
        self.server_label = server_label
        self.server_url = server_url
        self.kb_name = kb_name

    def descriptor(self) -> Dict[str, Any]:
        return {"label": self.server_label, "url": self.server_url, "kb": self.kb_name}

    def call(self, client, perspective: str, query: str) -> Any:
        """Call the provided client (e.g., FoundryClient or a HTTP endpoint) to retrieve evidence.

        `client` is expected to expose a `retrieve_evidence(perspective, query)` method.
        """
        if not hasattr(client, "retrieve_evidence"):
            raise RuntimeError("Client does not support retrieve_evidence")
        return client.retrieve_evidence(perspective, query)
