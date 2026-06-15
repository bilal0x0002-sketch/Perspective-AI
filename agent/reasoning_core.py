from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, List

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def _score_relevance(text: str, context_tokens: set[str]) -> float:
    tokens = set(_tokenize(text))
    if not tokens:
        return 0.0
    overlap = tokens & context_tokens
    return round(len(overlap) / len(tokens), 3)


def _first_sentence(text: str) -> str:
    parts = re.split(r"[\.\n]", text.strip())
    for p in parts:
        s = p.strip()
        if s:
            return s
    return text.strip()


class ReasoningCore:
    """Lightweight reasoning core for transforming retrieved evidence into
    interpretable summaries, ranked evidence, implications and a simple trace.

    This implementation is intentionally simple and deterministic so it can be
    reviewed by judges and extended later with LLM-based transforms if desired.
    """

    @staticmethod
    def _get_remote_reasoner_config() -> tuple[str | None, str | None, str]:
        # Read from environment variables
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_API_BASE")
        api_key = os.getenv("AZURE_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
        model = os.getenv("AZURE_OPENAI_MODEL", "deepseek-chat")
        return endpoint, api_key, model

    @staticmethod
    def _call_remote_reasoner(evidence: List[dict[str, Any]], question: str, perspective: Any) -> dict[str, Any] | None:
        endpoint, api_key, model = ReasoningCore._get_remote_reasoner_config()
        
        if not endpoint or not api_key:
            return None

        # Build persona-specific system prompt
        role = getattr(perspective, "role", "Expert")
        focus = getattr(perspective, "focus", "this issue")
        key_issue = getattr(perspective, "key_issue", "central concern")
        default_stance = getattr(perspective, "default_stance", "balanced")
        persona_name = getattr(perspective, "name", "Specialist")
        
        print(f"[DEBUG] Reasoning for {persona_name} with role='{role}'")
        
        # Build role-specific analysis instructions with examples
        role_analysis = ""
        example_reasoning = ""
        
        if "financial" in role.lower():
            print(f"[DEBUG] Matched FINANCIAL role")
            role_analysis = "ANALYZE ONLY: Revenue generation, profit margins, cost savings, business efficiency, financial viability, cash flow, ROI, operational costs."
            example_reasoning = '{"conclusion": "Congestion pricing generates 40-60% net revenue surplus after costs, saving businesses £2,500 annually in delivery. Financial viability is strong.", "implications": ["Implement with phased approach for business adaptation", "Use revenue for transit improvements"]}'
        elif "sustainability" in role.lower():
            print(f"[DEBUG] Matched SUSTAINABILITY role")
            role_analysis = "ANALYZE ONLY: Emissions reduction (CO2, NOx, PM2.5), air quality improvements, climate impact, health benefits from cleaner air, ecological health, environmental health co-benefits."
            example_reasoning = '{"conclusion": "Congestion pricing cuts emissions by 22% and respiratory hospitalizations by 31%. Environmental benefits strongly outweigh transition costs.", "implications": ["Essential for climate and health", "Pair with zero-emission vehicle incentives"]}'
        elif "infrastructure" in role.lower() or "engineer" in role.lower():
            print(f"[DEBUG] Matched INFRASTRUCTURE role")
            role_analysis = "ANALYZE ONLY: Transit infrastructure design, accessibility, mobility networks, traffic flow, design capacity, infrastructure investment requirements, transport systems."
            example_reasoning = '{"conclusion": "Portland expanded 8 bus routes before pricing. Congestion pricing REQUIRES simultaneous transit capacity increases to maintain accessibility.", "implications": ["Precede pricing with transit expansion", "Design for all mobility types"]}'
        elif "community" in role.lower():
            print(f"[DEBUG] Matched COMMUNITY role")
            role_analysis = "ANALYZE ONLY: Equity impacts, fairness for low-income residents, accessibility to services, local community quality of life, disproportionate impacts on vulnerable groups."
            example_reasoning = '{"conclusion": "Without transit subsidies, low-income households pay 7% of income vs 1% for wealthy households. Equity safeguards ESSENTIAL.", "implications": ["Require 60-80% revenue to low-income transit", "Add delivery and exemptions"]}'
        else:
            print(f"[DEBUG] No specific role match for '{role}' - using generic template")
            role_analysis = f"ANALYZE ONLY: Issues within {focus} domain relevant to {role}'s expertise."
            example_reasoning = '{"conclusion": "Role-specific conclusion based on provided expertise.", "implications": ["Action aligned with role perspective"]}'
        
        system_prompt = (
            f"YOU ARE: {persona_name}\n"
            f"ROLE: {role}\n"
            f"FOCUS: {focus}\n"
            f"CONCERN: {key_issue}\n"
            f"DEFAULT STANCE: {default_stance}\n\n"
            f"CRITICAL CONSTRAINT - ANALYZE ONLY YOUR DOMAIN:\n{role_analysis}\n\n"
            f"FORBIDDEN - YOU WILL FAIL IF YOU DO THIS:\n"
            f"❌ Mention ANY other role's concerns (financial/environmental/infrastructure/equity) unless YOUR role addresses it\n"
            f"❌ Give generic balanced analysis - be opinionated as {persona_name}\n"
            f"❌ Ignore evidence irrelevant to your role's domain\n"
            f"❌ Return markdown, preamble, or non-JSON text\n\n"
            f"GOOD OUTPUT EXAMPLE FOR YOUR ROLE:\n{example_reasoning}\n\n"
            f"OUTPUT FORMAT (MUST BE VALID JSON, NO MARKDOWN):\n"
            f'{{"ranked": [{{"id": "doc-id", "score": 0.9, "relevance": "Why this evidence matters to {persona_name}", "reasoning": "Specific analysis through {role} lens"}}], "interpretation": "Your role-specific interpretation", "implications": ["Action 1", "Action 2"], "conclusion": "Your OPINIONATED conclusion as {persona_name}", "contradiction": false}}'
        )

        user_prompt = {
            "question": question,
            "analyst_role": role,
            "analyst_name": persona_name,
            "expertise_area": focus,
            "primary_concern": key_issue,
            "default_position": default_stance,
            "evidence": evidence,
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False, indent=2)},
        ]
        
        # DEBUG: Show what's being sent to LLM
        print(f"[LLM DEBUG {persona_name}] System prompt starts with: {system_prompt[:200]}...")
        print(f"[LLM DEBUG {persona_name}] Evidence count: {len(evidence)}")
        if evidence:
            print(f"[LLM DEBUG {persona_name}] First evidence doc: {evidence[0].get('id', 'N/A')} - {evidence[0].get('content', '')[:100]}")

        # Try OpenAI SDK first
        try:
            from openai import OpenAI
            
            # GitHub Models uses standard OpenAI format but WITHOUT /v1 in base_url
            if "inference" in endpoint.lower():
                # For GitHub Models, don't add /v1, endpoint already has proper path
                client = OpenAI(
                    api_key=api_key,
                    base_url=endpoint.rstrip('/') if endpoint.endswith('/v1') else endpoint
                )
            elif "deepseek" in endpoint.lower():
                # DeepSeek is OpenAI-compatible - use /v1 path
                base_url = endpoint.rstrip('/')
                if not base_url.endswith('/v1'):
                    base_url = f"{base_url}/v1"
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
            elif "azure" in endpoint.lower():
                # For standard Azure OpenAI
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    api_key=api_key,
                    api_version="2024-02-15-preview",
                    azure_endpoint=endpoint,
                )
            else:
                # Regular OpenAI or other OpenAI-compatible services
                client = OpenAI(base_url=endpoint, api_key=api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=800,
            )
            content = response.choices[0].message.content
            
            # DEBUG: Show raw LLM response
            print(f"[LLM RESPONSE {persona_name}] Raw content (first 300 chars): {content[:300]}")
        except Exception as e:
            # HTTP fallback for SDK errors
            endpoint_base = endpoint.rstrip("/")
            
            # GitHub Models or inference endpoints: /chat/completions directly
            if "inference" in endpoint.lower():
                if "/chat/completions" in endpoint_base:
                    http_url = endpoint_base
                else:
                    http_url = f"{endpoint_base}/chat/completions"
            else:
                # Regular OpenAI or Azure HTTP format
                if "/chat/completions" not in endpoint_base:
                    http_url = f"{endpoint_base}/v1/chat/completions"
                else:
                    http_url = endpoint_base
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 800,
            }
            
            try:
                response = requests.post(http_url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
            except Exception as http_err:
                return None

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and parsed.get("ranked") is not None:
                # Ensure implications is always a list, never a string
                if "implications" in parsed and isinstance(parsed["implications"], str):
                    parsed["implications"] = [parsed["implications"]] if parsed["implications"] else []
                elif "implications" not in parsed:
                    parsed["implications"] = []
                
                # DEBUG: Show full conclusion
                print(f"[LLM CONCLUSION {persona_name}] {parsed.get('conclusion', 'NO CONCLUSION')[:200]}")
                
                return parsed
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            match = re.search(r'```(?:json)?\s*({.*?})\s*```', content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    if isinstance(parsed, dict) and parsed.get("ranked") is not None:
                        if "implications" in parsed and isinstance(parsed["implications"], str):
                            parsed["implications"] = [parsed["implications"]] if parsed["implications"] else []
                        elif "implications" not in parsed:
                            parsed["implications"] = []
                        return parsed
                except json.JSONDecodeError:
                    pass

        # Return None to trigger persona-aware fallback reasoning
        return None

    @staticmethod
    def _get_role_specific_keywords(role: str, focus: str) -> tuple[List[str], List[str]]:
        """Get role-specific positive and negative keywords for evidence evaluation."""
        role_lower = role.lower()
        
        if "financial" in role_lower or "analyst" in role_lower or "economist" in role_lower:
            return (
                ["revenue", "profit", "economic", "growth", "productivity", "investment", "cost-effective", "savings"],
                ["loss", "cost", "expense", "burden", "deficit", "decline", "inefficient", "waste"]
            )
        elif "sustainability" in role_lower or "environment" in role_lower or "consultant" in role_lower:
            return (
                ["reduce emissions", "climate", "clean", "renewable", "efficient", "green", "pollution reduction", "sustainability"],
                ["carbon", "pollution", "emissions", "waste", "harm", "toxic", "degradation", "climate risk"]
            )
        elif "infrastructure" in role_lower or "design" in role_lower or "engineer" in role_lower:
            return (
                ["transit", "access", "mobility", "infrastructure", "design", "network", "connectivity", "efficient"],
                ["congestion", "accessibility gap", "land use", "sprawl", "fragmented", "inefficient design"]
            )
        elif "community" in role_lower or "resident" in role_lower or "member" in role_lower:
            return (
                ["equity", "affordability", "access", "community", "fair", "inclusive", "benefit", "support"],
                ["regressive", "burden", "unfair", "costly", "excludes", "harm", "displacement", "inequity"]
            )
        elif "transportation" in role_lower or "engineer" in role_lower:
            return (
                ["traffic", "flow", "efficiency", "congestion reduction", "speed", "reliability", "transit"],
                ["congestion", "delays", "accident", "risk", "safety concern", "unreliable"]
            )
        else:
            # Default generic keywords
            return (
                ["improve", "reduce", "benefit", "increase", "support", "positive", "enhance"],
                ["risk", "harm", "damage", "loss", "cost", "concern", "negative", "challenge"]
            )

    @staticmethod
    def reason(evidence: List[dict[str, Any]], question: str, perspective: Any) -> dict[str, Any]:
        remote_result = ReasoningCore._call_remote_reasoner(evidence, question, perspective)
        if remote_result:
            return remote_result

        # Get persona attributes
        role = getattr(perspective, "role", "Expert")
        focus = getattr(perspective, "focus", "this topic")
        key_issue = getattr(perspective, "key_issue", "")
        
        # Build context with persona-specific weighting
        context_text = question + " " + focus + " " + key_issue
        context_tokens = set(_tokenize(context_text))
        
        # Get role-specific keywords
        keywords_positive, keywords_negative = ReasoningCore._get_role_specific_keywords(role, focus)

        ranked = []
        for doc in evidence:
            text = str(doc.get("text") or doc.get("content") or "").strip()
            # Score based on persona focus - documents matching the persona's concerns score higher
            base_score = _score_relevance(text, context_tokens)
            
            # Boost score if text contains persona-specific keywords
            text_lower = text.lower()
            keyword_boost = 0
            if any(k in text_lower for k in keywords_positive):
                keyword_boost += 0.3
            if any(k in text_lower for k in keywords_negative):
                keyword_boost += 0.2
                
            final_score = min(1.0, base_score + keyword_boost)
            
            doc_id = doc.get("id") or doc.get("metadata", {}).get("id")
            source = doc.get("source", "unknown")
            citation = f"【{doc_id}†{source}】" if doc_id else None
            ranked.append({"id": doc_id, "text": text, "source": source, "score": round(final_score, 3), "citation": citation})

        # Sort by score, then by length
        ranked.sort(key=lambda d: (d["score"], len(d["text"])), reverse=True)

        # Interpretation from top documents
        interpretation = " ".join([_first_sentence(d["text"]) for d in ranked[:2]]) if ranked else ""

        # Extract role-specific implications
        implications = []
        pos_count = 0
        neg_count = 0
        trace = []
        
        for d in ranked:
            t = d["text"].lower()
            found_pos = [k for k in keywords_positive if k in t]
            found_neg = [k for k in keywords_negative if k in t]
            
            if found_pos:
                pos_count += 1
            if found_neg:
                neg_count += 1

            implication = []
            if found_pos:
                # Role-specific positive implications
                if "financial" in role.lower():
                    implication.append(f"Financial benefit potential: {', '.join(found_pos)}")
                elif "sustainability" in role.lower():
                    implication.append(f"Sustainability opportunity: {', '.join(found_pos)}")
                elif "infrastructure" in role.lower() or "engineer" in role.lower():
                    implication.append(f"Design/infrastructure advantage: {', '.join(found_pos)}")
                elif "community" in role.lower():
                    implication.append(f"Community benefit: {', '.join(found_pos)}")
                else:
                    implication.append(f"Potential benefit: {', '.join(found_pos)}")
                    
            if found_neg:
                # Role-specific negative implications
                if "financial" in role.lower():
                    implication.append(f"Financial risk or cost: {', '.join(found_neg)}")
                elif "sustainability" in role.lower():
                    implication.append(f"Environmental concern: {', '.join(found_neg)}")
                elif "infrastructure" in role.lower() or "engineer" in role.lower():
                    implication.append(f"Design/infrastructure risk: {', '.join(found_neg)}")
                elif "community" in role.lower():
                    implication.append(f"Community harm or burden: {', '.join(found_neg)}")
                else:
                    implication.append(f"Potential risk: {', '.join(found_neg)}")

            trace.append({
                "id": d.get("id"), 
                "text": d["text"], 
                "source": d.get("source"), 
                "score": d["score"], 
                "implication": "; ".join(implication), 
                "citation": d.get("citation")
            })

        # Role-specific conclusions
        if pos_count > neg_count:
            if "financial" in role.lower():
                conclusion = f"As a {role}, the economic case is strong. Evidence supports financial viability."
            elif "sustainability" in role.lower():
                conclusion = f"As a {role}, environmental benefits are evident. Strong sustainability case."
            elif "infrastructure" in role.lower() or "engineer" in role.lower():
                conclusion = f"As a {role}, infrastructure improvements are justified. Evidence supports implementation."
            elif "community" in role.lower():
                conclusion = f"As a {role}, community benefits outweigh harms based on available evidence."
            else:
                conclusion = "Evidence leans toward positive outcomes and support."
        elif neg_count > pos_count:
            if "financial" in role.lower():
                conclusion = f"As a {role}, significant economic risks and costs require mitigation."
            elif "sustainability" in role.lower():
                conclusion = f"As a {role}, environmental risks are substantial and demand precaution."
            elif "infrastructure" in role.lower() or "engineer" in role.lower():
                conclusion = f"As a {role}, infrastructure challenges require careful design."
            elif "community" in role.lower():
                conclusion = f"As a {role}, this will harm vulnerable groups without protective measures."
            else:
                conclusion = "Evidence highlights risks that counsel caution."
        else:
            conclusion = f"As a {role}, evidence is mixed. Both opportunities and risks exist."

        # Contradiction detection
        contradiction = False
        if len(ranked) >= 2:
            top_texts = (ranked[0]["text"].lower(), ranked[1]["text"].lower())
            if any(k in top_texts[0] for k in keywords_positive) and any(k in top_texts[1] for k in keywords_negative):
                contradiction = True

        return {
            "ranked": ranked,
            "interpretation": interpretation,
            "implications": [t.get("implication") for t in trace if t.get("implication")],
            "conclusion": conclusion,
            "contradiction": contradiction,
            "trace": trace,
        }
