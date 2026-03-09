# Swarm Board — React App

## Overview

The Swarm Board is a standalone React web application that gives an operator a visual command centre for the Solar Swarm. It runs on `http://localhost:5173` (Vite dev server) or `http://localhost:4173` (Vite preview/production build).

**Files:**

- `swarm-board/src/App.jsx` — Main component; all UI logic in one file
- `swarm-board/src/components/Confirm.jsx` — Confirmation modal
- `swarm-board/src/components/InfoTip.jsx` — Tooltip component
- `swarm-board/package.json` — React 18.3.1, Vite 5.4.2

**Design aesthetic:** Dark ops terminal x mission control. Background `#050810`, amber/cyan accent colours, Syne Mono for code elements, DM Sans for body text.

---

## Starting the Board

```bash
cd swarm-board
npm install
npm run dev
# Open http://localhost:5173
```

For a production build:

```bash
npm run build
npm run preview   # serves on :4173
```

The Dashboard API (`python main.py` on port 5003) must also be running for the Overview tab to show live data.

---

## Board Tab — Task Kanban

The Board tab is a full Kanban task tracker for managing agent work items. All data persists in browser `localStorage` (no server storage required).

### Columns

| Column | WIP Limit | Purpose |
|--------|-----------|---------|
| BACKLOG | None | Ideas not yet started |
| QUEUED | 8 | Ready to work |
| IN PROGRESS | 4 | Actively being worked |
| REVIEW | 4 | Awaiting review |
| DONE | None | Completed |
| BLOCKED | None | Waiting on something external |

### Seed Tasks

The board ships with 17 pre-loaded tasks (`SEED_TASKS`) that represent the actual project backlog. These load on first visit when `localStorage` is empty. Notable seed tasks include:

- Wire async lead queue to prevent GHL retries (critical, in-progress)
- Add X-API-Key auth to Human Gate API (critical, in-progress)
- Australian solar SME market size deep-dive (high, queued)
- Identify 20 GHL solar companies in Perth + Sydney (high, queued)
- Write 3-touch email follow-up sequence (high, queued)
- DocuSign/PandaDoc e-sign integration (high, blocked — pending provider decision)

### Agents

Each task is assigned to one of 13 agents displayed as coloured pills:

| Agent | Tier | Role |
|-------|------|------|
| The General | 1 | Strategic Command |
| Research Head | 2 | Market Intelligence |
| Content Head | 2 | Copy & Creative |
| Analytics Head | 2 | Performance Analysis |
| Scout | 3 | Prospect Hunter |
| Qualification | 3 | Lead Scorer |
| Voice AI | 3 | Outbound Caller |
| Proposal | 3 | Proposal Generator |
| A/B Evaluator | 3 | Test Evaluator |
| Mutation Engine | 3 | Strategy Evolver |
| Retrospective | 3 | Learning Synthesis |
| Pipeline Proc. | 3 | Data Processor |
| Unassigned | — | Not yet assigned |

### Priorities

| Priority | Colour |
|----------|--------|
| CRITICAL | Red |
| HIGH | Orange |
| NORMAL | Blue |
| LOW | Muted grey |

### Categories

Lead Pipeline, Experiment, Research, Content, Infrastructure, Client Delivery, Capital, Integration, Bug Fix, Feature.

### Creating a Task

Click the `+` button at the top of any column to open the Add Task panel. Required fields: title. Optional: agent, priority, category, tags (comma-separated), description.

### Editing a Task

Click any task card to open the detail panel. All fields are editable in-place. Changes save immediately to `localStorage`.

### Dragging Tasks

Tasks can be dragged between columns. The column WIP limit is enforced visually (column header turns red when at capacity) but does not block drops.

### Deleting a Task

Open the task detail panel and click Delete. A confirmation modal appears before the task is removed.

### Filtering

The toolbar above the board provides:

- **Agent filter** — show only tasks assigned to a specific agent
- **Priority filter** — show only tasks of a specific priority
- **Category filter** — show only tasks in a category
- **Search** — full-text search across title, description, and tags

Multiple filters can be active simultaneously.

---

## Overview Tab — Live Metrics

The Overview tab polls the Dashboard API every 30 seconds to display live system state. It requires `python main.py` to be running.

### Panels

**Swarm Status** — Reads from `GET /api/swarm/summary`:
- Active experiments count
- Pending approval count
- Budget used this week (AUD)
- Circuit breaker level (Green / Yellow / Orange / Red)

**CRM Status** — Reads from `GET /api/crm/status`:
- Active CRM (GHL / HubSpot / Salesforce / none)
- Which integrations are configured

**Pipeline** — Reads from `GET /api/crm/pipeline`:
- Stage names and contact counts
- Cache age

**Recent Leads** — Reads from `GET /api/swarm/leads`:
- Last 20 leads with name, score, recommended action, status

**Live Stats** — Reads from `GET /api/board/state`:
- Experiment counts by status (pending / approved / running / complete)
- Total lead count
- Running A/B tests

**Circuit Breaker** — Reads from `GET /api/swarm/circuit-breaker`:
- Current level with colour coding
- Halted flag

---

## board-state.json

File: `public/board-state.json`

A JSON file in the project's `public/` directory. The `GET /api/board/state` endpoint reads this file and merges it with live DB counts before returning the response to the React board.

The file can be edited manually to add static context (such as current sprint goals or notes) that appears in the Overview tab alongside the live data.

Structure (example):

```json
{
  "sprintGoal": "Land first paying client",
  "weeklyBudgetAUD": 500,
  "notes": "Focus on Perth outreach this week"
}
```

The API appends a `liveStats` key to this object before returning it.

---

## localStorage Keys

The board stores all task data under these localStorage keys:

| Key | Contents |
|-----|----------|
| `swarm_tasks` | JSON array of all task objects |
| `swarm_filters` | Active filter state |

To reset the board to seed tasks, clear `swarm_tasks` from DevTools → Application → Local Storage and reload.

---

## Connecting to an AI Assistant (Optional)

The board has a built-in AI assistant panel that can answer questions about the swarm using the Anthropic API directly from the browser. To enable it:

1. Open the board at `http://localhost:5173`
2. Click the AI assistant icon in the toolbar
3. Enter your Anthropic API key when prompted (stored in localStorage, never sent to the backend)

The key is stored under `anthropic_key` in localStorage. The assistant has read access to the current board state and can help prioritise tasks or answer questions about the architecture.

**Note:** This uses the Anthropic API directly from the browser. Browser-side API key usage is appropriate for personal/local tools only — do not expose this interface publicly.

---

## Tech Stack

| Package | Version | Purpose |
|---------|---------|---------|
| react | 18.3.1 | UI framework |
| @vitejs/plugin-react | 4.3.1 | Vite React plugin |
| vite | 5.4.2 | Build tool and dev server |

No additional UI libraries — all components are built inline in `App.jsx` using inline styles with the colour constants defined in the `C` object at the top of the file.
