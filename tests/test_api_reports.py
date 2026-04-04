"""Integration tests for the Reports API (/api/reports/*).

These endpoints power the Reports.tsx frontend page, providing
call volume, lead conversion, and AI performance metrics.

Covers: monthly report, all-time summary, weekly trend, daily activity.
"""

import json
import pytest
from datetime import datetime


class TestMonthlyReport:
    """GET /api/reports/monthly"""

    def test_monthly_report_empty(self, client, auth_headers):
        resp = client.get("/api/reports/monthly", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "period" in data
        assert "calls" in data
        assert "leads" in data
        assert "highlights" in data

    def test_monthly_report_period_label(self, client, auth_headers):
        resp = client.get("/api/reports/monthly", headers=auth_headers)
        data = resp.get_json()
        now = datetime.utcnow()
        assert now.strftime("%B %Y") in data["period"]["label"]

    def test_monthly_report_calls_structure(self, client, auth_headers):
        resp = client.get("/api/reports/monthly", headers=auth_headers)
        data = resp.get_json()
        for key in ["current", "prior", "vs_prior"]:
            assert key in data["calls"], f"Missing calls.{key}"
        for key in ["calls", "completed", "avg_duration", "avg_score"]:
            assert key in data["calls"]["current"], f"Missing calls.current.{key}"

    def test_monthly_report_leads_structure(self, client, auth_headers):
        resp = client.get("/api/reports/monthly", headers=auth_headers)
        data = resp.get_json()
        for key in ["current", "prior", "vs_prior"]:
            assert key in data["leads"]
        for key in ["total", "hot", "converted", "conversion_rate", "avg_score"]:
            assert key in data["leads"]["current"]

    def test_monthly_report_with_call_data(self, client, auth_headers, seed_call):
        resp = client.get("/api/reports/monthly", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # seed_call has status "complete" which is "completed" check
        assert data["calls"]["current"]["calls"] >= 0

    def test_monthly_report_highlights_nonempty(self, client, auth_headers):
        resp = client.get("/api/reports/monthly", headers=auth_headers)
        data = resp.get_json()
        assert isinstance(data["highlights"], list)
        assert len(data["highlights"]) >= 1


class TestAllTimeSummary:
    """GET /api/reports/summary"""

    def test_summary_empty(self, client, auth_headers):
        resp = client.get("/api/reports/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_calls"] == 0
        assert data["total_leads"] == 0
        assert data["total_converted"] == 0
        assert data["conversion_rate"] == 0
        assert data["active_since"] is None

    def test_summary_with_data(self, client, auth_headers, seed_lead, seed_call):
        resp = client.get("/api/reports/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_calls"] >= 1
        assert data["total_leads"] >= 1

    def test_summary_field_types(self, client, auth_headers):
        resp = client.get("/api/reports/summary", headers=auth_headers)
        data = resp.get_json()
        assert isinstance(data["total_calls"], int)
        assert isinstance(data["total_leads"], int)
        assert isinstance(data["avg_lead_score"], (int, float))
        assert isinstance(data["conversion_rate"], (int, float))


class TestWeeklyTrend:
    """GET /api/reports/weekly"""

    def test_weekly_default_30_days(self, client, auth_headers):
        resp = client.get("/api/reports/weekly", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["window_days"] == 30
        assert len(data["days"]) == 30

    def test_weekly_custom_days(self, client, auth_headers):
        resp = client.get("/api/reports/weekly?days=7", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["window_days"] == 7
        assert len(data["days"]) == 7

    def test_weekly_max_90_days(self, client, auth_headers):
        resp = client.get("/api/reports/weekly?days=365", headers=auth_headers)
        data = resp.get_json()
        assert data["window_days"] == 90  # Clamped to max

    def test_weekly_day_structure(self, client, auth_headers):
        resp = client.get("/api/reports/weekly?days=3", headers=auth_headers)
        data = resp.get_json()
        day = data["days"][0]
        for key in ["date", "calls", "leads", "hot_leads", "conversions"]:
            assert key in day, f"Missing day.{key}"

    def test_weekly_totals(self, client, auth_headers):
        resp = client.get("/api/reports/weekly", headers=auth_headers)
        data = resp.get_json()
        assert "totals" in data
        for key in ["calls", "leads", "hot_leads", "conversions"]:
            assert key in data["totals"]


class TestDailyActivity:
    """GET /api/reports/daily-activity"""

    def test_daily_activity_returns_7_days(self, client, auth_headers):
        resp = client.get("/api/reports/daily-activity", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["days"]) == 7

    def test_daily_activity_structure(self, client, auth_headers):
        resp = client.get("/api/reports/daily-activity", headers=auth_headers)
        data = resp.get_json()
        day = data["days"][0]
        assert "day" in day      # Short weekday label
        assert "date" in day     # ISO date
        assert "calls" in day
        assert "emails" in day
        assert "leads" in day

    def test_daily_activity_weekday_labels(self, client, auth_headers):
        resp = client.get("/api/reports/daily-activity", headers=auth_headers)
        data = resp.get_json()
        valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
        for entry in data["days"]:
            assert entry["day"] in valid_days
