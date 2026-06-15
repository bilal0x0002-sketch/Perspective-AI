#!/usr/bin/env python
"""
Set up Azure Search index for evidence documents (policy briefs, research, reports).

Usage:
    python scripts/setup_evidence_index.py

Prerequisites:
    Set environment variables:
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_KEY
    - AZURE_SEARCH_INDEX (or use default "perspective-ai-evidence")
"""

import json
import os
import sys
import requests
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


def create_evidence_index_schema() -> dict:
    """Create the index schema for evidence documents."""
    return {
        "name": "perspective-ai-evidence",
        "fields": [
            {
                "name": "id",
                "type": "Edm.String",
                "key": True,
                "searchable": False,
                "filterable": False,
                "retrievable": True,
                "sortable": False,
                "facetable": False
            },
            {
                "name": "content",
                "type": "Edm.String",
                "searchable": True,
                "filterable": False,
                "retrievable": True,
                "sortable": False,
                "facetable": False,
                "analyzer": "standard"
            },
            {
                "name": "source",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": True,
                "facetable": True
            },
            {
                "name": "url",
                "type": "Edm.String",
                "searchable": False,
                "filterable": False,
                "retrievable": True,
                "sortable": False,
                "facetable": False
            },
            {
                "name": "category",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": True,
                "facetable": True
            },
            {
                "name": "author",
                "type": "Edm.String",
                "searchable": True,
                "filterable": False,
                "retrievable": True,
                "sortable": True,
                "facetable": False
            },
            {
                "name": "date",
                "type": "Edm.DateTimeOffset",
                "searchable": False,
                "filterable": True,
                "retrievable": True,
                "sortable": True,
                "facetable": False
            },
            {
                "name": "relevance_keywords",
                "type": "Collection(Edm.String)",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": False,
                "facetable": True
            },
            {
                "name": "personas",
                "type": "Collection(Edm.String)",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": False,
                "facetable": True
            },
            {
                "name": "stance",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": False,
                "facetable": True
            }
        ],
        "scoringProfiles": [],
        "similarity": {
            "@odata.type": "#Microsoft.Azure.Search.BM25Similarity"
        }
    }


def setup_evidence_index(endpoint: str, api_key: str, index_name: str) -> bool:
    """Create or update the Azure Search evidence index."""
    url = f"{endpoint}/indexes/{index_name}?api-version=2023-11-01"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    schema = create_evidence_index_schema()
    
    try:
        # Try to update existing index
        response = requests.put(url, json=schema, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"✓ Evidence index '{index_name}' created/updated successfully")
        print(f"\nFields in evidence index:")
        for field in schema["fields"]:
            print(f"  - {field['name']} ({field['type']})")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Index setup failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


def main():
    print("=" * 60)
    print("Azure Search Evidence Index Setup")
    print("=" * 60)
    
    # Get Azure config
    endpoint, api_key, index = get_azure_config()
    print(f"Endpoint: {endpoint}")
    print(f"Index: {index}\n")
    
    # Setup index
    if setup_evidence_index(endpoint, api_key, index):
        print("\n✓ Evidence index setup completed successfully")
        print("\nNext steps:")
        print("1. Upload evidence documents using scripts/upload_evidence.py")
        print("2. Or upload documents via Azure Portal bulk import")
        print("3. Run debate system with --mode real")
        sys.exit(0)
    else:
        print("\n✗ Evidence index setup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
