#!/usr/bin/env python
"""
Upload personas/bots from data/personas.json to Azure Search index.

Usage:
    python scripts/upload_personas.py

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


def load_personas(file_path: str) -> list:
    """Load personas from JSON file."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found")
        sys.exit(1)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


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


def get_index_schema(endpoint: str, api_key: str, index: str) -> dict:
    """Get the schema of the Azure Search index."""
    url = f"{endpoint}/indexes/{index}?api-version=2023-11-01"
    headers = {"api-key": api_key}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        schema = response.json()
        return schema
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not fetch index schema: {e}")
        return {}


def upload_personas(personas: list, endpoint: str, api_key: str, index: str) -> bool:
    """Upload personas to Azure Search."""
    url = f"{endpoint}/indexes/{index}/docs/index?api-version=2023-11-01"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    # Prepare documents for upload
    documents = {
        "value": [
            {
                "@search.action": "upload",
                "id": p["id"],
                "name": p["name"],
                "role": p["role"],
                "focus": p["focus"],
                "evidence_topics": p["evidence_topics"],
                "default_stance": p["default_stance"],
                "key_issue": p["key_issue"],
                "category": p.get("category", "extended")
            }
            for p in personas
        ]
    }
    
    try:
        response = requests.post(url, json=documents, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ Successfully uploaded {len(personas)} personas")
        print(f"Response: {json.dumps(result, indent=2)}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Upload failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


def main():
    print("=" * 60)
    print("Persona Upload Tool")
    print("=" * 60)
    
    # Load personas
    personas_file = os.path.join(os.path.dirname(__file__), "..", "data", "personas.json")
    personas = load_personas(personas_file)
    print(f"Loaded {len(personas)} personas from {personas_file}")
    
    # Get Azure config
    endpoint, api_key, index = get_azure_config()
    print(f"Target: {endpoint}/indexes/{index}")
    
    # Get and display index schema
    schema = get_index_schema(endpoint, api_key, index)
    if schema and "fields" in schema:
        field_names = [f["name"] for f in schema["fields"]]
        print(f"Available fields: {', '.join(field_names)}")
    
    # Upload
    if upload_personas(personas, endpoint, api_key, index):
        print("\n✓ Upload completed successfully")
        sys.exit(0)
    else:
        print("\n✗ Upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
