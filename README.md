# Policy Enforcement Engine

Automated policy extraction, rule generation, and request evaluation system using LLM.

---

## Quick Start - Phase 1 Workflow

### Step 1: Extract Policy
Extract text from PDF/DOCX/TXT policy documents.

```bash
python3 extract_policy.py extract dopt_policy.pdf
```

**Output:** `policy.txt` (extracted policy text)

---

### Step 2: Extract Rules (ONE TIME ONLY)

First run - generate rules from policy:
```bash
python3 extract_policy.py extract dopt_policy.pdf --rules --no-cache
```

**Output:** `rules.json` (20 structured policy rules)

**Important:** After first run, always use cache:
```bash
python3 extract_policy.py extract dopt_policy.pdf --rules
```

This prevents variation in rule generation. Same rules every time.

---

### Step 3: Create Request

Create request JSON with required fields:

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

Save as: `request_sample.json` (or via API)

---

### Step 4: Evaluate Request

Evaluate request against rules:

```bash
python3 extract_policy.py evaluate request_sample.json
```

**Output:** `request_sample_result.json`

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
# Step 1: Extract
python3 extract_policy.py extract dopt_policy.pdf

# Step 2: Generate rules (one time)
python3 extract_policy.py extract dopt_policy.pdf --rules --no-cache

# Step 3: Create request (or API)
cat > request_test.json << EOF
{
  "request_id": "REQ_001",
  "employee_type": "regular",
  "travel_type": "within_india"
}
EOF

# Step 4: Evaluate
python3 extract_policy.py evaluate request_test.json

# View result
cat request_test_result.json
```

---

## Key Features

✓ Multi-format policy support (PDF, DOCX, TXT)
✓ Automatic rule extraction via LLM (Gemini)
✓ Caching to prevent rule variation
✓ Whitelist-based evaluation (safe by default)
✓ Detailed decision tracking with reasons
✓ Web scraping with LLM verification
