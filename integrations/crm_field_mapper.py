"""CRM Field Mapper — Normalizes contact data across CRM providers.

Each CRM uses different field names for the same data. This module
provides bidirectional mapping so business logic works with a single
canonical schema while each CRM client receives correctly-named fields.

Canonical schema (what agents/workers use):
    first_name, last_name, email, phone, company, city, state,
    homeowner_status, monthly_bill, roof_type, roof_age, source,
    qualification_score, tags

Usage:
    from integrations.crm_field_mapper import to_canonical, from_canonical

    # CRM response → canonical
    canonical = to_canonical("ghl", ghl_contact_data)

    # Canonical → CRM format
    crm_data = from_canonical("hubspot", canonical_data)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FIELD MAPPING TABLES
# ─────────────────────────────────────────────────────────────────────────────

# canonical_field → crm_field for each provider
_FIELD_MAP: dict[str, dict[str, str]] = {
    "ghl": {
        "first_name": "firstName",
        "last_name": "lastName",
        "email": "email",
        "phone": "phone",
        "company": "companyName",
        "city": "city",
        "state": "state",
        "address": "address1",
        "postal_code": "postalCode",
        "country": "country",
        "source": "source",
        "tags": "tags",
        # Solar-specific custom fields (GHL custom field keys)
        "homeowner_status": "homeowner_status",
        "monthly_bill": "monthly_bill",
        "roof_type": "roof_type",
        "roof_age": "roof_age",
    },
    "hubspot": {
        "first_name": "firstname",
        "last_name": "lastname",
        "email": "email",
        "phone": "phone",
        "company": "company",
        "city": "city",
        "state": "state",
        "address": "address",
        "postal_code": "zip",
        "country": "country",
        "source": "hs_lead_status",
        "tags": "hs_tag",
        "homeowner_status": "homeowner_status",
        "monthly_bill": "monthly_bill",
        "roof_type": "roof_type",
        "roof_age": "roof_age",
    },
    "salesforce": {
        "first_name": "FirstName",
        "last_name": "LastName",
        "email": "Email",
        "phone": "Phone",
        "company": "Account.Name",
        "city": "MailingCity",
        "state": "MailingState",
        "address": "MailingStreet",
        "postal_code": "MailingPostalCode",
        "country": "MailingCountry",
        "source": "LeadSource",
        "tags": "Tags__c",
        "homeowner_status": "Homeowner_Status__c",
        "monthly_bill": "Monthly_Bill__c",
        "roof_type": "Roof_Type__c",
        "roof_age": "Roof_Age__c",
    },
    "agilecrm": {
        "first_name": "first_name",
        "last_name": "last_name",
        "email": "email",
        "phone": "phone",
        "company": "company",
        "city": "city",
        "state": "state",
        "address": "address",
        "postal_code": "zip",
        "country": "country",
        "source": "source",
        "tags": "tags",
        # Solar-specific custom fields (stored as CUSTOM properties in Agile CRM)
        "homeowner_status": "homeowner_status",
        "monthly_bill": "monthly_bill",
        "roof_type": "roof_type",
        "roof_age": "roof_age",
    },
}

# Build reverse maps: crm_field → canonical_field
_REVERSE_MAP: dict[str, dict[str, str]] = {}
for crm, mapping in _FIELD_MAP.items():
    _REVERSE_MAP[crm] = {v: k for k, v in mapping.items()}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def to_canonical(crm: str, data: dict) -> dict:
    """Convert CRM-specific contact data to canonical schema.

    Handles nested structures (GHL customField, HubSpot properties).

    Args:
        crm: CRM name ('ghl', 'hubspot', 'salesforce')
        data: Raw CRM contact dict

    Returns:
        Dict with canonical field names
    """
    if crm not in _REVERSE_MAP:
        logger.warning("[FIELD_MAPPER] Unknown CRM '%s'; returning data as-is", crm)
        return data

    flat = _flatten_crm_data(crm, data)
    reverse = _REVERSE_MAP[crm]
    canonical = {}

    for crm_field, value in flat.items():
        if crm_field in reverse:
            canonical[reverse[crm_field]] = value
        # Keep unmapped fields with their original names
        elif crm_field not in ("id", "Id", "contactId"):
            canonical[crm_field] = value

    # Ensure ID is always present
    contact_id = data.get("id") or data.get("Id") or data.get("contactId")
    if contact_id:
        canonical["id"] = contact_id

    return canonical


def from_canonical(crm: str, data: dict) -> dict:
    """Convert canonical contact data to CRM-specific format.

    Args:
        crm: CRM name ('ghl', 'hubspot', 'salesforce')
        data: Dict with canonical field names

    Returns:
        Dict with CRM-specific field names, structured for the target API
    """
    if crm not in _FIELD_MAP:
        logger.warning("[FIELD_MAPPER] Unknown CRM '%s'; returning data as-is", crm)
        return data

    mapping = _FIELD_MAP[crm]
    result = {}

    for canonical_field, value in data.items():
        if canonical_field in mapping:
            crm_field = mapping[canonical_field]
            result[crm_field] = value
        elif canonical_field != "id":
            result[canonical_field] = value

    return _structure_crm_data(crm, result)


def get_crm_field(crm: str, canonical_field: str) -> str | None:
    """Get the CRM-specific field name for a canonical field.

    Args:
        crm: CRM name
        canonical_field: Canonical field name

    Returns:
        CRM field name or None if not mapped
    """
    return _FIELD_MAP.get(crm, {}).get(canonical_field)


def get_canonical_field(crm: str, crm_field: str) -> str | None:
    """Get the canonical field name for a CRM-specific field.

    Args:
        crm: CRM name
        crm_field: CRM-specific field name

    Returns:
        Canonical field name or None if not mapped
    """
    return _REVERSE_MAP.get(crm, {}).get(crm_field)


def supported_crms() -> list[str]:
    """Return list of CRMs with field mapping support."""
    return list(_FIELD_MAP.keys())


def canonical_fields() -> list[str]:
    """Return list of all canonical field names."""
    # Union of all canonical fields across all CRMs
    fields = set()
    for mapping in _FIELD_MAP.values():
        fields.update(mapping.keys())
    return sorted(fields)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _flatten_crm_data(crm: str, data: dict) -> dict:
    """Flatten CRM-specific nested structures into a flat dict.

    GHL nests custom fields under 'customField', HubSpot under 'properties',
    Salesforce is already flat.
    """
    flat = {}

    if crm == "ghl":
        # GHL: top-level + customField dict
        for k, v in data.items():
            if k == "customField" and isinstance(v, dict):
                flat.update(v)
            elif k == "customFields" and isinstance(v, list):
                for cf in v:
                    flat[cf.get("id", cf.get("key", ""))] = cf.get("value", "")
            elif k not in ("id", "contactId"):
                flat[k] = v

    elif crm == "hubspot":
        # HubSpot: properties dict is the main data
        props = data.get("properties", data)
        for k, v in props.items():
            if isinstance(v, dict) and "value" in v:
                flat[k] = v["value"]
            else:
                flat[k] = v

    elif crm == "salesforce":
        # Salesforce: flat with 'attributes' metadata to skip
        for k, v in data.items():
            if k != "attributes":
                flat[k] = v

    elif crm == "agilecrm":
        # Agile CRM: properties array of {type, name, value} dicts + tags array
        props = data.get("properties", [])
        if isinstance(props, list):
            for prop in props:
                name = prop.get("name", "")
                value = prop.get("value", "")
                if name:
                    flat[name] = value
        # Tags are a top-level array
        tags = data.get("tags", [])
        if tags:
            flat["tags"] = ";".join(tags) if isinstance(tags, list) else tags

    return flat


def _structure_crm_data(crm: str, flat: dict) -> dict:
    """Re-structure flat data into CRM-specific nested format for API calls.

    Separates standard fields from custom fields where needed.
    """
    if crm == "ghl":
        standard_fields = {"firstName", "lastName", "email", "phone", "companyName",
                           "city", "state", "address1", "postalCode", "country",
                           "source", "tags", "locationId"}
        result = {}
        custom = {}
        for k, v in flat.items():
            if k in standard_fields:
                result[k] = v
            else:
                custom[k] = v
        if custom:
            result["customField"] = custom
        return result

    elif crm == "hubspot":
        # HubSpot API expects a flat 'properties' dict
        return flat

    elif crm == "salesforce":
        # Salesforce API expects a flat dict
        return flat

    elif crm == "agilecrm":
        # Agile CRM expects a properties array of {type, name, value}
        system_fields = {"first_name", "last_name", "email", "phone", "company",
                         "title", "address", "city", "state", "zip", "country"}
        properties = []
        tags = None
        for k, v in flat.items():
            if k == "tags":
                tags = v
                continue
            prop_type = "SYSTEM" if k in system_fields else "CUSTOM"
            prop = {"type": prop_type, "name": k, "value": str(v)}
            if k == "email":
                prop["subtype"] = "work"
            elif k == "phone":
                prop["subtype"] = "work"
            properties.append(prop)
        result = {"properties": properties}
        if tags:
            result["tags"] = tags.split(";") if isinstance(tags, str) else tags
        return result

    return flat
