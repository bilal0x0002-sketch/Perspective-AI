from __future__ import annotations

from typing import Any, List
import requests
from requests.exceptions import RequestException


class KnowledgeBaseAdapter:
    """Base adapter interface for knowledge sources."""

    def search(self, perspective_name: str, query: str) -> List[dict[str, Any]]:
        raise NotImplementedError()


class AzureSearchAdapter(KnowledgeBaseAdapter):
    """Adapter for Azure Cognitive Search / Foundry search indexes.

    This is a minimal adapter that performs a POST /docs/search call and
    returns structured evidence entries with id, text, source, url, score, metadata.
    """

    def __init__(self, endpoint: str, api_key: str, index: str):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.index = index

    def search(self, perspective: Any, query: str) -> List[dict[str, Any]]:
        # Build persona-specific search query using focus and evidence_topics
        perspective_name = perspective.name if hasattr(perspective, 'name') else perspective
        search_terms = [query]
        
        # Add persona's focus and evidence topics if available for context-aware search
        if hasattr(perspective, 'focus') and perspective.focus:
            search_terms.append(perspective.focus)
        if hasattr(perspective, 'evidence_topics') and perspective.evidence_topics:
            search_terms.extend(perspective.evidence_topics)
        
        search_query = " ".join(search_terms)
        print(f"[{perspective_name}] Searching for: {search_query}")
        
        search_url = f"{self.endpoint}/indexes/{self.index}/docs/search?api-version=2023-11-01"
        
        payload = {
            "search": search_query,
            "top": 10,
            "queryType": "simple",
            "select": "*",
            "searchMode": "any",
        }
        
        # Add OData filter to limit by persona if we have the name
        if isinstance(perspective_name, str) and perspective_name.strip():
            # Correct OData syntax for collection contains: personas/any(p: p eq 'PersonaName')
            payload["filter"] = f"personas/any(p: p eq '{perspective_name}')"
            print(f"[{perspective_name}] Applying filter: {payload['filter']}")
        
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        try:
            response = requests.post(search_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
        except RequestException as exc:
            print(f"[{perspective_name}] Search error: {exc}")
            # If filter fails, try without filter (fallback)
            if "filter" in payload:
                print(f"[{perspective_name}] Filter failed, retrying without filter")
                del payload["filter"]
                payload["queryType"] = "simple"
                try:
                    response = requests.post(search_url, json=payload, headers=headers, timeout=30)
                    response.raise_for_status()
                except RequestException:
                    raise exc
            else:
                raise

        result = response.json()
        print(f"[{perspective_name}] Raw response: {result}")
        documents = result.get("value", [])
        print(f"[{perspective_name}] Found {len(documents)} documents")
        
        # Debug: show first document structure
        if documents:
            print(f"[{perspective_name}] Sample doc keys: {list(documents[0].keys())}")
        
        # Client-side filtering: only keep documents relevant to this persona
        filtered_documents = []
        if isinstance(perspective_name, str) and perspective_name.strip():
            for doc in documents:
                personas_list = doc.get("personas", [])
                # Handle both array and comma-separated string formats
                if isinstance(personas_list, str):
                    personas_list = [p.strip() for p in personas_list.split(",")]
                
                # Debug first document
                if doc == documents[0]:
                    print(f"[{perspective_name}] First doc personas: {personas_list}")
                
                # Check if this persona is in the document's personas list
                if any(p.strip().lower() == perspective_name.lower() for p in personas_list):
                    filtered_documents.append(doc)
            
            print(f"[{perspective_name}] After persona filtering: {len(filtered_documents)} documents")
            documents = filtered_documents if filtered_documents else documents[:5]  # Fallback to first 5 if no matches
        else:
            documents = documents[:5]
        print(f"[{perspective_name}] Found {len(documents)} documents")

        evidence: List[dict[str, Any]] = []
        for doc in documents:
            text = self._extract_text(doc)
            if not text:
                continue
            source = self._extract_source(doc)
            doc_id = doc.get("id") or doc.get("@search.documentKey") or source
            score = doc.get("@search.score") or doc.get("score") or None
            url = None
            if isinstance(doc.get("metadata_storage_path"), str):
                url = doc.get("metadata_storage_path")

            evidence.append({
                "id": str(doc_id),
                "text": text,
                "source": source,
                "url": url,
                "score": float(score) if score is not None else None,
                "metadata": doc.get("metadata", {}),
            })

        if not evidence:
            evidence.append(
                {
                    "id": "none",
                    "text": "No relevant evidence was found in the configured knowledge base.",
                    "source": "search",
                    "url": None,
                    "score": 0.0,
                    "metadata": {},
                }
            )

        return evidence

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


class BlobAdapter(KnowledgeBaseAdapter):
    """Adapter for Azure Blob Storage.

    This adapter lists blobs in a container and downloads content for simple
    text extraction. It requires `azure-storage-blob` to be installed.

    Expected connection configuration:
    - `connection_string` (preferred), or
    - `account_url` and `credential`.
    """

    def __init__(self, connection_string: str | None = None, container: str | None = None, account_url: str | None = None, credential: str | None = None):
        self.connection_string = connection_string
        self.container = container
        self.account_url = account_url
        self.credential = credential

        try:
            from azure.storage.blob import BlobServiceClient

            if self.connection_string:
                self.client = BlobServiceClient.from_connection_string(self.connection_string)
            elif self.account_url and self.credential:
                self.client = BlobServiceClient(account_url=self.account_url, credential=self.credential)
            else:
                self.client = None
        except Exception:
            self.client = None

    def search(self, perspective_name: str, query: str) -> List[dict[str, Any]]:
        results: List[dict[str, Any]] = []
        if not self.client or not self.container:
            return results

        container_client = self.client.get_container_client(self.container)
        try:
            blob_list = container_client.list_blobs()
        except Exception:
            return results

        # Naive approach: download first N blobs and do simple text matching
        for idx, blob in enumerate(blob_list):
            if idx >= 10:
                break
            try:
                blob_client = container_client.get_blob_client(blob)
                stream = blob_client.download_blob()
                data = stream.readall()

                text = ""
                name = (blob.name or "").lower()
                try:
                    if name.endswith('.pdf'):
                        from PyPDF2 import PdfReader
                        import io
                        reader = PdfReader(io.BytesIO(data))
                        pages = []
                        for p in reader.pages:
                            try:
                                pages.append(p.extract_text() or "")
                            except Exception:
                                pages.append("")
                        text = "\n".join(pages)
                    elif name.endswith('.docx'):
                        from docx import Document
                        import io
                        doc = Document(io.BytesIO(data))
                        paragraphs = [p.text for p in doc.paragraphs if p.text]
                        text = "\n".join(paragraphs)
                    else:
                        text = data.decode('utf-8', errors='replace')
                except Exception:
                    # fallback to raw decode
                    try:
                        text = data.decode('utf-8', errors='replace')
                    except Exception:
                        text = str(data)

                # simple keyword filter
                if query.lower() in text.lower() or perspective_name.lower() in text.lower():
                    results.append({
                        "id": blob.name,
                        "text": text[:2000],
                        "source": f"blob:{self.container}",
                        "url": None,
                        "score": None,
                        "metadata": {"blob_size": getattr(blob, 'size', None)},
                    })
            except Exception:
                continue

        return results


class SharePointAdapter(KnowledgeBaseAdapter):
    """Adapter for SharePoint via Microsoft Graph Search.

    This adapter performs a client-credentials OAuth flow to get a token for
    Microsoft Graph and then issues a search query to the Graph Search API.

    Required environment/configuration for use:
      - `client_id`, `client_secret`, `tenant_id` (Azure AD app with appropriate Graph permissions)
      - optionally `site_id` to scope searches to a specific SharePoint site

    If credentials are not provided or the call fails, the adapter returns an
    empty list so the system can continue operating in degraded mode.
    """

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, tenant_id: str | None = None, site_id: str | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.site_id = site_id
        self._token = None

    def _get_token(self) -> str | None:
        if self._token:
            return self._token
        if not (self.client_id and self.client_secret and self.tenant_id):
            return None

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        try:
            import requests

            r = requests.post(token_url, data=data, timeout=10)
            r.raise_for_status()
            body = r.json()
            self._token = body.get("access_token")
            return self._token
        except Exception:
            return None

    def search(self, perspective_name: str, query: str) -> List[dict[str, Any]]:
        token = self._get_token()
        if not token:
            return []

        search_url = "https://graph.microsoft.com/v1.0/search/query"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {
            "requests": [
                {
                    "entityTypes": ["driveItem", "listItem", "site"],
                    "query": {"queryString": f"{perspective_name} {query}"},
                    "from": 0,
                    "size": 5,
                }
            ]
        }

        try:
            import requests

            r = requests.post(search_url, json=body, headers=headers, timeout=20)
            r.raise_for_status()
            resp = r.json()
        except Exception:
            return []

        results: List[dict[str, Any]] = []
        try:
            requests_block = resp.get("value", [])
            if not requests_block:
                # Some tenants return top-level 'value' with requests
                requests_block = resp.get("requests", [])

            # iterate hitsContainers for each request
            for req in requests_block:
                for container in req.get("hitsContainers", []):
                    for hit in container.get("hits", []):
                        resource = hit.get("resource", {})
                        doc_id = resource.get("id") or hit.get("hitId")
                        title = resource.get("title") or resource.get("name") or resource.get("webUrl")
                        summary = hit.get("summary") or resource.get("summary") or title
                        web_url = resource.get("webUrl")
                        results.append({
                            "id": str(doc_id),
                            "text": str(summary),
                            "source": "sharepoint",
                            "url": web_url,
                            "score": None,
                            "metadata": {"resource": resource},
                        })
        except Exception:
            return []

        return results
