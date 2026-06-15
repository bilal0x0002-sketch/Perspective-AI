# Perspective AI - Multi-Agent Debate System

A sophisticated multi-agent reasoning system that generates nuanced, evidence-based policy debates from 19 distinct professional perspectives. Each persona retrieves role-specific evidence and generates unique conclusions, creating truly multifaceted analysis.

## 🎯 What It Does

Given a policy question, the system:

1. **Selects Relevant Personas** (5 core + 14 extended perspectives)
2. **Retrieves Evidence** (Each persona gets different, role-specific documents)
3. **Generates Opening Statements** (Unique initial positions)
4. **Engages in 5-Round Debate**:
   - Opening statements
   - Rebuttals (addressing previous speakers)
   - Counterpoints (challenging assumptions)
   - Compromise proposals (synthesizing concerns)
   - Pragmatic conclusions (balanced recommendations)
5. **Outputs Structured Analysis** (Evidence, reasoning, implications, conclusions)

## ✨ Key Features

✅ **19 Professional Personas** - Diverse perspectives from finance to social equity to environment
✅ **Evidence-Based Reasoning** - Each persona retrieves documents matching their expertise
✅ **Dynamic Debate Flow** - Personas respond to each other, not isolated
✅ **Real-Time Streaming** - Watch debate unfold live in web UI
✅ **Azure Search Integration** - Two-index architecture (personas + evidence)
✅ **Easy Customization** - Edit JSON files to add evidence and personas
✅ **Multiple LLM Support** - Azure OpenAI, DeepSeek, GitHub Models
✅ **Offline Mode** - Persona-aware reasoning without LLM (fallback)

## 📊 Example Output

### Question: "Should the city implement congestion pricing?"

**Financial Analyst** (Supporting Evidence: Economic Impact Documents)
- Evidence: Revenue generation, traffic reduction data
- Conclusion: "Conditional support - costs decrease long-term, supports transit"

**Sustainability Consultant** (Supporting Evidence: Environmental Documents)
- Evidence: Emissions reduction, air quality improvements
- Conclusion: "Strong support - aligns with climate targets"

**Community Member** (Supporting Evidence: Equity Documents)
- Evidence: Low-income impact studies, affordability concerns
- Conclusion: "Oppose without protection mechanisms"

**Infrastructure Designer** (Supporting Evidence: Transit Infrastructure Documents)
- Evidence: Technology requirements, implementation best practices
- Conclusion: "Support - if coordinated with transit expansion"

**Retailer** (Supporting Evidence: Business Impact Documents)
- Evidence: Sales recovery timelines, cost structure analysis
- Conclusion: "Conditional support - need implementation timeline"

---

## 🚀 Quick Start (3 Minutes)

### Prerequisites
- Python 3.9+
- Azure Search account (with 2 indexes)
- LLM endpoint (Azure OpenAI, DeepSeek, or GitHub Models)

### Setup

```powershell
# 1. Set Azure credentials
$env:AZURE_SEARCH_ENDPOINT = "https://your-service.search.windows.net"
$env:AZURE_SEARCH_KEY = "your-api-key"
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"

# 2. Create evidence index (one-time)
python scripts/setup_evidence_index.py

# 3. Upload evidence documents
python scripts/upload_evidence.py

# 4. Start web UI
python web.py --real

# 5. Open browser
# http://127.0.0.1:5000
```

### Use via Web UI

1. Open browser to `http://127.0.0.1:5000`
2. Enter your policy question
3. Click "Run Debate"
4. Watch personas debate in real-time
5. Export results to JSON

### Use via CLI

```powershell
python -m agent.main `
  --query "Should the city implement congestion pricing?" `
  --mode real
```

---

## 📁 Project Structure

```
data/
├── personas.json           # 19 personas (editable)
└── evidence.json           # Evidence documents (editable)

scripts/
├── setup_index.py          # Create personas index
├── upload_personas.py      # Upload personas to Azure
├── setup_evidence_index.py # Create evidence index
└── upload_evidence.py      # Upload evidence to Azure

agent/
├── main.py                 # CLI entry point
├── orchestrator.py         # Debate orchestration
├── foundry_client.py       # Evidence retrieval
├── reasoning_core.py       # Evidence interpretation & conclusions
├── persona_agents.py       # Initial position building
├── knowledge.py            # Azure Search adapter
├── perspectives.py         # Persona definitions
├── persona_retriever.py    # Load personas from Azure
├── synthesizer.py          # Debate synthesis
├── telemetry.py            # Analytics
└── mcp_tool.py             # MCP integration

templates/
└── index.html              # React 18 web UI

web.py                      # Flask server
requirements.txt            # Python dependencies
```

---

## 🎓 How It Works

### Architecture

```
User Query
    ↓
Persona Selection (5 core + filter extended)
    ↓
For Each Persona:
  1. Load perspective (focus, role, expertise)
  2. Retrieve evidence (role-specific documents)
  3. Interpret evidence (extract key findings)
  4. Generate initial stance (position statement)
    ↓
5-Round Debate:
  • Each round: persona retrieves new evidence
  • Each round: persona responds to previous speakers
  • Positions evolve based on debate
    ↓
Synthesis & Output
    ↓
Web UI / CLI Output
```

### Two-Index Azure Search Architecture

**Index 1: Personas** (`perspective-ai-personas`)
- Metadata about each professional perspective
- Used for: Persona initialization, attribute lookup
- Documents: 19 persona definitions

**Index 2: Evidence** (`perspective-ai-evidence`)
- Policy documents, research, case studies
- Used for: Evidence retrieval during debate rounds
- Documents: 10+ customizable evidence documents

**Why Two Indexes?**
- Personas need different evidence retrieval than personas metadata
- Allows role-specific searches (Financial Analyst searches for "revenue", "cost")
- Separates concerns: personas rarely change, evidence constantly updated

---

## 🔧 Customization

### Add Evidence

1. Edit `data/evidence.json`
2. Add a document object:

```json
{
  "id": "unique-id",
  "content": "Full text of evidence...",
  "source": "Publication or Organization",
  "url": "https://link-to-source.com",
  "category": "economic-impact",
  "author": "Author Name",
  "date": "2024-03-20",
  "relevance_keywords": ["keyword1", "keyword2"],
  "personas": ["Financial Analyst", "Sustainability Consultant"],
  "stance": "supports"
}
```

3. Run: `python scripts/upload_evidence.py`

### Add Persona

1. Edit `data/personas.json`
2. Add a persona object:

```json
{
  "id": "persona-020",
  "name": "Your Persona Name",
  "role": "Your Professional Role",
  "focus": "Area of expertise",
  "evidence_topics": ["topic1", "topic2"],
  "default_stance": "position",
  "key_issue": "main concern",
  "category": "extended"
}
```

3. Run: `python scripts/upload_personas.py`

### Configure LLM

```powershell
# Azure OpenAI
$env:AZURE_OPENAI_ENDPOINT = "https://..."
$env:AZURE_OPENAI_KEY = "your-key"
$env:AZURE_OPENAI_MODEL = "gpt-4"

# Or: DeepSeek
$env:DEEPSEEK_API_KEY = "your-key"

# Or: GitHub Models
$env:GITHUB_TOKEN = "your-token"
```

---

## 📚 Evidence Categories

- `economic-impact` - Business costs, revenue, efficiency
- `environmental` - Emissions, air quality, climate
- `social-equity` - Fairness, low-income impact
- `infrastructure` - Transit, design, mobility
- `business-impact` - Retail, commerce, operations
- `policy-design` - Implementation, governance
- `risk-analysis` - Challenges, failures, risks
- `health-impact` - Public health, air quality
- `technology-implementation` - Systems, enforcement
- `real-estate` - Property values, development

---

## 👥 Available Personas

### Core (5)
- Financial Analyst
- Sustainability Consultant
- Infrastructure Designer
- Community Member
- Retailer

### Extended (14)
- Public Health Official
- Transportation Engineer
- Climate Scientist
- Equity Advocate
- Real Estate Developer
- Data Scientist
- Community Organizer
- Tech Entrepreneur
- Policy Advocate
- Social Worker
- Law Enforcement Officer
- Media Representative
- Cultural Advocate
- Senior Citizen Advocate

---

## 🌐 Web UI

Access at `http://127.0.0.1:5000`

### Features
- **Live Debate Streaming** - See arguments unfold in real-time
- **Persona Cards** - View evidence and reasoning for each persona
- **Round Visualization** - Opening → Rebuttal → Counterpoint → Compromise → Pragmatic
- **Evidence Display** - See which documents influenced each persona
- **Export JSON** - Download complete debate with all data
- **Summary Metrics** - Confidence scores, key risks, recommended stance

---

## 💻 CLI Usage

### Basic Debate
```powershell
python -m agent.main --query "Your question?" --mode real
```

### Offline Mode (No LLM)
```powershell
python -m agent.main --query "Your question?" --mode offline
```

### Specify Personas
```powershell
python -m agent.main `
  --query "Your question?" `
  --personas "Financial Analyst,Sustainability Consultant" `
  --mode real
```

### Output Format
```
Question: Your question?

=== Selected Agents ===
Financial Analyst, Sustainability Consultant, ...

=== Agent Evidence Summaries ===
--- Financial Analyst (Financial Analyst) ---
Focus: economic impacts, business activity
Evidence:
  - econ-001: Document title and key finding
  - retail-001: Another relevant document

Reasoning Summary:
  Interpretation: What the evidence means
  Implications: Business and economic impacts
  Conclusion: [Stance based on evidence]

[Continues for all personas...]

=== Final Synthesis ===
Consensus approach, key tensions, recommended policy
```

---

## 🔧 Configuration

### Environment Variables

```powershell
# Azure Search (Required)
$env:AZURE_SEARCH_ENDPOINT = "https://your-service.search.windows.net"
$env:AZURE_SEARCH_KEY = "your-api-key"
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"

# LLM Selection (Pick one)
# Option 1: Azure OpenAI
$env:AZURE_OPENAI_ENDPOINT = "https://..."
$env:AZURE_OPENAI_KEY = "key"
$env:AZURE_OPENAI_MODEL = "gpt-4"

# Option 2: DeepSeek
$env:DEEPSEEK_API_KEY = "key"

# Option 3: GitHub Models
$env:GITHUB_TOKEN = "token"

# Flask (Optional)
$env:FLASK_ENV = "development"
$env:FLASK_DEBUG = "1"
```

---

## � Recent Fixes (June 2026)

### ✅ Fixed: Web UI Displaying Identical Persona Positions

**Problem:** Web UI was showing identical Financial Analyst position text for all personas despite backend LLM generating unique conclusions.

**Root Cause:** Bug in `agent/orchestrator.py` line 289:
```python
# WRONG - reused first persona's initial_statement for all subsequent personas
initial_statement = persona_out.get("position") if 'initial_statement' not in locals() else initial_statement
```

The conditional check `'initial_statement' not in locals()` was only true for the first persona. For personas 2-5, it fell through to the `else` clause and reused the previous persona's `initial_statement` variable.

**Solution:** Track when fallback text is used separately, and always update `initial_statement` from fresh persona output:
```python
# CORRECT - unique statement per iteration
used_fallback = False
if not instr_result.get("compliant"):
    initial_statement = instr_result.get("fallback")
    used_fallback = True
else:
    # ... process evidence ...

# Always get fresh position from persona, unless using fallback
if not used_fallback:
    initial_statement = persona_out.get("position")
```

**Verification:**
- LLM conclusions are unique per persona ✅
- Web UI now displays different conclusions ✅
- Each persona shows role-specific interpretation ✅
- Evidence retrieval per persona confirmed ✅

**Files Modified:**
- `agent/orchestrator.py` - Fixed variable reuse bug
- `agent/persona_agents.py` - Changed to use LLM `conclusion` field instead of generic `interpretation`

---

## �🚨 Troubleshooting

| Problem | Solution |
|---------|----------|
| All personas show identical position | ✅ **FIXED** - See "Recent Fixes" section above. Update to latest code |
| All personas identical output | Check `AZURE_SEARCH_INDEX` = `perspective-ai-evidence` |
| "No relevant evidence found" | Verify personas in `data/evidence.json` match searched personas |
| JSON syntax error | Run `python test_evidence.py` |
| Azure connection fails | Check credentials and endpoint URL |
| Web UI won't start | Ensure port 5000 is available |
| LLM not responding | Verify API key and endpoint configuration |

---

## 📖 Documentation

- **[QUICK_START.md](QUICK_START.md)** - 3-minute setup
- **[COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md)** - Full workflow reference
- **[EVIDENCE_DATA_GUIDE.md](EVIDENCE_DATA_GUIDE.md)** - Evidence field reference
- **[AZURE_SETUP_GUIDE.md](AZURE_SETUP_GUIDE.md)** - Detailed Azure configuration
- **[TWO_INDEX_ARCHITECTURE.md](TWO_INDEX_ARCHITECTURE.md)** - Architecture explanation
- **[COMPLETE_SETUP_GUIDE.md](COMPLETE_SETUP_GUIDE.md)** - Full setup instructions

---

## 🎬 Demo Workflow

```powershell
# 1. Setup (first time only)
$env:AZURE_SEARCH_ENDPOINT = "https://..."
$env:AZURE_SEARCH_KEY = "..."
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"

python scripts/setup_evidence_index.py
python scripts/upload_evidence.py

# 2. Start server
python web.py --real

# 3. Open browser
# http://127.0.0.1:5000

# 4. Enter question and watch debate

# 5. To add more evidence:
#    - Edit data/evidence.json
#    - Run python scripts/upload_evidence.py
#    - Refresh browser
```

---

## 📝 Dependencies

```
flask
flask-cors
requests
azure-search-documents
openai
python-dotenv
```

Install with: `pip install -r requirements.txt`

---

## 🤝 Use Cases

✅ **Policy Analysis** - Understand implications from multiple stakeholder perspectives
✅ **Stakeholder Engagement** - Present balanced view of policy debates
✅ **Decision Support** - Get evidence-based recommendations before implementation
✅ **Public Communication** - Explain complex policy tradeoffs
✅ **Research** - Study how different expertise domains view same issue
✅ **Education** - Learn about nuanced policy debates and evidence

---

## 🎯 Example Policies

The system works with any policy question. Examples:
- "Should the city implement congestion pricing?"
- "Should we transition to electric buses by 2030?"
- "Should parking minimums be eliminated in downtown?"
- "Should we mandate mixed-income housing?"
- "Should we expand the bike lane network?"

---

## 💡 Key Insights

1. **Evidence Matters** - Each persona gets different research, generating unique conclusions
2. **Dynamic Debate** - Personas respond to each other, arguments evolve
3. **Multiple Perspectives** - 19 viewpoints capture real policy complexity
4. **Balanced Output** - System shows tensions and tradeoffs, not false consensus
5. **Customizable** - Add your own evidence and personas for specific contexts

---

## 📞 Support

**For setup issues**: Check `AZURE_SETUP_GUIDE.md`

**For customization**: Check `EVIDENCE_DATA_GUIDE.md`

**For architecture**: Check `TWO_INDEX_ARCHITECTURE.md`

**For workflow**: Check `COMPLETE_WORKFLOW.md`

---

## 📜 License

[Your License Here]

---

## 🚀 Get Started

1. Read [QUICK_START.md](QUICK_START.md) (3 minutes)
2. Run setup commands from Prerequisites section
3. Open web UI at http://127.0.0.1:5000
4. Ask a policy question
5. Watch 19 perspectives debate 🎯

**Ready to generate multifaceted policy analysis!**
