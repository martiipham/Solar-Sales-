# Setup Guide — New Client Onboarding

Step-by-step guide to deploying Solar Sales AI Admin for a new solar SME client.

---

## Prerequisites

Before starting, confirm you have:

- **Python 3.11+** — `python3 --version`
- **Node.js 18+** and npm — `node --version`
- **Git** — `git --version`
- A publicly accessible server (or ngrok for testing)
- The following accounts and API keys ready:

| Service | Required? | Purpose |
|---------|-----------|---------|
| OpenAI | Required | GPT-4o for qualification, email triage, proposals |
| GoHighLevel | Required | CRM — contacts, pipeline, webhooks, messaging |
| Retell AI | Required for voice | AI voice agent on inbound/outbound calls |
| Slack | Recommended | HOT LEAD alerts, error notifications, approvals |

---

## Step 1 — Clone and install

```bash
git clone <your-repo-url> solar-sales
cd solar-sales

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Step 2 — Configure .env

```bash
cp .env.example .env
```

Open `.env` and fill in the values. Here's what each key does and where to find it:

```env
# ── Required ──────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
# → platform.openai.com → API Keys → Create new secret key

# ── GoHighLevel ───────────────────────────────────────────────────
GHL_API_KEY=
# → GHL → Settings → Integrations → API → Private Integration Key
# → Needs scopes: contacts.readonly, contacts.write, opportunities.write,
#   conversations.readonly, conversations.write

GHL_LOCATION_ID=
# → GHL → Settings → Business Profile
# → Copy the location ID from the URL (e.g. /location/abc123def456)

GHL_PIPELINE_ID=
# → GHL → CRM → Pipelines → click your pipeline → copy ID from URL

GHL_WEBHOOK_SECRET=
# → GHL → Settings → Integrations → Webhooks → copy Signing Secret
# → (set this after you create the webhooks in Step 5)

# ── Retell AI ─────────────────────────────────────────────────────
RETELL_API_KEY=
# → app.retellai.com → Settings → API Keys

# ── Slack ─────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL=
# → api.slack.com → Your Apps → Incoming Webhooks → Add New Webhook
# → Choose a channel (e.g. #solar-leads)

# ── Security ──────────────────────────────────────────────────────
GATE_API_KEY=your-strong-random-string
# → Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
# → Used to authenticate calls to the Human Gate API (:5010)

# ── Ports (defaults are fine unless you have conflicts) ────────────
PORT_HUMAN_GATE=5010
PORT_GHL_WEBHOOKS=5001
PORT_VOICE_WEBHOOK=5002
PORT_DASHBOARD_API=5003
```

The system works with only `OPENAI_API_KEY` and `GHL_API_KEY` set. Voice calls are
skipped without `RETELL_API_KEY`. Slack alerts are skipped without `SLACK_WEBHOOK_URL`.

---

## Step 3 — Initialise the database

```bash
python3 -c "from memory.database import init_db; init_db()"
```

Expected output:
```
[DB] Initialising database...
[DB] Database ready.
```

This creates `solar_admin.db` in the project root with all tables.

---

## Step 4 — Set up the Retell AI agent

In the Retell dashboard (app.retellai.com):

1. Go to **Agents → Create Agent**
2. Set **Agent name**: `[ClientName] Solar Receptionist`
3. Under **LLM**: select Custom LLM → set the endpoint to your server:
   `https://your-server.com/voice/response`
4. Under **General Settings**:
   - Begin message: *"Thanks for calling [Company Name], this is [Agent Name]. How can I help you today?"*
   - Language: English (Australian)
5. Under **Functions**: add the following function names:
   `qualify_lead`, `book_appointment`, `send_sms`, `update_crm`, `transfer_to_human`, `end_call`
6. **Save** the agent and copy the **Agent ID**

Link a phone number:
1. Go to **Phone Numbers → Import Number** (or purchase via Retell)
2. Assign the number to your new agent

Save the Agent ID to the client's company profile in the database:
```bash
python3 -c "
from memory.database import fetch_one, update
# Find the company record
company = fetch_one('SELECT id FROM company_profiles WHERE client_id = ?', ('your_client_id',))
update('company_profiles', company['id'], {'retell_agent_id': 'agent_xxx', 'phone': '+61412345678'})
print('Agent ID saved')
"
```

---

## Step 5 — Set up GHL webhooks

Your server must be publicly accessible for GHL to send events.

For local testing, use [ngrok](https://ngrok.com):
```bash
ngrok http 5001
# Copy the HTTPS URL, e.g. https://abc123.ngrok.io
```

In GoHighLevel:
1. Go to **Settings → Integrations → Webhooks → Add Webhook**

Add these three webhooks:

| Event | URL |
|-------|-----|
| Contact Created | `https://your-server.com/webhook/new-lead` |
| Opportunity Status Changed | `https://your-server.com/webhook/stage-change` |
| Inbound Message | `https://your-server.com/webhook/inbound-message` |

2. Copy the **Signing Secret** from the Webhooks page → add to `.env` as `GHL_WEBHOOK_SECRET`
3. Restart `main.py` after updating `.env`

---

## Step 6 — Run the system

```bash
python3 main.py
```

Expected startup output:
```
[DB] Initialising database...
[DB] Database ready.
[MAIN] Starting Human Gate API on port 5010
[MAIN] Starting GHL Webhook Server on port 5001
[MAIN] Starting Voice Webhook Server on port 5002
[MAIN] Starting Dashboard API on port 5003
[SCHEDULER] CRM sync scheduled (every 30 min)
[SCHEDULER] Lead check scheduled (every 60 min)
[SCHEDULER] All jobs running.
```

Verify all four ports are healthy:
```bash
curl http://localhost:5010/health
curl http://localhost:5001/health
curl http://localhost:5002/voice/health
curl http://localhost:5003/api/health
```

All should return `{"status": "ok"}`.

---

## Step 7 — Test with a call

1. Ensure `RETELL_API_KEY` is set and your Retell agent's webhook points to `:5002`
2. Call the linked phone number from any mobile
3. The AI should answer within 2 rings
4. Say: *"Hi, I own my home, my electricity bill is about $350 a month, I have a tile roof"*
5. After the call, check the database:

```bash
python3 -c "
from memory.database import fetch_all
leads = fetch_all('SELECT name, score, recommended_action FROM leads ORDER BY created_at DESC LIMIT 3')
for l in leads: print(l)
"
```

Expected: a lead record with `score` and `recommended_action` populated.

---

## Step 8 — Access the swarm board

```bash
cd swarm-board
npm install
npm run dev
```

Open `http://localhost:5173` — log in with the default admin credentials (set via `/api/auth/register` on first run).

The dashboard shows:
- **Overview** — calls today, hot leads, proposals sent, CRM sync status
- **Calls** — full call log with transcripts and scores
- **Leads** — all qualified leads with scores and recommended actions
- **Agents** — status of all 5 active agents
- **Settings** — runtime config for voice, notifications, CRM sync

---

## Step 9 — Production deployment

Use systemd (Linux) to keep the backend running:

```ini
# /etc/systemd/system/solar-sales.service
[Unit]
Description=Solar Sales AI Admin
After=network.target

[Service]
WorkingDirectory=/opt/solar-sales
ExecStart=/opt/solar-sales/.venv/bin/python3 main.py
Restart=always
User=ubuntu
EnvironmentFile=/opt/solar-sales/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable solar-sales
sudo systemctl start solar-sales
sudo systemctl status solar-sales
```

Build the dashboard for production:
```bash
cd swarm-board && npm run build
# Serve dist/ with nginx or any static host
# Set FRONTEND_URL in .env to your production dashboard URL
```

---

## Onboarding checklist

- [ ] `.env` filled in with all required keys
- [ ] `python3 main.py` starts cleanly, all 4 ports healthy
- [ ] GHL webhooks created and pointing to correct URLs
- [ ] Retell agent created, phone number linked, webhook pointing to `:5002`
- [ ] Test call completed — lead record created with score
- [ ] Slack channel receiving HOT LEAD alerts
- [ ] Swarm board accessible, company name showing on dashboard
- [ ] CRM sync running — pipeline stages visible in dashboard
