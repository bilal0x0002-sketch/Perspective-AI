# Perspective AI - System Architecture

## 🏗️ High-Level Overview

Perspective AI is a multi-agent debate system that generates evidence-based policy analysis from 19 distinct professional perspectives. The system orchestrates parallel evidence retrieval, LLM reasoning, and debate simulation to produce nuanced recommendations.

```
User Query
    ↓
Query Classification (Policy/Technical/Implementation)
    ↓
Persona Selection (5 core + filtered extended)
    ↓
┌──────────────────────────────────────────┐
│  For Each Selected Persona (Parallel):   │
├──────────────────────────────────────────┤
│  1. Retrieve Evidence (role-specific)    │
│  2. LLM Reasoning (interpret evidence)   │
│  3. Generate Position (stance + text)    │
│  4. Build Debate State                   │
└──────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────┐
│  5-Round Debate Simulation:              │
├──────────────────────────────────────────┤
│  Round 1: Opening statements             │
│  Round 2: Rebuttals (respond to prior)   │
│  Round 3: Counterpoints (challenge)      │
│  Round 4: Compromise (synthesis)         │
│  Round 5: Pragmatic (final position)     │
└──────────────────────────────────────────┘
    ↓
Synthesis & Recommendations
    ↓
Output: JSON with full debate transcript
```

---

## 📊 Two-Index Azure Search Architecture

The system uses **two separate Azure Search indexes** for different purposes:

### Index 1: Personas (`perspective-ai-personas`)

**Purpose**: Metadata about professional personas
**Content**: 19 persona definitions
**Update Frequency**: Rarely (only when adding/removing personas)
**Use Cases**: 
- Persona initialization and attribute lookup
- Persona filtering during selection
- System configuration

**Document Schema**:
```json
{
  "id": "financial-analyst-001",
  "name": "Financial Analyst",
  "role": "Financial Analyst",
  "focus": "economic impacts, business activity, and market incentives",
  "evidence_topics": ["urban economics", "transport reports", "downtown commerce"],
  "default_stance": "conditional support",
  "key_issue": "economic transition risk",
  "category": "core"
}
```

### Index 2: Evidence (`perspective-ai-evidence`)

**Purpose**: Policy documents, research, case studies
**Content**: 10+ customizable evidence documents
**Update Frequency**: Frequently (as new research/data available)
**Use Cases**:
- Role-specific evidence retrieval during debate
- Persona-filtered searches (e.g., "Financial Analyst evidence only")
- Citation tracking for reasoning transparency

**Document Schema**:
```json
{
  "id": "econ-001",
  "content": "Congestion pricing in downtown zones...",
  "source": "Journal of Urban Economics",
  "url": "https://example.com/research",
  "category": "economic-impact",
  "author": "Dr. Michael Chen",
  "date": "2024-01-15",
  "relevance_keywords": ["congestion pricing", "revenue", "efficiency"],
  "personas": ["Financial Analyst", "Transportation Engineer"],
  "stance": "supports"
}
```

### Why Two Indexes?

1. **Separation of Concerns**
   - Personas: Static reference data, rarely changed
   - Evidence: Dynamic policy documents, frequently updated

2. **Performance Optimization**
   - Personas index is small (19 docs) → fast lookup
   - Evidence index is queried frequently → can scale independently

3. **Query Specificity**
   - Persona queries: Exact match on ID (fast lookup)
   - Evidence queries: Full-text search + filtering (complex)

4. **Access Patterns**
   - Personas loaded once at startup
   - Evidence retrieved per-persona per-round (frequent)

---

## 🔄 Data Flow Architecture

### Phase 1: Initialization

```
.env Configuration
    ↓
Load Environment Variables:
  - AZURE_SEARCH_ENDPOINT
  - AZURE_SEARCH_KEY
  - FOUNDY_INDEX (points to evidence index)
  - AZURE_OPENAI_ENDPOINT
  - AZURE_OPENAI_KEY
    ↓
Load Personas from Azure Search (Index 1)
    ↓
Initialize 5 Core Personas in Debate State
    ↓
Ready for Query
```

### Phase 2: Query Ingestion

```
User Query Input
    ↓
Query Classification:
  - Detect question type (policy/technical/implementation)
  - Extract key terms and context
    ↓
Persona Selection:
  - Load all 19 personas
  - Apply relevance filter
  - Select 5 best matches
    ↓
Pass selected personas to Orchestrator
```

### Phase 3: Evidence Retrieval (Per Persona)

```
For Each Selected Persona:

Persona Context:
  - name: "Financial Analyst"
  - role: "Financial Analyst"
  - focus: "economic impacts"
  - evidence_topics: ["urban economics"]

    ↓
    
Build Search Query:
  - Topic: user query + persona focus
  - Filter: personas/any(p: p eq 'Financial Analyst')
    ↓
Execute Azure Search Query:
  - Full-text search on evidence.json content
  - Apply persona collection filter
  - Score by relevance
    ↓
Return Top 3-5 Documents:
  - [econ-001, retail-001, developer-001]
    ↓
Format as Evidence List:
  - {id, content, source, url, category, personas[], stance}
```

**Critical OData Filter Syntax:**
```
CORRECT:  personas/any(p: p eq 'PersonaName')
WRONG:    search.in(personas, 'PersonaName')  ← 400 Bad Request
```

### Phase 4: LLM Reasoning

```
For Each Persona with Retrieved Evidence:

Input:
  - evidence: [{id, content, source, ...}]
  - question: "Should we implement congestion pricing?"
  - persona: {name, role, focus, key_issue, default_stance}

    ↓
    
Build System Prompt (Role-Specific):
  - YOU ARE: {PersonaName}
  - ROLE: {Role description}
  - FOCUS: {Area of expertise}
  - ANALYZE ONLY: {Role-specific directives}
  - FORBIDDEN: {Invalid reasoning patterns}
  - GOOD OUTPUT EXAMPLE: {Role-specific example}

    ↓
    
Call LLM API:
  - System: persona-specific prompt (strict role constraints)
  - User: evidence + question + analytical directives
  - Temperature: 0.2 (deterministic, persona-consistent)
  - Max Tokens: 800
  - Response Format: JSON with ranked, interpretation, conclusion
    ↓
    
Parse LLM Response:
  {
    "ranked": [
      {"id": "econ-001", "score": 0.95, "relevance": "why this matters", "reasoning": "analysis"}
    ],
    "interpretation": "What the evidence means",
    "implications": ["Implication 1", "Implication 2"],
    "conclusion": "PERSONA-SPECIFIC CONCLUSION",
    "contradiction": false
  }
    ↓
    
Return Reasoned Dict
```

**LLM Configuration:**
- **Endpoint**: `AZURE_OPENAI_ENDPOINT` or `https://api.deepseek.com`
- **API Key**: `AZURE_OPENAI_KEY`
- **Model**: `AZURE_OPENAI_MODEL` (e.g., "deepseek-chat")
- **Temperature**: 0.2 (low = more deterministic)
- **Max Tokens**: 800

**Fallback Reasoning** (if LLM unavailable):
If LLM fails, system falls back to keyword-based reasoning:
- Extract role-specific positive/negative keywords
- Score evidence by keyword overlap
- Generate synthetic "interpretation" and "conclusion"
- Result: Still unique per persona (keyword sets differ)

### Phase 5: Position Building

```
For Each Persona:

Input:
  - reasoned: {ranked, interpretation, implications, conclusion, contradiction}
  - stance: "conditional support" (computed from evidence)
  - confidence: 0.69 (evidence match score)

    ↓
    
Build Initial Position:
  - Use LLM conclusion (unique per role)
  - Add confidence and stance
  - Format as position statement
  - Example: "Congestion pricing is financially viable and beneficial, 
    generating significant net revenue. Conditional support is warranted 
    with targeted mitigation."
    ↓
    
Create Agent Data:
  {
    "perspective": "Financial Analyst",
    "role": "Financial Analyst",
    "stance": "conditional support",
    "confidence": 0.69,
    "position": "...",
    "evidence": [...],
    "reasoned": {...}
  }
    ↓
    
Add to Debate State
```

### Phase 6: Debate Simulation

```
For Each of 5 Rounds:

Input: agents[] with positions, evidence, reasoning

Round Logic:
  1. Determine who speaks (rotate or relevance-based)
  2. Speaker retrieves NEW evidence for this round
  3. Speaker generates response considering:
     - Their core position (stance)
     - Previous speakers' arguments
     - New evidence retrieved
     - Round-specific objective:
       - Round 2: Rebuttal (respond to prior)
       - Round 3: Counterpoint (challenge others)
       - Round 4: Compromise (find common ground)
       - Round 5: Pragmatic (final synthesis)

Output: Generated debate round with:
  - speaker: PersonaName
  - statement: Their argument
  - targets: Who they're responding to
  - evidence_used: New citations
  - analysis: What they agree/disagree on

Store in rounds[] array
```

### Phase 7: Synthesis & Output

```
Input: All debate rounds + agent reasoning

Synthesize:
  1. Extract key arguments per round
  2. Identify consensus areas
  3. Identify conflict areas
  4. Find strongest/weakest arguments
  5. Generate final recommendation

Output JSON:
  {
    "query": "Should we implement congestion pricing?",
    "mode": "real",
    "summary": {
      "recommendation": "Phased implementation with...",
      "agreement": 0.61,
      "conflict": 0.35,
      "consensus_confidence": 0.7,
      "strongest_argument": "Sustainability Consultant",
      "weakest_argument": "Transportation Engineer"
    },
    "agents": [...all agent data...],
    "rounds": [...all debate rounds...]
  }
```

---

## 🏛️ Module Architecture

### Core Modules

#### `agent/main.py`
**Purpose**: CLI entry point and scenario orchestration
**Key Functions**:
- `run_scenario(query, mode, personas)` - Main entry point
- Mode selection: `--real` (Azure Search) vs `--offline` (mock)
- Returns complete debate structure

#### `agent/orchestrator.py`
**Purpose**: Coordinate the complete debate flow
**Key Functions**:
- `run(query, perspectives, progress_callback)` - Orchestrate all phases
- Evidence retrieval → Reasoning → Position building → Debate simulation
- **CRITICAL FIX**: Fresh `initial_statement` per persona iteration
- Emits progress events: "stage", "agent", "round", "synthesis"

#### `agent/reasoning_core.py`
**Purpose**: Transform evidence into role-specific conclusions via LLM
**Key Functions**:
- `reason(evidence, question, perspective)` - Main entry point
- `_call_remote_reasoner()` - LLM API integration
- `_get_role_specific_keywords()` - Fallback reasoning
- Handles multiple LLM providers (Azure, DeepSeek, GitHub Models)
- Role-specific system prompts with analysis constraints
- Falls back to keyword-based reasoning if LLM unavailable

#### `agent/persona_agents.py`
**Purpose**: Convert LLM reasoning into debate positions
**Key Functions**:
- `build_initial(perspective_name, reasoned, stance, query)` - Build opening position
- Uses LLM `conclusion` field (unique per role)
- Returns `{"position": text, "argument": text}`

#### `agent/foundry_client.py`
**Purpose**: Route evidence retrieval between Azure Search and mock data
**Key Functions**:
- `retrieve_evidence(perspective, query)` - Main retrieval entry point
- Mode-based routing: `--real` calls `_real_search()`, `--offline` uses mock
- Uses `FOUNDY_INDEX` environment variable (must point to evidence index)

#### `agent/knowledge.py`
**Purpose**: Azure Search adapter for evidence queries
**Key Functions**:
- `search(perspective, query)` - Execute filtered search
- OData filter syntax: `personas/any(p: p eq 'PersonaName')`
- Returns ranked documents with relevance scores

#### `agent/perspectives.py`
**Purpose**: Persona management and definitions
**Key Functions**:
- `load_perspectives(mode)` - Load personas from Azure Search
- Populates persona objects with role, focus, evidence_topics, stance

#### `agent/synthesizer.py`
**Purpose**: Generate final recommendations from debate
**Key Functions**:
- `synthesize_debate(agents, rounds, query)` - Create final summary
- Computes agreement/conflict metrics
- Identifies strongest/weakest arguments

---

## 🔐 Environment Configuration

### Required Variables

```powershell
# Azure Search (Evidence Index)
$env:AZURE_SEARCH_ENDPOINT = "https://perspective-search.search.windows.net"
$env:AZURE_SEARCH_KEY = "YourSearchKey"
$env:FOUNDY_INDEX = "perspective-ai-evidence"  # CRITICAL: Points to evidence index

# LLM Provider (Select One)
$env:AZURE_OPENAI_ENDPOINT = "https://api.deepseek.com"
$env:AZURE_OPENAI_KEY = "sk-xxxxx"
$env:AZURE_OPENAI_MODEL = "deepseek-chat"

# Optional
$env:FLASK_ENV = "development"
$env:FLASK_DEBUG = "1"
```

### Configuration Loading

1. **`.env` file** (highest priority)
   ```
   AZURE_SEARCH_ENDPOINT=...
   AZURE_SEARCH_KEY=...
   FOUNDY_INDEX=perspective-ai-evidence
   ```

2. **Environment variables** (system or shell)
   ```powershell
   $env:AZURE_SEARCH_ENDPOINT = "..."
   ```

3. **Loaded by**:
   - `foundry_client.py` - Uses `dotenv.load_dotenv()`
   - `reasoning_core.py` - Uses `os.getenv()`

---

## 🌊 Event Flow (Web UI)

The web interface uses Server-Sent Events (SSE) for real-time debate streaming.

```
Client Browser
    ↓
GET /api/debate-stream?query=...
    ↓
Flask Route (web.py):
  1. Create event_queue (thread-safe Queue)
  2. Spawn worker thread
  3. Start event_stream generator
    ↓
Worker Thread:
  1. Call run_scenario(query, progress_callback=callback)
  2. For each event, put() into event_queue
  3. Callback receives: ("stage"|"agent"|"round", payload)
    ↓
SSE Stream Generator:
  1. Loop: get() from event_queue
  2. Format: "event: {type}\ndata: {json}\n\n"
  3. Yield to browser
    ↓
Browser (JavaScript):
  1. EventSource listens on SSE
  2. Receives events in real-time
  3. Updates UI (persona cards, debate rounds)
  4. Shows progress indicators
```

**Event Types**:
- `stage`: {"stage": "retrieval", "message": "...", "perspective": "..."}
- `agent`: {"perspective": "...", "stance": "...", "confidence": 0.69, "position": "..."}
- `round`: {"round": {...full round data...}}
- `done`: {...final synthesis...}
- `error`: {"message": "..."}

---

## 🔌 LLM Provider Integration

### Supported Providers

1. **Azure OpenAI** (via OpenAI SDK)
   ```python
   from openai import AzureOpenAI
   client = AzureOpenAI(
       api_key=api_key,
       api_version="2024-02-15-preview",
       azure_endpoint=endpoint,
   )
   ```

2. **DeepSeek** (OpenAI-compatible)
   ```python
   from openai import OpenAI
   client = OpenAI(
       api_key=api_key,
       base_url="https://api.deepseek.com/v1"
   )
   ```

3. **GitHub Models** (OpenAI-compatible)
   ```python
   from openai import OpenAI
   client = OpenAI(
       api_key=api_key,
       base_url="https://models.inference.ai.azure.com"
   )
   ```

4. **Fallback** (HTTP via requests)
   If SDK fails, retry with HTTP POST to `/v1/chat/completions`

### Response Parsing

```python
# Try JSON parsing first
parsed = json.loads(content)

# If fails, try markdown code block extraction
match = re.search(r'```(?:json)?\s*({.*?})\s*```', content, re.DOTALL)
if match:
    parsed = json.loads(match.group(1))
```

---

## 📈 Scaling Considerations

### Current Capacity
- **Personas**: 19 (5 core + 14 extended)
- **Evidence Documents**: 10+ (customizable)
- **Debate Rounds**: 5 sequential
- **Concurrent Requests**: Limited by Flask development server

### Bottlenecks
1. **LLM API Latency**: ~2-5 seconds per persona response
2. **Azure Search Queries**: ~500ms per query
3. **Total Debate Time**: ~60-90 seconds (5 personas × 5 rounds)

### Optimization Opportunities
1. **Parallel Evidence Retrieval**: Retrieve all personas' evidence simultaneously
2. **LLM Batching**: Send multiple persona prompts in parallel
3. **Evidence Caching**: Cache frequently-searched evidence
4. **Index Optimization**: Add Azure Search performance tuning

---

## 🧪 Testing Architecture

### Unit Tests
- Individual module testing (reasoning, evidence retrieval, position building)

### Integration Tests
- Full debate flow with mock evidence
- LLM response parsing and error handling

### End-to-End Tests
- Web UI debate submission
- CLI scenario execution
- SSE event streaming

---

## 🐛 Recent Bug Fixes

### Bug: Identical Persona Positions in Web UI

**Root Cause**: Variable reuse in `orchestrator.py`
```python
# WRONG - only first persona got unique initial_statement
initial_statement = persona_out.get("position") if 'initial_statement' not in locals() else initial_statement
```

**Fix**: Track fallback separately, always get fresh position
```python
used_fallback = False
if not instr_result.get("compliant"):
    initial_statement = instr_result.get("fallback")
    used_fallback = True

if not used_fallback:
    initial_statement = persona_out.get("position")  # Fresh per iteration
```

**Impact**: Each persona now displays unique conclusions ✅

---

## 📋 Deployment Checklist

- [ ] Python 3.9+ installed
- [ ] All dependencies in requirements.txt installed
- [ ] Azure Search indexes created (personas + evidence)
- [ ] Evidence documents uploaded to Azure
- [ ] `.env` file configured with credentials
- [ ] `FOUNDY_INDEX` points to evidence index (not personas)
- [ ] LLM credentials verified and tested
- [ ] Web server starts: `python web.py --real`
- [ ] Browser loads: `http://127.0.0.1:5000`
- [ ] Sample debate runs successfully
- [ ] Events stream to browser in real-time

---

## 🎯 Future Architecture Enhancements

1. **Distributed Debate**: Run debate rounds in parallel
2. **Memory State**: Store debate outcomes for learning
3. **Multi-Round Conversation**: Continue debate across multiple sessions
4. **Custom Persona Templates**: Allow users to define new personas
5. **Evidence Versioning**: Track how evidence changes over time
6. **Advanced Synthesis**: ML-based recommendation generation
7. **Audit Trail**: Full logging of all reasoning decisions

