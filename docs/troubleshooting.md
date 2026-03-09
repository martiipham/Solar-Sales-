# Troubleshooting Guide

Common errors, symptoms, and fixes.

---

## Startup Errors

### `ModuleNotFoundError: No module named 'openai'`

**Cause:** Dependencies not installed, or running Python outside the virtual environment.

**Fix:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

### `sqlite3.OperationalError: no such table: experiments`

**Cause:** Database not initialised.

**Fix:**
```bash
python3 -c "from memory.database import init_db; init_db()"
```

If the error persists after init, check that `DATABASE_PATH` in `.env` points to a writable location.

---

### `Address already in use` (port 5000, 5001, 5002, or 5003)

**Cause:** A previous instance of `main.py` is still running, or another process is using the port.

**Fix:**
```bash
# Find the process
lsof -i :5000

# Kill it
kill -9 <PID>
```

Or change the port in `.env`:
```env
PORT_HUMAN_GATE=5010
```

---

### `ImportError: cannot import name 'flask_limiter'`

**Cause:** `flask-limiter` not installed.

**Fix:**
```bash
pip install flask-limiter
```

---

## OpenAI / AI Errors

### `openai.AuthenticationError: Incorrect API key`

**Cause:** `OPENAI_API_KEY` is missing, wrong, or has leading/trailing whitespace.

**Fix:**
1. Check `.env`: `OPENAI_API_KEY=sk-...` (no quotes, no trailing spaces)
2. Verify the key at [platform.openai.com](https://platform.openai.com)
3. Confirm the virtual environment loaded the `.env`: `python3 -c "import config; print(config.OPENAI_API_KEY[:8])"`

---

### `openai.RateLimitError`

**Cause:** Too many requests per minute, or API tier limit reached.

**Fix:**
- Check your OpenAI usage tier at [platform.openai.com/usage](https://platform.openai.com/usage)
- The system's try/except wrappers log and continue — individual agent runs may produce partial results
- Upgrade to a higher OpenAI tier if this is recurring

---

### `openai.BadRequestError: maximum context length exceeded`

**Cause:** A system prompt or transcript is too long for the model's context window.

**Fix:**
- For voice calls: reduce the number of `company_knowledge` items in `voice/prompt_templates.py`
- For the General: the `_generate_ideas()` function will fall back to `_mock_ideas()` and log an error

---

### The General generates mock ideas instead of real ones

**Cause:** OpenAI API key is not configured, or the API call failed.

**Symptom:** Output contains "Solar Prospecting Automation" and "Solar ROI Content Engine" — these are the mock idea names.

**Fix:**
1. Verify `OPENAI_API_KEY` is set
2. Check the logs for the preceding error: `[GENERAL] GPT-4o ideas failed:...`
3. Confirm the key has sufficient credits

---

## GoHighLevel / CRM Errors

### `[GHL] Not configured — missing GHL_API_KEY or GHL_LOCATION_ID`

**Cause:** GHL credentials not set.

**Fix:**
Add to `.env`:
```env
GHL_API_KEY=your-key
GHL_LOCATION_ID=your-location-id
```

The system runs in mock mode without these — all CRM calls are silently skipped.

---

### `[GHL WEBHOOK] new-lead: invalid signature` — leads not being processed

**Cause:** `GHL_WEBHOOK_SECRET` in `.env` doesn't match the signing secret in GHL, or the secret isn't set.

**Fix:**
1. Go to GHL → Settings → Integrations → Webhooks
2. Find your webhook and copy the Signing Secret
3. Add to `.env`: `GHL_WEBHOOK_SECRET=your-signing-secret`
4. Restart `main.py`

If you don't have a signing secret configured in GHL, remove `GHL_WEBHOOK_SECRET` from `.env` — the system will skip validation and allow all requests (acceptable for trusted networks only).

---

### `crm_router: active CRM is 'none'`

**Cause:** No CRM credentials are configured.

**Fix:** Set at least one of: `GHL_API_KEY` + `GHL_LOCATION_ID`, `HUBSPOT_API_KEY`, or Salesforce credentials. The router selects the first configured CRM in priority order: GHL → HubSpot → Salesforce.

---

### Leads arrive in the database but don't appear in GHL

**Cause:** The system stores leads locally first, then syncs to GHL. Sync fails silently if GHL is not configured or the API call fails.

**Fix:**
1. Check that `GHL_API_KEY` and `GHL_LOCATION_ID` are set
2. Check the logs for `[GHL CLIENT]` error lines
3. Test the GHL connection: `curl http://localhost:5003/api/crm/status`

---

## Voice AI Errors

### Outbound calls not triggering for high-score leads

**Cause:** `RETELL_API_KEY` not configured, or the lead is missing a phone number.

**Fix:**
1. Check `RETELL_API_KEY` in `.env`
2. Verify the lead has a `phone` field: `sqlite3 swarm.db "SELECT phone FROM leads ORDER BY id DESC LIMIT 5;"`
3. Check qualification agent logs for: `[QUALIFICATION] Skipping outbound call — no phone`

---

### `/voice/response` returns 500 errors during calls

**Cause:** GPT-4o call failed mid-conversation. This causes Retell to hear silence or fall back to its own LLM.

**Fix:**
1. Check logs for `[VOICE] GPT-4o call failed:`
2. Confirm OpenAI rate limits aren't being hit (voice calls make 8–20 GPT-4o calls each)
3. Check that the `_call_contexts` dict has a valid entry for the `call_id` — if the server restarted mid-call, context is lost

---

### Voice agent says "I'm sorry, I'm having trouble right now"

**Cause:** The system prompt or transcript exceeded GPT-4o's context limit, or the API call timed out.

**Fix:**
- Reduce the `company_knowledge` payload in `voice/prompt_templates.py`
- Check the OpenAI timeout setting in `voice/call_handler.py`

---

### ElevenLabs voice not working, falling back to default

**Cause:** `ELEVENLABS_API_KEY` not set, or the `elevenlabs_voice_id` on the company profile is invalid.

**Fix:**
1. Set `ELEVENLABS_API_KEY` in `.env`
2. Verify the voice ID in the ElevenLabs dashboard
3. Check logs for `[VOICE] ElevenLabs error:`

---

## Circuit Breaker

### System halted — Red circuit breaker

**Symptom:** The General stops running. New experiments are not generated. Logs show `[CIRCUIT BREAKER] System halted — Red level`.

**Cause:** Either 5+ consecutive experiment failures, or a single experiment lost more than 40% of the weekly budget.

**Fix:** Requires explicit human reset:
```bash
curl -X POST http://localhost:5000/approve-breaker \
  -H "Authorization: Bearer $GATE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "martin"}'
```

Before resetting, review what triggered it:
```bash
sqlite3 swarm.db "SELECT * FROM circuit_breaker_log ORDER BY triggered_at DESC LIMIT 5;"
```

---

### Experiments keep failing and not learning from history

**Cause:** Warm memory files may be missing or corrupt.

**Fix:**
```bash
ls memory/knowledge/
# Should contain: experiments.json, learnings.json, verticals.json
```

If files are missing:
```bash
mkdir -p memory/knowledge
echo '[]' > memory/knowledge/experiments.json
echo '[]' > memory/knowledge/learnings.json
echo '{}' > memory/knowledge/verticals.json
```

---

## Scheduler / Timing Issues

### Agents not running on schedule

**Cause:** APScheduler failed to start, or a previous job run errored and blocked the thread.

**Fix:**
1. Check logs at startup for `[SCHEDULER]` lines
2. Look for unhandled exceptions in previous job runs — APScheduler swallows them silently unless logging is configured
3. Restart `main.py` — APScheduler starts fresh on restart

To trigger an agent manually:
```bash
python3 cli.py run-general
python3 cli.py run-scout
```

---

### Data collection not running

**Symptom:** `collected_data` table is empty or not growing.

**Fix:**
1. Check that at least one row exists in `collection_sources` with `active = 1`
2. Check logs for `[DATA COLLECTION]` errors
3. Run manually: `python3 -c "from data_collection.orchestrator import run; run()"`

---

## Swarm Board Errors

### Board shows "API Offline" or Overview tab is blank

**Cause:** The Dashboard API on port 5003 is not running, or CORS is blocking requests.

**Fix:**
1. Confirm `main.py` is running and the dashboard API started: `curl http://localhost:5003/api/health`
2. If running on a different port, update `VITE_API_URL` in `swarm-board/.env.local`
3. If the frontend is on a non-localhost domain, set `FRONTEND_URL` in `.env` and restart `main.py`

---

### Board tasks reset to seed tasks on every reload

**Cause:** The browser's localStorage was cleared, or the board is running in private/incognito mode.

**Fix:** Use a regular (non-incognito) browser window. Tasks persist in `localStorage` under the key `swarm_tasks`.

---

### npm error: `Cannot find module @vitejs/plugin-react`

**Cause:** Node modules not installed.

**Fix:**
```bash
cd swarm-board
npm install
```

---

## Slack Errors

### Slack notifications not sending

**Cause:** `SLACK_WEBHOOK_URL` not configured, or the webhook URL has been revoked.

**Fix:**
1. Check `.env`: `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...`
2. Test the webhook: `curl -X POST -H 'Content-type: application/json' --data '{"text":"Test"}' $SLACK_WEBHOOK_URL`
3. If revoked, create a new incoming webhook at api.slack.com/apps

---

### `/slack/actions` returning 403

**Cause:** Slack signature verification failed. `SLACK_SIGNING_SECRET` is wrong, or the request is too old (>5 minutes).

**Fix:**
1. Go to api.slack.com/apps → your app → Basic Information → App Credentials → Signing Secret
2. Update `SLACK_SIGNING_SECRET` in `.env`
3. Restart `main.py`

---

## Database Errors

### `sqlite3.OperationalError: database is locked`

**Cause:** Two processes are writing to the database simultaneously and WAL mode isn't resolving the contention fast enough.

**Fix:**
- The database uses WAL journal mode which handles concurrent access — this should be rare
- If it persists, check for zombie processes: `ps aux | grep python`
- Ensure only one instance of `main.py` is running
- If a backup tool is locking the file, exclude `swarm.db` from live backup

---

### Column missing errors after upgrade (`no such column`)

**Cause:** A new column was added to the schema but the migration didn't run.

**Fix:** Migrations run automatically on every startup via `_apply_migrations()`. Simply restart `main.py`:

```bash
python3 main.py
```

If the error persists, check `memory/database.py` → `_apply_migrations()` to see if the column is in the migrations list. If not, add it and restart.

---

## Getting More Debug Information

Enable verbose logging by adding to `.env`:
```env
LOG_LEVEL=DEBUG
```

Or at runtime:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

To watch the database in real time during a run:
```bash
watch -n 2 'sqlite3 swarm.db "SELECT status, COUNT(*) FROM experiments GROUP BY status;"'
```
