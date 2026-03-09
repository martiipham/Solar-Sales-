# Solar Swarm — Business Overview

**Owner:** Martin Pham | Perth, Australia | AI Automation Consultant
**Date:** March 2026
**Version:** 2.0

---

## Executive Summary

Solar Swarm is an AI-powered sales automation platform purpose-built for Australian solar installation companies. It eliminates the two biggest revenue leaks in solar sales: slow lead response times and inconsistent follow-up.

The platform integrates directly into a client's existing GoHighLevel CRM and begins operating within 48 hours of setup. Every inbound lead is automatically scored, called by an AI voice agent, and moved through the pipeline — without any action required from the sales team.

**Revenue model:** $1,500–2,000 AUD/month retainer per client
**Margin:** 80–90% (total operating costs ~$400 AUD/month)
**Break-even:** 1 client

---

## The Problem We Solve

Australian solar SMEs (5–15 salespeople) share a universal pattern:

| Pain Point | Business Impact |
|---|---|
| Leads sit uncontacted for 2–4 hours | Industry data: response after 5 min = 9x more conversions |
| Sales reps cherry-pick leads | Hot prospects go cold while unqualified ones get called |
| No consistent follow-up system | 80% of solar deals close after 3+ touchpoints; most reps stop at 1 |
| Owner has no visibility | Can't see pipeline health, call volumes, or what's working |
| Staff turnover disrupts process | Every new hire needs retraining on the follow-up playbook |

Solar Swarm replaces all five failure points with automated, AI-driven systems that run 24/7.

---

## What the Platform Delivers

### Lead Qualification (Immediate)
Every new enquiry receives a GPT-4o qualification score from 1–10 within seconds of arriving in GHL. The score is based on:
- Solar interest signals (roof ownership, electricity bill, timeline)
- Contact completeness (phone, email, suburb)
- Competitive context (existing quotes, urgency)

### AI Voice Outreach (Within Minutes)
Hot leads (score ≥ 7) trigger an outbound AI phone call via Retell AI. The AI:
- Speaks in natural Australian English
- Qualifies the lead further using a customised script
- Books a site assessment into the sales calendar
- Updates the GHL pipeline with call outcome

### Pipeline Automation
- Contacts tagged and moved through stages automatically
- Slack alerts sent to owner and rep for hot leads
- Cold leads placed into long-term nurture sequences
- Weekly performance report delivered every Monday

### Live Dashboard
A web-based dashboard (port 5003) shows:
- Pipeline stage counts in real time
- Lead qualification scores and call outcomes
- Swarm experiment status and AI activity
- Budget utilisation and circuit breaker state

---

## Target Client Profile

| Attribute | Specification |
|---|---|
| Industry | Residential/commercial solar installation |
| Location | Australia (primarily WA, QLD, VIC, NSW) |
| Company size | 5–15 salespeople |
| Monthly lead volume | 50–500 enquiries |
| CRM | GoHighLevel (or willing to adopt) |
| Current pain | Slow response, inconsistent follow-up, no visibility |
| Decision maker | Owner/Director |
| Budget signal | Already paying for GHL ($97–$297/month) — understands SaaS |

---

## Competitive Differentiation

| Feature | Solar Swarm | Generic CRM Automation | Offshore VA | In-house SDR |
|---|---|---|---|---|
| Response time | < 2 minutes | Hours (if configured) | Business hours | Business hours |
| 24/7 operation | Yes | Yes | No | No |
| Industry-specific scoring | Yes | No | No | Trained only |
| Voice AI calls | Yes | No | No | Yes |
| Setup time | 48 hours | Weeks | Days | Months |
| Monthly cost | $1,500–2,000 | $200–500 | $3,000–5,000 | $8,000–12,000 |
| Scales without cost | Yes | Partly | No | No |

---

## Revenue Model

### Retainer Structure
```
Tier 1 — Foundation:  $1,500/month
  ├── Lead qualification + pipeline automation
  ├── Weekly performance reports
  └── Standard Slack alerts

Tier 2 — Growth:      $2,000/month
  ├── Everything in Tier 1
  ├── AI voice outreach (Retell integration)
  ├── Custom qualification criteria
  └── Monthly strategy review call

Add-ons (future):
  ├── Multi-location support:     +$500/location
  ├── Custom AI persona/voice:    +$300 one-time
  └── Advanced A/B experiment:    $500 per experiment
```

### Unit Economics
```
Revenue per client:          $1,750/month (average)
OpenAI API costs:            ~$150/month (GPT-4o at scale)
Retell AI voice costs:       ~$100/month (500 calls × $0.20)
Infrastructure/hosting:      ~$50/month
Slack/tools:                 ~$50/month
Gross cost per client:       ~$350–400/month
Gross margin:                80%+

At 5 clients:
  Revenue:    $8,750/month
  Costs:      ~$2,000/month
  Profit:     ~$6,750/month
```

---

## Growth Roadmap

### Phase 1 — Proof of Concept (Current)
- First 1–2 clients onboarded at reduced rate ($1,000/month)
- Validate qualification accuracy and AI call quality
- Build case studies with real metrics

### Phase 2 — Productise (Months 3–6)
- Standard onboarding playbook (48-hour setup)
- Self-service dashboard for clients
- Referral incentive programme
- Target: 5 clients

### Phase 3 — Scale (Months 6–12)
- Agency partner model (other consultants white-label)
- Multi-industry expansion (HVAC, pools, property)
- Hiring first contractor support
- Target: 15+ clients, $25,000+/month revenue

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Client churns after month 1 | Medium | High | Strong onboarding + first-week WOW moments |
| OpenAI API price increase | Low | Medium | Margin buffer; switch to Anthropic if needed |
| GHL changes API | Low | High | CRM router abstraction; HubSpot/SF fallback |
| AI call quality complaints | Medium | High | Human review toggle; call recording review |
| Competitor copies approach | High | Medium | Relationships + speed advantage |
| Regulatory (AI calling laws) | Low | High | Human handoff option; full disclosure |

---

## Success Metrics

| Metric | Target |
|---|---|
| Lead response time | < 5 minutes for hot leads |
| Qualification accuracy | > 80% agreement with human assessment |
| AI call answer rate | > 40% of outbound calls answered |
| Pipeline velocity | 20%+ increase in stage progression speed |
| Client retention | > 90% at 3 months |
| NPS score | > 50 |
