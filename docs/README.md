# Solar Sales — AI Admin System

**Owner:** Martin Pham | Perth, Australia | AI Automation Consultant
**Target clients:** Australian solar SMEs, 5–15 salespeople
**Revenue model:** $1,500–2,000 AUD/month retainer per client

---

## What it does

Handles inbound calls, triages emails, qualifies leads, and syncs everything
to GoHighLevel CRM. Built for Australian solar companies.

The system runs 24/7 without supervision. When a lead calls or emails, the AI
answers, qualifies, and routes them — the sales team only touches the hot ones.

---

## Core Features

- **Voice AI receptionist** (Retell AI) — answers calls 24/7, qualifies leads conversationally, books site assessments, transfers to human when needed
- **Email triage** — classifies intent and urgency, drafts replies in the company's voice, routes for human approval before sending
- **Lead qualification** — automatic 1–10 scoring based on homeowner status, monthly bill, roof type, and state location. Score ≥ 8 fires a Slack HOT LEAD alert
- **Proposal generation** — tailored solar installation proposals with system size, annual savings, STC rebate, payback period, and pricing range — sent as HTML email
- **GHL CRM sync** — every 30 minutes, keeps local SQLite cache in sync with GoHighLevel contacts and pipeline stages

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <your-repo-url> solar-sales
cd solar-sales

# 2. Configure environment
cp .env.example .env
# Edit .env — fill in OPENAI_API_KEY, GHL_API_KEY, GHL_LOCATION_ID, RETELL_API_KEY

# 3. Install Python dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Start the backend
python3 main.py

# 5. Start the dashboard
cd swarm-board && npm install && npm run dev
```

---

## Ports

| Port | Service |
|------|---------|
| 5000 | Human Gate API — operator approvals for email drafts and flagged actions |
| 5001 | GHL Webhooks — receives new lead, stage change, and inbound message events |
| 5002 | Voice AI Webhook — Retell call events (started, response, ended) |
| 5003 | Dashboard API — React swarm board reads from here |

---

## Required API Keys

See `.env.example` for the full list. Critical keys:

| Key | Where to get it |
|-----|-----------------|
| `OPENAI_API_KEY` | platform.openai.com → API Keys |
| `GHL_API_KEY` | GHL → Settings → Integrations → Private Integration |
| `GHL_LOCATION_ID` | GHL → Settings → Business Profile → URL |
| `RETELL_API_KEY` | app.retellai.com → API Keys |
| `SLACK_WEBHOOK_URL` | api.slack.com → Incoming Webhooks |

The system degrades gracefully without optional keys:
- No `RETELL_API_KEY` → voice agent won't answer calls, but all other features work
- No `SLACK_WEBHOOK_URL` → no Slack alerts, everything else works
- No `GHL_API_KEY` → CRM sync skipped, leads stored locally only

---

## Architecture

Single Python process running four Flask servers on separate threads.
APScheduler handles recurring jobs (CRM sync every 30 min, lead qualification hourly).
SQLite for all storage — no external database required.
React dashboard at `swarm-board/` reads from the Dashboard API on port 5003.

```
Inbound call  → Retell AI  → :5002 → voice/call_handler.py
                                    → post_call.py (score + log)
                                    → qualification_agent.py
                                    → GHL CRM update

Inbound email → GHL webhook → :5001 → email_processing/email_agent.py
                                     → human approval queue (:5000)
                                     → GHL send reply

New lead form → GHL webhook → :5001 → ghl_handler.py
                                     → qualification_agent.py
                                     → proposal_agent.py (if score ≥ 7)
                                     → Slack alert (if score ≥ 8)

CRM Sync      → APScheduler (30 min) → api/crm_sync.py → SQLite cache
```

---

## Documentation Index

| File | Contents |
|------|---------|
| [architecture.md](architecture.md) | System overview, data flows, DB schema, scheduler jobs |
| [setup-guide.md](setup-guide.md) | Step-by-step client onboarding and deployment |
| [memory-database.md](memory-database.md) | SQLite table reference for all active tables |
| [voice-ai.md](voice-ai.md) | Retell AI setup, call functions, KB configuration |
| [api-reference.md](api-reference.md) | All REST endpoints across the 4 servers |
| [agents.md](agents.md) | Qualification and proposal agent logic |
| [crm-integrations.md](crm-integrations.md) | GHL webhook events and CRM sync details |
| [troubleshooting.md](troubleshooting.md) | Common issues and fixes |
| [sales-playbook.md](sales-playbook.md) | How to pitch and onboard a new solar client |
