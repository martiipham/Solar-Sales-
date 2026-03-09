# CRM Integration Guide

## Overview: crm_router Abstraction

File: `integrations/crm_router.py`

All agent code calls `crm_router` functions directly. The router selects the active CRM at runtime based on which credentials are configured.

**Priority order:** GoHighLevel → HubSpot → Salesforce

If GHL_API_KEY is set, all calls go to GHL. If only HubSpot is configured, calls go to HubSpot. Agents never need to know which platform is live.

```python
from integrations.crm_router import crm_router

# These calls work identically regardless of which CRM is active
crm_router.get_contact("abc123")
crm_router.create_contact({"name": "Jane Smith", "email": "jane@example.com"})
crm_router.move_pipeline_stage("abc123", "qualified")
```

---

## GoHighLevel (GHL) Setup

GHL is the primary CRM. All clients are expected to be on GHL.

### Step 1: Get your API key

1. Log in to your GHL sub-account (not the agency account)
2. Go to **Settings → Integrations → API**
3. Copy the **Private Integration API Key**
4. Add to `.env`: `GHL_API_KEY=your-key-here`

### Step 2: Get your Location ID

1. In GHL, go to **Settings → Business Profile**
2. The Location ID is visible in the URL: `app.gohighlevel.com/location/{LOCATION_ID}/...`
3. Add to `.env`: `GHL_LOCATION_ID=your-location-id`

### Step 3: Get your Pipeline ID (for stage sync)

1. Go to **CRM → Pipelines**
2. Open the pipeline you want to track
3. The pipeline ID is in the URL
4. Add to `.env`: `GHL_PIPELINE_ID=your-pipeline-id`

### Step 4: Configure Webhooks

GHL needs to be configured to send events to the Solar Swarm webhook server.

1. Go to **Settings → Integrations → Webhooks**
2. Click **Add Webhook**
3. Set the URL to your server: `https://your-server.com/webhook/new-lead`
4. Select the following events:
   - **Contact Created** → maps to `/webhook/new-lead`
   - **Opportunity Stage Change** → maps to `/webhook/stage-change`
5. Copy the **Signing Secret** and add to `.env`: `GHL_WEBHOOK_SECRET=...`

For voice call events:
- Point the **Conversation Status Changed** event to `/webhook/call-complete`

For form submissions:
- Create a GHL Funnel with a form and set the webhook URL to `/webhook/form-submit`

**Note:** Your server must be publicly accessible. Use ngrok for local development:
```bash
ngrok http 5001
# Copy the https URL and use it as the base for your webhook URLs
```

### GHL Custom Fields Expected

The system reads these custom fields from GHL contact payloads:

| Field Key | Description |
|-----------|-------------|
| `homeowner_status` | owner / renter / unknown |
| `monthly_bill` | Monthly electricity bill in AUD |
| `roof_type` | tile / colorbond / flat / metal |
| `roof_age` | Roof age in years |

---

## HubSpot Setup

HubSpot is supported as a fallback CRM.

### Required credentials

```
HUBSPOT_API_KEY=pat-na1-...  # Private app token (not legacy API key)
```

### Getting a Private App Token

1. Go to **Settings → Integrations → Private Apps**
2. Click **Create a private app**
3. Under **Scopes**, enable:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.deals.read`
   - `crm.objects.deals.write`
   - `conversations.read`
   - `timeline` (for notes)
4. Click **Create app** and copy the token

---

## Salesforce Setup

Salesforce is supported as a third fallback.

### Required credentials

```
SALESFORCE_USERNAME=your@email.com
SALESFORCE_PASSWORD=yourpassword
SALESFORCE_SECURITY_TOKEN=yourtoken
SALESFORCE_CLIENT_ID=your-connected-app-client-id
SALESFORCE_CLIENT_SECRET=your-connected-app-secret
```

### Getting credentials

1. **Security Token:** Go to **Settings → My Personal Information → Reset My Security Token**
2. **Connected App:** Go to **Setup → Apps → App Manager → New Connected App**
   - Enable **OAuth Settings**
   - Add scopes: `api`, `refresh_token`
   - Save and copy the Consumer Key (Client ID) and Consumer Secret

---

## Feature Matrix

| Feature | GHL | HubSpot | Salesforce |
|---------|-----|---------|-----------|
| Get contact | Yes | Yes | Yes |
| Create contact | Yes | Yes | Yes |
| Update contact field | Yes | Yes | Yes |
| Add tag | Yes | Yes (property) | Yes (field) |
| Move pipeline stage | Yes | Yes (deal stage) | Yes (opportunity stage) |
| Create task | Yes | Yes | Yes |
| Send SMS | Yes | No | No |
| Add note | No (no native API) | Yes | Yes |
| Find by phone | Yes | Yes | Yes (SOQL) |
| Get pipeline stages | Yes | Yes | Yes |
| Inbound webhooks | Yes (native) | Yes (via subscriptions) | Yes (via outbound messages) |

---

## How to Switch CRMs

1. Remove or blank out the current CRM's key in `.env`
2. Add the new CRM's credentials
3. Restart `python main.py`

The `active_crm()` function re-evaluates on every call, so no code changes are needed.

To check which CRM is active:
```bash
curl http://localhost:5003/api/crm/status
```

---

## crm_router Public API Reference

All functions are in `integrations/crm_router.py`. All return `None` on failure (never raise).

| Function | Params | Returns | GHL | HubSpot | SF |
|----------|--------|---------|-----|---------|-----|
| `active_crm()` | — | `str` ('ghl'/'hubspot'/'salesforce'/'none') | — | — | — |
| `all_configured_crms()` | — | `list[str]` | — | — | — |
| `is_configured()` | — | `bool` | — | — | — |
| `status()` | — | `{active, ghl, hubspot, salesforce}` | — | — | — |
| `get_contact(contact_id)` | `str` | contact dict or None | Yes | Yes | Yes |
| `create_contact(data)` | `dict` | created contact dict or None | Yes | Yes | Yes |
| `update_contact_field(contact_id, field, value)` | `str, str, any` | dict or None | Yes | Yes | Yes |
| `add_contact_tag(contact_id, tag)` | `str, str` | dict or None | Yes | Yes | Yes |
| `move_pipeline_stage(contact_id, stage_id)` | `str, str` | dict or None | Yes | Yes | Yes |
| `create_task(contact_id, title, due_date)` | `str, str, str` | dict or None | Yes | Yes | Yes |
| `send_sms(contact_id, message)` | `str, str` | dict or None | Yes | No | No |
| `add_note(contact_id, note_body)` | `str, str` | dict or None | No | Yes | Yes |
| `get_pipeline_stages(pipeline_id=None)` | `str \| None` | list | Yes | Yes | Yes |
| `find_contact_by_phone(phone)` | `str` | dict or None | Yes | Yes | Yes |

---

## GHL API Client Reference

The underlying `integrations/ghl_client.py` (used directly when not going through crm_router):

| Function | Params | Notes |
|----------|--------|-------|
| `get_contact(contact_id)` | `str` | GET /contacts/{id} |
| `update_contact_field(contact_id, field, value)` | `str, str, any` | PUT /contacts/{id} with customField |
| `move_pipeline_stage(contact_id, stage_id)` | `str, str` | POST /contacts/{id}/pipeline-stage |
| `add_contact_tag(contact_id, tag)` | `str, str` | POST /contacts/{id}/tags |
| `create_task(contact_id, title, due_date)` | `str, str, str` | POST /tasks/ |
| `send_sms(contact_id, message)` | `str, str` | POST /conversations/messages (type: SMS) |
| `create_contact(data)` | `dict` | POST /contacts/ (locationId auto-injected) |
| `get_pipeline_stages(pipeline_id)` | `str` | GET /opportunities/pipelines/{id} |
| `is_configured()` | — | True if GHL_API_KEY and GHL_LOCATION_ID both set |

All functions return `None` on error. Check `config.GHL_API_KEY` before calling if you want to skip gracefully.

Base URL: `https://services.leadconnectorhq.com`
API Version header: `2021-07-28`
