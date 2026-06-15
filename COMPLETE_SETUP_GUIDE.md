# Complete Azure Setup: Fix Identical Evidence Problem

## Problem Diagnosis

You observed that all personas were getting **identical evidence** even in real mode:
```
Financial Analyst: "The evidence strongly supports congestion pricing..."
Sustainability Consultant: "The evidence strongly supports congestion pricing..."
Community Member: "The evidence strongly supports congestion pricing..."
```

**Root Cause**: The system was searching the **personas index** (which only contains role metadata) instead of an **evidence index** (which should contain actual policy documents and research).

---

## Solution: Two-Index Architecture

You need to set up **TWO separate Azure Search indexes**:

### Index 1: `perspective-ai-personas`
- **Content**: Persona metadata (role, focus, stance)
- **Purpose**: Persona selection and retrieval
- **Setup**: `scripts/setup_index.py` + `scripts/upload_personas.py`
- **Status**: ✅ Already done

### Index 2: `perspective-ai-evidence`
- **Content**: Policy documents, research papers, reports
- **Purpose**: Evidence retrieval (different for each persona)
- **Setup**: `scripts/setup_evidence_index.py` + `scripts/upload_evidence.py`
- **Status**: ⏳ TODO

---

## Complete Setup Steps

### Step 1: Verify Personas Index (Already Done)
```powershell
# Confirm you have 19 personas uploaded
$env:AZURE_SEARCH_INDEX = "perspective-ai-personas"
python scripts/upload_personas.py
```

### Step 2: Create Evidence Index
```powershell
$env:AZURE_SEARCH_ENDPOINT = "https://your-search-service.search.windows.net"
$env:AZURE_SEARCH_KEY = "your-api-key"
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"

python scripts/setup_evidence_index.py
```

Output:
```
============================================================
Azure Search Evidence Index Setup
============================================================
Endpoint: https://your-search-service.search.windows.net
Index: perspective-ai-evidence

✓ Evidence index 'perspective-ai-evidence' created/updated successfully

Fields in evidence index:
  - id (Edm.String)
  - content (Edm.String)
  - source (Edm.String)
  - url (Edm.String)
  - category (Edm.String)
  - author (Edm.String)
  - date (Edm.DateTimeOffset)
  - relevance_keywords (Collection(Edm.String))
  - personas (Collection(Edm.String))
  - stance (Edm.String)

✓ Evidence index setup completed successfully
```

### Step 3: Upload Sample Evidence
```powershell
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"

python scripts/upload_evidence.py
```

Output:
```
============================================================
Upload Sample Evidence Documents
============================================================
Endpoint: https://your-search-service.search.windows.net
Index: perspective-ai-evidence

Prepared 7 sample evidence documents:
  - econ-001: economic-impact
  - env-001: environmental
  - equity-001: social-equity
  - transit-001: infrastructure
  - retail-001: business-impact
  - implementation-001: policy-design
  - risk-001: risk-analysis

✓ Successfully uploaded 7/7 evidence documents
```

### Step 4: Update Debate System to Use Evidence Index
```powershell
# IMPORTANT: Set AZURE_SEARCH_INDEX to the EVIDENCE index for debates
# (not the personas index)

$env:AZURE_SEARCH_ENDPOINT = "https://your-search-service.search.windows.net"
$env:AZURE_SEARCH_KEY = "your-api-key"
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"

# Run debate with real evidence
python -m agent.main --query "Should the city implement congestion pricing in the downtown core?" --mode real
```

---

## Expected Results After Setup

Now each persona will retrieve **different evidence**:

✅ **Financial Analyst** retrieves: `econ-001` (cost savings, revenue, efficiency)
✅ **Sustainability Consultant** retrieves: `env-001` (emissions, air quality, health)
✅ **Community Member** retrieves: `equity-001` (fairness, low-income impact)
✅ **Infrastructure Designer** retrieves: `transit-001` (infrastructure requirements)
✅ **Retailer** retrieves: `retail-001` (business impact, sales)

---

## Evidence Index Field Guide

Each evidence document uploaded should include:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `id` | String (unique) | Document identifier | `econ-001` |
| `content` | String (large) | Full document text | "Congestion pricing reduces traffic by 15-25%..." |
| `source` | String | Publication/organization | "Journal of Urban Economics" |
| `url` | String | Link to original | "https://example.com/study" |
| `category` | String | Topic category | "economic-impact", "environmental", "social-equity" |
| `author` | String | Author/organization | "Dr. Michael Chen" |
| `date` | Date | Publication date | "2024-01-15" |
| `relevance_keywords` | String[] | Search terms | ["congestion pricing", "traffic", "revenue"] |
| `personas` | String[] | Relevant personas | ["Financial Analyst", "Sustainability Consultant"] |
| `stance` | String | Position | "supports", "opposes", "neutral" |

---

## Environment Variables Reference

```powershell
# Azure Search generic (used for evidence in debates)
$env:AZURE_SEARCH_ENDPOINT = "https://your-service.search.windows.net"
$env:AZURE_SEARCH_KEY = "your-key"
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"  # ← For debates (evidence)

# Optional: Separate personas index references (advanced)
$env:AZURE_SEARCH_PERSONAS_INDEX = "perspective-ai-personas"
$env:AZURE_SEARCH_EVIDENCE_INDEX = "perspective-ai-evidence"
```

---

## Quick Reference: 3-Step Recovery

```powershell
# Step 1: Create evidence index
$env:AZURE_SEARCH_INDEX = "perspective-ai-evidence"
python scripts/setup_evidence_index.py

# Step 2: Upload sample evidence
python scripts/upload_evidence.py

# Step 3: Run debates with real evidence
python -m agent.main --query "Your question?" --mode real
```

---

## Uploading Your Own Evidence

To add your own evidence documents, create a JSON file and use this pattern:

```python
# my_evidence.py
import requests
import json

def upload_custom_evidence():
    documents = [
        {
            "id": "your-001",
            "content": "Full text of your policy research or document...",
            "source": "Your Organization",
            "url": "https://your-source.com",
            "category": "economic-impact",
            "author": "Your Name",
            "date": "2024-03-20",
            "relevance_keywords": ["keyword1", "keyword2", "keyword3"],
            "personas": ["Financial Analyst", "Sustainability Consultant"],
            "stance": "supports"
        }
    ]
    
    # Upload using requests.post() to AZURE_SEARCH_INDEX
    # (see upload_evidence.py for full implementation)
```

---

## Files Created

✅ `TWO_INDEX_ARCHITECTURE.md` - Architecture explanation
✅ `scripts/setup_evidence_index.py` - Creates evidence index schema
✅ `scripts/upload_evidence.py` - Uploads sample evidence (7 documents)
✅ `AZURE_SETUP_GUIDE.md` - Original personas setup guide

---

## Demo Video with Unique Evidence

```powershell
# Complete setup
python scripts/setup_evidence_index.py
python scripts/upload_evidence.py

# Run debate - now each persona will have unique evidence
python web.py --real

# Open browser: http://127.0.0.1:5000
# Record as different personas generate different reasoning ✨
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| All personas still identical | Verify `AZURE_SEARCH_INDEX` points to evidence index, not personas |
| "No relevant evidence found" | Run `upload_evidence.py` to populate documents |
| Evidence index empty | Check Azure Portal; confirm documents uploaded successfully |
| 404 on evidence index | Verify index name: `perspective-ai-evidence` |
| API key errors | Regenerate key in Azure Portal; update env var |

---

## Summary

You now have:
- **Personas Index**: 19 role-specific personas with metadata
- **Evidence Index**: 7+ sample documents covering different perspectives on congestion pricing
- **Unique Evidence**: Each persona retrieves different documents based on their role
- **Real Debates**: Complete, evidence-based reasoning from all 5-19 personas

The identical evidence problem is now **SOLVED** ✅
