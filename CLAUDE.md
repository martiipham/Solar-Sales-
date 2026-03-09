# Solar Swarm — Project Memory

## Owner
Martin Pham | Perth, Australia | AI Automation Consultant

## Mission
Build recurring revenue from Australian solar SMEs using AI automation.
First client target: $1,500–2,000 AUD/month retainer.
Use revenue to fund broader autonomous swarm experiments.

## System 1 — Autonomous Agent Swarm
3-tier hierarchy: General → Department Heads → Workers
Capital allocation: 25% Fractional Kelly Criterion
Portfolio: Exploit 60% / Explore 30% / Moonshot 10%
Circuit breakers: Yellow / Orange / Red
Memory: Hot (SQLite) → Warm (JSON) → Cold (append-only ledger)

## System 2 — Solar Sales Automation
Vertical: Australian solar SMEs, 5-15 salespeople
Platform: GoHighLevel CRM (client already on GHL)
Revenue model: $1,500-2,000 AUD/month retainer
Margin: 80-90% (total costs ~$400 AUD/month)

## Tech Stack
Python 3.11, Flask, APScheduler, SQLite, OpenAI GPT-4o,
Slack Webhooks, GHL API, dotenv

## Coding Rules
- All API keys from environment variables via .env file
- Every function has a docstring
- Every API call wrapped in try/except with logging
- Print status updates so operator can see what's happening
- Keep functions under 30 lines
- SQLite for all storage (no external databases needed to start)

## Current Phase
PHASE 2: Full swarm architecture built and operational

## Full Architecture

### Agent Hierarchy
- Tier 1: master_agent.py — The General (strategy, Kelly allocation, experiment routing)
- Tier 2: research_agent.py, content_agent.py, analytics_agent.py — Department heads
- Tier 3: Workers (qualification, proposal, solar_research, report, red_team)
- New: scout_agent.py — Proactive prospect hunter (daily 08:00 UTC)
- New: mutation_engine.py — Evolves failing experiments (Monday retrospective)
- New: ab_tester.py — A/B test lifecycle management (daily 10:00 UTC)

### Research Engine (research/)
- orchestrator.py — Coordinates research cycles, synthesises findings
- agents/market_research.py — AU solar market intelligence
- agents/competitive_intel.py — Competitor matrix + market gaps
- agents/prospect_researcher.py — Deep solar company profiling
- agents/technical_research.py — Tool/API/integration assessment
- agents/synthesis.py — Multi-source reconciliation, opportunity extraction

### Data Collection Engine (data_collection/)
- orchestrator.py — Source registry, collection scheduling
- agents/web_scraper.py — CEC installer registry, directories
- agents/api_poller.py — GoHighLevel contacts and pipeline
- agents/social_signal.py — LinkedIn buying signals (GPT-4o classified)
- agents/price_monitor.py — CPL benchmarks → time_series table
- pipeline/processor.py — Deduplication, enrichment, bus signal routing

### Storage Extensions (storage/)
- knowledge_graph.py — Entity/relationship store (kg_entities, kg_relationships)
- time_series.py — Metric recording and trend detection
- opportunity_store.py — Opportunity lifecycle (discovered→won|lost)

### Message Bus (bus/)
- message_bus.py — SQLite-backed async inter-agent messaging
  Priority: CRITICAL → HIGH → NORMAL → LOW
  Types: TASK | REPORT | ALERT | ACK | KILL | QUERY | RESPONSE

### New DB Tables (added to memory/database.py)
message_bus, research_findings, kg_entities, kg_relationships,
collection_sources, collected_data, time_series, opportunities, ab_tests

### Scheduler (main.py) — all UTC
- Every 6h:  The General
- Every 4h:  Data collection + pipeline processor (+30min offset)
- Every 6h:  Message bus expiry
- 06:00:     Research engine
- 08:00:     Scout agent
- 09:00:     Department heads
- 10:00:     A/B test evaluator
- Mon 22:00: Weekly retrospective
- Mon 22:30: Mutation engine
- 00:00:     Pheromone decay

## File Structure
solar-swarm/
├── CLAUDE.md
├── config.py
├── main.py
├── cli.py
├── requirements.txt
├── memory/
│   ├── database.py          (SQLite schema — 9 new tables added)
│   ├── hot_memory.py
│   ├── warm_memory.py
│   ├── cold_ledger.py
│   └── retrospective.py
├── agents/
│   ├── master_agent.py      (Tier 1: The General)
│   ├── research_agent.py    (Tier 2)
│   ├── content_agent.py     (Tier 2)
│   ├── analytics_agent.py   (Tier 2)
│   ├── worker.py            (Tier 3)
│   ├── scout_agent.py       (NEW — prospect hunter)
│   ├── mutation_engine.py   (NEW — strategy evolution)
│   ├── ab_tester.py         (NEW — A/B test lifecycle)
│   ├── red_team_agent.py
│   ├── qualification_agent.py
│   ├── solar_research_agent.py
│   ├── proposal_agent.py
│   └── report_agent.py
├── research/
│   ├── orchestrator.py
│   └── agents/
│       ├── market_research.py
│       ├── competitive_intel.py
│       ├── prospect_researcher.py
│       ├── technical_research.py
│       └── synthesis.py
├── data_collection/
│   ├── orchestrator.py
│   ├── agents/
│   │   ├── web_scraper.py
│   │   ├── api_poller.py
│   │   ├── social_signal.py
│   │   └── price_monitor.py
│   └── pipeline/
│       └── processor.py
├── storage/
│   ├── knowledge_graph.py
│   ├── time_series.py
│   └── opportunity_store.py
├── bus/
│   └── message_bus.py
├── capital/
│   ├── kelly_engine.py
│   ├── portfolio_manager.py
│   └── circuit_breaker.py
├── webhooks/
│   └── ghl_handler.py
├── integrations/
│   └── ghl_client.py
├── notifications/
│   └── slack_notifier.py
├── api/
│   └── human_gate.py
└── .claude/agents/

## API Keys Required (never put real keys in this file)
OPENAI_API_KEY=
GHL_API_KEY=
GHL_LOCATION_ID=
SLACK_WEBHOOK_URL=
WEEKLY_BUDGET_AUD=500
PORT_HUMAN_GATE=5000
PORT_GHL_WEBHOOKS=5001

## Key Algorithms
- Kelly Criterion: f* = (bp - q) / b, use 25% fractional
- Confidence scoring: avg of market_signal, competitive_gap, execution_speed, revenue_path
- Pheromone decay: 50% weight loss per day after 7 days
- 72-hour explore protocol: create → distribute → observe → decide → assess

## Circuit Breaker States
- Yellow: 3 consecutive failures (warning only)
- Orange: budget burn > 150% of plan
- Red: 5 consecutive failures OR single loss > 40% budget → full halt

## Confidence Routing
- Score > 8.5: auto-proceed
- Score 5.0–8.5: human gate required
- Score < 5.0: auto-kill
