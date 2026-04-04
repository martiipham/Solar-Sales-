"""Shared test fixtures for SolarAdmin AI integration tests.

Provides:
  - In-memory SQLite database (isolated per test)
  - Flask test client for the Dashboard API
  - Auth helpers (login, get token, make auth headers)
  - Seed data factories for leads, calls, emails, etc.
"""

import json
import os
import sys
import tempfile

import pytest

# Ensure the solaradmin package is importable
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_ROOT)

# Override config BEFORE importing any app modules
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-do-not-use-in-prod"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key"
os.environ["GATE_API_KEY"] = "test-gate-key"
os.environ["REDIS_URL"] = ""  # Use in-memory storage for rate limiter


@pytest.fixture(autouse=True)
def _patch_db(tmp_path, monkeypatch):
    """Use a fresh temp SQLite file for every test (avoids :memory: sharing issues)."""
    db_path = str(tmp_path / "test_solaradmin.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)

    import importlib
    import config as cfg
    importlib.reload(cfg)
    cfg.DATABASE_PATH = db_path

    from memory.database import init_db
    init_db()

    yield db_path


@pytest.fixture()
def app(_patch_db):
    """Create a fresh Flask test app with all blueprints registered."""
    import importlib
    import config as cfg
    importlib.reload(cfg)

    from api.dashboard_api import dashboard_app

    dashboard_app.config["TESTING"] = True
    dashboard_app.config["SERVER_NAME"] = "localhost"

    yield dashboard_app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def seed_owner(_patch_db):
    """Seed the default owner account and return credentials."""
    import bcrypt
    from memory.database import insert

    pw_hash = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode()
    user_id = insert("users", {
        "email": "owner@test.solar",
        "password_hash": pw_hash,
        "name": "Test Owner",
        "role": "owner",
        "active": 1,
    })
    return {
        "id": user_id,
        "email": "owner@test.solar",
        "password": "testpass123",
        "role": "owner",
    }


@pytest.fixture()
def auth_token(client, seed_owner):
    """Get a valid JWT token for the seeded owner."""
    resp = client.post("/api/auth/login", json={
        "email": seed_owner["email"],
        "password": seed_owner["password"],
    })
    data = resp.get_json()
    return data["token"]


@pytest.fixture()
def auth_headers(auth_token):
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ── Seed data factories ─────────────────────────────────────────────────────

@pytest.fixture()
def seed_lead(_patch_db):
    """Insert a test lead and return its ID."""
    from memory.database import insert
    lead_id = insert("leads", {
        "name": "Jane Solar",
        "phone": "+61400000001",
        "email": "jane@example.com",
        "suburb": "Perth",
        "state": "WA",
        "qualification_score": 8.5,
        "score_reason": "Homeowner, high bill, good roof",
        "recommended_action": "book_assessment",
        "status": "new",
        "source": "manual",
    })
    return lead_id


@pytest.fixture()
def seed_call(_patch_db):
    """Insert a test call log and return its call_id."""
    from memory.database import insert
    insert("call_logs", {
        "call_id": "call_test_001",
        "client_id": "default",
        "from_phone": "+61400000001",
        "to_phone": "+61800000001",
        "agent_id": "retell_test",
        "status": "complete",
        "duration_seconds": 180,
        "lead_score": 7.5,
        "transcript_text": json.dumps([
            {"role": "agent", "content": "Hello, Solar Solutions."},
            {"role": "user", "content": "Hi, I need a quote for solar panels."},
        ]),
    })
    return "call_test_001"


@pytest.fixture()
def seed_email(_patch_db):
    """Insert a test email record and return its ID."""
    from memory.database import insert
    email_id = insert("emails", {
        "from_email": "customer@example.com",
        "from_name": "John Customer",
        "subject": "Solar panel inquiry",
        "body": "Hi, I'd like to know about your solar panel options.",
        "classification": "inquiry",
        "urgency_score": 7,
        "draft_reply": "Thank you for your interest! We offer a range of solar solutions.",
        "status": "pending",
    })
    return email_id


@pytest.fixture()
def seed_company_profile(_patch_db):
    """Insert a test company profile."""
    from memory.database import insert
    profile_id = insert("company_profiles", {
        "client_id": "default",
        "name": "Test Solar Co",
        "company_name": "Test Solar Co",
        "phone": "+61800123456",
        "email": "info@testsolar.com.au",
        "service_areas": "Perth metro, Mandurah",
        "years_in_business": 10,
        "num_installers": 5,
        "certifications": "CEC Accredited",
    })
    return profile_id


@pytest.fixture()
def seed_product(_patch_db):
    """Insert a test product in the KB."""
    from memory.database import insert
    product_id = insert("company_products", {
        "client_id": "default",
        "product_type": "solar_panel",
        "name": "6.6kW Solar System",
        "description": "Standard residential solar system",
        "price_from_aud": 4500,
        "price_to_aud": 6500,
        "features": "Tier 1 panels, 10yr warranty",
        "brands": "Jinko, Enphase",
        "active": 1,
    })
    return product_id


@pytest.fixture()
def seed_faq(_patch_db):
    """Insert a test FAQ entry."""
    from memory.database import insert
    faq_id = insert("company_faqs", {
        "client_id": "default",
        "question": "How long does installation take?",
        "answer": "Typically 1-2 days for a standard residential system.",
        "category": "installation",
        "priority": 1,
    })
    return faq_id
