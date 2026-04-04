"""Integration tests for the Knowledge Base API (/api/kb/*).

These endpoints power the Knowledge Base editor frontend page (planned)
and provide CRUD for company profiles, products, FAQs, and objections.

Covers: profile CRUD, products CRUD, FAQs CRUD, objections CRUD.
"""

import pytest


class TestKBProfile:
    """GET/PUT /api/kb/profile"""

    def test_get_profile_empty(self, client, auth_headers):
        resp = client.get("/api/kb/profile", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["profile"] == {}

    def test_get_profile_with_data(self, client, auth_headers, seed_company_profile):
        resp = client.get("/api/kb/profile", headers=auth_headers)
        assert resp.status_code == 200
        profile = resp.get_json()["profile"]
        assert profile["company_name"] == "Test Solar Co"
        assert profile["phone"] == "+61800123456"

    def test_update_profile(self, client, auth_headers, seed_company_profile):
        resp = client.put("/api/kb/profile", headers=auth_headers, json={
            "company_name": "Updated Solar Co",
            "website": "https://updated.solar",
        })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        # Verify update
        resp2 = client.get("/api/kb/profile", headers=auth_headers)
        profile = resp2.get_json()["profile"]
        assert profile["company_name"] == "Updated Solar Co"
        assert profile["website"] == "https://updated.solar"

    def test_update_profile_no_fields(self, client, auth_headers, seed_company_profile):
        resp = client.put("/api/kb/profile", headers=auth_headers, json={})
        assert resp.status_code == 400

    def test_update_profile_ignores_internal_fields(self, client, auth_headers, seed_company_profile):
        resp = client.put("/api/kb/profile", headers=auth_headers, json={
            "client_id": "hacked",
            "id": 999,
            "company_name": "Legit Update",
        })
        assert resp.status_code == 200
        # client_id should NOT have changed
        resp2 = client.get("/api/kb/profile", headers=auth_headers)
        assert resp2.get_json()["client_id"] != "hacked"

    def test_create_profile_via_update(self, client, auth_headers):
        """PUT should upsert if no profile exists yet."""
        resp = client.put("/api/kb/profile", headers=auth_headers, json={
            "company_name": "New Co",
        })
        assert resp.status_code == 200
        resp2 = client.get("/api/kb/profile", headers=auth_headers)
        assert resp2.get_json()["profile"]["company_name"] == "New Co"


class TestKBProducts:
    """GET/POST/PUT/DELETE /api/kb/products"""

    def test_list_products_empty(self, client, auth_headers):
        resp = client.get("/api/kb/products", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["products"] == []

    def test_add_product(self, client, auth_headers):
        resp = client.post("/api/kb/products", headers=auth_headers, json={
            "product_type": "battery",
            "name": "Tesla Powerwall 3",
            "description": "Home battery storage",
            "price_from_aud": 12000,
            "price_to_aud": 15000,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert "id" in data

    def test_list_products_with_data(self, client, auth_headers, seed_product):
        resp = client.get("/api/kb/products", headers=auth_headers)
        products = resp.get_json()["products"]
        assert len(products) >= 1
        assert products[0]["name"] == "6.6kW Solar System"

    def test_update_product(self, client, auth_headers, seed_product):
        resp = client.put(f"/api/kb/products/{seed_product}", headers=auth_headers, json={
            "name": "10kW Solar System",
            "price_from_aud": 8000,
        })
        assert resp.status_code == 200

    def test_update_product_no_fields(self, client, auth_headers, seed_product):
        resp = client.put(f"/api/kb/products/{seed_product}", headers=auth_headers, json={})
        assert resp.status_code == 400

    def test_delete_product_soft_delete(self, client, auth_headers, seed_product):
        resp = client.delete(f"/api/kb/products/{seed_product}", headers=auth_headers)
        assert resp.status_code == 200

        # Product still exists but active=0
        resp2 = client.get("/api/kb/products", headers=auth_headers)
        products = resp2.get_json()["products"]
        found = [p for p in products if p["id"] == seed_product]
        if found:
            assert found[0]["active"] == 0


class TestKBFAQs:
    """GET/POST/PUT/DELETE /api/kb/faqs"""

    def test_list_faqs_empty(self, client, auth_headers):
        resp = client.get("/api/kb/faqs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["faqs"] == []

    def test_add_faq(self, client, auth_headers):
        resp = client.post("/api/kb/faqs", headers=auth_headers, json={
            "question": "What warranty do you offer?",
            "answer": "25 year panel warranty, 10 year inverter warranty.",
            "category": "warranty",
            "priority": 2,
        })
        assert resp.status_code == 201
        assert resp.get_json()["ok"] is True

    def test_add_faq_missing_question(self, client, auth_headers):
        resp = client.post("/api/kb/faqs", headers=auth_headers, json={
            "answer": "Some answer",
        })
        assert resp.status_code == 400

    def test_add_faq_missing_answer(self, client, auth_headers):
        resp = client.post("/api/kb/faqs", headers=auth_headers, json={
            "question": "Some question?",
        })
        assert resp.status_code == 400

    def test_list_faqs_with_data(self, client, auth_headers, seed_faq):
        resp = client.get("/api/kb/faqs", headers=auth_headers)
        faqs = resp.get_json()["faqs"]
        assert len(faqs) >= 1
        assert faqs[0]["question"] == "How long does installation take?"

    def test_update_faq(self, client, auth_headers, seed_faq):
        resp = client.put(f"/api/kb/faqs/{seed_faq}", headers=auth_headers, json={
            "answer": "Usually 1 day for standard systems.",
        })
        assert resp.status_code == 200

    def test_delete_faq(self, client, auth_headers, seed_faq):
        resp = client.delete(f"/api/kb/faqs/{seed_faq}", headers=auth_headers)
        assert resp.status_code == 200

        # Should be gone
        resp2 = client.get("/api/kb/faqs", headers=auth_headers)
        faqs = resp2.get_json()["faqs"]
        assert all(f["id"] != seed_faq for f in faqs)


class TestKBObjections:
    """GET/POST/PUT/DELETE /api/kb/objections"""

    def test_list_objections_empty(self, client, auth_headers):
        resp = client.get("/api/kb/objections", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["objections"] == []

    def test_add_objection(self, client, auth_headers):
        resp = client.post("/api/kb/objections", headers=auth_headers, json={
            "objection": "Solar is too expensive",
            "response": "With STCs, a standard system costs $4,500-6,500 and pays for itself in 3-5 years.",
            "priority": 1,
        })
        assert resp.status_code == 201
        assert resp.get_json()["ok"] is True

    def test_add_objection_missing_fields(self, client, auth_headers):
        resp = client.post("/api/kb/objections", headers=auth_headers, json={
            "objection": "Too expensive",
        })
        assert resp.status_code == 400

    def test_update_objection(self, client, auth_headers, _patch_db):
        # Create then update
        from memory.database import insert
        obj_id = insert("company_objections", {
            "client_id": "default",
            "objection": "Test objection",
            "response": "Test response",
            "priority": 5,
        })
        resp = client.put(f"/api/kb/objections/{obj_id}", headers=auth_headers, json={
            "response": "Updated response with more detail.",
        })
        assert resp.status_code == 200

    def test_delete_objection(self, client, auth_headers, _patch_db):
        from memory.database import insert
        obj_id = insert("company_objections", {
            "client_id": "default",
            "objection": "To delete",
            "response": "Will be deleted",
        })
        resp = client.delete(f"/api/kb/objections/{obj_id}", headers=auth_headers)
        assert resp.status_code == 200
