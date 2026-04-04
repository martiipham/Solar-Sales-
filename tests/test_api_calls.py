"""Integration tests for the Calls API (/api/calls/*).

These endpoints serve call log data for the dashboard and reports pages.

Covers: list calls (with pagination/filtering), call stats, single call detail.
"""

import json
import pytest


class TestListCalls:
    """GET /api/calls"""

    def test_list_calls_empty(self, client, auth_headers):
        resp = client.get("/api/calls", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["calls"] == []
        assert data["total"] == 0

    def test_list_calls_with_data(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        call = data["calls"][0]
        assert call["call_id"] == "call_test_001"
        assert call["status"] == "complete"
        assert call["duration_seconds"] == 180
        assert "duration_fmt" in call
        assert call["duration_fmt"] == "3:00"

    def test_list_calls_transcript_parsed(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls", headers=auth_headers)
        call = resp.get_json()["calls"][0]
        assert "transcript" in call
        assert isinstance(call["transcript"], list)
        assert len(call["transcript"]) == 2
        assert call["transcript"][0]["role"] == "agent"
        # transcript_text raw field should be removed
        assert "transcript_text" not in call

    def test_list_calls_pagination(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls?limit=1&offset=0", headers=auth_headers)
        data = resp.get_json()
        assert data["limit"] == 1
        assert data["offset"] == 0
        assert len(data["calls"]) <= 1

    def test_list_calls_filter_by_status(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls?status=complete", headers=auth_headers)
        data = resp.get_json()
        assert all(c["status"] == "complete" for c in data["calls"])

    def test_list_calls_filter_by_since(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls?since=2020-01-01", headers=auth_headers)
        assert resp.status_code == 200

    def test_list_calls_invalid_since(self, client, auth_headers):
        resp = client.get("/api/calls?since=not-a-date", headers=auth_headers)
        assert resp.status_code == 400


class TestCallStats:
    """GET /api/calls/stats"""

    def test_call_stats_empty(self, client, auth_headers):
        resp = client.get("/api/calls/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "today" in data
        assert "this_week" in data
        assert "this_month" in data

    def test_call_stats_structure(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls/stats", headers=auth_headers)
        data = resp.get_json()
        # Today
        assert "calls" in data["today"]
        # This week
        week = data["this_week"]
        for key in ["calls", "completed", "avg_duration", "avg_score", "booking_rate"]:
            assert key in week, f"Missing this_week.{key}"
        # This month
        month = data["this_month"]
        assert "calls" in month
        assert "completed" in month

    def test_call_stats_with_data(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls/stats", headers=auth_headers)
        data = resp.get_json()
        assert data["this_week"]["calls"] >= 1
        assert data["this_month"]["calls"] >= 1


class TestGetCall:
    """GET /api/calls/<call_id>"""

    def test_get_call_success(self, client, auth_headers, seed_call):
        resp = client.get("/api/calls/call_test_001", headers=auth_headers)
        assert resp.status_code == 200
        call = resp.get_json()["call"]
        assert call["call_id"] == "call_test_001"
        assert call["from_phone"] == "+61400000001"
        assert isinstance(call["transcript"], list)

    def test_get_call_not_found(self, client, auth_headers):
        resp = client.get("/api/calls/nonexistent_call", headers=auth_headers)
        assert resp.status_code == 404
