#!/usr/bin/env python
"""
Upload evidence documents from data/evidence.json to Azure Search evidence index.

This script reads policy briefs, research papers, and reports from data/evidence.json
and uploads them to Azure Search. Each document can be tagged with relevant personas,
allowing evidence retrieval to be role-specific rather than identical for all personas.

Usage:
    python scripts/upload_evidence.py

To add more evidence documents:
    1. Edit data/evidence.json
    2. Add new documents with required fields (id, content, source, category, etc.)
    3. Run this script

Prerequisites:
    Set environment variables:
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_KEY
    - AZURE_SEARCH_INDEX (or use "perspective-ai-evidence")
"""

import json
import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def get_azure_config() -> tuple[str, str, str]:
    """Get Azure Search configuration from environment."""
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_KEY")
    index = os.getenv("AZURE_SEARCH_EVIDENCE_INDEX") or "perspective-ai-evidence"
    
    if not endpoint or not api_key:
        print("Error: Missing environment variables")
        print("  - AZURE_SEARCH_ENDPOINT")
        print("  - AZURE_SEARCH_KEY")
        print("  - AZURE_SEARCH_EVIDENCE_INDEX (optional)")
        sys.exit(1)
    
    return endpoint.rstrip("/"), api_key, index


def get_sample_evidence() -> list:
    """Load evidence documents from data/evidence.json."""
    import os
    evidence_file = os.path.join(os.path.dirname(__file__), "..", "data", "evidence.json")
    
    if not os.path.exists(evidence_file):
        print(f"Error: {evidence_file} not found")
        print("Create data/evidence.json with evidence documents")
        return []
    
    try:
        with open(evidence_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing data/evidence.json: {e}")
        return []
    except Exception as e:
        print(f"Error loading evidence: {e}")
        return []


def upload_evidence(documents: list, endpoint: str, api_key: str, index: str) -> bool:
    """Upload evidence documents to Azure Search."""
    url = f"{endpoint}/indexes/{index}/docs/index?api-version=2023-11-01"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    # Prepare documents for upload
    documents_payload = {
        "value": [
            {
                "@search.action": "upload",
                "id": doc["id"],
                "content": doc["content"],
                "source": doc["source"],
                "url": doc.get("url", ""),
                "category": doc.get("category", "general"),
                "author": doc.get("author", ""),
                "date": doc.get("date", datetime.now().isoformat()),
                "relevance_keywords": doc.get("relevance_keywords", []),
                "personas": doc.get("personas", []),
                "stance": doc.get("stance", "neutral")
            }
            for doc in documents
        ]
    }
    
    try:
        response = requests.post(url, json=documents_payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        successful = sum(1 for item in result.get("value", []) if item.get("status"))
        print(f"✓ Successfully uploaded {successful}/{len(documents)} evidence documents")
        
        if successful > 0:
            print(f"\nUploaded documents:")
            for item in result.get("value", []):
                if item.get("status"):
                    doc_id = item.get("key", "unknown")
                    print(f"  ✓ {doc_id} (HTTP {item.get('statusCode', 'N/A')})")
        
        return successful == len(documents)
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Upload failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


def main():
    print("=" * 60)
    print("Upload Evidence Documents")
    print("=" * 60)
    
    # Get Azure config
    endpoint, api_key, index = get_azure_config()
    print(f"Endpoint: {endpoint}")
    print(f"Index: {index}\n")
    
    # Get evidence from data/evidence.json
    evidence_docs = get_sample_evidence()
    
    if not evidence_docs:
        print("✗ No evidence documents found")
        print("  Create or check data/evidence.json")
        sys.exit(1)
    
    print(f"Loaded {len(evidence_docs)} evidence documents from data/evidence.json:")
    for doc in evidence_docs:
        print(f"  - {doc['id']}: {doc['category']} ({doc['source']})")
    
    print()
    
    # Upload
    if upload_evidence(evidence_docs, endpoint, api_key, index):
        print("\n✓ Evidence upload completed successfully")
        print("\nNow you can run debates with real evidence:")
        print("  python -m agent.main --query 'Your question?' --mode real")
        print("\nTo add more evidence documents:")
        print("  1. Edit data/evidence.json")
        print("  2. Run this script again")
        sys.exit(0)
    else:
        print("\n✗ Evidence upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
