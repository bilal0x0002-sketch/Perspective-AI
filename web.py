import argparse
import json
import os
import queue
import threading

from flask import Flask, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from agent.foundry_client import FoundryClient
from agent.main import run_scenario
from agent.perspectives import default_perspectives

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

# ============================================================================
# API ENDPOINT - Clean JSON for React frontend
# ============================================================================

@app.route("/api/config", methods=["GET"])
def api_config():
    """Return current configuration"""
    return jsonify({
        "mode": MODE,
    })

@app.route("/api/debate", methods=["POST"])
def api_debate():
    """Stream debate results as clean JSON"""
    data = request.get_json()
    query = data.get("query", "")
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Run the debate engine in the configured mode
    result = run_scenario(query, mode=MODE)
    
    # Transform data into optimized frontend format
    return jsonify(build_reason_response(result))

@app.route("/api/debate-stream", methods=["GET"])
def api_debate_stream():
    query = request.args.get("query", "")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    event_queue = queue.Queue()

    def progress_callback(event_type, payload):
        event_queue.put({"event": event_type, "payload": payload})

    def worker():
        try:
            result = run_scenario(query, mode=MODE, progress_callback=progress_callback)
            event_queue.put({"event": "done", "payload": build_reason_response(result)})
        except Exception as exc:
            event_queue.put({"event": "error", "payload": {"message": str(exc)}})
        finally:
            event_queue.put({"event": "close", "payload": {}})

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def event_stream():
        while True:
            item = event_queue.get()
            if item["event"] == "close":
                break
            data = json.dumps(item["payload"], ensure_ascii=False)
            yield f"event: {item['event']}\ndata: {data}\n\n"

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

@app.route("/api/reason", methods=["POST"])
def api_reason():
    """Explicit reasoning API exposing debate generation on top of retrieval."""
    data = request.get_json(silent=True) or {}
    query = data.get("query", "")

    if not query:
        return jsonify({"error": "No query provided"}), 400

    result = run_scenario(query, mode=MODE)
    return jsonify(build_reason_response(result))

@app.route("/api/retrieval", methods=["POST"])
def api_retrieval():
    """Return retrieval evidence for one or more perspectives."""
    data = request.get_json(silent=True) or {}
    query = data.get("query", "")
    perspectives = data.get("perspectives")

    if not query:
        return jsonify({"error": "No query provided"}), 400

    if not isinstance(perspectives, list) or not perspectives:
        perspectives = [p.name for p in default_perspectives()]

    client = FoundryClient(mode=MODE)
    retrieval = {}
    for perspective_name in perspectives:
        items = client.retrieve_evidence(perspective_name, query)
        retrieval[perspective_name] = [
            {
                "id": item.get("id"),
                "text": item.get("text"),
                "source": item.get("source"),
                "url": item.get("url"),
                "score": item.get("score"),
                "metadata": item.get("metadata"),
            }
            for item in items
        ]

    return jsonify({
        "mode": MODE,
        "query": query,
        "perspectives": perspectives,
        "retrieval": retrieval,
        "total_hits": sum(len(v) for v in retrieval.values()),
    })


def build_reason_response(result):
    agents = result["agents"]
    evidence_map = deduplicate_evidence(agents, result["rounds"])
    agent_confidences = [agent.get("confidence", 0.0) for agent in agents if isinstance(agent.get("confidence", 0.0), (int, float))]
    average_confidence = round(sum(agent_confidences) / len(agent_confidences), 2) if agent_confidences else 0.0

    return {
        "query": result["query"],
        "mode": result.get("mode", "offline"),
        "question_type": result.get("question_type", "policy"),
        "summary": {
            "recommendation": result["summary"]["final_recommendation"],
            "agreement": result["summary"]["agreement_level"],
            "conflict": result["summary"]["conflict_level"],
            "confidence": result["summary"]["consensus_confidence"],
            "agreement_level": result["summary"]["agreement_level"],
            "conflict_level": result["summary"]["conflict_level"],
            "consensus_confidence": result["summary"]["consensus_confidence"],
            "strongest_argument": result["summary"].get("strongest_argument", ""),
            "weakest_argument": result["summary"].get("weakest_argument", ""),
            "risk_balance": result["summary"].get("risk_balance", ""),
            "average_confidence": average_confidence,
            "evidence_count": len(evidence_map),
        },
        "agents": agents,
        "rounds": result["rounds"],
        "evidence_map": evidence_map,
    }


def deduplicate_evidence(agents, rounds):
    """Build centralized evidence map with deduplication"""
    evidence_map = {}
    evidence_id = 0
    
    for agent in agents:
        for evidence in agent.get("evidence", []):
            text = evidence.get("text", "")
            source = evidence.get("source", "")
            key = f"{text}|{source}"
            
            if key not in evidence_map:
                evidence_id += 1
                evidence_map[key] = {
                    "id": f"ev-{evidence_id}",
                    "text": text,
                    "source": source,
                    "used_by": []
                }
            evidence_map[key]["used_by"].append(agent.get("role", ""))
    
    for round_item in rounds:
        for evidence in round_item.get("evidence_used", []):
            text = evidence.get("text", "")
            source = evidence.get("source", "")
            key = f"{text}|{source}"
            
            if key not in evidence_map:
                evidence_id += 1
                evidence_map[key] = {
                    "id": f"ev-{evidence_id}",
                    "text": text,
                    "source": source,
                    "used_by": []
                }
            if round_item.get("speaker") not in evidence_map[key]["used_by"]:
                evidence_map[key]["used_by"].append(round_item.get("speaker", ""))
    
    return {v["id"]: v for v in evidence_map.values()}


# ============================================================================
# ROUTES
# ============================================================================

MODE = "offline"

@app.route("/", methods=["GET"])
def home():
    """Serve the new React-based frontend"""
    try:
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
        print(f"DEBUG: Attempting to read from: {template_path}")
        print(f"DEBUG: File exists: {os.path.exists(template_path)}")
        
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"DEBUG: Successfully read {len(content)} bytes")
            return content
    except Exception as e:
        print(f"ERROR in home(): {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>Error loading template: {e}</h1>"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Perspective AI web interface.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--real", action="store_true", help="Use real Foundry client mode.")
    group.add_argument("--online", action="store_true", help="Alias for --real; use online Foundry mode.")
    group.add_argument("--offline", action="store_true", help="Use offline mock mode (default).")
    args = parser.parse_args()

    if args.real or args.online:
        MODE = "real"
    else:
        MODE = "offline"

    print(f"Starting Perspective AI in '{MODE}' mode...")
    app.run(debug=False, host="127.0.0.1", port=5000)
