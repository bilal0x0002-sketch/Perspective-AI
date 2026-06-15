from typing import List
import json
import os
import requests


class PerspectiveSynthesizer:
    @staticmethod
    def _get_llm_config() -> tuple[str | None, str | None, str]:
        """Get LLM configuration for synthesis."""
        endpoint = (
            os.getenv("AZURE_OPENAI_ENDPOINT")
            or os.getenv("OPENAI_API_BASE")
        )
        api_key = (
            os.getenv("AZURE_OPENAI_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        model = (
            os.getenv("AZURE_OPENAI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o"
        )
        return endpoint, api_key, model

    @staticmethod
    def _generate_dynamic_recommendation(debate: List[dict], question: str) -> str:
        """Generate a unique recommendation based on actual debate content using LLM."""
        endpoint, api_key, model = PerspectiveSynthesizer._get_llm_config()
        if not endpoint or not api_key:
            return "Unable to generate dynamic recommendation (LLM not configured)."
        
        # Build debate summary for LLM
        debate_summary = f"Question: {question}\n\nPerspectives debated:\n"
        for entry in debate:
            debate_summary += f"- {entry['perspective']} ({entry['stance']}): {entry.get('initial_statement', 'No statement')[:200]}...\n"
        
        system_prompt = (
            "You are a policy synthesis expert. Based on the debate transcript provided, "
            "generate a unique, evidence-based final recommendation. "
            "Consider areas of agreement, disagreement, and key tradeoffs. "
            "Output ONLY the recommendation text (no JSON)."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": debate_summary},
        ]
        
        try:
            from openai import OpenAI
            client = OpenAI(base_url=endpoint, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.5,
                max_tokens=400,
            )
            return response.choices[0].message.content
        except Exception:
            # Fallback to HTTP request
            try:
                endpoint = endpoint.rstrip("/")
                if "/chat/completions" not in endpoint:
                    endpoint = f"{endpoint}/v1/chat/completions"
                
                headers = {"Content-Type": "application/json"}
                if "azure" in endpoint.lower():
                    headers["api-key"] = api_key
                else:
                    headers["Authorization"] = f"Bearer {api_key}"
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": 400,
                }
                
                response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception:
                return "Unable to generate dynamic recommendation (LLM call failed)."


    def summarize(self, debate: List[dict], debate_state: dict | None = None, question: str = "") -> dict:
        if not debate:
            return {
                "final_recommendation": "No debate was generated.",
                "tradeoffs": [],
                "highlights": [],
                "agreement_level": 0.0,
                "conflict_level": 1.0,
                "consensus_confidence": 0.0,
                "strongest_argument": "none",
                "weakest_argument": "none",
                "risk_balance": "unknown",
                "uncertainty": 1.0,
                "reasoning_confidence": 0.0,
            }

        tradeoffs = []
        highlights = []
        stance_map = {
            "support": 1.0,
            "conditional support": 0.6,
            "cautious": 0.3,
            "opposed without better access": 0.1,
            "mixed": 0.5,
        }

        confidences = []
        stances = []
        evidence_strengths = []
        contradiction_flags = 0
        for entry in debate:
            highlights.append(f"{entry['perspective']}: {entry['stance']}")
            tradeoffs.append(f"{entry['perspective']} focus: {entry['focus']}")
            confidence = float(entry.get("confidence", 0.5))
            confidences.append(confidence)
            stances.append(stance_map.get(entry["stance"].lower(), 0.5))
            # reasoned evidence strength (average ranked score)
            reasoned = entry.get("reasoned") or {}
            ranked = reasoned.get("ranked") or []
            if ranked:
                avg_score = sum(r.get("score", 0.0) for r in ranked) / len(ranked)
            else:
                avg_score = 0.0
            evidence_strengths.append(avg_score)
            if reasoned.get("contradiction"):
                contradiction_flags += 1

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        consensus_confidence = round(min(max(avg_confidence, 0.0), 1.0), 2)

        stance_mean = sum(stances) / len(stances) if stances else 0.5
        dispersion = sum(abs(s - stance_mean) for s in stances) / len(stances) if stances else 0.0

        agreement_count = len(debate_state.get("agreements", [])) if debate_state else 0
        conflict_count = len(debate_state.get("conflicts", [])) if debate_state else 0
        relation_total = max(1, agreement_count + conflict_count)
        relation_balance = (agreement_count - conflict_count) / relation_total

        agreement_level = round(max(0.0, min(1.0, 0.62 + 0.18 * relation_balance - 0.30 * dispersion)), 2)
        conflict_level = round(max(0.0, min(1.0, 0.30 - 0.16 * relation_balance + 0.54 * dispersion)), 2)
        uncertainty = round(max(0.0, min(1.0, 1.0 - consensus_confidence)), 2)
        # reasoning confidence incorporates evidence strength and contradiction signals
        avg_evidence_strength = sum(evidence_strengths) / len(evidence_strengths) if evidence_strengths else 0.0
        contradiction_penalty = max(0.0, min(1.0, contradiction_flags / max(1, len(debate))))
        reasoning_confidence = round(consensus_confidence * agreement_level * (0.5 + avg_evidence_strength * 0.5) * (1.0 - contradiction_penalty), 2)

        risk_balance = "Medium"
        if dispersion < 0.18 and conflict_count <= agreement_count:
            risk_balance = "Low"
        elif dispersion > 0.35 or conflict_count > agreement_count:
            risk_balance = "High"

        strongest = max(debate, key=lambda entry: float(entry.get("confidence", 0.0)))
        weakest = min(debate, key=lambda entry: float(entry.get("confidence", 0.0)))

        # Generate dynamic recommendation based on actual debate instead of templates
        recommendation = PerspectiveSynthesizer._generate_dynamic_recommendation(debate, question)

        return {
            "final_recommendation": recommendation,
            "tradeoffs": tradeoffs,
            "highlights": highlights,
            "agreement_level": agreement_level,
            "conflict_level": conflict_level,
            "consensus_confidence": consensus_confidence,
            "strongest_argument": strongest["perspective"],
            "weakest_argument": weakest["perspective"],
            "risk_balance": risk_balance,
            "uncertainty": uncertainty,
            "reasoning_confidence": reasoning_confidence,
            "evidence_trace": {entry['perspective']: entry.get('reasoned', {}).get('trace', []) for entry in debate},
        }
