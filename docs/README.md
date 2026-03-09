# Solar Swarm — Master Documentation Index

Solar Swarm is a two-system platform built to generate recurring revenue from Australian solar SMEs using AI automation.

**Owner:** Martin Pham | Perth, Australia | AI Automation Consultant
**Target:** $1,500–2,000 AUD/month retainer per solar client
**Margin:** 80–90% (total costs ~$400 AUD/month)

---

## What the System Does

### System 1 — Autonomous Agent Swarm

A 3-tier hierarchy of AI agents that continuously generates, evaluates, and runs business experiments. The General (Tier 1) creates experiment ideas via GPT-4o, scores them using a 4-component confidence system, runs them through a red team critic, then routes them: auto-proceed, human gate, or auto-kill. Budget is allocated using a 25% Fractional Kelly Criterion. Agents communicate via a SQLite-backed message bus. Results feed back as pheromone signals that bias future experiment generation.

### System 2 — Solar Sales Automation

A production CRM automation layer targeting Australian solar companies with 5–15 salespeople. When a lead arrives via GoHighLevel webhook, the system qualifies them with GPT-4o (score 1–10), triggers outbound AI voice calls for hot leads via Retell AI, updates the GHL pipeline, sends Slack alerts, and produces weekly performance reports.

---

## ASCII Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        SOLAR SWARM                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                SYSTEM 1 — AGENT SWARM                   │    │
│  │                                                         │    │
│  │  TIER 1      ┌─────────────────┐                        │    │
│  │              │   master_agent  │  (The General)         │    │
│  │              │   every 6h      │                        │    │
│  │              └────────┬────────┘                        │    │
│  │                       │ generates + routes experiments  │    │
│  │  TIER 2      ┌────────┴────────────────────────┐        │    │
│  │              │  research_agent │ content_agent  │        │    │
│  │              │  analytics_agent                │        │    │
│  │              └────────┬────────────────────────┘        │    │
│  │                       │ spawns workers                  │    │
│  │  TIER 3      ┌────────┴────────────────────────┐        │    │
│  │              │ qualification │ proposal │ solar │        │    │
│  │              │ research │ report │ red_team      │        │    │
│  │              └─────────────────────────────────┘        │    │
│  │                                                         │    │
│  │  SUPPORT     scout_agent (daily 08:00 UTC)              │    │
│  │              mutation_engine (Monday 22:30 UTC)         │    │
│  │              ab_tester (daily 10:00 UTC)                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SYSTEM 2 — SOLAR SALES AUTOMATION          │    │
│  │                                                         │    │
│  │  GHL Webhook → qualify lead → score 1–10 → route        │    │
│  │  score ≥ 7 → Retell outbound call + Slack alert         │    │
│  │  post-call → GPT extract → GHL update → task            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 SHARED INFRASTRUCTURE                    │    │
│  │                                                         │    │
│  │  Memory:  Hot (SQLite) → Warm (JSON) → Cold (ledger)   │    │
│  │  Capital: Kelly engine → Portfolio → Circuit breaker    │    │
│  │  Bus:     message_bus (SQLite, priority queues)         │    │
│  │  Data:    web_scraper, api_poller, social_signal        │    │
│  │  KG:      kg_entities / kg_relationships                │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# 1. Clone and enter the project
cd Solar-Concept-main

# 2. Run the setup script (installs deps, creates .env, initialises DB)
bash setup.sh

# 3. Edit .env with your API keys (minimum: OPENAI_API_KEY)
nano .env

# 4. Start all services
python main.py

# 5. (Optional) Start the swarm board UI
cd swarm-board
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## Port Map

| Port | Service | File |
|------|---------|------|
| 5000 | Human Gate API (approve/reject experiments) | `api/human_gate.py` |
| 5001 | GHL Webhook Server (inbound lead events) | `webhooks/ghl_handler.py` |
| 5002 | Voice AI Webhook (Retell + ElevenLabs) | `voice/call_handler.py` |
| 5003 | Dashboard API (swarm-board live feed) | `api/dashboard_api.py` |
| 5173 | Swarm Board React App (Vite dev server) | `swarm-board/` |

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | GPT-4o key. System runs in mock mode without it. |
| `GHL_API_KEY` | Yes (for CRM) | — | GoHighLevel private API key |
| `GHL_LOCATION_ID` | Yes (for CRM) | — | GHL sub-account location ID |
| `GHL_PIPELINE_ID` | No | — | GHL pipeline ID for stage sync |
| `GHL_WEBHOOK_SECRET` | No | — | Validates inbound GHL webhook signatures |
| `SLACK_WEBHOOK_URL` | No | — | Incoming webhook URL for Slack alerts |
| `SLACK_BOT_TOKEN` | No | — | xoxb- token for Slack Web API |
| `SLACK_SIGNING_SECRET` | No | — | Verifies interactive Slack button payloads |
| `SLACK_DEFAULT_CHANNEL` | No | `#swarm-alerts` | Default Slack channel |
| `WEEKLY_BUDGET_AUD` | No | `500` | Total weekly experiment budget in AUD |
| `GATE_API_KEY` | No | — | Bearer token to protect human gate endpoints |
| `RETELL_API_KEY` | No | — | Retell AI API key for voice calls |
| `RETELL_DEFAULT_VOICE_ID` | No | `11labs-Adrian` | Default Retell/ElevenLabs voice |
| `ELEVENLABS_API_KEY` | No | — | ElevenLabs API key |
| `ELEVENLABS_DEFAULT_VOICE` | No | — | ElevenLabs voice ID |
| `PORT_HUMAN_GATE` | No | `5000` | Port for human gate Flask app |
| `PORT_GHL_WEBHOOKS` | No | `5001` | Port for GHL webhook Flask app |
| `PORT_VOICE_WEBHOOK` | No | `5002` | Port for voice AI Flask app |
| `PORT_DASHBOARD_API` | No | `5003` | Port for dashboard API Flask app |
| `VOICE_WEBHOOK_BASE_URL` | No | `http://localhost:5002` | Public URL Retell can reach |
| `TRANSFER_PHONE` | No | — | Phone number for human transfer calls |
| `DEFAULT_CLIENT_ID` | No | `default` | Fallback client ID |
| `DATABASE_PATH` | No | `swarm.db` | SQLite database file path |
| `LOG_LEVEL` | No | `INFO` | Python logging level |
| `HUBSPOT_API_KEY` | No | — | HubSpot private app token |
| `SALESFORCE_USERNAME` | No | — | Salesforce username |
| `SALESFORCE_PASSWORD` | No | — | Salesforce password |
| `SALESFORCE_SECURITY_TOKEN` | No | — | Salesforce security token |
| `SALESFORCE_CLIENT_ID` | No | — | Salesforce connected app client ID |
| `SALESFORCE_CLIENT_SECRET` | No | — | Salesforce connected app client secret |
| `IMAP_HOST` | No | — | IMAP server for email polling |
| `IMAP_USER` | No | — | IMAP username |
| `IMAP_PASS` | No | — | IMAP password |
| `IMAP_FOLDER` | No | `INBOX` | IMAP folder to poll |
| `FRONTEND_URL` | No | — | Production frontend URL for CORS allowlist |

---

## Documentation Index

| File | What it covers |
|------|---------------|
| [architecture.md](architecture.md) | 3-tier hierarchy, capital flow, memory system, message bus, scheduler jobs |
| [agents.md](agents.md) | Every agent: purpose, functions, triggers, DB reads/writes |
| [crm-integrations.md](crm-integrations.md) | GHL, HubSpot, Salesforce setup; crm_router API |
| [capital-allocation.md](capital-allocation.md) | Kelly criterion, circuit breakers, 72-hour explore protocol |
| [voice-ai.md](voice-ai.md) | Retell + ElevenLabs integration, call flow, post-call processing |
| [data-collection.md](data-collection.md) | Web scraper, API poller, social signal, pipeline processor |
| [memory-database.md](memory-database.md) | Full SQLite schema, hot/warm/cold memory, message bus lifecycle |
| [api-reference.md](api-reference.md) | Every Flask endpoint with method, params, response, curl examples |
| [swarm-board.md](swarm-board.md) | React app: how to run, Board/Overview tabs, board-state.json |
| [setup-guide.md](setup-guide.md) | Step-by-step setup from zero to running |
| [client-onboarding.md](client-onboarding.md) | Non-technical guide for solar business owners |
| [cost-tracking.md](cost-tracking.md) | API usage table, token tracking, cost projections |
| [troubleshooting.md](troubleshooting.md) | Common errors and fixes |
