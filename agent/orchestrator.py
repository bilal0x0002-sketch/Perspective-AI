from __future__ import annotations

import json
import os
import re
import uuid
from types import SimpleNamespace
from typing import Any, List

import requests

from .foundry_client import FoundryClient
from .reasoning_core import ReasoningCore
from .persona_agents import PersonaEngine
from .perspectives import Perspective, persona_registry, load_perspectives
from .bots import extended_perspectives
from .instructions import DEFAULT_INSTRUCTIONS, apply_instructions
from .telemetry import telemetry


class DebateState:
    """Maintains the state of the ongoing debate with memories and conflict tracking."""

    def __init__(self):
        self.rounds: List[dict[str, Any]] = []
        self.agent_stances: dict[str, dict[str, Any]] = {}
        self.agreements: List[tuple[str, str, str]] = []
        self.conflicts: List[tuple[str, str, str]] = []

    def add_agent(self, name: str, stance: str, confidence: float, position: str) -> None:
        self.agent_stances[name] = {
            "stance": stance,
            "confidence": confidence,
            "position": position,
            "revised": False,
        }

    def add_round(self, speaker: str, role: str, move: str, statement: str, targets: List[str], evidence_used: List[str]) -> None:
        self.rounds.append({
            "speaker": speaker,
            "role": role,
            "move": move,
            "statement": statement,
            "targets": targets,
            "evidence_used": evidence_used,
        })

    def track_agreement(self, agent_a: str, agent_b: str, reason: str) -> None:
        self.agreements.append((agent_a, agent_b, reason))

    def track_conflict(self, agent_a: str, agent_b: str, reason: str) -> None:
        self.conflicts.append((agent_a, agent_b, reason))


class PerspectiveOrchestrator:
    def __init__(self, foundry_client: FoundryClient):
        self.foundry_client = foundry_client
        self.debate_state = DebateState()
        self.stance_map = {
            "support": 1.0,
            "conditional support": 0.6,
            "cautious": 0.3,
            "opposed without better access": 0.1,
            "mixed": 0.5,
        }

    def _get_router_config(self) -> tuple[str | None, str | None, str]:
        return ReasoningCore._get_remote_reasoner_config()

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"\w+", text.lower()))

    def _score_persona_relevance(self, perspective: Perspective, query_tokens: set[str]) -> float:
        persona_text = " ".join([
            perspective.name,
            perspective.role,
            perspective.focus,
            perspective.key_issue,
            " ".join(perspective.evidence_topics),
        ])
        persona_tokens = self._tokenize(persona_text)
        return float(len(persona_tokens & query_tokens))

    def _call_persona_router(self, query: str, max_agents: int, candidates: List[Perspective] = None) -> list[str] | None:
        endpoint, api_key, model = self._get_router_config()
        if not endpoint or not api_key:
            return None

        # If no candidates provided, get from registry (fallback to hardcoded)
        if candidates is None:
            personas_list = persona_registry()
        else:
            # Build list from candidates (preferred for real mode with Azure)
            personas_list = [
                {
                    "name": p.name,
                    "role": p.role,
                    "focus": p.focus,
                    "key_issue": p.key_issue,
                    "description": f"{p.role} focused on {p.focus}, with a core concern of {p.key_issue}.",
                }
                for p in candidates
            ]
        
        if not personas_list:
            return None

        prompt = (
            "You are an expert selector. Given the user query and a list of expert personas, "
            "choose the most relevant personas for the task. Return only a JSON array of persona names. "
            f"Select at most {max_agents} names from the provided list."
        )

        user_content = (
            f"User query: {query}\n\n"
            "Available personas:\n"
            f"{json.dumps(personas_list, ensure_ascii=False, indent=2)}\n\n"
            "Return only a JSON array of persona names, for example: [\"Financial Analyst\", \"Infrastructure Designer\"]"
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            from openai import OpenAI

            client = OpenAI(base_url=endpoint, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=300,
            )
            content = response.choices[0].message.content
        except Exception:
            endpoint = endpoint.rstrip("/")
            if "/chat/completions" not in endpoint and "/openai/" not in endpoint:
                endpoint = f"{endpoint}/v1/chat/completions"

            headers = {"Content-Type": "application/json"}
            if any(key in endpoint.lower() for key in ("azure", "inference.ai", "foundry")):
                headers["api-key"] = api_key
            else:
                headers["Authorization"] = f"Bearer {api_key}"

            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 300,
            }

            try:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
            except Exception:
                return None

        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return [name for name in parsed if isinstance(name, str)]
        except json.JSONDecodeError:
            return None
        return None

    def _fallback_select_perspectives(self, query: str, max_agents: int, candidates: List[Perspective] = None) -> List[Perspective]:
        if candidates is None:
            candidates = extended_perspectives()
        query_tokens = self._tokenize(query)
        scored = sorted(
            candidates,
            key=lambda p: self._score_persona_relevance(p, query_tokens),
            reverse=True,
        )
        if all(self._score_persona_relevance(p, query_tokens) == 0 for p in scored):
            return candidates[:max_agents]
        return scored[:max_agents]

    def select_perspectives(self, query: str, max_agents: int = 5) -> List[Perspective]:
        # Load candidates based on mode
        if self.foundry_client.mode == "real":
            candidates = load_perspectives(mode="auto")  # Try Azure, fallback to default
        else:
            candidates = load_perspectives(mode="default")  # Use default 5 core personas for offline
        
        # Try to get LLM to select best personas
        selected_names = self._call_persona_router(query, max_agents, candidates)
        if selected_names:
            available = {p.name: p for p in candidates}
            selected = [available[name] for name in selected_names if name in available]
            if selected:
                return selected

        # Fallback: score by relevance
        return self._fallback_select_perspectives(query, max_agents, candidates)

    def _build_persona_memory_document(self, agent_data: dict[str, Any]) -> dict[str, Any]:
        evidence_text = "\n".join([item.get("text", "") for item in agent_data.get("evidence", [])[:5]])
        reasoned = agent_data.get("reasoned", {}) or {}
        conclusion = reasoned.get("conclusion") or ""
        interpretation = reasoned.get("interpretation") or ""
        content_lines = [
            f"Persona: {agent_data['perspective']}",
            f"Role: {agent_data['role']}",
            f"Focus: {agent_data['focus']}",
            f"Key issue: {agent_data['key_issue']}",
            f"Position: {agent_data['position']}",
            "Evidence:",
            evidence_text,
            f"Reasoning interpretation: {interpretation}",
            f"Reasoning conclusion: {conclusion}",
        ]
        return {
            "@search.action": "upload",
            "id": f"persona-memory-{agent_data['perspective'].lower().replace(' ', '-')}-{uuid.uuid4()}",
            "title": f"{agent_data['perspective']} persona memory",
            "content": "\n".join([line for line in content_lines if line]),
            "source": "persona-engine",
            "category": "agent-memory",
            "metadata": {
                "persona": agent_data["perspective"],
                "role": agent_data["role"],
                "focus": agent_data["focus"],
                "stance": agent_data.get("stance"),
                "confidence": agent_data.get("confidence"),
                "retrieval_count": agent_data.get("retrieval_count"),
                "topics": agent_data.get("topics", []),
            },
        }

    def _upload_persona_memory_docs(self, docs: List[dict[str, Any]]) -> dict[str, Any] | None:
        if self.foundry_client.mode != "real":
            return None

        try:
            return self.foundry_client.upload_documents(docs)
        except Exception:
            telemetry.incr("memory_upload_failures")
            return None

    def run(self, query: str, perspectives: List[Perspective] | None = None, progress_callback=None) -> dict[str, Any]:
        if perspectives is None:
            perspectives = self.select_perspectives(query)

        agents: List[dict[str, Any]] = []
        memory_docs: List[dict[str, Any]] = []

        # Stage 1: initial perspective grounding with evidence and stance scoring
        for perspective in perspectives:
            if progress_callback:
                progress_callback("stage", {"stage": "retrieval", "message": f"Retrieving evidence for {perspective.name}", "perspective": perspective.name})
            evidence = self.foundry_client.retrieve_evidence(perspective, query)

            if progress_callback:
                progress_callback("stage", {"stage": "reasoning", "message": f"Reasoning for {perspective.name}", "perspective": perspective.name})
            reasoned = ReasoningCore.reason(evidence, query, perspective)

            # enforce retrieval instructions (per-agent can be extended later)
            instr_result = apply_instructions(DEFAULT_INSTRUCTIONS, evidence)
            used_fallback = False  # Track if we're using fallback text
            if not instr_result.get("compliant"):
                # no evidence found and instructions require retrieval
                telemetry.incr("fallbacks")
                # use fallback text as position and skip persona generation
                initial_statement = instr_result.get("fallback")
                used_fallback = True
                # ensure reasoned trace exists but empty
                reasoned = reasoned or {}
                evidence = []
            else:
                # count citations returned
                citation_count = sum(1 for e in evidence if e.get("id"))
                if citation_count:
                    telemetry.incr("citations_returned", citation_count)

            stance, confidence = self._score_perspective(perspective, evidence)
            # build persona-aware initial position from reasoned evidence
            print(f"\n[ORCHESTRATOR] {perspective.name} reasoned dict keys: {list(reasoned.keys())}")
            print(f"[ORCHESTRATOR] {perspective.name} conclusion: {reasoned.get('conclusion', 'NO CONCLUSION')[:100]}")
            print(f"[ORCHESTRATOR] {perspective.name} interpretation: {reasoned.get('interpretation', 'NO INTERPRETATION')[:100]}")
            persona_out = PersonaEngine.build_initial(perspective.name, reasoned, stance, query)
            print(f"[ORCHESTRATOR] {perspective.name} position: {persona_out.get('position', 'NO POSITION')[:100]}\n")
            # CRITICAL FIX: Only use fallback if it was actually generated; otherwise use unique persona_out per iteration
            if not used_fallback:
                initial_statement = persona_out.get("position")

            agent_data = {
                "perspective": perspective.name,
                "role": perspective.role,
                "personality": self._personality_for(perspective.name),
                "focus": perspective.focus,
                "topics": perspective.evidence_topics,
                "stance": stance,
                "confidence": confidence,
                "key_issue": perspective.key_issue,
                "position": initial_statement,
                "evidence": evidence,
                "reasoned": reasoned,
                "retrieval_count": len(evidence),
                "evidence_by_stage": {
                    "initial": [{"text": item.get("text"), "id": item.get("id"), "source": item.get("source"), "citation": (f"【{item.get('id')}†{item.get('source')}】" if item.get('id') else None)} for item in evidence],
                    "initial_ranked": [{"text": r.get("text"), "id": r.get("id"), "source": r.get("source"), "score": r.get("score"), "citation": r.get("citation")} for r in reasoned.get("ranked", [])],
                },
            }
            agents.append(agent_data)
            memory_docs.append(self._build_persona_memory_document(agent_data))
            if progress_callback:
                progress_callback("agent", {"perspective": perspective.name, "stance": stance, "confidence": confidence, "position": initial_statement})
            self.debate_state.add_agent(perspective.name, stance, confidence, initial_statement)

        if memory_docs:
            self._upload_persona_memory_docs(memory_docs)

        rounds = self._build_debate_rounds_stateful(agents, query, progress_callback=progress_callback)

        return {
            "selected_personas": [p.name for p in perspectives],
            "agents": agents,
            "rounds": rounds,
            "debate_state": {
                "conflicts": self.debate_state.conflicts,
                "agreements": self.debate_state.agreements,
            },
        }

    def _build_debate_rounds_stateful(self, agents: List[dict[str, Any]], query: str, progress_callback=None) -> List[dict[str, Any]]:
        rounds: List[dict[str, Any]] = []
        if not agents:
            return rounds

        def add_round(
            speaker: dict[str, Any],
            move: str,
            statement: str,
            targets: List[str],
            evidence_used: List[dict[str, str]],
            analysis: List[dict[str, str]],
        ) -> None:
            mood = self._select_round_mood(move, analysis)
            rounds.append({
                "speaker": speaker["perspective"],
                "role": speaker["role"],
                "move": move,
                "statement": statement,
                "targets": targets,
                "evidence_used": evidence_used,
                "analysis": analysis,
                "mood": mood,
            })
            self.debate_state.add_round(speaker["perspective"], speaker["role"], move, statement, targets, [item["text"] for item in evidence_used])

        opener = agents[0]
        opener_stmt = self._opening_statement(opener)
        opener_evidence = opener["evidence"][:1]
        opener_analysis = self._evaluate_relations(opener, [])
        add_round(opener, "Opening argument", opener_stmt, [], opener_evidence, opener_analysis)
        if progress_callback:
            progress_callback("round", {"round": rounds[-1]})

        if len(agents) > 1:
            rebuttal = agents[1]
            # Create perspective wrapper with name, focus, and evidence_topics for context-aware search
            rebuttal_perspective = SimpleNamespace(
                name=rebuttal["perspective"],
                focus=rebuttal.get("focus", ""),
                evidence_topics=rebuttal.get("topics", [])
            )
            rebuttal_evidence_items = self.foundry_client.retrieve_evidence(
                rebuttal_perspective,
                f"rebuttal to {opener['perspective']} on {query}"
            )
            rebuttal_evidence_used = rebuttal_evidence_items[:1]
            rebuttal["evidence_by_stage"]["rebuttal"] = [
                {
                    "text": item.get("text"),
                    "id": item.get("id"),
                    "source": item.get("source"),
                    "citation": (f"【{item.get('id')}†{item.get('source')}】" if item.get("id") else None),
                }
                for item in rebuttal_evidence_used
            ]
            rebuttal_stmt = self._rebuttal_statement_with_memory(rebuttal, opener)
            rebuttal_analysis = self._evaluate_relations(rebuttal, [opener])
            add_round(rebuttal, "Rebuttal", rebuttal_stmt, [opener["perspective"]], rebuttal_evidence_used, rebuttal_analysis)
            if progress_callback:
                progress_callback("round", {"round": rounds[-1]})

        if len(agents) > 2:
            counterpoint = agents[2]
            # Create perspective wrapper with name, focus, and evidence_topics for context-aware search
            counterpoint_perspective = SimpleNamespace(
                name=counterpoint["perspective"],
                focus=counterpoint.get("focus", ""),
                evidence_topics=counterpoint.get("topics", [])
            )
            counter_evidence_items = self.foundry_client.retrieve_evidence(
                counterpoint_perspective,
                f"counterpoint emphasizing {counterpoint['key_issue']}"
            )
            counter_evidence_used = counter_evidence_items[:1]
            counterpoint["evidence_by_stage"]["counterpoint"] = [
                {
                    "text": item.get("text"),
                    "id": item.get("id"),
                    "source": item.get("source"),
                    "citation": (f"【{item.get('id')}†{item.get('source')}】" if item.get("id") else None),
                }
                for item in counter_evidence_used
            ]
            counter_stmt = self._counterpoint_statement_with_memory(counterpoint, [opener, agents[1]])
            counter_analysis = self._evaluate_relations(counterpoint, [opener, agents[1]])
            add_round(counterpoint, "Counterpoint", counter_stmt, [opener["perspective"], agents[1]["perspective"]], counter_evidence_used, counter_analysis)
            if progress_callback:
                progress_callback("round", {"round": rounds[-1]})

        if len(agents) > 3:
            compromise = agents[3]
            # Create perspective wrapper with name, focus, and evidence_topics for context-aware search
            compromise_perspective = SimpleNamespace(
                name=compromise["perspective"],
                focus=compromise.get("focus", ""),
                evidence_topics=compromise.get("topics", [])
            )
            comp_evidence_items = self.foundry_client.retrieve_evidence(
                compromise_perspective,
                "compromise solution balancing multiple perspectives and concerns"
            )
            comp_evidence_used = comp_evidence_items[:1]
            compromise["evidence_by_stage"]["compromise"] = [
                {
                    "text": item.get("text"),
                    "id": item.get("id"),
                    "source": item.get("source"),
                    "citation": (f"【{item.get('id')}†{item.get('source')}】" if item.get("id") else None),
                }
                for item in comp_evidence_used
            ]
            comp_stmt = self._compromise_statement_with_memory(compromise, [opener, agents[1], agents[2]])
            comp_analysis = self._evaluate_relations(compromise, [opener, agents[1], agents[2]])
            add_round(compromise, "Compromise proposal", comp_stmt, [opener["perspective"], agents[1]["perspective"], agents[2]["perspective"]], comp_evidence_used, comp_analysis)
            if progress_callback:
                progress_callback("round", {"round": rounds[-1]})

        if len(agents) > 4:
            pragmatic = agents[4]
            # Create perspective wrapper with name, focus, and evidence_topics for context-aware search
            pragmatic_perspective = SimpleNamespace(
                name=pragmatic["perspective"],
                focus=pragmatic.get("focus", ""),
                evidence_topics=pragmatic.get("topics", [])
            )
            prag_evidence_items = self.foundry_client.retrieve_evidence(
                pragmatic_perspective,
                "practical implementation and stakeholder concerns"
            )
            prag_evidence_used = prag_evidence_items[:1]
            pragmatic["evidence_by_stage"]["pragmatic"] = [
                {
                    "text": item.get("text"),
                    "id": item.get("id"),
                    "source": item.get("source"),
                    "citation": (f"【{item.get('id')}†{item.get('source')}】" if item.get("id") else None),
                }
                for item in prag_evidence_used
            ]
            prag_stmt = self._pragmatic_statement_with_memory(pragmatic, [opener, agents[1], agents[2], agents[3]])
            prag_analysis = self._evaluate_relations(pragmatic, [opener, agents[1], agents[2], agents[3]])
            add_round(pragmatic, "Pragmatic conclusion", prag_stmt, [opener["perspective"], agents[1]["perspective"], agents[2]["perspective"], agents[3]["perspective"]], prag_evidence_used, prag_analysis)

        return rounds

    def _select_round_mood(self, move: str, analysis: List[dict[str, str]]) -> str:
        if move == "Opening argument":
            return "🧐 Neutral curiosity"
        if move == "Rebuttal":
            if any(item["type"] == "conflict" for item in analysis):
                return "😠 Challenging"
            return "💪 Assertive"
        if move == "Counterpoint":
            if any(item["type"] == "conflict" for item in analysis):
                return "🤔 Concerned"
            return "🤝 Reflective"
        if move == "Compromise proposal":
            return "🙂 Hopeful"
        if move == "Pragmatic conclusion":
            return "💼 Practical"

        if any(item["type"] == "conflict" for item in analysis):
            return "😤 Frustrated"
        if all(item["type"] == "agreement" for item in analysis if item["target"]):
            return "😊 Cooperative"

        return "😐 Thoughtful"

    def _score_perspective(self, perspective: Perspective, evidence: List[dict[str, str]]) -> tuple[str, float]:
        # No evidence = very low confidence
        if not evidence:
            return perspective.default_stance, 0.25
        
        # Base confidence scales with evidence quantity and quality
        base_confidence = 0.5 + 0.08 * min(len(evidence), 5)
        stance = perspective.default_stance
        
        # Evidence quality adjustments
        contradictory = sum(1 for item in evidence if "risk" in item.get("text", "").lower() or "concern" in item.get("text", "").lower())
        supportive = sum(1 for item in evidence if "benefit" in item.get("text", "").lower() or "improve" in item.get("text", "").lower())
        
        # Adjust stance based on evidence balance (only if evidence is clear)
        stance_map = {
            "support": ("conditional support", "cautious"),
            "conditional support": ("support", "opposed without better access"),
            "cautious": ("conditional support", "opposed without better access"),
            "opposed without better access": ("cautious", "mixed"),
            "mixed": ("cautious", "opposed without better access"),
        }
        
        if supportive > contradictory + 1:
            # Strong support evidence - escalate stance
            next_stance, _ = stance_map.get(stance, (stance, stance))
            stance = next_stance
            base_confidence += 0.15
        elif contradictory > supportive + 1:
            # Strong contradictory evidence - weaken stance
            _, next_stance = stance_map.get(stance, (stance, stance))
            stance = next_stance
            base_confidence -= 0.10
        else:
            # Mixed signals reduce confidence but keep stance
            base_confidence -= 0.05
        
        # Different personas can have different max confidence (no hard 0.8 cap)
        # This allows more distinction between personas
        persona_confidence_range = {
            "Financial Analyst": (0.25, 0.95),
            "Sustainability Consultant": (0.30, 0.98),
            "Infrastructure Designer": (0.25, 0.92),
            "Community Member": (0.20, 0.85),
            "Retailer": (0.25, 0.88),
        }
        
        min_conf, max_conf = persona_confidence_range.get(perspective.name, (0.2, 0.9))
        final_confidence = round(max(min_conf, min(base_confidence, max_conf)), 2)
        
        return stance, final_confidence

    def _personality_for(self, perspective_name: str) -> str:
        mapping = {
            "Financial Analyst": "Precise, strategic, and data-driven; focuses on ROI and financial impacts",
            "Sustainability Consultant": "Passionate, evidence-based, and urgency-focused on environmental outcomes",
            "Infrastructure Designer": "Balanced, detail-oriented, and systems-minded about urban mobility and design",
            "Community Member": "Empathetic, practical, and neighborhood-aware about daily life impacts",
            "Retailer": "Street-smart, pragmatic, and results-oriented about business viability",
        }
        return mapping.get(perspective_name, "Thoughtful and curious")

    def _opening_statement(self, speaker: dict[str, Any]) -> str:
        reasoned = speaker.get("reasoned", {})
        interpretation = reasoned.get("interpretation") or (speaker["evidence"][0]["text"] if speaker["evidence"] else "No strong evidence is available yet.")
        return (
            f"I open the debate from my lens of {speaker['focus']}. {speaker['position']} "
            f"Interpreting evidence: {interpretation}"
        )

    def _rebuttal_statement_with_memory(self, speaker: dict[str, Any], target: dict[str, Any]) -> str:
        reasoned = speaker.get("reasoned", {})
        conclusion = reasoned.get("conclusion") or (speaker["evidence"][0]["text"] if speaker["evidence"] else "I lack strong evidence here.")
        return (
            f"I directly respond to {target['perspective']}'s opening. "
            f"While {target['perspective']} emphasizes {target['focus']}, my perspective on {speaker['focus']} leads me to different conclusions. "
            f"{speaker['position']} Reasoned conclusion: {conclusion}"
        )

    def _counterpoint_statement_with_memory(self, speaker: dict[str, Any], previous: List[dict[str, Any]]) -> str:
        reasoned = speaker.get("reasoned", {})
        evidence = reasoned.get("interpretation") or (speaker["evidence"][0]["text"] if speaker["evidence"] else "More evidence needed.")
        prior_perspectives = ", ".join([p["perspective"] for p in previous])
        return (
            f"Having heard {prior_perspectives}, I want to highlight what could be overlooked: {speaker['key_issue']}. "
            f"Both prior speakers raise valid points, but my concern is crucial. {speaker['position']} "
            f"Evidence interpretation: {evidence}"
        )

    def _compromise_statement_with_memory(self, speaker: dict[str, Any], previous: List[dict[str, Any]]) -> str:
        reasoned = speaker.get("reasoned", {})
        evidence = reasoned.get("interpretation") or (speaker["evidence"][0]["text"] if speaker["evidence"] else "Implementation details pending.")
        prior_perspectives = ", ".join([p["perspective"] for p in previous])
        previous_concerns = "; ".join([p.get("key_issue", "") for p in previous if p.get("key_issue")])
        
        return (
            f"After hearing {prior_perspectives}, I see a path forward that addresses key concerns. "
            f"Looking at the evidence, a workable solution would: balance {speaker['focus']} with the concerns raised about {previous_concerns}. "
            f"This requires collaboration and staged implementation. "
            f"{speaker['position']} Evidence: {evidence}"
        )

    def _pragmatic_statement_with_memory(self, speaker: dict[str, Any], previous: List[dict[str, Any]]) -> str:
        reasoned = speaker.get("reasoned", {})
        evidence = reasoned.get("interpretation") or (speaker["evidence"][0]["text"] if speaker["evidence"] else "Operational details require discussion.")
        prior_perspectives = ", ".join([p["perspective"] for p in previous])
        all_focuses = "; ".join([p.get("focus", "") for p in previous if p.get("focus")])
        
        return (
            f"From my vantage point after hearing {prior_perspectives}, I emphasize {speaker['key_issue']}. "
            f"Any practical solution must respect these interconnected concerns: {all_focuses}. "
            f"Implementation requires careful sequencing and stakeholder engagement. "
            f"{speaker['position']} Evidence: {evidence}"
        )

    def _evaluate_relations(self, speaker: dict[str, Any], previous: List[dict[str, Any]]) -> List[dict[str, str]]:
        analysis: List[dict[str, str]] = []
        if not previous:
            analysis.append({
                "target": None,
                "type": "opening",
                "reason": "Initial perspective framing and evidence grounding.",
            })
            return analysis

        for target in previous:
            relation, reason = self._analyze_relation(speaker, target)
            if relation == "conflict":
                self.debate_state.track_conflict(speaker["perspective"], target["perspective"], reason)
            elif relation == "agreement":
                self.debate_state.track_agreement(speaker["perspective"], target["perspective"], reason)

            analysis.append({
                "target": target["perspective"],
                "type": relation,
                "reason": reason,
            })

        return analysis

    def _analyze_relation(self, speaker: dict[str, Any], target: dict[str, Any]) -> tuple[str, str]:
        speaker_score = self.stance_map.get(speaker["stance"].lower(), 0.5)
        target_score = self.stance_map.get(target["stance"].lower(), 0.5)

        speaker_words = set(re.findall(r"\w+", speaker["position"].lower()))
        target_words = set(re.findall(r"\w+", target["position"].lower()))
        overlap = len(speaker_words & target_words)

        if abs(speaker_score - target_score) >= 0.4:
            return "conflict", f"Stance difference: {speaker['stance']} vs {target['stance']}"
        if overlap >= 3:
            return "agreement", "Shared reasoning themes"
        if (speaker_score >= 0.55 and target_score >= 0.55) or (speaker_score <= 0.45 and target_score <= 0.45):
            return "agreement", f"Similar direction between {speaker['stance']} and {target['stance']}"

        return "conflict", "Different priorities and evidence"
