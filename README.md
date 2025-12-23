# Policy Enforcement Engine

Automated policy extraction, rule generation, and request evaluation system using LLM.

---

## Workflow

### Phase 1: Setup (One Time)

#### Step 1: Extract Policy
Extract text from PDF/DOCX/TXT policy documents.

```bash
python3 extract_policy.py extract dopt_policy.pdf
```

**Output:** `policy.txt` (extracted policy text)

#### Step 2: Generate Rules (ONE TIME ONLY)

First run - generate rules from policy:
```bash
python3 extract_policy.py extract dopt_policy.pdf --rules --no-cache
```

**Output:** `rules.json` (structured policy rules)

**Important:** After first run, always use cache to prevent variation:
```bash
python3 extract_policy.py extract dopt_policy.pdf --rules
```

---

### Phase 2: Runtime (API)

#### Step 3: Receive Request from API

User sends request via API endpoint with required fields:

```json
{
  "request_id": "DOPT_REQ_2024_001",
  "employee_type": "regular",
  "travel_type": "within_india",
  "destination": "New Delhi, India",
  "home_town": "Mumbai",
  "hometown_distance": 800,
  "duration_days": 10,
  "advance_booking": true
}
```

**Note:** Request JSON is generated from API payload, not manually created.

#### Step 4: Evaluate Request

Evaluate request against cached rules:

```bash
python3 extract_policy.py evaluate request_payload.json
```

**Output:** Decision result with approval/rejection reason

```json
{
  "decision": "APPROVE",
  "primary_reason": "Request complies with all policies",
  "applicable_rules": ["RULE_CEN_001", "RULE_CEN_003"],
  "violations": [],
  "approvals": [...]
}
```

---

## Decision Logic

- **APPROVE**: Request matches one or more ELIGIBLE rules
- **REJECT**: Request matches a REJECT rule OR has no matching rule (whitelist mode)
- **REQUIRE_DOCUMENTATION**: Request needs additional supporting documents

---

## Files

| File | Purpose |
|------|---------|
| `extract_policy.py` | Main extraction & evaluation engine |
| `universal_scraper_with_llm.py` | Web scraper for policies |
| `policy.txt` | Extracted policy text |
| `rules.json` | Generated policy rules (cached) |
| `request_sample.json` | Request to evaluate |
| `request_sample_result.json` | Evaluation result |

---

## Command Reference

```bash
# Extract policy only
python3 extract_policy.py extract <file.pdf|.docx|.txt>

# Extract policy + rules (first time)
python3 extract_policy.py extract <file.pdf|.docx> --rules --no-cache

# Extract policy + rules (subsequent runs - uses cache)
python3 extract_policy.py extract <file.pdf|.docx> --rules

# Evaluate request
python3 extract_policy.py evaluate <request.json>
```

---

## Requirements

```
PyPDF2==3.0.1
google-generativeai
pandoc (for DOCX support)
pdftotext (for PDF extraction)
tesseract-ocr (for scanned PDFs)
```

Install:
```bash
pip install -r requirements.txt
apt-get install pandoc poppler-utils tesseract-ocr
```

---

## API Key Setup

Set Gemini API key in `extract_policy.py` line 601:
```python
api_key = "YOUR_GEMINI_API_KEY"
```

---

## Example Workflow

```bash
# PHASE 1: SETUP (One Time)

# Step 1: Extract policy
python3 extract_policy.py extract dopt_policy.pdf

# Step 2: Generate rules (one time only)
python3 extract_policy.py extract dopt_policy.pdf --rules --no-cache

# After this, never use --no-cache again. Always use cached rules.

---

# PHASE 2: RUNTIME (API)

# Step 3: API receives request payload and generates JSON
# (In actual system, this comes from API endpoint)
cat > request_payload.json << EOF
{
  "request_id": "REQ_001",
  "employee_type": "regular",
  "travel_type": "within_india"
}
EOF

# Step 4: Evaluate request
python3 extract_policy.py evaluate request_payload.json

# View decision result
cat request_payload_result.json
```

---

## Key Features

✓ Multi-format policy support (PDF, DOCX, TXT)
✓ Automatic rule extraction via LLM (Gemini)
✓ Caching to prevent rule variation
✓ Whitelist-based evaluation (safe by default)
✓ Detailed decision tracking with reasons
✓ Web scraping with LLM verification
