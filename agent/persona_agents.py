from __future__ import annotations

from typing import Any, Dict


class PersonaEngine:
    @staticmethod
    def build_initial(perspective_name: str, reasoned: dict[str, Any], stance: str, query: str) -> Dict[str, str]:
        # Use the LLM's unique conclusion (role-specific) if available, otherwise fall back to interpretation
        conclusion = reasoned.get("conclusion") or reasoned.get("interpretation") or "No clear conclusion available."
        implications = reasoned.get("implications") or []
        
        print(f"[PERSONA_ENGINE {perspective_name}] Has conclusion: {'conclusion' in reasoned}")
        print(f"[PERSONA_ENGINE {perspective_name}] Conclusion text: {conclusion[:100]}")
        
        # Handle implications safely - can be string, list, or other type
        if isinstance(implications, (str, bytes)):
            # implications is already a string
            impl_text = implications
        elif isinstance(implications, list):
            # implications is a list - filter and join
            impl_text = "; ".join([str(i) for i in implications if i]) if implications else "no clear implications"
        else:
            # fallback for other types
            impl_text = str(implications) if implications else "no clear implications"

        # Use the role-specific conclusion directly, which contains all needed context
        position = f"{conclusion} Policy stance: {stance}."

        return {"position": position, "argument": position}
