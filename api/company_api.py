"""Company Profiles API — manage solar SME client company profiles.

Each profile is keyed by client_id (a short slug like 'perth-solar-co').
Profiles are used to brand client-facing dashboards and pre-fill proposals.

Blueprint: company_bp
  GET    /api/companies              — list all company profiles
  POST   /api/companies              — create a new profile
  GET    /api/companies/<client_id>  — get one profile
  PATCH  /api/companies/<client_id>  — update a profile
  DELETE /api/companies/<client_id>  — delete a profile (owner only)
"""

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from api.auth import require_auth
from memory.database import fetch_all, fetch_one, insert, get_conn

logger = logging.getLogger(__name__)
company_bp = Blueprint("company", __name__)

FIELDS = [
    "name", "abn", "address", "logo_url", "primary_color",
    "contact_email", "contact_phone", "website", "notes",
]


@company_bp.route("/api/companies", methods=["GET"])
@require_auth(roles=["owner", "admin"])
def list_companies():
    """Return all company profiles."""
    rows = fetch_all(
        "SELECT id, client_id, name, abn, address, logo_url, primary_color, "
        "contact_email, contact_phone, website, notes, created_at, updated_at "
        "FROM company_profiles ORDER BY name"
    )
    return jsonify({"companies": [dict(r) for r in rows]}), 200


@company_bp.route("/api/companies", methods=["POST"])
@require_auth(roles=["owner", "admin"])
def create_company():
    """Create a new company profile."""
    data = request.get_json() or {}
    client_id = (data.get("client_id") or "").strip().lower().replace(" ", "-")
    name = (data.get("name") or "").strip()

    if not client_id or not name:
        return jsonify({"error": "client_id and name are required"}), 400

    existing = fetch_one(
        "SELECT id FROM company_profiles WHERE client_id = ?", (client_id,)
    )
    if existing:
        return jsonify({"error": f"Company '{client_id}' already exists"}), 409

    row_data = {"client_id": client_id, "name": name}
    for field in FIELDS:
        if field != "name" and field in data:
            row_data[field] = data[field]

    new_id = insert("company_profiles", row_data)
    profile = fetch_one(
        "SELECT * FROM company_profiles WHERE id = ?", (new_id,)
    )
    return jsonify({"company": dict(profile)}), 201


@company_bp.route("/api/companies/<client_id>", methods=["GET"])
@require_auth()
def get_company(client_id: str):
    """Return a single company profile. Clients can only see their own."""
    if g.user["role"] == "client" and g.user.get("client_id") != client_id:
        return jsonify({"error": "Access denied"}), 403

    profile = fetch_one(
        "SELECT * FROM company_profiles WHERE client_id = ?", (client_id,)
    )
    if not profile:
        return jsonify({"error": "Company not found"}), 404
    return jsonify({"company": dict(profile)}), 200


@company_bp.route("/api/companies/<client_id>", methods=["PATCH"])
@require_auth(roles=["owner", "admin"])
def update_company(client_id: str):
    """Update a company profile."""
    data = request.get_json() or {}
    profile = fetch_one(
        "SELECT id FROM company_profiles WHERE client_id = ?", (client_id,)
    )
    if not profile:
        return jsonify({"error": "Company not found"}), 404

    allowed = {f: data[f] for f in FIELDS if f in data}
    allowed["updated_at"] = datetime.utcnow().isoformat()

    if not allowed:
        return jsonify({"error": "No valid fields to update"}), 400

    try:
        with get_conn() as conn:
            assignments = ", ".join(f"{k} = ?" for k in allowed)
            conn.execute(
                f"UPDATE company_profiles SET {assignments} WHERE client_id = ?",
                list(allowed.values()) + [client_id]
            )
    except Exception as e:
        logger.error(f"[COMPANY] update error: {e}")
        return jsonify({"error": str(e)}), 500

    updated = fetch_one(
        "SELECT * FROM company_profiles WHERE client_id = ?", (client_id,)
    )
    return jsonify({"company": dict(updated)}), 200


@company_bp.route("/api/companies/<client_id>", methods=["DELETE"])
@require_auth(roles=["owner"])
def delete_company(client_id: str):
    """Delete a company profile. Owner-only."""
    profile = fetch_one(
        "SELECT id FROM company_profiles WHERE client_id = ?", (client_id,)
    )
    if not profile:
        return jsonify({"error": "Company not found"}), 404

    try:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM company_profiles WHERE client_id = ?", (client_id,)
            )
    except Exception as e:
        logger.error(f"[COMPANY] delete error: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True}), 200
