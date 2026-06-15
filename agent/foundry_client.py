from __future__ import annotations

import os
import re
from typing import Any, List

import requests
from requests.exceptions import RequestException
from .telemetry import telemetry


class FoundryClient:
    def __init__(self, mode: str = "offline"):
        self.mode = mode.lower()
        self._endpoint = None
        self._api_key = None
        self._index = None
        self._kb_manager = None
        if self.mode == "real":
            self._endpoint, self._api_key, self._index = self._load_config()
            # initialize a knowledge base manager with available adapters
            try:
                from .knowledge_manager import KnowledgeBaseManager
                from .knowledge import AzureSearchAdapter, BlobAdapter, SharePointAdapter

                manager = KnowledgeBaseManager()
                adapters = [AzureSearchAdapter(self._endpoint, self._api_key, self._index)]

                # optional blob adapter if configured
                blob_conn = (
                    os.getenv("AZURE_BLOB_CONNECTION_STRING")
                )
                blob_container = os.getenv("AZURE_BLOB_CONTAINER")
                if blob_conn and blob_container:
                    adapters.append(BlobAdapter(connection_string=blob_conn, container=blob_container))

                # optional SharePoint adapter if configured
                sp_client = os.getenv("SP_CLIENT_ID") or os.getenv("SHAREPOINT_CLIENT_ID")
                sp_secret = os.getenv("SP_CLIENT_SECRET") or os.getenv("SHAREPOINT_CLIENT_SECRET")
                sp_tenant = os.getenv("SP_TENANT_ID") or os.getenv("SHAREPOINT_TENANT_ID")
                sp_site = os.getenv("SP_SITE_ID") or os.getenv("SHAREPOINT_SITE_ID")
                if sp_client and sp_secret and sp_tenant:
                    adapters.append(SharePointAdapter(client_id=sp_client, client_secret=sp_secret, tenant_id=sp_tenant, site_id=sp_site))

                # Optionally enable semantic reranking around adapters
                enable_sem = os.getenv("ENABLE_SEMANTIC")
                if enable_sem and enable_sem.lower() in ("1", "true", "yes"):
                    try:
                        from .semantic import SemanticAdapter
                        model_name = os.getenv("EMBEDDING_MODEL") or "all-MiniLM-L6-v2"
                        adapters = [SemanticAdapter(a, model_name=model_name) for a in adapters]
                    except Exception:
                        # if sentence-transformers not available, continue with base adapters
                        pass

                manager.register_kb("default", adapters)
                self._kb_manager = manager
            except Exception:
                self._kb_manager = None

    def retrieve_evidence(self, perspective: Any, query: str) -> List[dict[str, str]]:
        telemetry.incr("retrieval_calls")
        # Accept both Perspective objects and string names for backward compatibility
        perspective_name = perspective.name if hasattr(perspective, 'name') else perspective
        
        if self.mode == "real":
            # prefer knowledge manager if available
            if self._kb_manager:
                results = self._kb_manager.search("default", perspective_name, query)
                print(f"Retrieved {len(results)} evidence documents for {perspective_name}")
                return results
            results = self._real_search(perspective, query)
            print(f"Retrieved {len(results)} evidence documents for {perspective_name}")
            return results
        return self._mock_evidence(perspective_name, query)

    def _load_config(self) -> tuple[str, str, str]:
        endpoint = os.getenv("FOUNDY_ENDPOINT") or os.getenv("AZURE_SEARCH_ENDPOINT")
        api_key = os.getenv("FOUNDY_API_KEY") or os.getenv("AZURE_SEARCH_KEY")
        index = os.getenv("FOUNDY_INDEX") or os.getenv("AZURE_SEARCH_EVIDENCE_INDEX") or "perspective-ai-evidence"

        if not endpoint or not api_key:
            raise RuntimeError(
                "Real mode requires FOUNDY_ENDPOINT / FOUNDY_API_KEY / FOUNDY_INDEX "
                "or AZURE_SEARCH_ENDPOINT / AZURE_SEARCH_KEY / AZURE_SEARCH_EVIDENCE_INDEX environment variables."
            )

        return endpoint.rstrip("/"), api_key, index

    def _mock_evidence(self, perspective_name: str, query: str) -> List[dict[str, str]]:
        """Mock evidence removed - use real Azure Search instead.
        
        For proper debate with real evidence, configure:
        - AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_EVIDENCE_INDEX
        - OR FOUNDY_ENDPOINT, FOUNDY_API_KEY, FOUNDY_INDEX
        - Then use mode='real'
        
        Without real evidence, fallback reasoning uses persona-aware keyword analysis.
        """
        return []

    def _real_search(self, perspective: Any, query: str) -> List[dict[str, str]]:
        try:
            from .knowledge import AzureSearchAdapter

            adapter = AzureSearchAdapter(self._endpoint, self._api_key, self._index)
            # Pass full perspective to AzureSearchAdapter for context-aware search
            return adapter.search(perspective, query)
        except Exception as exc:
            return [
                {
                    "id": "error",
                    "text": f"Search failed: {type(exc).__name__}: {str(exc)}",
                    "source": "search-error",
                    "url": None,
                    "score": 0.0,
                    "metadata": {},
                }
            ]

    def upload_documents(self, docs: List[dict[str, Any]]) -> dict[str, Any]:
        if self.mode != "real":
            raise RuntimeError("Document upload is only supported in real mode.")

        if not self._endpoint or not self._api_key or not self._index:
            raise RuntimeError(
                "Real mode requires FOUNDY_ENDPOINT / FOUNDY_API_KEY / FOUNDY_INDEX "
                "or AZURE_SEARCH_ENDPOINT / AZURE_SEARCH_KEY / AZURE_SEARCH_INDEX environment variables."
            )

        url = f"{self._endpoint.rstrip('/')}/indexes/{self._index}/docs/index?api-version=2021-04-30-Preview"
        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key,
        }
        payload = {"value": docs}

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        telemetry.incr("upload_calls")
        return response.json()

    def _extract_text(self, document: dict[str, Any]) -> str:
        if not isinstance(document, dict):
            return str(document)

        text_fields = [
            document.get("content"),
            document.get("text"),
            document.get("body"),
            document.get("answer"),
        ]
        for value in text_fields:
            if isinstance(value, str) and value.strip():
                return value.strip()

        for key, value in document.items():
            if isinstance(value, str) and value.strip():
                return value.strip()

        return "(document content unavailable)"

    def _extract_source(self, document: dict[str, Any]) -> str:
        source = document.get("metadata_storage_name") or document.get("source") or document.get("id")
        if source:
            return str(source)

        if "@search.documentKey" in document:
            return str(document["@search.documentKey"])

        return "unknown source"
