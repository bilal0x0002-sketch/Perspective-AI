from __future__ import annotations

from typing import List

from .perspectives import Perspective

# Personas are now loaded dynamically from Azure Search.
# See: agent/persona_retriever.py and PERSONA_SETUP.md
# To add/edit personas, modify data/personas.json and run: python scripts/upload_personas.py

PERSONA_DEFINITIONS = []
EXTENDED_PERSONA_METADATA = []
EXTENDED_PERSONA_DEFINITIONS = []

DEFAULT_POSITION_TEMPLATE = (
    "As a {role}, I evaluate {{query}} through the lens of {focus}. "
    "Based on the evidence, I conclude {{claim}}."
)


def extended_perspectives() -> List[Perspective]:
    """Return empty list - personas are loaded from Azure Search instead."""
    return []


def persona_registry() -> List[dict[str, str]]:
    """Return empty list - personas are loaded from Azure Search instead."""
    return []
