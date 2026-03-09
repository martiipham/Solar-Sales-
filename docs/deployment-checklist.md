# Solar Swarm — Deployment Checklist

**Use this checklist for every production deployment.**

---

## Pre-Deployment

### Environment
- [ ] `.env` file has all required keys (run `python cli.py status`)
- [ ] No placeholder values remaining (e.g. `sk-your-openai-key-here`)
- [ ] Database file exists or will be auto-created (`swarm.db`)
- [ ] Python 3.11+ installed (`python --version`)
- [ ] All dependencies installed (`pip install -r requirements.txt`)

### Code
- [ ] All changes committed to git (`git status` clean)
- [ ] Change category identified (see change-management.md)
- [ ] Rollback procedure documented (see rollback-procedures.md)
- [ ] No hardcoded secrets in any file (`grep -r "sk-" . --include="*.py"`)

### Testing (complete before every deploy)
- [ ] Import check passes: `python -c "import main; print('OK')`
- [ ] Config loads: `python -c "import config; print(config.is_configured())"`
- [ ] Database initialises: `python -c "from memory.database import init_db; init_db()"`
- [ ] CRM router loads: `python -c "from integrations.crm_router import status; print(status())"`
- [ ] Dashboard API starts: run `python main.py` and check port 5003 responds

---

## Deployment Steps

### Step 1 — Stop Current Services
```bash
# If running as a process
pkill -f "python main.py"

# If running as a systemd service
sudo systemctl stop solar-swarm

# Verify stopped
ps aux | grep main.py
```

### Step 2 — Pull Latest Code
```bash
git pull origin main
```

### Step 3 — Update Dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Run Database Migrations
```bash
python -c "from memory.database import init_db; init_db(); print('DB OK')"
```

Check for any schema errors in output.

### Step 5 — Verify Configuration
```bash
python cli.py status
```

Expected output: all configured services show green/active status.

### Step 6 — Start Services
```bash
# Development / single-server
python main.py &

# Or as a service
sudo systemctl start solar-swarm
```

### Step 7 — Smoke Tests
```bash
# Dashboard API health
curl http://localhost:5003/api/health

# Human gate health
curl http://localhost:5000/health

# CRM status
curl http://localhost:5003/api/crm/status
```

Expected: all return `{"status": "ok"}` or similar JSON.

---

## Post-Deployment Monitoring (First 30 Minutes)

### Check Every 5 Minutes
- [ ] Slack #swarm-alerts — no error messages
- [ ] Dashboard board — live stats updating
- [ ] `tail -f logs/swarm.log` — no exceptions

### Verify Scheduler Jobs
After 6 minutes, check that the first scheduler tick ran:
```bash
grep "General" logs/swarm.log | tail -5
grep "CRM sync" logs/swarm.log | tail -5
```

### Verify Lead Flow (If Active Client)
- [ ] Send a test webhook to GHL handler port 5001
- [ ] Confirm qualification score appears in database
- [ ] Confirm Slack alert fires
- [ ] Confirm CRM pipeline stage updated

---

## Deployment Sign-Off

```
Date:           _______________
Deployed by:    _______________
Version/commit: _______________
Change type:    [ ] Cat 1  [ ] Cat 2  [ ] Cat 3  [ ] Cat 4
Issues found:   [ ] None  [ ] Minor (noted below)  [ ] Rolled back
Notes:
_______________________________________________
```

---

## Rollback Trigger Conditions

Execute rollback immediately if:
- Any P1 incident occurs within 30 minutes of deployment
- Lead qualification stops producing scores
- CRM pipeline updates fail
- AI voice calls error > 10% of attempts
- Database integrity errors appear in logs
- Any security alert fires

See `rollback-procedures.md` for rollback steps.
