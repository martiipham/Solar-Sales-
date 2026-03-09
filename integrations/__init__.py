"""Integrations package for Solar Swarm.

Available CRM clients:
    ghl_client       — GoHighLevel
    hubspot_client   — HubSpot
    salesforce_client — Salesforce

CRM abstraction (use this in agents — auto-routes to active CRM):
    crm_router       — Single interface regardless of which CRM is live

Messaging:
    slack_client     — Slack Web API (read + write)

The existing notifications/slack_notifier.py handles outbound webhook alerts.
slack_client adds full two-way Slack API support.
"""

# Modules: ghl_client, hubspot_client, salesforce_client, crm_router, slack_client
