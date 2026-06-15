"""
Persona retrieval from Azure Search.

This module provides functions to load persona/bot data from Azure Search
instead of hardcoded files.
"""

import os
from typing import List
import requests

from .perspectives import Perspective


def get_personas_from_azure(limit: int = 100) -> List[Perspective] | None:
    """
    Fetch personas from Azure Search index.
    
    Returns None if not configured, otherwise returns list of Perspectives.
    """
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_KEY")
    index = os.getenv("AZURE_SEARCH_PERSONAS_INDEX") or "perspective-ai-index"
    
    if not endpoint or not api_key:
        return None
    
    try:
        url = f"{endpoint}/indexes/{index}/docs/search?api-version=2023-11-01"
        headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
        
        payload = {
            "search": "*",
            "searchMode": "all",
            "top": limit,
            "select": "id,name,role,focus,evidence_topics,default_stance,key_issue,category"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        personas = []
        
        for doc in result.get("value", []):
            try:
                # Parse evidence_topics (may be space-separated or JSON array)
                topics = doc.get("evidence_topics", "")
                if isinstance(topics, str):
                    topics = [t.strip() for t in topics.split(",") if t.strip()]
                
                persona = Perspective(
                    name=doc.get("name", ""),
                    role=doc.get("role", ""),
                    focus=doc.get("focus", ""),
                    evidence_topics=topics,
                    default_stance=doc.get("default_stance", "mixed"),
                    key_issue=doc.get("key_issue", "")
                )
                personas.append(persona)
            except Exception as e:
                print(f"Warning: Failed to parse persona {doc.get('id')}: {e}")
                continue
        
        if personas:
            print(f"Loaded {len(personas)} personas from Azure Search")
            return personas
        
    except Exception as e:
        print(f"Warning: Failed to fetch personas from Azure: {e}")
    
    return None
