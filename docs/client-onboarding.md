# Solar Client Onboarding Guide

This guide is written for solar business owners. No technical knowledge required.

---

## What You're Getting

Solar Swarm is an AI system that works in the background of your business, 24 hours a day, doing three things:

1. **Qualifies your leads** — Every time a new enquiry comes in, the AI scores them from 1 to 10 and decides whether to call them immediately, nurture them, or move on.

2. **Handles calls for you** — Hot leads (score 7 or higher with a phone number) get an outbound AI call automatically. The AI speaks in plain Australian English, asks the right questions, and books assessments into your calendar.

3. **Shows you what's working** — You get a weekly report and a live dashboard showing your lead pipeline, call outcomes, and what the AI is learning.

The system connects to your existing GoHighLevel (GHL) account. Nothing changes about how you use GHL — you just start seeing leads arrive pre-scored, pre-called, and pre-organised.

---

## What We Need From You

To get you set up, we need:

### 1. Your GHL Sub-Account Access

Either:
- Add us as a user on your GHL sub-account (preferred), or
- Give us your GHL API key and Location ID (your consultant will tell you exactly where to find these)

We need access to your:
- **Contacts** — so the AI knows who's in your pipeline
- **Pipelines** — so we can move leads through stages automatically
- **Workflows** — so we can trigger actions based on lead score

### 2. Your Phone Number for Voice Calls

We'll set up a dedicated number (or use your existing one) for the AI to call leads from. It needs to be in Australian format.

If you want the AI to sound like a specific person from your team, we can clone their voice using ElevenLabs (takes about 10 minutes of audio).

### 3. Your Key Business Info

We need to programme the AI with:

- **Company name** and what you do
- **Service areas** (postcodes, states, or cities you cover)
- **System sizes and pricing** (approximate is fine — the AI won't quote exact prices, just ranges)
- **Current government rebates** and any special offers
- **What makes you different** from other solar companies in your area

This takes about 30 minutes in a Zoom call.

### 4. Your Lead Qualification Criteria

Tell us what a great lead looks like for you. For example:
- Homeowner (not renter)
- Monthly electricity bill over $250
- Roof less than 15 years old
- Not already got solar

The AI scores leads against these criteria. Anything scoring 7 or higher gets an automatic outbound call.

---

## What Happens With Your Leads

Here's the journey a new lead takes through the system:

**Step 1: Lead arrives**
A new contact is created in GHL (from your website form, Facebook ad, or direct entry).

**Step 2: AI scores the lead (< 5 seconds)**
The AI reads the lead's details and gives them a score from 1 to 10:
- Score 7–10 → "Call now" (hot lead)
- Score 5–6 → "Nurture" (worth following up manually)
- Score 1–4 → "Disqualify" (unlikely to convert)

**Step 3: Hot leads get an AI call**
Within minutes of arriving, the AI calls your hot leads. It:
- Asks about their electricity bill, roof type, and home ownership
- Answers common questions about solar in plain language
- Books an assessment if they're interested
- Creates a GHL task for your sales team if they ask for a callback

**Step 4: You see the result in GHL**
After every call, the lead record in GHL is updated with:
- A summary of the conversation
- Tags like "assessment-booked" or "callback-requested"
- The recording URL so you can listen back

**Step 5: You get a weekly report**
Every Monday, you receive a performance summary showing call volume, booking rate, lead scores, and what the AI is learning.

---

## What the AI Will and Won't Do

**The AI will:**
- Introduce itself clearly (it doesn't pretend to be human — though it won't volunteer that it's an AI unless asked directly)
- Collect the information your sales team needs before a site visit
- Book assessment appointments if you've connected your calendar
- Handle objections politely and professionally
- Transfer to a human if the prospect insists

**The AI won't:**
- Quote exact prices (it gives ranges and says your team will confirm)
- Pressure or rush prospects
- Call leads who are on the Do Not Call Register
- Make promises about savings that can't be guaranteed

---

## Your Dashboard

You have access to a live dashboard showing:

- **Lead pipeline** — how many leads are at each stage
- **Recent calls** — outcome and score for every AI call
- **Weekly budget** — how much has been spent on experiments this week
- **AI learnings** — what's working and what isn't

Your consultant will send you the dashboard link and login credentials.

---

## Approval Flow

Some things require your approval before the AI acts on them. You'll receive a Slack message (or email if Slack isn't set up) with an Approve or Reject button.

This typically happens for:
- New experiment ideas the AI wants to test
- Budget requests above the weekly threshold
- Any action that would spend money externally

You can approve or reject with a single button click. If you don't respond within 24 hours, the experiment stays on hold — nothing happens without your approval.

---

## What You'll See in GHL

The system adds these tags to contacts automatically:

| Tag | Meaning |
|-----|---------|
| `voice-ai-qualified` | AI called and qualified the lead |
| `assessment-booked` | Assessment appointment was booked on the call |
| `callback-requested` | Lead asked for a human callback |
| `hot-lead` | Score was 7 or higher |
| `battery-interest` | Lead mentioned interest in battery storage |
| `ev-owner` | Lead mentioned they own an electric vehicle |
| `not-interested-voice` | Lead declined on the call |

You can use these tags to build GHL automations (for example, triggering a task for your sales team when `assessment-booked` is added).

---

## Costs and What's Included in Your Retainer

Your monthly retainer covers:

| Item | Included |
|------|---------|
| Lead qualification scoring | All leads |
| AI outbound calls | Up to ~200 calls/month |
| Weekly performance reports | Yes |
| Dashboard access | Yes |
| GHL integration and maintenance | Yes |
| Support (email + Slack) | Business hours |

API costs (OpenAI, Retell, ElevenLabs) run approximately $50–100 AUD per month at typical volumes and are included in your retainer. If your call volume significantly exceeds 200 calls per month, we'll discuss a small overage charge.

---

## Privacy and Data

All lead data is stored in a secure database on your consultant's server. Data is not shared with any third parties except the API services used to run the system (OpenAI for AI, Retell for calls, GoHighLevel for your CRM).

Call recordings are stored by Retell and linked in your GHL contact record. You can request deletion of any recording at any time.

---

## Getting Help

**For urgent issues** (system down, calls not working):
Contact your consultant directly via the number or email provided in your onboarding email.

**For general questions or changes**:
Email or Slack your consultant. Turnaround is typically same business day.

**To pause the system**:
Your consultant can pause all outbound calls or lead processing with one command. Just ask.

---

## Checklist: Before We Go Live

Your consultant will work through this with you:

- [ ] GHL access confirmed
- [ ] Phone number set up and linked to the AI agent
- [ ] Company knowledge base written (products, pricing, service areas, FAQs)
- [ ] Lead qualification criteria agreed
- [ ] Test call done and voice approved
- [ ] GHL webhooks connected and tested
- [ ] Approval notifications set up (Slack or email)
- [ ] Dashboard access shared
- [ ] First weekly report template reviewed

Typical time from signed agreement to live system: **3–5 business days**.
