# Solar Swarm — Change Management Process

**Version:** 1.0
**Owner:** Martin Pham
**Purpose:** Define how system changes are evaluated, approved, tested, and deployed

---

## Overview

Solar Swarm is a production system handling live client leads and active AI voice calls. Uncontrolled changes can break lead qualification, silently stop pipeline automation, or cause AI calls to fail mid-conversation. This document defines the mandatory process for all changes.

**Golden rule:** No change to production without a tested rollback path.

---

## Change Categories

### Category 1 — Low Risk (No Approval Required)
Changes that cannot affect production lead flow:

- Documentation updates
- Dashboard UI cosmetic changes (colours, layout, labels)
- Adding new Slack notification channels
- Updating `.env` values for non-critical config (LOG_LEVEL, port numbers)
- Adding new monitoring/logging statements
- Updating `board-state.json` content manually

**Process:** Make change → test locally → commit → deploy

---

### Category 2 — Medium Risk (Self-Approval with Testing)
Changes that affect system behaviour but have quick rollback:

- Adding new API endpoints (non-destructive)
- Changing GPT-4o prompt templates
- Adjusting confidence score thresholds
- Modifying scheduler job intervals
- Adding new database columns (additive only)
- Updating CRM field mappings
- Changing voice call scripts

**Process:** Test locally → document expected behaviour change → commit with detailed message → deploy → monitor for 30 minutes → confirm or rollback

---

### Category 3 — High Risk (Requires Review Checklist)
Changes that affect core business logic or client data:

- Modifying the Kelly Criterion calculator
- Changing circuit breaker thresholds
- Altering database schema (columns removed or renamed)
- Modifying authentication / API key validation
- Changing CRM router logic
- Updating lead qualification scoring algorithm
- Modifying the human gate approval workflow
- Budget allocation changes

**Process:** Complete change review checklist → test on staging → document rollback steps → deploy with monitoring → confirm or execute rollback

---

### Category 4 — Critical (Requires Explicit Sign-Off)
Changes that could cause data loss, billing errors, or security issues:

- Removing database tables or columns
- Changing authentication system
- Modifying circuit breaker halt conditions
- Any change to payment or budget allocation logic
- Changing API keys or secrets rotation process
- Deploying to production during active client calls

**Process:** Written sign-off in commit message → full staging test → production deploy in maintenance window → immediate monitoring → 24-hour observation period

---

## Change Review Checklist (Category 3+)

```
[ ] Change description written in plain English
[ ] Business impact assessed: what could go wrong?
[ ] Affected components identified (list them)
[ ] Database migrations tested locally
[ ] All automated tests pass
[ ] Rollback steps documented (see rollback-procedures.md)
[ ] No hardcoded API keys or secrets introduced
[ ] Logging added for new critical paths
[ ] Dashboard API endpoints return expected responses
[ ] GHL webhook handler tested with sample payload
[ ] Scheduler jobs run without error
[ ] CRM sync completes successfully
[ ] Human gate approve/reject flow verified
```

---

## Deployment Windows

### Standard Deployments
- Preferred: Tuesday–Thursday, 10:00–14:00 AWST
- Avoid: Monday mornings (scheduler-heavy), Friday afternoons
- Avoid: During known client peak times (e.g. end of quarter)

### Emergency Deployments (Bug Fixes)
- Any time, but notify in #swarm-alerts Slack channel first
- Always have rollback ready before deploying
- Monitor for 15 minutes post-deploy

### Blocked Windows (No Deployments)
- During active A/B tests in final 24 hours
- When circuit breaker is at Orange or Red
- When a client onboarding is in progress (first 48 hours)

---

## Version Control Standards

### Commit Message Format
```
[TYPE] Short description (under 72 chars)

Body: What changed and why.
Risk level: Low / Medium / High / Critical
Testing: What was tested and how.
Rollback: How to revert if needed.
```

**Types:**
- `[FIX]` — Bug fix
- `[FEAT]` — New feature
- `[CONFIG]` — Configuration change
- `[SCHEMA]` — Database schema change
- `[PROMPT]` — AI prompt change
- `[SECURITY]` — Security fix
- `[DOCS]` — Documentation only
- `[HOTFIX]` — Emergency production fix

### Branch Strategy
```
main          ← production only; auto-deploys
develop       ← integration branch
feature/xxx   ← new features (branch from develop)
fix/xxx       ← bug fixes (branch from main for hotfixes)
```

---

## Incident Response

### Severity Levels

**P1 — Critical (respond immediately)**
- AI calls failing or calling wrong numbers
- Lead qualification returning null scores
- CRM pipeline not updating
- Database corruption or data loss
- Security breach suspected

**P2 — High (respond within 1 hour)**
- Dashboard API down (board shows stale data)
- Slack notifications not sending
- Scheduler jobs silently failing
- Human gate unreachable

**P3 — Medium (respond within 4 hours)**
- Individual webhook payloads failing
- Slow API responses (> 5 seconds)
- CRM sync delayed > 2 hours

**P4 — Low (next business day)**
- Documentation out of date
- Minor UI display issues
- Non-critical log warnings

### Incident Process
1. **Detect** — alert from Slack, monitoring, or client report
2. **Contain** — use circuit breaker or disable scheduler job
3. **Diagnose** — check logs, identify root cause
4. **Fix or Rollback** — apply fix or execute rollback procedure
5. **Verify** — confirm system back to normal
6. **Document** — write brief post-mortem (what happened, fix, prevention)

---

## Configuration Change Log

All changes to production `.env` must be recorded:

| Date | Key Changed | Changed By | Reason |
|------|-------------|------------|--------|
| YYYY-MM-DD | KEY_NAME | Name | Reason for change |

---

## AI Prompt Change Process

Prompt changes are Category 2 (medium risk) but require extra care because:
- GPT-4o outputs can change unpredictably with minor wording shifts
- Qualification score distributions may shift (affecting routing)
- Voice call scripts affect the client's brand and customer experience

**Before changing any prompt:**
1. Run the existing prompt against 10 test leads — record scores
2. Apply new prompt to same test leads — compare scores
3. Check that hot/cold/borderline classification stays consistent
4. Review AI voice call script changes with a sample call

---

## Change Communication

### Internal (Martin / solo operator)
- Document changes in commit messages
- Update CLAUDE.md if architecture changes
- Note prompt changes in `docs/` if significant

### Client-Facing
- Notify clients of changes that affect their experience:
  - New qualification criteria (discuss first)
  - Voice call script changes (send new script for review)
  - New pipeline stages or CRM field mappings
  - Scheduled maintenance windows (> 30 min downtime)
- Use Slack #solar-clients channel for client notifications
