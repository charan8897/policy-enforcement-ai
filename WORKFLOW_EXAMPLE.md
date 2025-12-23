# Complete Workflow Example: Leave Policy Processing

**Starting Point:** `/Downloads/leave-policy.docx`

---

## Step 1: Document Extraction (Pandoc)

**What Happens:**
Pandoc converts unstructured DOCX → plain text

**Input:**
```
leave-policy.docx (binary Microsoft Word file)
```

**Process:**
```bash
pandoc leave-policy.docx -t plain > leave-policy.txt
```

**Output (Raw Text):**
```
Leave Policy

Objective: The primary objective is to ensure employees are provided 
with reasonable rest and recreation. This policy explains types of 
leaves, eligibility, and procedures.

Scope: All employees in the organisation.

Policy/Process:

4.5.1. Annual / Privilege Leave
  All confirmed employees are eligible for [18] days of AL/PL per 
  completed year of service. Any un-availed AL/PL during the year 
  will be carried forward to maximum of [10] days. AL/PL can be 
  accumulated up to maximum of [35] days during a year.

4.5.2. Casual Leave
  All confirmed employees are eligible for [8] days of CL per annum.

4.5.3. Sick Leave
  All employees are eligible for [10] days of SL per annum. SL cannot 
  be availed for more than [3] days at a time. In case of SL availed 
  for more than [3] days, it must be accompanied by doctor's certificate.

4.5.4. Maternity Leave
  Female employees with 80+ days service in past 12 months are eligible 
  for 26 weeks paid maternity leave (8 weeks pre-natal).

4.5.5. Paternity Leave
  Male employees eligible for [15] days paternity leave from date of 
  birth of child.

Special Circumstances:
  Maternity Leave applicable only for female employees
  Paternity Leave applicable only for male employees
  Any deviation requires HR approval
```

**Result:** Readable text document ready for AI analysis

---

## Step 2: Text Chunking & Preprocessing

**What Happens:**
Split large text into manageable chunks (500-1000 chars each) for LLM processing

**Process:**
```
Chunk 1: "Leave Policy - Objective & Scope..."
Chunk 2: "4.5.1 Annual Privilege Leave - Eligibility..."
Chunk 3: "4.5.2 Casual Leave - Conditions..."
... (continue for each policy type)
```

**Why:** LLMs have token limits; chunking ensures accurate processing

---

## Step 3: LLM-Based Rule Extraction

**What Happens:**
AI reads chunks and extracts structured rules in JSON format

### Example: Processing Chunk about Annual Leave

**Input Chunk:**
```
4.5.1. Annual / Privilege Leave
All confirmed employees are eligible for 18 days of AL/PL per 
completed year of service. Any un-availed AL/PL during the year 
will be carried forward to maximum of 10 days. AL/PL can be 
accumulated up to maximum of 35 days during a year.
```

**LLM Prompt:**
```
Extract structured rules from this policy text. Return JSON with:
- policy_id, policy_name
- rules: [condition, action, severity, message]
- entities: [entity_name, type, values]

Policy text:
[chunk above]
```

**LLM Output (Generated JSON):**
```json
{
  "policy_id": "POL_ANNUAL_LEAVE",
  "policy_name": "Annual Leave Policy",
  "rules": [
    {
      "rule_id": "RULE_AL_001",
      "entity": "employee",
      "conditions": [
        {
          "field": "employment_status",
          "operator": "equals",
          "value": "confirmed"
        }
      ],
      "action": "ELIGIBLE",
      "allocation": 18,
      "period": "per_completed_year",
      "message": "Confirmed employees eligible for 18 days annual leave per year"
    },
    {
      "rule_id": "RULE_AL_002",
      "conditions": [
        {
          "field": "unused_leave_carry_forward",
          "operator": "greater_than",
          "value": 10
        }
      ],
      "action": "REJECT",
      "message": "Cannot carry forward more than 10 days to next year",
      "severity": "HIGH"
    },
    {
      "rule_id": "RULE_AL_003",
      "conditions": [
        {
          "field": "accumulated_leave",
          "operator": "greater_than",
          "value": 35
        }
      ],
      "action": "LAPSE_DAYS",
      "message": "Days exceeding 35 accumulated days will lapse",
      "severity": "MEDIUM"
    }
  ],
  "entities": {
    "annual_leave": {
      "type": "leave_type",
      "code": "AL",
      "alternate_names": ["Privilege Leave", "PL"]
    },
    "employment_status": {
      "type": "employee_attribute",
      "valid_values": ["confirmed", "probation", "trainee"]
    }
  }
}
```

### Example 2: Processing Sick Leave Chunk

**Input Chunk:**
```
4.5.3. Sick Leave
All employees are eligible for 10 days of SL per annum. SL cannot 
be availed for more than 3 days at a time. In case of SL availed 
for more than 3 days, it must be accompanied by doctor's certificate.
```

**LLM Output:**
```json
{
  "policy_id": "POL_SICK_LEAVE",
  "policy_name": "Sick Leave Policy",
  "rules": [
    {
      "rule_id": "RULE_SL_001",
      "conditions": [
        {
          "field": "leave_type",
          "operator": "equals",
          "value": "sick"
        }
      ],
      "allocation": 10,
      "period": "per_annum",
      "action": "ELIGIBLE",
      "message": "All employees eligible for 10 days sick leave per year"
    },
    {
      "rule_id": "RULE_SL_002",
      "conditions": [
        {
          "field": "consecutive_sick_days",
          "operator": "greater_than",
          "value": 3
        }
      ],
      "action": "REQUIRE_DOCUMENTATION",
      "required_doc": "doctor_certificate",
      "message": "Sick leave > 3 days requires doctor's certificate",
      "severity": "HIGH"
    }
  ]
}
```

---

## Step 4: Validation & Conflict Detection

**What Happens:**
System validates extracted rules for completeness and conflicts

**Validation Checks:**
```
✓ All rules have required fields (condition, action, message)
✓ All operators are valid (>, <, ==, !=, AND, OR, NOT)
✓ All actions exist in system (APPROVE, REJECT, ESCALATE, WARN)
✓ Entity references are defined
✓ No conflicting rules (same condition → different actions)
```

**Result:** All rules marked as `validated = true` or flagged with errors

---

## Step 5: Storage in Database

**What Happens:**
Validated rules saved to PostgreSQL

**Database Inserts:**

**Policies Table:**
```
id                | name                 | version | status
--------------------------------
POL_ANNUAL_LEAVE  | Annual Leave Policy  | 1       | ACTIVE
POL_SICK_LEAVE    | Sick Leave Policy    | 1       | ACTIVE
POL_MATERNITY     | Maternity Leave      | 1       | ACTIVE
POL_PATERNITY     | Paternity Leave      | 1       | ACTIVE
```

**Rules Table:**
```
id          | policy_id          | condition              | action  | severity
--------------------------------------------------------------------------------
RULE_AL_001 | POL_ANNUAL_LEAVE  | status=confirmed       | ELIGIBLE| MEDIUM
RULE_AL_002 | POL_ANNUAL_LEAVE  | carry_fwd > 10 days    | REJECT  | HIGH
RULE_SL_002 | POL_SICK_LEAVE    | consecutive_days > 3   | REQUIRE | HIGH
```

---

## Step 6: User Submits Leave Request

**What Happens:**
Employee opens leave portal and fills form

**User Input Example:**
```
Name: John Doe
Employee ID: EMP_001
Employment Status: Confirmed
Request Type: Annual Leave
Start Date: 2025-01-15
End Date: 2025-01-25
Days Requested: 10 days
Project: PROJECT_X
```

**Frontend Sends to Backend:**
```
POST /api/evaluate-request
{
  "request_id": "REQ_20250110_001",
  "request_type": "leave",
  "user_id": "EMP_001",
  "employment_status": "confirmed",
  "leave_type": "annual",
  "start_date": "2025-01-15",
  "end_date": "2025-01-25",
  "days_requested": 10,
  "project_id": "PROJECT_X"
}
```

---

## Step 7: Intent Classification (Backend)

**What Happens:**
System identifies which policies apply to this request

**Process:**
```
1. Extract context from request
   - leave_type = "annual" → matches POL_ANNUAL_LEAVE
   - employment_status = "confirmed" → eligible
   - days_requested = 10 → need to check allocation rules

2. Query applicable policies
   SELECT * FROM policies WHERE name LIKE '%annual%'
   
3. Rank by relevance
   - POL_ANNUAL_LEAVE (100% match)
   - POL_GENERAL_LEAVE (50% match - maybe)

4. Return ranked list
```

**Output:**
```json
{
  "applicable_policies": [
    {
      "policy_id": "POL_ANNUAL_LEAVE",
      "policy_name": "Annual Leave Policy",
      "relevance_score": 1.0
    }
  ]
}
```

---

## Step 8: Rule Evaluation (Backend)

**What Happens:**
System evaluates all rules from applicable policies

**Process:**

### Rule 1: Check Employment Status
```
Rule: RULE_AL_001
Condition: employment_status == "confirmed"
Context: employee.employment_status = "confirmed"
Match? YES ✓
Action: ELIGIBLE (approved to apply for annual leave)
```

### Rule 2: Check Leave Allocation
```
Rule: RULE_AL_002
Condition: employee.used_annual_leave + 10 <= 18 (annual limit)
Context: 
  - annual_leave_allocated = 18 days
  - already_used_this_year = 5 days
  - remaining_balance = 13 days
  - requested_days = 10
Match? YES ✓ (13 >= 10, so compliant)
Action: APPROVE
```

### Rule 3: Check Carryforward Limit
```
Rule: RULE_AL_002_CARRYFORWARD
Condition: previous_year_carryforward <= 10
Context: previous_year_leftover = 8 days
Match? NO (not applicable, no carryforward issue)
Action: N/A
```

**Aggregated Decision:**
```json
{
  "decision": "APPROVE",
  "primary_reason": "Request complies with all annual leave policies",
  "applicable_rules": [
    "RULE_AL_001 (employment status confirmed)",
    "RULE_AL_002 (sufficient balance: 13/10 days)"
  ],
  "violations": [],
  "suggestions": []
}
```

---

## Step 9: Suggestion Generation

**What Happens:**
Since request is approved, no suggestions needed. If it was denied, system generates alternatives.

### Example: If Request Had Violated Rules

**Scenario:** User requested 15 days but only had 10 days balance

**Violation:**
```
Rule: RULE_AL_002
Condition: remaining_balance (10) < requested_days (15)
Match? YES ✗ (VIOLATION)
Action: REJECT
Message: "You only have 10 days annual leave remaining. Cannot approve 15 days."
```

**Suggestion Generation:**
```json
{
  "decision": "WARN",
  "primary_reason": "You requested 15 days but only have 10 days balance",
  "suggestions": [
    "Reduce your request to 10 days (Jan 15-24 instead of Jan 15-25)",
    "Split into two requests: 10 days now + 5 days after balance resets on Apr 1",
    "Take 5 days as casual leave if available (you have 8 days CL remaining)",
    "Request manager escalation for exception approval"
  ],
  "alternatives": {
    "option_1": {
      "action": "Use available balance",
      "new_dates": "2025-01-15 to 2025-01-24",
      "days": 10
    },
    "option_2": {
      "action": "Mix leave types",
      "annual_days": 10,
      "casual_days": 5,
      "dates": "2025-01-15 to 2025-01-25"
    }
  }
}
```

---

## Step 10: Frontend Displays Alert & Suggestions

**What Happens:**
Real-time alert appears as user fills form

### Scenario 1: Request Compliant (APPROVE)

```
┌─────────────────────────────────┐
│ ✅ Policy Check Complete         │
├─────────────────────────────────┤
│ Your leave request complies      │
│ with all company policies.       │
│                                 │
│ ✓ 10 days annual leave approved │
│ ✓ Sufficient balance available  │
└─────────────────────────────────┘

[Submit Request] button → ENABLED
```

### Scenario 2: Request Violates Policy (WARN/REJECT)

```
┌─────────────────────────────────┐
│ ⚠️ Policy Violation              │
├─────────────────────────────────┤
│ You requested 15 days but only  │
│ have 10 days balance remaining. │
│                                 │
│ Here are your options:           │
│ 💡 Reduce to 10 days            │
│ 💡 Split into 2 requests        │
│ 💡 Mix with casual leave        │
│ 💡 Request manager approval     │
└─────────────────────────────────┘

User clicks "Reduce to 10 days"
→ Form auto-updates: end_date = 2025-01-24
→ Re-evaluation triggered (debounced 500ms)
→ Alert changes to ✅ APPROVED
```

---

## Step 11: User Submits Form

**What Happens:**
User submits leave request. Backend re-validates (defense-in-depth)

**Form Submission:**
```json
POST /api/leave-requests
{
  "employee_id": "EMP_001",
  "start_date": "2025-01-15",
  "end_date": "2025-01-24",
  "leave_type": "annual",
  "days": 10,
  "policy_decision": "APPROVE"
}
```

**Backend Validation:**
```
1. Re-run /api/evaluate-request (ensure no changes since frontend eval)
   → Decision must be APPROVE or ESCALATE, not REJECT
   
2. Verify user's leave balance again
   Query: SELECT * FROM employee_leave_balance 
          WHERE employee_id = 'EMP_001' AND leave_type = 'annual'
   
3. Check for conflicts with other approved leaves
   Query: SELECT * FROM leave_requests 
          WHERE employee_id = 'EMP_001' AND status = 'APPROVED'
          AND (start_date BETWEEN ... AND ...)

4. If all checks pass → INSERT into database
```

---

## Step 12: Storage & Audit Trail

**What Happens:**
Request saved. Full audit logged.

**Leave Requests Table Insert:**
```
id              | employee_id | start_date | end_date   | days | status  | created_at
────────────────────────────────────────────────────────────────────────────────────
LEAVE_20250110  | EMP_001     | 2025-01-15 | 2025-01-24 | 10   | APPROVED| 2025-01-10
```

**Audit Trail Insert:**
```
id              | request_id        | user_id | action        | decision | timestamp
────────────────────────────────────────────────────────────────────────────────────
AUDIT_001       | REQ_20250110_001  | EMP_001 | FORM_EVAL     | APPROVE  | 10:30:45
AUDIT_002       | REQ_20250110_001  | EMP_001 | FORM_SUBMIT   | APPROVE  | 10:32:10
AUDIT_003       | REQ_20250110_001  | EMP_001 | BACKEND_EVAL  | APPROVE  | 10:32:11
```

---

## Step 13: Response to User

**What Happens:**
System sends confirmation

**Response:**
```json
{
  "status": "success",
  "request_id": "LEAVE_20250110",
  "message": "Your leave request has been approved",
  "details": {
    "leave_type": "Annual Leave",
    "dates": "Jan 15 - Jan 24, 2025",
    "days": 10,
    "remaining_balance": 3,
    "status": "APPROVED"
  },
  "next_steps": [
    "Notification sent to your manager",
    "Leave added to your calendar",
    "No further action needed"
  ]
}
```

**User Sees:**
```
✅ Leave Request Approved

Annual Leave: Jan 15 - Jan 24, 2025 (10 days)
Status: Approved
Remaining Balance: 3 days

You're all set! Your manager has been notified.
```

---

## Summary: Complete Flow

```
1. leave-policy.docx
   ↓ (Pandoc extraction)
2. Raw policy text
   ↓ (Chunking)
3. Policy chunks
   ↓ (LLM extraction)
4. JSON rules
   ↓ (Validation)
5. Validated rules
   ↓ (Database storage)
6. Rules in PostgreSQL
   ↓ (User submits request)
7. Leave request received
   ↓ (Intent classification)
8. Applicable policies identified
   ↓ (Rule evaluation)
9. Decision generated + suggestions
   ↓ (Frontend display)
10. Alert shown to user
    ↓ (User applies suggestion or submits)
11. Form resubmitted
    ↓ (Backend re-validates)
12. Decision confirmed
    ↓ (Database insert + audit log)
13. Confirmation to user
    ↓ (Notification to manager)
14. Leave approved & scheduled
```

---

## Key Points

- **Extraction:** DOCX → Plain text (Pandoc)
- **Parsing:** Text → Structured JSON rules (LLM)
- **Storage:** Rules → Database (PostgreSQL)
- **Evaluation:** User request → Policy check (Rules engine)
- **Guidance:** Violations → Suggestions (LLM)
- **Frontend:** Real-time alerts (React chatbot)
- **Audit:** All decisions logged (Compliance trail)
