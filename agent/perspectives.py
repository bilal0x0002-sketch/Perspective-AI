from dataclasses import dataclass
from typing import List

@dataclass
class Perspective:
    name: str
    role: str
    focus: str
    evidence_topics: List[str]
    default_stance: str
    key_issue: str


def default_perspectives() -> List[Perspective]:
    return [
        Perspective(
            name="Financial Analyst",
            role="Financial Analyst",
            focus="economic impacts, business activity, and market incentives",
            evidence_topics=["urban economics", "transport reports", "downtown commerce"],
            default_stance="conditional support",
            key_issue="economic transition risk",
        ),
        Perspective(
            name="Sustainability Consultant",
            role="Sustainability Consultant",
            focus="pollution, climate, and long-term ecological health",
            evidence_topics=["air quality studies", "climate impact reports", "health costs"],
            default_stance="support",
            key_issue="air quality and health",
        ),
        Perspective(
            name="Infrastructure Designer",
            role="Infrastructure Designer",
            focus="mobility, land use, and city design",
            evidence_topics=["transit planning", "street design", "land use"],
            default_stance="conditional support",
            key_issue="accessibility and transport design",
        ),
        Perspective(
            name="Community Member",
            role="Community Member",
            focus="everyday convenience, equity, and local quality of life",
            evidence_topics=["accessibility studies", "equity reports", "mobility surveys"],
            default_stance="opposed without better access",
            key_issue="equity and mobility",
        ),
        Perspective(
            name="Retailer",
            role="Retailer",
            focus="customer traffic, operating costs, and neighborhood vitality",
            evidence_topics=["local commerce", "delivery logistics", "customer behavior"],
            default_stance="cautious",
            key_issue="delivery logistics and foot traffic",
        ),
    ]


def load_perspectives(mode: str = "auto") -> List[Perspective]:
    """
    Load perspectives from Azure Search (if real mode and configured) or fallback to defaults.
    
    Args:
        mode: "auto" (try Azure, fallback to default), "azure", or "default"
    
    Returns:
        List of Perspective objects
    """
    if mode in ("auto", "azure"):
        try:
            from .persona_retriever import get_personas_from_azure
            personas = get_personas_from_azure()
            if personas:
                return personas
        except ImportError:
            pass
    
    # Fallback to default
    return default_perspectives()


def persona_registry() -> List[dict[str, str]]:
    try:
        from .bots import persona_registry as registry_from_bots

        return registry_from_bots()
    except ImportError:
        return [
            {
                "name": p.name,
                "role": p.role,
                "focus": p.focus,
                "key_issue": p.key_issue,
                "description": f"{p.role} focused on {p.focus}, with a core concern of {p.key_issue}.",
            }
            for p in default_perspectives()
        ]
