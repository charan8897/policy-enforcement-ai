# Policy Enforcement Engine - Complete Build Plan

**Document Version:** 1.0  
**Last Updated:** Dec 21, 2025  
**Status:** Ready for Implementation

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Phase 1: Policy Digitization (Parser)](#phase-1-policy-digitization-parser)
4. [Phase 2: Enforcement Engine](#phase-2-enforcement-engine)
5. [Phase 3: Real-time Guidance (Frontend)](#phase-3-real-time-guidance-frontend)
6. [Complete Workflow](#complete-workflow)
7. [Database Schema](#database-schema)
8. [API Specifications](#api-specifications)
9. [Implementation Timeline](#implementation-timeline)
10. [Testing Strategy](#testing-strategy)
11. [Deployment](#deployment)

---

## System Overview

### Problem Statement
Organizations struggle with:
- Manual policy enforcement (time-consuming, error-prone)
- Long approval cycles (staff don't know rules beforehand)
- Ambiguous policy documents (different interpretations)
- Lack of real-time guidance (rejections increase friction)

### Solution
An AI-powered system that:
1. **Parses** unstructured policies into machine-readable rules
2. **Enforces** rules automatically in workflows
3. **Guides** users in real-time before submission

### Key Features
- ✅ Parse PDFs/DOCX → JSON rules
- ✅ Intent-based policy routing
- ✅ Real-time rule evaluation
- ✅ AI-generated suggestions
- ✅ Audit trail + compliance
- ✅ Appeal/escalation workflows

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   POLICY DOCUMENTS                      │
│              (PDFs, DOCX, Text Files)                   │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│            PHASE 1: PARSER (Backend)                    │
│  - Document extraction (Pandoc/OCR)                     │
│  - LLM-based rule extraction                            │
│  - Rule validation & normalization                      │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│              RULE DATABASE (PostgreSQL)                 │
│  - Policies, Rules, Conditions, Actions                 │
│  - Entity mappings (projects, departments, etc.)        │
└────────────────┬────────────────────────────────────────┘
                 │
      ┌──────────┼──────────┐
      │          │          │
      ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌──────────┐
  │Frontend│ │Backend │ │Audit Log │
  │(React) │ │(FastAPI)│ │(Postgres)│
  └────────┘ └────────┘ └──────────┘
      │          │
      └──────────┼──────────┐
                 │          │
                 ▼          ▼
     ┌──────────────────────────┐
     │ PHASE 2: ENFORCEMENT     │
     │ - Intent Analysis        │
     │ - Rule Evaluation        │
     │ - Decision + Suggestion  │
     └──────────────────────────┘
                 │
                 ▼
     ┌──────────────────────────┐
     │ PHASE 3: GUIDANCE        │
     │ - Real-time Chat Alert   │
     │ - AI Suggestions         │
     │ - User Decision          │
     └──────────────────────────┘
```

---

## Phase 1: Policy Digitization (Parser)

### Objective
Convert unstructured policy documents into structured, machine-readable rules.

### Components

#### 1.1 Document Extraction Layer

**Tools:**
- Pandoc (PDFs, DOCX, ODT, RTF)
- Tesseract (OCR for scanned PDFs)
- python-docx (DOCX metadata extraction)

**Workflow:**
```
Input: policy.pdf / policy.docx
  ↓
[Pandoc/Tesseract] → Extract text
  ↓
Output: policy.txt (raw text)
  ↓
[Chunking] → Split into paragraphs (max 500 chars)
  ↓
Output: policy_chunks.json
```



#### 1.2 LLM-Based Rule Extraction

**Tool:** OpenAI API (GPT-4) or local LLaMA

**Prompt Design:**

Use LLM to extract structured rules with prompt that specifies:
- Policy ID and name
- Rules with condition, action, severity, message
- Entity mappings (date ranges, thresholds, contexts)
- Output format as JSON for easy parsing

#### 1.3 Rule Validation & Normalization

**Validation Checks:**
- ✅ All required fields present (condition, action, message)
- ✅ Valid operators (>, <, ==, !=, AND, OR, NOT)
- ✅ Valid actions (APPROVE, REJECT, ESCALATE, WARN)
- ✅ No conflicting rules (same condition, different actions)
- ✅ Entity references exist in database



#### 1.4 Storage

**Database Tables:**
- Policies table: store policy metadata, versions, status
- Rules table: store extracted rules with conditions, actions, messages

### Phase 1 Deliverables
- ✅ Document extraction pipeline
- ✅ LLM-based rule parser
- ✅ Rule validation engine
- ✅ Conflict detection
- ✅ Database schema + storage
- ✅ Audit trail (policy versions)

---

## Phase 2: Enforcement Engine

### Objective
Evaluate user requests against extracted rules and return decisions + suggestions.

### Components

#### 2.1 Intent Classification

**Goal:** Map user request to applicable policies

**Approach:**
- Use LLM to extract intent from request
- Match intent to policy tags/keywords
- Return ranked list of applicable policies

**Implementation:**
- Extract context from request (leave days, dates, project, employee)
- Query database for policies matching context
- Rank policies by relevance score
- Return ranked list for evaluation

#### 2.2 Rule Evaluation Engine

**Logic:**
1. For each applicable policy, evaluate all rules
2. Stop at first matching rule (highest priority)
3. Return decision + message

**Implementation:**
- For each applicable policy, retrieve and evaluate rules
- Evaluate conditions against request context
- Support operators: >, <, ==, !=, >=, <=, AND, OR, NOT, IN
- Stop at first matching rule
- Aggregate decisions with priority: REJECT > ESCALATE > WARN > APPROVE

#### 2.3 Suggestion Generation

**Approach:**
- Rule-based suggestions (predefined alternatives)
- LLM-generated suggestions (context-aware)

**Implementation:**
- Rule-based: Generate suggestions based on what would make request compliant
  - Reduce days if exceeding threshold
  - Move dates to after milestones
  - Request manager escalation
- LLM-generated: Use GPT to create creative alternatives based on context
- Return top 3 suggestions ranked by relevance

#### 2.4 REST API Endpoint

**Endpoint:** `POST /api/evaluate-request`

**Request:**
```json
{
  "request_id": "REQ_12345",
  "request_type": "leave",
  "user_id": "EMP_001",
  "project_id": "PROJECT_X",
  "start_date": "2025-01-15",
  "end_date": "2025-01-25",
  "leave_type": "annual"
}
```

**Response:**
```json
{
  "decision": "WARN",
  "severity": "HIGH",
  "primary_reason": "Your requested dates overlap with a critical milestone for Project X. Leaves during this period are limited to 3 days maximum.",
  "applicable_policies": [
    {
      "policy_id": "POL_MILESTONE",
      "policy_name": "Project Milestone Leave Policy"
    }
  ],
  "suggestions": [
    "Reduce your leave request to 3 days",
    "Move your vacation to February 1st when the milestone ends",
    "Request escalation to your manager"
  ],
  "timestamp": "2025-01-10T10:30:00Z"
}
```

**Implementation:**
- Extract context from request (leave days, dates, project, employee)
- Classify intent and find applicable policies
- Evaluate rules against context
- Generate actionable suggestions
- Log to audit trail for compliance
- Return decision with reasons and suggestions

### Phase 2 Deliverables
- ✅ Intent classification engine
- ✅ Rule evaluation logic
- ✅ Suggestion generation
- ✅ REST API endpoints
- ✅ Audit logging
- ✅ Error handling + edge cases

---

## Phase 3: Real-time Guidance (Frontend)

### Objective
Provide users with real-time policy guidance before submission.

### Components

#### 3.1 Frontend Architecture (React)

**Structure:**
```
src/
├── components/
│   ├── LeaveForm.tsx
│   ├── PolicyAlert.tsx
│   ├── PolicyChatbot.tsx
│   └── SuggestionCard.tsx
├── hooks/
│   └── useEvaluateRequest.ts
├── services/
│   ├── api.ts
│   └── policyService.ts
├── context/
│   └── PolicyContext.tsx
└── utils/
    └── dateUtils.ts
```

#### 3.2 Real-time Evaluation Hook

**Purpose:**
- Manage API calls to /api/evaluate-request
- Handle loading, error, and result states
- Debounce requests as user types
- Cache evaluation results

#### 3.3 Policy Alert Chatbot Component

**Features:**
- Display alert with decision (REJECT=red, WARN=yellow, ESCALATE=orange, APPROVE=green)
- Show policy violation reason
- Display 3 actionable suggestions as clickable buttons
- Allow users to apply suggestions (auto-populate form fields)
- Enable escalation request to manager
- Dismissible alert

#### 3.4 Styling & UX

**Design:**
- Fixed position alert on bottom-right of screen
- Slide-up animation on appearance
- Color-coded by decision (red/yellow/orange/green)
- Responsive for mobile devices
- Accessible form labels and button focus states

#### 3.5 Leave Form Integration

**Features:**
- Capture start date, end date, leave type, project assignment
- Debounce API calls (500ms) as user types
- Display PolicyChatbot when evaluation completes
- Apply suggestions by auto-populating form fields
- Server-side re-validation on form submission
- Success/error notifications

### Phase 3 Deliverables
- ✅ React leave form component
- ✅ Real-time policy alert chatbot
- ✅ Suggestion-based form updates
- ✅ Responsive UI (mobile-friendly)
- ✅ Accessibility compliance (WCAG)

---

## Complete Workflow

### User Journey Flow

```
1. USER OPENS LEAVE PORTAL
   │
   ├─→ Selects dates: Jan 15-25, 2025
   │
   └─→ Frontend triggers /api/evaluate-request
                       ↓
2. BACKEND: INTENT ANALYSIS
   │
   ├─→ Extract context: 10 days, Project X, milestone active
   │
   ├─→ Classify intent: "Leave during milestone"
   │
   └─→ Find applicable policies: [Milestone Policy, Leave Policy]
                       ↓
3. BACKEND: RULE EVALUATION
   │
   ├─→ Evaluate condition: leave_days (10) > threshold (3) ✗
   │
   ├─→ During milestone: YES ✗
   │
   └─→ Decision: WARN (leaves > 3 not allowed during milestone)
                       ↓
4. BACKEND: SUGGESTION GENERATION
   │
   ├─→ Reduce to 3 days
   │
   ├─→ Move to Feb 1 (after milestone)
   │
   └─→ Request manager escalation
                       ↓
5. FRONTEND: DISPLAY CHATBOT ALERT
   │
   ├─→ ⚠️ Yellow alert appears
   │
   ├─→ Message: "Wait! Your requested dates overlap with..."
   │
   ├─→ Show 3 suggestions as buttons
   │
   └─→ User clicks "Move to February 1st"
                       ↓
6. FORM AUTO-UPDATE
   │
   ├─→ End date changed to Feb 1
   │
   └─→ Re-evaluate (debounced)
                       ↓
7. BACKEND: RE-EVALUATION
   │
   ├─→ New dates: Feb 1-11 (after milestone)
   │
   └─→ Decision: APPROVE ✓
                       ↓
8. FRONTEND: UPDATE ALERT
   │
   ├─→ ✅ Green checkmark
   │
   ├─→ Message: "Your request complies with all policies"
   │
   └─→ Submit button enabled
                       ↓
9. USER SUBMITS REQUEST
   │
   ├─→ Backend re-validates (defense-in-depth)
   │
   ├─→ Insert into leave_requests table
   │
   ├─→ Log to audit_trail
   │
   └─→ Send notification email
                       ↓
10. APPROVAL WORKFLOW (if needed)
    │
    ├─→ Auto-approve if APPROVE decision
    │
    └─→ Route to manager if ESCALATE decision
```

### Key Integration Points

| Component | Integration | Protocol |
|-----------|-------------|----------|
| Frontend → Backend | Real-time evaluation | REST API + WebSocket (optional) |
| Backend → Database | Rule queries | SQL (PostgreSQL) |
| Backend → LLM API | Rule parsing & suggestions | OpenAI API / Local model |
| Backend → Audit System | Logging all decisions | PostgreSQL + Kafka (optional) |

---

## Database Schema

### Core Tables

**Policies Table:** Store policy metadata, versions, status, source file reference

**Rules Table:** Store extracted rules with conditions, actions, messages, severity levels

**Entity Mappings Table:** Store entity references (projects, departments, thresholds)

**Project Milestones Table:** Store project milestone dates and phases

**Audit Trail Table:** Log all policy evaluations, user decisions, timestamps, IP addresses

**Leave Requests Table:** Store submitted leave requests with status and approvals

### Indexes

- Policy ID → Rules (foreign key)
- Rules enabled status
- Entity mappings → Policy (foreign key)
- Project ID → Milestones
- Audit trail by user ID and timestamp
- Leave requests by employee ID and status

---

## API Specifications

### 1. Evaluate Request

**Endpoint:** `POST /api/evaluate-request`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer {token}
```

**Request Body:**
```json
{
  "request_id": "REQ_12345",
  "request_type": "leave",
  "user_id": "EMP_001",
  "project_id": "PROJECT_X",
  "start_date": "2025-01-15",
  "end_date": "2025-01-25",
  "leave_type": "annual"
}
```

**Response (200 OK):**
```json
{
  "request_id": "REQ_12345",
  "decision": "WARN",
  "severity": "HIGH",
  "primary_reason": "Your requested dates overlap with a critical milestone for Project X...",
  "applicable_policies": [
    {
      "policy_id": "POL_001",
      "policy_name": "Project Milestone Leave Policy",
      "version": 1
    }
  ],
  "suggestions": [
    "Reduce your leave request to 3 days",
    "Move your vacation to February 1st when the milestone ends",
    "Request escalation to your manager"
  ],
  "timestamp": "2025-01-10T10:30:00Z"
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "Invalid date range",
  "details": "end_date must be after start_date"
}
```

### 2. Submit Leave Request

**Endpoint:** `POST /api/leave-requests`

**Request Body:**
```json
{
  "employee_id": "EMP_001",
  "start_date": "2025-02-01",
  "end_date": "2025-02-11",
  "leave_type": "annual",
  "policy_decision": "APPROVE",
  "comments": "Adjusted per policy recommendations"
}
```

**Response (201 Created):**
```json
{
  "request_id": "LEAVE_12345",
  "status": "APPROVED",
  "message": "Leave request submitted and auto-approved"
}
```

### 3. Get Policy

**Endpoint:** `GET /api/policies/{policy_id}`

**Response:**
```json
{
  "id": "POL_001",
  "name": "Project Milestone Leave Policy",
  "description": "Defines leave restrictions during critical project phases",
  "rules": [
    {
      "rule_id": "RULE_001",
      "condition": {
        "entity": "leave_days",
        "operator": "greater_than",
        "value": 3
      },
      "action": "REJECT",
      "message": "Leaves exceeding 3 days not permitted during milestone"
    }
  ],
  "version": 1,
  "status": "ACTIVE"
}
```

### 4. Parse Policy Document

**Endpoint:** `POST /api/policies/parse`

**Headers:**
```
Content-Type: multipart/form-data
Authorization: Bearer {token}
```

**Request Body:**
```
file: [PDF/DOCX file]
policy_type: "leave_policy" (optional)
```

**Response (202 Accepted):**
```json
{
  "job_id": "JOB_12345",
  "status": "PROCESSING",
  "message": "Policy parsing started. Check status with job_id",
  "polling_endpoint": "/api/policies/parse/JOB_12345/status"
}
```

**Polling Endpoint:** `GET /api/policies/parse/{job_id}/status`

**Response (when complete):**
```json
{
  "job_id": "JOB_12345",
  "status": "COMPLETED",
  "policy_id": "POL_002",
  "rules_count": 15,
  "validation_issues": [],
  "message": "Policy parsed successfully"
}
```

---

## Implementation Timeline

### POC (2-3 Days): Quick Validation

**Goal:** Prove the core concept works end-to-end with minimal code

**Day 1: Document Extraction + Setup**
- Extract leave-policy.docx with Pandoc → policy.txt
- Set up Python project structure (requirements.txt, src/ folder)
- Chunk policy text into 500-char paragraphs
- **Deliverable:** policy.txt + chunked paragraphs

**Day 2: LLM Rule Extraction + Evaluation Logic**
- Write LLM prompt: "Extract 5 critical leave rules from this policy as JSON"
- Call OpenAI API → rules.json (store operator, condition, action, message)
- Build simple Python rule evaluator: `evaluate_request(start_date, end_date, leave_type)`
- Implement basic condition matching (>, <, ==, AND, OR, IN operators)
- **Deliverable:** rules.json + evaluate.py

**Day 2-3: Testing + CLI Interface**
- Test with 3 scenarios:
  - ✅ Valid 5-day annual leave (compliant)
  - ❌ 25-day annual leave (exceeds 20-day quota)
  - ⚠️ Leave during project milestone (violates milestone policy)
- Build CLI interface with argparse
- **Deliverable:** CLI tool working

**POC Stack:**
- Python 3.11 (no FastAPI, no database, no frontend)
- Pandoc (document extraction)
- OpenAI API (rule extraction + suggestions)
- JSON (rule storage)

**POC Deliverable:**
```bash
python evaluate.py --start 2025-01-15 --end 2025-01-25 --type annual --project project_x
# Output: 
# Decision: WARN
# Reason: Overlaps project milestone. Max 3 days allowed.
# Suggestions:
#   1. Reduce to 3 days
#   2. Move to February 1st (after milestone)
#   3. Request manager escalation
```

**Success Criteria:**
- ✅ Policy document parsed to text
- ✅ 5+ rules extracted as JSON
- ✅ Evaluation logic returns decision + reasoning
- ✅ CLI tool runs without API server/database

---

### Week 1: Phase 1 (Parser)
- **Days 1-2:** Set up project structure, dependencies, database
- **Days 3-4:** Document extraction pipeline (Pandoc + OCR)
- **Days 5:** LLM integration for rule extraction
- **Deliverable:** Parse 1 sample policy PDF → JSON rules

### Week 2: Phase 2 (Enforcement Engine)
- **Days 1-2:** Intent classification logic
- **Days 3-4:** Rule evaluation engine
- **Days 5:** Suggestion generation + API endpoints
- **Deliverable:** /api/evaluate-request fully functional

### Week 3: Phase 3 (Frontend)
- **Days 1-2:** React components (Form, Chatbot)
- **Days 3-4:** Real-time evaluation integration
- **Days 5:** Styling + responsive design
- **Deliverable:** Leave form with policy alerts working end-to-end

### Week 4: Testing & Integration
- **Days 1-2:** Unit tests (backend)
- **Days 3:** Integration tests (frontend + backend)
- **Days 4:** End-to-end testing
- **Days 5:** Bug fixes + refinements
- **Deliverable:** All tests passing, documented edge cases

### Week 5: Deployment
- **Days 1-2:** Docker containerization
- **Days 3:** CI/CD pipeline setup (GitHub Actions)
- **Days 4:** Deploy to staging + production
- **Days 5:** Monitoring, logging, alerts
- **Deliverable:** System live and monitored

---

## Testing Strategy

### Unit Tests

**Backend:**
- Rule evaluation logic (condition matching, operator evaluation)
- Suggestion generation (both rule-based and LLM-based)
- Intent classification accuracy
- Policy parsing and validation

**Frontend:**
- Component rendering (alert visibility, suggestion buttons)
- User interactions (suggestion click, form updates)
- Hook state management (loading, error, evaluation result)

### Integration Tests

**API Testing:**
- Test full evaluation pipeline (request → intent → rules → decision → suggestions)
- Verify response format and status codes
- Test with multiple policy overlaps
- Validate audit logging

### E2E Tests

**User Workflows:**
- Violating policy → show alert → apply suggestion → re-evaluate → approve
- Compliant request → show green checkmark → submit
- Policy parsing → rule extraction → enforcement

---

## Deployment

### Containerization

**Backend:**
- Python 3.11 with FastAPI
- Environment: DATABASE_URL, OPENAI_API_KEY, LOG_LEVEL
- Exposed ports: 8000

**Frontend:**
- Node.js with React build
- Environment: REACT_APP_API_URL
- Exposed ports: 3000

**Database:**
- PostgreSQL 15
- Persistent data volume
- Exposed ports: 5432

### Infrastructure

**Docker Compose Setup:**
- Multi-service deployment (backend, frontend, postgres)
- Environment variable management
- Volume mounting for data persistence

**CI/CD Pipeline:**
- Run tests on push to main
- Build Docker images
- Push to container registry
- Deploy to staging/production

---

## Key Metrics & Monitoring

### Performance Metrics
- **API Response Time:** < 500ms for evaluate-request
- **Policy Parse Time:** < 5 seconds per document
- **Database Query Time:** < 100ms per rule evaluation
- **Frontend Alert Display:** < 200ms

### Success Metrics
- **Reduction in approval cycle time:** 50% faster
- **Policy compliance:** 95%+ requests compliant before submission
- **User satisfaction:** 4.5/5 rating on guidance
- **System uptime:** 99.9%

### Monitoring Stack
- **Logs:** ELK Stack (Elasticsearch, Logstash, Kibana)
- **Metrics:** Prometheus + Grafana
- **Tracing:** Jaeger
- **Alerts:** PagerDuty

---

## Summary

This complete system provides:
1. **Automated policy digitization** from unstructured documents
2. **Real-time rule evaluation** integrated into workflows
3. **Proactive user guidance** before submission
4. **Audit trail** for compliance
5. **Scalable architecture** for enterprise use

**Next Steps:**
1. Set up project repository
2. Configure development environment
3. Begin Phase 1 implementation
4. Iterate weekly with stakeholders
