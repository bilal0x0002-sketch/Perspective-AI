#!/usr/bin/env python
"""
Set up Azure Search index with the correct schema for personas.

Usage:
    python scripts/setup_index.py

Prerequisites:
    Set environment variables:
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_KEY
    - AZURE_SEARCH_INDEX
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
    index = os.getenv("AZURE_SEARCH_PERSONAS_INDEX") or "perspective-ai-index"
    
    if not endpoint or not api_key:
        print("Error: Missing environment variables")
        print("  - AZURE_SEARCH_ENDPOINT")
        print("  - AZURE_SEARCH_KEY")
        sys.exit(1)
    
    return endpoint.rstrip("/"), api_key, index


def create_index_schema() -> dict:
    """Create the index schema for personas."""
    return {
        "name": "perspective-ai-index",
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
                "name": "name",
                "type": "Edm.String",
                "searchable": True,
                "filterable": False,
                "retrievable": True,
                "sortable": True,
                "facetable": False
            },
            {
                "name": "role",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": True,
                "facetable": True
            },
            {
                "name": "focus",
                "type": "Edm.String",
                "searchable": True,
                "filterable": False,
                "retrievable": True,
                "sortable": False,
                "facetable": False
            },
            {
                "name": "evidence_topics",
                "type": "Collection(Edm.String)",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": False,
                "facetable": True
            },
            {
                "name": "default_stance",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "sortable": False,
                "facetable": True
            },
            {
                "name": "key_issue",
                "type": "Edm.String",
                "searchable": True,
                "filterable": False,
                "retrievable": True,
                "sortable": False,
                "facetable": False
            },
            {
                "name": "category",
                "type": "Edm.String",
                "searchable": False,
                "filterable": True,
                "retrievable": True,
                "sortable": True,
                "facetable": True
            }
        ],
        "scoringProfiles": [],
        "similarity": {
            "@odata.type": "#Microsoft.Azure.Search.BM25Similarity"
        }
    }


def setup_index(endpoint: str, api_key: str, index_name: str) -> bool:
    """Create or update the Azure Search index."""
    url = f"{endpoint}/indexes/{index_name}?api-version=2023-11-01"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    schema = create_index_schema()
    
    try:
        # Try to update existing index
        response = requests.put(url, json=schema, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"✓ Index '{index_name}' created/updated successfully")
        print(f"\nFields in index:")
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
    print("Azure Search Index Setup")
    print("=" * 60)
    
    # Get Azure config
    endpoint, api_key, index = get_azure_config()
    print(f"Endpoint: {endpoint}")
    print(f"Index: {index}\n")
    
    # Setup index
    if setup_index(endpoint, api_key, index):
        print("\n✓ Index setup completed successfully")
        sys.exit(0)
    else:
        print("\n✗ Index setup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
