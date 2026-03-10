# Architecture — Solar Sales AI Admin System

## System Overview

Single Python process (`main.py`) running four Flask API servers on separate threads,
with APScheduler managing recurring background jobs. All state is stored in a local
SQLite database. The React dashboard (`swarm-board/`) reads from the Dashboard API.

```
┌─────────────────────────────────────────────────────────────┐
│                     main.py (single process)                 │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ :5000        │  │ :5001        │  │ :5002              │ │
│  │ Human Gate   │  │ GHL Webhooks │  │ Voice AI Webhook   │ │
│  │ (approvals)  │  │ (leads,      │  │ (Retell call       │ │
│  │              │  │  emails,     │  │  events)           │ │
│  │              │  │  stage chg)  │  │                    │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
│                                                              │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │ :5003        │  │ APScheduler                          │ │
│  │ Dashboard    │  │  • crm_sync      every 30 min        │ │
│  │ API          │  │  • lead_check    every 60 min        │ │
│  └──────────────┘  └──────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  SQLite  (solar_admin.db)               │ │
│  │  leads · call_logs · email_logs · proposals            │ │
│  │  company_profiles · crm_cache · settings · users       │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         ▲                    ▲
         │                    │
  React Dashboard       External APIs
  swarm-board/          (GHL, Retell, OpenAI, Slack)
  :5173 (dev)
```

---

## Data Flows

### 1. Inbound Call → Lead Qualified

```
Caller dials client's number
        │
        ▼
Retell AI (cloud) ──── POST /voice/call-started ────▶ :5002
                                                        │
                                        voice/call_handler.py
                                        • loads company KB
                                        • GPT-4o drives conversation
                                        • functions: qualify, book, transfer
                                        │
                                        POST /voice/call-ended
                                        │
                                        voice/post_call.py
                                        • saves transcript to call_logs
                                        • calls qualification_agent.qualify()
                                        │
                                        qualification_agent.py
                                        • GPT-4o or rule-based score 1–10
                                        • score ≥ 7 → call_now
                                        • score ≥ 8 → Slack HOT LEAD alert
                                        • writes leads.score + recommended_action
                                        │
                                        GHL API update (pipeline stage)
```

### 2. Inbound Email → Human Approved Reply

```
Customer sends email
        │
        ▼
GoHighLevel receives → POST /webhook/inbound-message ──▶ :5001
                                                           │
                                           email_processing/email_agent.py
                                           • GPT-4o classifies: intent, urgency
                                           • drafts reply using company KB
                                           • low urgency → auto-queue (15min delay)
                                           • high urgency → POST to :5000/approve
                                           │
                                   :5000 Human Gate
                                   • operator reviews draft in swarm board
                                   • approves or edits → GHL send API
                                   • action logged to email_logs
```

### 3. New Lead (Web Form) → Proposal Generated

```
Lead submits form on GHL funnel
        │
        ▼
GHL webhook → POST /webhook/new-lead ──▶ :5001
                                          │
                              webhooks/ghl_handler.py
                              • creates lead record in SQLite
                              • calls qualification_agent.qualify()
                              │
                      score ≥ 7?
                      ├── YES → proposal_agent.generate_from_lead()
                      │         • calculates system size, savings, STC rebate
                      │         • renders HTML email proposal
                      │         • saves to proposals table
                      └── NO  → nurture or disqualify action logged
                              │
                      score ≥ 8?
                      └── YES → Slack HOT LEAD alert (masked PII)
```

### 4. CRM Sync (Scheduled)

```
APScheduler fires every 30 minutes
        │
        ▼
api/crm_sync.py
• GHL API → GET /contacts (recent 50)
• GHL API → GET /pipelines (stage counts)
• writes to crm_cache table
• logs run to agent_run_log
        │
        ▼
Dashboard API serves crm_cache to swarm board
```

---

## Scheduler Jobs

| Job ID | Interval | What it does |
|--------|----------|-------------|
| `crm_sync` | Every 30 min | Pull contacts + pipeline from GHL into SQLite cache |
| `lead_check` | Every 60 min | Re-score unqualified leads older than 1 hour |

---

## Database Schema (Active Tables)

See [memory-database.md](memory-database.md) for full column reference.

| Table | Purpose |
|-------|---------|
| `leads` | Inbound prospects — qualification score, recommended action, proposal link |
| `call_logs` | Every AI voice call — transcript, duration, lead score, outcome |
| `email_logs` | Every inbound email — intent, urgency, draft reply, approval status |
| `proposals` | Generated solar proposals — system size, savings, STC rebate, HTML content |
| `company_profiles` | One row per solar SME client — KB config, voice agent ID, GHL location |
| `company_products` | Products/services offered by the client (for KB) |
| `company_faqs` | FAQ pairs used by the voice agent and email drafter |
| `company_objections` | Objection handling scripts for the voice agent |
| `crm_cache` | Key-value store for GHL pipeline and contact data (30-min refresh) |
| `settings` | Runtime config overrides — editable from the dashboard |
| `api_keys` | Keys for client embed widgets and webhook authentication |
| `users` | Dashboard user accounts (owner, admin, client roles) |
| `auth_tokens` | JWT revocation list |
| `agent_run_log` | Scheduler job run history — job_id, ran_at, status, notes |
| `api_usage` | Per-call OpenAI and Retell API cost tracking |

---

## API Servers

| Port | Module | Key Endpoints |
|------|--------|---------------|
| 5000 | `api/human_gate.py` | `GET /pending`, `POST /approve/<id>`, `POST /reject/<id>` |
| 5001 | `webhooks/ghl_handler.py` | `POST /webhook/new-lead`, `/webhook/inbound-message`, `/webhook/stage-change` |
| 5002 | `voice/call_handler.py` | `POST /voice/call-started`, `POST /voice/response`, `POST /voice/call-ended` |
| 5003 | `api/dashboard_api.py` | `GET /api/dashboard/summary`, `/api/leads`, `/api/calls`, `/api/agents/status` |

---

## Key Modules

| File | Responsibility |
|------|---------------|
| `config.py` | Loads all env vars, exposes `is_configured()`, `retell_configured()` |
| `memory/database.py` | SQLite schema + CRUD helpers: `insert`, `update`, `fetch_one`, `fetch_all` |
| `memory/hot_memory.py` | Fast in-process cache for frequently read data |
| `knowledge/company_kb.py` | Loads company profile, products, FAQs, and objections for a given client |
| `agents/qualification_agent.py` | Lead scoring 1–10 via GPT-4o or rule-based fallback |
| `agents/proposal_agent.py` | Solar installation proposal generation (system size, STC, savings, HTML) |
| `voice/call_handler.py` | Retell webhook handler — conversation loop, function dispatch |
| `voice/call_functions.py` | Functions called during a voice call (qualify, book, CRM update) |
| `voice/post_call.py` | Post-call processing — transcript analysis, lead update, cost logging |
| `email_processing/email_agent.py` | Email classification, reply drafting, approval queue |
| `api/crm_sync.py` | GHL data pull and SQLite cache writer |
| `integrations/ghl_client.py` | GHL REST API wrapper |
| `notifications/slack_notifier.py` | Slack webhook alerts for hot leads, errors, approvals |
