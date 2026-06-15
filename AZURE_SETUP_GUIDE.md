# Azure Search Setup Guide

## Overview
This guide explains how to set up Azure Search to store and retrieve personas for the Perspective AI system.

---

## Prerequisites

1. **Azure Search Instance**
   - Create an Azure Search service in Azure Portal
   - Note your endpoint URL and API key

2. **Environment Variables**
   Set these before running the scripts:
   ```powershell
   $env:AZURE_SEARCH_ENDPOINT = "https://your-search-service.search.windows.net"
   $env:AZURE_SEARCH_KEY = "your-api-key"
   $env:AZURE_SEARCH_INDEX = "perspective-ai-index"
   ```

---

## Step 1: Create Index Schema

The index schema defines the structure for storing personas.

**Script**: `scripts/setup_index.py`

**What it does**:
- Creates or updates an Azure Search index
- Defines fields for personas: id, name, role, focus, evidence_topics, default_stance, key_issue, category
- Sets up proper indexing, filtering, and retrieval options

**Run**:
```powershell
cd "c:\Project 2"
python scripts/setup_index.py
```

**Expected Output**:
```
============================================================
Azure Search Index Setup
============================================================
Endpoint: https://your-search-service.search.windows.net
Index: perspective-ai-index

✓ Index 'perspective-ai-index' created/updated successfully

Fields in index:
  - id (Edm.String)
  - name (Edm.String)
  - role (Edm.String)
  - focus (Edm.String)
  - evidence_topics (Collection(Edm.String))
  - default_stance (Edm.String)
  - key_issue (Edm.String)
  - category (Edm.String)

✓ Index setup completed successfully
```

---

## Step 2: Upload Personas

Upload the 19 personas from `data/personas.json` to Azure Search.

**Script**: `scripts/upload_personas.py`

**What it does**:
- Reads personas from `data/personas.json` (19 total: 5 core + 14 extended)
- Validates against index schema
- Uploads each persona as a searchable document

**Run**:
```powershell
cd "c:\Project 2"
python scripts/upload_personas.py
```

**Expected Output**:
```
============================================================
Persona Upload Tool
============================================================
Loaded 19 personas from data/personas.json
Target: https://your-search-service.search.windows.net/indexes/perspective-ai-index
Available fields: id, name, role, focus, evidence_topics, default_stance, key_issue, category

✓ Successfully uploaded 19 personas
Response: {
  "value": [
    {
      "key": "persona-001",
      "status": true,
      "statusCode": 201,
      "errorMessage": null
    },
    ...
  ]
}

✓ Upload completed successfully
```

---

## Step 3: Use Real Mode in Debate System

After uploading personas, you can use the debate system with real Azure Search data.

**CLI Mode**:
```powershell
cd "c:\Project 2"
python -m agent.main --query "Your policy question?" --mode real
```

**Web Server Mode**:
```powershell
cd "c:\Project 2"
python web.py --real
```

Then open `http://127.0.0.1:5000` in your browser.

---

## Personas Included

### Core Personas (5)
1. **Financial Analyst** - Economic impacts, business activity
2. **Sustainability Consultant** - Pollution, climate, ecology
3. **Infrastructure Designer** - Mobility, land use, design
4. **Community Member** - Equity, quality of life
5. **Retailer** - Customer traffic, operations, vitality

### Extended Personas (14)
6. Public Health Official - Community health outcomes
7. Transportation Engineer - Traffic flow, optimization
8. Climate Scientist - Carbon emissions, resilience
9. Equity Advocate - Fair access, social justice
10. Real Estate Developer - Property value, development
11. Data Scientist - Quantitative analysis, modeling
12. Community Organizer - Grassroots, collective action
13. Tech Entrepreneur - Innovation, disruption
14. Policy Advocate - Regulation, governance
15. Social Worker - Vulnerable populations, welfare
16. Law Enforcement Officer - Public safety, crime prevention
17. Media Representative - Communication, transparency
18. Cultural Advocate - Arts, culture, identity
19. Senior Citizen Advocate - Aging, accessibility

---

## Personas Data Structure

Each persona in the database includes:
- **id**: Unique identifier (persona-001 through persona-019)
- **name**: Display name
- **role**: Professional role/perspective
- **focus**: Area of concern or expertise
- **evidence_topics**: Relevant research topics (array)
- **default_stance**: Default position (support, opposed, cautious, etc.)
- **key_issue**: Primary concern for this persona
- **category**: "core" or "extended"

---

## Troubleshooting

### "Error: Missing environment variables"
**Solution**: Set all three environment variables before running scripts:
```powershell
$env:AZURE_SEARCH_ENDPOINT = "https://your-service.search.windows.net"
$env:AZURE_SEARCH_KEY = "your-key"
$env:AZURE_SEARCH_INDEX = "perspective-ai-index"
```

### "Index setup failed: 401 Unauthorized"
**Solution**: Check your API key - it may be invalid or have been regenerated

### "Upload failed: 400 Bad Request"
**Solution**: Ensure the index was created first by running `setup_index.py`

### Personas not loading in debate
**Ensure**:
1. Environment variables are set
2. Index was created with `setup_index.py`
3. Personas were uploaded with `upload_personas.py`
4. System is running in "real" mode (not "offline")

---

## API Integration

Once uploaded, personas are automatically fetched by:
- `agent.orchestrator` → `FoundryClient.retrieve_personas()`
- `agent.persona_retriever` → `get_personas_from_azure()`

The system will automatically fall back to the 5 core personas if Azure Search is not configured.

---

## Demo Video Setup

**For recording with extended personas**:
1. Run `python scripts/setup_index.py` (one-time)
2. Run `python scripts/upload_personas.py` (one-time)
3. Run debate with `python web.py --real`
4. Record browser showing the 19 personas available

---

## Quick Start (Copy-Paste)

```powershell
# Set environment variables
$env:AZURE_SEARCH_ENDPOINT = "https://your-service.search.windows.net"
$env:AZURE_SEARCH_KEY = "your-key"
$env:AZURE_SEARCH_INDEX = "perspective-ai-index"

# Setup index
python scripts/setup_index.py

# Upload personas
python scripts/upload_personas.py

# Run debate with real personas
python -m agent.main --query "Should the city implement congestion pricing?" --mode real
```
