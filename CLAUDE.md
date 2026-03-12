# SolarAdmin AI — Project Instructions

## Owner
Martin Pham | Perth, Australia

## Mission
Build recurring revenue from Australian solar SMEs using AI voice automation.
First client target: $1,500–2,000+ AUD/month.
Replace $4-5K/month admin hires with AI voice receptionist + CRM automation.

## Product
AI voice receptionist for solar companies that:
1. Answers inbound calls (Retell AI + GPT-4o)
2. Qualifies leads with solar-specific criteria
3. Books assessments via Cal.com
4. Syncs everything to CRM (GoHighLevel first, extensible)
5. Processes inbound emails with AI classification
6. Sends Slack notifications to the sales team

## Tech Stack
Python 3.11, Flask, APScheduler, SQLite (→ Postgres), OpenAI GPT-4o,
Retell AI, GoHighLevel API, Slack Webhooks, Cal.com, Twilio

## Architecture
Single Flask app with blueprints:
- Voice AI webhooks (Retell custom LLM endpoint)
- GHL webhook receiver
- Dashboard API (JWT auth, RBAC)
- Human approval gate
- APScheduler for CRM sync + lead qualification

## CRM Abstraction
All CRM operations go through `integrations/crm_router.py`.
GHL is the primary implementation. HubSpot and Salesforce are stubbed
for future expansion. Never import ghl_client directly from business logic.

## Coding Rules
- All API keys from environment variables via .env file
- Every function has a docstring
- Every API call wrapped in try/except with logging
- Keep functions under 30 lines
- SQLite for storage (migrate to Postgres before multi-client)

## Current Phase
MVP extraction — stripped swarm layer, consolidating for production.

## Key Directories
```
solaradmin/
├── voice/          # Core product — Retell AI call handling
├── agents/         # Lead qualification, proposal generation
├── integrations/   # CRM router, GHL client, Slack
├── webhooks/       # GHL event processing
├── knowledge/      # Per-client knowledge base
├── email_processing/ # IMAP + AI email classification
├── api/            # Dashboard API, auth, onboarding
├── memory/         # Database layer
├── monitor/        # Health checks
├── notifications/  # Slack alerts
├── config.py       # Environment config
└── main.py         # Entry point
```

## API Keys Required (never put real keys here)
OPENAI_API_KEY=
GHL_API_KEY=
GHL_LOCATION_ID=
RETELL_API_KEY=
RETELL_AGENT_ID=
SLACK_WEBHOOK_URL=
JWT_SECRET=
GATE_API_KEY=
