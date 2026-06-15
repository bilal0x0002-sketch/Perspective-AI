from __future__ import annotations

from typing import Any, Dict, List


DEFAULT_INSTRUCTIONS: Dict[str, Any] = {
    "always_retrieve": True,
    "citation_format": "【{id}†{source}】",
    "fallback_text": "I don't have that information in our current documentation. Please contact the relevant team.",
}


def apply_instructions(instructions: Dict[str, Any], evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply retrieval instructions to evidence and return enforcement results.

    Returns a dict with keys:
      - `used_evidence`: filtered evidence list
      - `compliant`: bool whether instructions were satisfied (e.g., evidence found when always_retrieve)
      - `fallback`: text to use when not compliant
    """
    instr = {**DEFAULT_INSTRUCTIONS}
    instr.update(instructions or {})

    used = evidence or []
    compliant = True
    if instr.get("always_retrieve") and not used:
        compliant = False

    return {
        "used_evidence": used,
        "compliant": compliant,
        "fallback": instr.get("fallback_text"),
        "citation_format": instr.get("citation_format"),
    }
