from __future__ import annotations

import json
import os
import argparse
from typing import Any

import requests

from .foundry_client import FoundryClient
from .orchestrator import PerspectiveOrchestrator
from .perspectives import persona_registry, load_perspectives
from .synthesizer import PerspectiveSynthesizer


class QuestionClassifier:
    """Classify questions as factual or policy-based."""
    
    @staticmethod
    def _get_llm_config() -> tuple[str | None, str | None, str]:
        """Get LLM configuration."""
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_API_BASE")
        api_key = os.getenv("AZURE_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
        model = os.getenv("AZURE_OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o"
        return endpoint, api_key, model
    
    @staticmethod
    def classify(query: str) -> dict[str, Any]:
        """
        Classify a question as 'factual' or 'policy'.
        Factual: Has a single correct answer (e.g., "What year did X happen?")
        Policy: Requires debate and multiple perspectives (e.g., "Should we ban cars downtown?")
        """
        endpoint, api_key, model = QuestionClassifier._get_llm_config()
        if not endpoint or not api_key:
            return {"type": "policy", "confidence": 0.5, "reason": "LLM not configured, defaulting to policy debate"}
        
        system_prompt = (
            "You are a question classifier. Analyze the given question and determine if it is FACTUAL or POLICY.\n\n"
            "FACTUAL questions have a single correct answer determinable by facts:\n"
            "- 'What year was the Internet invented?'\n"
            "- 'What is the capital of France?'\n"
            "- 'How many moons does Jupiter have?'\n\n"
            "POLICY questions require debate and multiple perspectives:\n"
            "- 'Should we ban cars downtown?'\n"
            "- 'Is climate change a priority?'\n"
            "- 'Should AI be regulated?'\n\n"
            "Return JSON: {\"type\": \"factual\" or \"policy\", \"confidence\": 0.0-1.0, \"reason\": \"brief explanation\"}"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Classify this question:\n{query}"},
        ]
        
        try:
            from openai import OpenAI
            client = OpenAI(base_url=endpoint, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=200,
            )
            content = response.choices[0].message.content
        except Exception:
            # Fallback to HTTP
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
                    "temperature": 0.2,
                    "max_tokens": 200,
                }
                
                response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
                result = response.json()
                content = result["choices"][0]["message"]["content"]
            except Exception:
                return {"type": "policy", "confidence": 0.5, "reason": "LLM call failed, defaulting to policy debate"}
        
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "type" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
        
        return {"type": "policy", "confidence": 0.5, "reason": "Could not parse classification, defaulting to policy debate"}
    
    @staticmethod
    def answer_factual(query: str) -> str:
        """Generate a direct answer to a factual question."""
        endpoint, api_key, model = QuestionClassifier._get_llm_config()
        if not endpoint or not api_key:
            return "Unable to answer (LLM not configured)."
        
        system_prompt = (
            "You are a factual question answering assistant. Provide a clear, concise, "
            "and accurate answer to the question. Cite sources if possible."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        
        try:
            from openai import OpenAI
            client = OpenAI(base_url=endpoint, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception:
            # Fallback to HTTP
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
                    "temperature": 0.2,
                    "max_tokens": 500,
                }
                
                response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception:
                return "Unable to answer (LLM call failed)."


def run_scenario(query: str, mode: str = "offline", progress_callback=None) -> dict[str, Any]:
    # Classify the question first
    if progress_callback:
        progress_callback("stage", {"stage": "classifying", "message": "Analyzing question type"})
    
    classification = QuestionClassifier.classify(query)
    
    # If factual question, return direct answer instead of debate
    if classification.get("type") == "factual" and classification.get("confidence", 0) > 0.6:
        if progress_callback:
            progress_callback("stage", {"stage": "answering", "message": "Generating factual answer"})
        
        answer = QuestionClassifier.answer_factual(query)
        return {
            "query": query,
            "mode": mode,
            "question_type": "factual",
            "question_classification": classification,
            "answer": answer,
            "is_debate": False,
        }
    
    # Otherwise, run full debate flow
    if progress_callback:
        progress_callback("stage", {"stage": "selecting", "message": "Selecting best agents"})
    
    client = FoundryClient(mode=mode)
    orchestrator = PerspectiveOrchestrator(client)
    
    # Select the best 4-5 personas relevant to the query
    perspectives = orchestrator.select_perspectives(query, max_agents=5)
    
    available_bots = persona_registry()
    
    debate_data = orchestrator.run(query, perspectives=perspectives, progress_callback=progress_callback)
    if progress_callback:
        progress_callback("stage", {"stage": "synthesizing", "message": "Generating final summary"})
    synthesizer = PerspectiveSynthesizer()
    summary = synthesizer.summarize(debate_data["agents"], debate_data.get("debate_state"), query)
    
    return {
        "query": query,
        "mode": mode,
        "question_type": "policy",
        "question_classification": classification,
        "available_bots": available_bots,
        "selected_personas": [p.name for p in perspectives],
        "agents": debate_data["agents"],
        "rounds": debate_data["rounds"],
        "debate_state": debate_data.get("debate_state", {}),
        "summary": summary,
        "is_debate": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Perspective AI debate engine.")
    parser.add_argument("--query", required=True, help="The question to debate.")
    parser.add_argument("--mode", default="offline", choices=["offline", "real"], help="Data mode for the Foundry client.")
    args = parser.parse_args()

    result = run_scenario(args.query, mode=args.mode)
    print(f"\nQuestion: {result['query']}\n")
    
    # Handle factual questions
    if not result.get("is_debate", True):
        print(f"Question Type: {result['question_type'].upper()}")
        print(f"Confidence: {result['question_classification'].get('confidence', 0):.1%}")
        print(f"Reason: {result['question_classification'].get('reason', 'N/A')}")
        print("\n=== Answer ===")
        print(result['answer'])
        return
    
    # Handle policy debates
    print(f"Question Type: {result['question_type'].upper()}")
    print(f"Classification: {result['question_classification'].get('reason', 'Policy debate needed')}")
    print()

    print(f"Available bot personas: {len(result['available_bots'])}")
    for bot in result["available_bots"]:
        print(f"- {bot['name']}: {bot['description']}")
    print()

    print("=== Selected agents ===")
    print(", ".join(result["selected_personas"]))
    print()
    print("=== Agent evidence summaries ===")
    for entry in result["agents"]:
        print(f"--- {entry['perspective']} ({entry['role']}) ---")
        print(f"Focus: {entry['focus']}")
        print(f"Stance: {entry['stance']}")
        print(f"Confidence: {entry['confidence']}")
        print(f"Key risk: {entry['key_issue']}")
        print(f"Foundry sources: {entry['retrieval_count']} ({', '.join(entry['topics'])})")
        print("Evidence:")
        for item in entry["evidence"]:
            print(f"  - {item['text']} [{item['source']}]")
        # Reasoning core summary (if available)
        reasoned = entry.get("reasoned")
        if reasoned:
            print("Reasoning summary:")
            print(f"  Interpretation: {reasoned.get('interpretation')}")
            if reasoned.get('implications'):
                print(f"  Implications: {', '.join([i for i in reasoned.get('implications') if i])}")
            print(f"  Conclusion: {reasoned.get('conclusion')}")
            print(f"  Contradiction detected: {reasoned.get('contradiction')}")
            print("  Trace:")
            for t in reasoned.get('trace', []):
                print(f"    - {t.get('text')} [{t.get('source')}] (score={t.get('score')}) -> {t.get('implication')}")
        print()

    print("=== Debate rounds ===")
    for round_item in result["rounds"]:
        targets = ", ".join(round_item["targets"]) if round_item["targets"] else "none"
        print(f"- {round_item['speaker']} ({round_item['move']}) targets: {targets}")
        print(f"  {round_item['statement']}")
        if round_item.get("analysis"):
            print("  Reasoning:")
            for item in round_item["analysis"]:
                if item["target"]:
                    print(f"    - {item['type'].capitalize()} vs {item['target']}: {item['reason']}")
                else:
                    print(f"    - {item['type'].capitalize()}: {item['reason']}")
        if round_item.get("evidence_used"):
            print("  Evidence:")
            for evidence in round_item["evidence_used"]:
                print(f"    - {evidence['text']} [{evidence['source']}]")
        print()

    print("=== Final Synthesis ===")
    print(result["summary"]["final_recommendation"])
    print(f"Agreement level: {result['summary']['agreement_level']}")
    print(f"Conflict level: {result['summary']['conflict_level']}")
    print(f"Consensus confidence: {result['summary']['consensus_confidence']}")
    print(f"Uncertainty: {result['summary']['uncertainty']}")
    print(f"Reasoning confidence: {result['summary']['reasoning_confidence']}")
    print(f"Strongest argument: {result['summary']['strongest_argument']}")
    print(f"Weakest argument: {result['summary']['weakest_argument']}")
    print(f"Risk balance: {result['summary']['risk_balance']}")
    print("\nKey tradeoffs:")
    for tradeoff in result["summary"]["tradeoffs"]:
        print(f"  - {tradeoff}")


if __name__ == "__main__":
    main()
