"""Knowledge Base API — client-facing CRUD for company KB.

Allows solar company clients (and admins) to update the information their
AI voice agent uses: company profile, products, FAQs, and objection handlers.

Endpoints:
  GET  /api/kb/profile                 — fetch company profile
  PUT  /api/kb/profile                 — update company profile
  GET  /api/kb/products                — list products
  POST /api/kb/products                — add product
  PUT  /api/kb/products/<id>           — update product
  DELETE /api/kb/products/<id>         — delete product
  GET  /api/kb/faqs                    — list FAQs
  POST /api/kb/faqs                    — add FAQ
  PUT  /api/kb/faqs/<id>               — update FAQ
  DELETE /api/kb/faqs/<id>             — delete FAQ
  GET  /api/kb/objections              — list objection handlers
  POST /api/kb/objections              — add objection handler
  PUT  /api/kb/objections/<id>         — update objection
  DELETE /api/kb/objections/<id>       — delete objection
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, g

from memory.database import fetch_all, fetch_one, get_conn
from api.auth import require_auth

logger = logging.getLogger(__name__)

kb_bp = Blueprint("kb", __name__)


def _client_id_for_user(user: dict) -> str:
    """Resolve client_id: owners/admins can pass ?client_id=, clients use their own."""
    if user.get("role") in ("owner", "admin"):
        return request.args.get("client_id") or user.get("client_id") or "default"
    return user.get("client_id") or "default"


# ─────────────────────────────────────────────────────────────────────────────
# COMPANY PROFILE
# ─────────────────────────────────────────────────────────────────────────────

@kb_bp.route("/api/kb/profile", methods=["GET"])
@require_auth()
def get_profile():
    """Fetch the company profile for the current client."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        row = fetch_one("SELECT * FROM company_profiles WHERE client_id = ?", (client_id,))
        return jsonify({"profile": dict(row) if row else {}, "client_id": client_id}), 200
    except Exception as e:
        logger.error(f"[KB API] get_profile error: {e}")
        return jsonify({"error": str(e)}), 500


@kb_bp.route("/api/kb/profile", methods=["PUT"])
@require_auth()
def update_profile():
    """Update the company profile."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        data = request.get_json(force=True) or {}

        # Allowed fields — prevent overwriting client_id or internal fields
        allowed = [
            "company_name", "abn", "phone", "email", "website",
            "service_areas", "years_in_business", "num_installers",
            "certifications", "retell_agent_id", "elevenlabs_voice_id",
            "ghl_location_id",
        ]
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return jsonify({"error": "No valid fields to update"}), 400

        fields["updated_at"] = datetime.utcnow().isoformat()

        existing = fetch_one(
            "SELECT id FROM company_profiles WHERE client_id = ?", (client_id,)
        )
        with get_conn() as conn:
            if existing:
                assigns = ", ".join(f"{k} = ?" for k in fields)
                conn.execute(
                    f"UPDATE company_profiles SET {assigns} WHERE client_id = ?",
                    list(fields.values()) + [client_id],
                )
            else:
                fields["client_id"] = client_id
                cols = ", ".join(fields.keys())
                placeholders = ", ".join("?" for _ in fields)
                conn.execute(
                    f"INSERT INTO company_profiles ({cols}) VALUES ({placeholders})",
                    list(fields.values()),
                )

        return jsonify({"ok": True, "client_id": client_id}), 200

    except Exception as e:
        logger.error(f"[KB API] update_profile error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────────────────────────────────────

@kb_bp.route("/api/kb/products", methods=["GET"])
@require_auth()
def list_products():
    """List all products for the current client."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        rows = fetch_all(
            "SELECT * FROM company_products WHERE client_id = ? ORDER BY id",
            (client_id,)
        )
        return jsonify({"products": [dict(r) for r in rows]}), 200
    except Exception as e:
        logger.error(f"[KB API] list_products error: {e}")
        return jsonify({"error": str(e), "products": []}), 500


@kb_bp.route("/api/kb/products", methods=["POST"])
@require_auth()
def add_product():
    """Add a new product to the KB."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        data = request.get_json(force=True) or {}
        allowed = ["product_type", "name", "description",
                   "price_from_aud", "price_to_aud", "features", "brands", "active"]
        fields = {k: v for k, v in data.items() if k in allowed}
        fields["client_id"] = client_id

        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        with get_conn() as conn:
            cur = conn.execute(
                f"INSERT INTO company_products ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            new_id = cur.lastrowid

        return jsonify({"ok": True, "id": new_id}), 201

    except Exception as e:
        logger.error(f"[KB API] add_product error: {e}")
        return jsonify({"error": str(e)}), 500


@kb_bp.route("/api/kb/products/<int:product_id>", methods=["PUT"])
@require_auth()
def update_product(product_id: int):
    """Update a product by ID."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        data = request.get_json(force=True) or {}
        allowed = ["product_type", "name", "description",
                   "price_from_aud", "price_to_aud", "features", "brands", "active"]
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return jsonify({"error": "No valid fields"}), 400

        assigns = ", ".join(f"{k} = ?" for k in fields)
        with get_conn() as conn:
            conn.execute(
                f"UPDATE company_products SET {assigns} WHERE id = ? AND client_id = ?",
                list(fields.values()) + [product_id, client_id],
            )
        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.error(f"[KB API] update_product error: {e}")
        return jsonify({"error": str(e)}), 500


@kb_bp.route("/api/kb/products/<int:product_id>", methods=["DELETE"])
@require_auth()
def delete_product(product_id: int):
    """Soft-delete a product (sets active=0)."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE company_products SET active = 0 WHERE id = ? AND client_id = ?",
                (product_id, client_id),
            )
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"[KB API] delete_product error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# FAQs
# ─────────────────────────────────────────────────────────────────────────────

@kb_bp.route("/api/kb/faqs", methods=["GET"])
@require_auth()
def list_faqs():
    """List all FAQs for the current client."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        rows = fetch_all(
            "SELECT * FROM company_faqs WHERE client_id = ? ORDER BY priority, id",
            (client_id,)
        )
        return jsonify({"faqs": [dict(r) for r in rows]}), 200
    except Exception as e:
        logger.error(f"[KB API] list_faqs error: {e}")
        return jsonify({"error": str(e), "faqs": []}), 500


@kb_bp.route("/api/kb/faqs", methods=["POST"])
@require_auth()
def add_faq():
    """Add a new FAQ entry."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        data = request.get_json(force=True) or {}
        question = (data.get("question") or "").strip()[:500]
        answer   = (data.get("answer") or "").strip()[:2000]
        category = (data.get("category") or "general")[:50]
        priority = int(data.get("priority", 5))

        if not question or not answer:
            return jsonify({"error": "question and answer are required"}), 400

        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO company_faqs (client_id, question, answer, category, priority) "
                "VALUES (?, ?, ?, ?, ?)",
                (client_id, question, answer, category, priority),
            )
            new_id = cur.lastrowid

        return jsonify({"ok": True, "id": new_id}), 201

    except Exception as e:
        logger.error(f"[KB API] add_faq error: {e}")
        return jsonify({"error": str(e)}), 500


@kb_bp.route("/api/kb/faqs/<int:faq_id>", methods=["PUT"])
@require_auth()
def update_faq(faq_id: int):
    """Update a FAQ by ID."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        data = request.get_json(force=True) or {}
        fields = {}
        if "question" in data:
            fields["question"] = str(data["question"])[:500]
        if "answer" in data:
            fields["answer"] = str(data["answer"])[:2000]
        if "category" in data:
            fields["category"] = str(data["category"])[:50]
        if "priority" in data:
            fields["priority"] = int(data["priority"])

        if not fields:
            return jsonify({"error": "No valid fields"}), 400

        assigns = ", ".join(f"{k} = ?" for k in fields)
        with get_conn() as conn:
            conn.execute(
                f"UPDATE company_faqs SET {assigns} WHERE id = ? AND client_id = ?",
                list(fields.values()) + [faq_id, client_id],
            )
        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.error(f"[KB API] update_faq error: {e}")
        return jsonify({"error": str(e)}), 500


@kb_bp.route("/api/kb/faqs/<int:faq_id>", methods=["DELETE"])
@require_auth()
def delete_faq(faq_id: int):
    """Delete a FAQ by ID."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM company_faqs WHERE id = ? AND client_id = ?",
                (faq_id, client_id),
            )
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"[KB API] delete_faq error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# OBJECTION HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

@kb_bp.route("/api/kb/objections", methods=["GET"])
@require_auth()
def list_objections():
    """List all objection handlers for the current client."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        rows = fetch_all(
            "SELECT * FROM company_objections WHERE client_id = ? ORDER BY priority, id",
            (client_id,)
        )
        return jsonify({"objections": [dict(r) for r in rows]}), 200
    except Exception as e:
        logger.error(f"[KB API] list_objections error: {e}")
        return jsonify({"error": str(e), "objections": []}), 500


@kb_bp.route("/api/kb/objections", methods=["POST"])
@require_auth()
def add_objection():
    """Add a new objection handler."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        data = request.get_json(force=True) or {}
        objection = (data.get("objection") or "").strip()[:500]
        response  = (data.get("response") or "").strip()[:2000]
        priority  = int(data.get("priority", 5))

        if not objection or not response:
            return jsonify({"error": "objection and response are required"}), 400

        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO company_objections (client_id, objection, response, priority) "
                "VALUES (?, ?, ?, ?)",
                (client_id, objection, response, priority),
            )
            new_id = cur.lastrowid

        return jsonify({"ok": True, "id": new_id}), 201

    except Exception as e:
        logger.error(f"[KB API] add_objection error: {e}")
        return jsonify({"error": str(e)}), 500


@kb_bp.route("/api/kb/objections/<int:obj_id>", methods=["PUT"])
@require_auth()
def update_objection(obj_id: int):
    """Update an objection handler by ID."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        data = request.get_json(force=True) or {}
        fields = {}
        if "objection" in data:
            fields["objection"] = str(data["objection"])[:500]
        if "response" in data:
            fields["response"] = str(data["response"])[:2000]
        if "priority" in data:
            fields["priority"] = int(data["priority"])

        if not fields:
            return jsonify({"error": "No valid fields"}), 400

        assigns = ", ".join(f"{k} = ?" for k in fields)
        with get_conn() as conn:
            conn.execute(
                f"UPDATE company_objections SET {assigns} WHERE id = ? AND client_id = ?",
                list(fields.values()) + [obj_id, client_id],
            )
        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.error(f"[KB API] update_objection error: {e}")
        return jsonify({"error": str(e)}), 500


@kb_bp.route("/api/kb/objections/<int:obj_id>", methods=["DELETE"])
@require_auth()
def delete_objection(obj_id: int):
    """Delete an objection handler by ID."""
    user = g.user
    client_id = _client_id_for_user(user)
    try:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM company_objections WHERE id = ? AND client_id = ?",
                (obj_id, client_id),
            )
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"[KB API] delete_objection error: {e}")
        return jsonify({"error": str(e)}), 500
