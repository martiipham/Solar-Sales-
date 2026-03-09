"""SQLite database setup and helpers for Solar Swarm.

Provides the single source of truth for all hot memory:
experiments, task queue, pheromone signals, leads,
circuit breaker log, and the append-only cold ledger.
"""

import sqlite3
import json
import logging
from datetime import datetime
from contextlib import contextmanager
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


@contextmanager
def get_conn():
    """Context manager for database connections."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    print("[DB] Initialising database...")
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                idea_text TEXT NOT NULL,
                vertical TEXT,
                bucket TEXT CHECK(bucket IN ('exploit','explore','moonshot')),
                confidence_score REAL,
                devil_score REAL,
                kelly_fraction REAL,
                budget_allocated REAL DEFAULT 0,
                status TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','running','complete','killed','rejected')),
                revenue_generated REAL DEFAULT 0,
                roi REAL,
                learnings TEXT,
                failure_mode TEXT,
                approved_by TEXT,
                approved_at TEXT,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                job_type TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                context_payload TEXT,
                assigned_to TEXT,
                status TEXT DEFAULT 'queued'
                    CHECK(status IN ('queued','running','complete','failed')),
                output TEXT,
                completed_at TEXT,
                tier INTEGER DEFAULT 3
            );

            CREATE TABLE IF NOT EXISTS pheromone_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                signal_type TEXT CHECK(signal_type IN ('POSITIVE','NEGATIVE','NEUTRAL')),
                topic TEXT,
                vertical TEXT,
                strength REAL DEFAULT 0.5,
                channel TEXT,
                experiment_id INTEGER,
                decay_factor REAL DEFAULT 1.0
            );

            CREATE TABLE IF NOT EXISTS cold_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                event_type TEXT NOT NULL,
                event_data TEXT,
                experiment_id INTEGER,
                agent_id TEXT,
                human_involved INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                source TEXT DEFAULT 'manual'
                    CHECK(source IN ('ghl_webhook','manual','form')),
                name TEXT,
                phone TEXT,
                email TEXT,
                suburb TEXT,
                state TEXT,
                homeowner_status TEXT,
                monthly_bill REAL,
                roof_type TEXT,
                roof_age INTEGER,
                qualification_score REAL,
                score_reason TEXT,
                recommended_action TEXT,
                pipeline_stage TEXT,
                status TEXT DEFAULT 'new',
                contacted_at TEXT,
                converted_at TEXT,
                client_account TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS circuit_breaker_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                triggered_at TEXT DEFAULT (datetime('now')),
                level TEXT CHECK(level IN ('yellow','orange','red')),
                reason TEXT,
                consecutive_failures INTEGER DEFAULT 0,
                budget_burn_rate REAL DEFAULT 1.0,
                resolved_at TEXT,
                resolved_by TEXT
            );

            -- Message bus: inter-agent communication
            CREATE TABLE IF NOT EXISTS message_bus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                msg_id TEXT UNIQUE NOT NULL,
                from_agent TEXT NOT NULL,
                to_queue TEXT NOT NULL,
                msg_type TEXT NOT NULL
                    CHECK(msg_type IN ('TASK','REPORT','ALERT','ACK','KILL','QUERY','RESPONSE')),
                priority TEXT DEFAULT 'NORMAL'
                    CHECK(priority IN ('CRITICAL','HIGH','NORMAL','LOW')),
                payload TEXT,
                reply_to TEXT,
                ttl_cycles INTEGER DEFAULT 3,
                requires_ack INTEGER DEFAULT 0,
                status TEXT DEFAULT 'queued'
                    CHECK(status IN ('queued','processing','complete','failed','expired')),
                acked_at TEXT,
                completed_at TEXT
            );

            -- Research findings from research engine
            CREATE TABLE IF NOT EXISTS research_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                research_id TEXT UNIQUE NOT NULL,
                research_type TEXT NOT NULL,
                query TEXT NOT NULL,
                requested_by TEXT,
                status TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','in_progress','complete','failed')),
                findings TEXT,
                confidence REAL DEFAULT 0.0,
                sources_count INTEGER DEFAULT 0,
                opportunities_found INTEGER DEFAULT 0,
                expires_at TEXT,
                completed_at TEXT
            );

            -- Knowledge graph: entities
            CREATE TABLE IF NOT EXISTS kg_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                entity_id TEXT UNIQUE NOT NULL,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT,
                confidence REAL DEFAULT 0.5,
                source TEXT,
                source_research_id TEXT,
                mention_count INTEGER DEFAULT 1,
                first_seen TEXT,
                last_seen TEXT,
                last_verified_at TEXT
            );

            -- Knowledge graph: relationships
            CREATE TABLE IF NOT EXISTS kg_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                rel_id TEXT UNIQUE,
                from_entity TEXT NOT NULL,
                to_entity TEXT NOT NULL,
                rel_type TEXT NOT NULL,
                properties TEXT,
                confidence REAL DEFAULT 0.5,
                source_research_id TEXT
            );

            -- Data collection: source registry
            CREATE TABLE IF NOT EXISTS collection_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                url_template TEXT,
                config TEXT,
                collection_frequency TEXT DEFAULT 'daily',
                frequency_hours INTEGER DEFAULT 24,
                priority TEXT DEFAULT 'NORMAL',
                active INTEGER DEFAULT 1,
                last_collected TEXT,
                health_status TEXT DEFAULT 'healthy'
                    CHECK(health_status IN ('healthy','degraded','dead')),
                error_count INTEGER DEFAULT 0,
                strategy_dependency TEXT
            );

            -- Data collection: collected records
            CREATE TABLE IF NOT EXISTS collected_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at TEXT DEFAULT (datetime('now')),
                source_id TEXT NOT NULL,
                source_type TEXT,
                record_type TEXT NOT NULL,
                record_key TEXT,
                raw_data TEXT,
                normalized_data TEXT,
                quality_score REAL DEFAULT 0.0,
                dedup_hash TEXT,
                processed INTEGER DEFAULT 0,
                normalized INTEGER DEFAULT 0
            );

            -- Time series: metrics and signals
            CREATE TABLE IF NOT EXISTS time_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT DEFAULT (datetime('now')),
                series_name TEXT NOT NULL,
                entity_id TEXT,
                value REAL NOT NULL,
                unit TEXT,
                tags TEXT
            );

            -- Opportunities discovered by scout/research
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                opportunity_id TEXT UNIQUE NOT NULL,
                opp_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                estimated_monthly_revenue_aud REAL DEFAULT 0,
                effort_score REAL DEFAULT 5.0,
                speed_score REAL DEFAULT 5.0,
                risk_score REAL DEFAULT 5.0,
                overall_score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'new'
                    CHECK(status IN ('new','researching','queued','active','passed','killed')),
                source_agent TEXT,
                research_id TEXT,
                experiment_id INTEGER,
                evidence TEXT
            );

            -- Voice AI call logs
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT DEFAULT (datetime('now')),
                ended_at TEXT,
                call_id TEXT UNIQUE NOT NULL,
                client_id TEXT,
                from_phone TEXT,
                to_phone TEXT,
                agent_id TEXT,
                status TEXT DEFAULT 'started'
                    CHECK(status IN ('started','active','complete','failed')),
                duration_seconds INTEGER DEFAULT 0,
                recording_url TEXT,
                outcome TEXT,
                lead_score REAL,
                summary TEXT,
                transcript_turns INTEGER DEFAULT 0
            );

            -- Email processing logs
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT DEFAULT (datetime('now')),
                from_address TEXT,
                subject TEXT,
                client_id TEXT,
                lead_id INTEGER,
                intent TEXT,
                score REAL,
                action TEXT,
                summary TEXT,
                draft_reply_queued INTEGER DEFAULT 0
            );

            -- CRM data cache (written by api/crm_sync.py every 30 minutes)
            CREATE TABLE IF NOT EXISTS crm_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cached_at TEXT DEFAULT (datetime('now')),
                cache_key TEXT UNIQUE NOT NULL,
                cache_value TEXT NOT NULL
            );

            -- A/B test tracking
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                test_id TEXT UNIQUE NOT NULL,
                name TEXT,
                parent_experiment_id INTEGER,
                experiment_id INTEGER,
                hypothesis TEXT NOT NULL,
                variant_a TEXT,
                variant_b TEXT,
                metric TEXT DEFAULT 'conversion_rate',
                variable_changed TEXT,
                status TEXT DEFAULT 'running'
                    CHECK(status IN ('running','complete','inconclusive')),
                a_impressions INTEGER DEFAULT 0,
                b_impressions INTEGER DEFAULT 0,
                a_conversions INTEGER DEFAULT 0,
                b_conversions INTEGER DEFAULT 0,
                a_clicks INTEGER DEFAULT 0,
                b_clicks INTEGER DEFAULT 0,
                variant_a_roi REAL,
                variant_b_roi REAL,
                winner TEXT,
                winner_stats TEXT,
                cycles_run INTEGER DEFAULT 0,
                min_cycles INTEGER DEFAULT 3,
                completed_at TEXT,
                conclusion TEXT
            );

            -- API Usage & Cost Tracking
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT DEFAULT (datetime('now')),
                service TEXT NOT NULL,
                operation TEXT NOT NULL,
                model TEXT,
                units REAL DEFAULT 0,
                unit_type TEXT,
                cost_usd REAL DEFAULT 0,
                call_id TEXT,
                client_id TEXT,
                metadata TEXT
            );

            -- Users (multi-user auth)
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'admin'
                    CHECK(role IN ('owner','admin','client')),
                client_id TEXT,
                active INTEGER DEFAULT 1,
                last_login TEXT
            );

            -- Auth tokens (JWT revocation list)
            CREATE TABLE IF NOT EXISTS auth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                token_hash TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER DEFAULT 0
            );

            -- Company profiles (one per solar SME client)
            CREATE TABLE IF NOT EXISTS company_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                client_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                abn TEXT,
                address TEXT,
                logo_url TEXT,
                primary_color TEXT DEFAULT '#F59E0B',
                contact_email TEXT,
                contact_phone TEXT,
                website TEXT,
                notes TEXT
            );

            -- API keys (for client embeds / webhook auth)
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                key_id TEXT UNIQUE NOT NULL,
                key_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                created_by INTEGER,
                client_id TEXT,
                permissions TEXT DEFAULT '["read"]',
                active INTEGER DEFAULT 1,
                last_used TEXT,
                expires_at TEXT
            );

            -- App settings (overrides .env at runtime)
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                updated_at TEXT DEFAULT (datetime('now')),
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                description TEXT
            );
        """)
    _apply_migrations()
    print("[DB] Database ready.")


def _apply_migrations():
    """Add any columns that exist in code but were missing from the original schema.

    Safe to run on every startup — ALTER TABLE ADD COLUMN is a no-op if the
    column already exists (caught and ignored).
    """
    migrations = [
        # ab_tests — columns the code writes to
        ("ab_tests", "name TEXT"),
        ("ab_tests", "experiment_id INTEGER"),
        ("ab_tests", "variant_a TEXT"),
        ("ab_tests", "variant_b TEXT"),
        ("ab_tests", "metric TEXT DEFAULT 'conversion_rate'"),
        ("ab_tests", "a_impressions INTEGER DEFAULT 0"),
        ("ab_tests", "b_impressions INTEGER DEFAULT 0"),
        ("ab_tests", "a_conversions INTEGER DEFAULT 0"),
        ("ab_tests", "b_conversions INTEGER DEFAULT 0"),
        ("ab_tests", "a_clicks INTEGER DEFAULT 0"),
        ("ab_tests", "b_clicks INTEGER DEFAULT 0"),
        ("ab_tests", "winner_stats TEXT"),
        # kg_entities — columns knowledge_graph.py expects
        ("kg_entities", "properties TEXT"),
        ("kg_entities", "source TEXT"),
        ("kg_entities", "mention_count INTEGER DEFAULT 1"),
        ("kg_entities", "first_seen TEXT"),
        ("kg_entities", "last_seen TEXT"),
        # kg_relationships — columns knowledge_graph.py expects
        ("kg_relationships", "rel_id TEXT"),
        ("kg_relationships", "from_entity TEXT"),
        ("kg_relationships", "to_entity TEXT"),
        ("kg_relationships", "rel_type TEXT"),
        ("kg_relationships", "properties TEXT"),
        # collection_sources — columns orchestrator.py expects
        ("collection_sources", "config TEXT"),
        ("collection_sources", "frequency_hours INTEGER DEFAULT 24"),
        ("collection_sources", "priority TEXT DEFAULT 'NORMAL'"),
        ("collection_sources", "active INTEGER DEFAULT 1"),
        ("collection_sources", "last_collected TEXT"),
        # collected_data — columns orchestrator.py queries
        ("collected_data", "source_type TEXT"),
        ("collected_data", "normalized INTEGER DEFAULT 0"),
        # experiments — paid spend flag for explore protocol
        ("experiments", "paid_spend_activated INTEGER DEFAULT 0"),
        ("experiments", "explore_phase TEXT"),
    ]
    with get_conn() as conn:
        for table, col_def in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            except Exception:
                pass  # column already exists — safe to ignore


def row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return {}
    return dict(row)


def insert(table: str, data: dict) -> int:
    """Insert a row into a table and return the new row id."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    values = list(data.values())
    with get_conn() as conn:
        cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", values)
        return cur.lastrowid or 0


def update(table: str, row_id: int, data: dict) -> None:
    """Update a row in a table by id."""
    assignments = ", ".join(f"{k} = ?" for k in data.keys())
    values = list(data.values()) + [row_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", values)


def fetch_one(query: str, params=()) -> dict:
    """Execute a SELECT and return the first row as a dict."""
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        return row_to_dict(row)
    return {}


def fetch_all(query: str, params=()) -> list:
    """Execute a SELECT and return all rows as a list of dicts."""
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [row_to_dict(r) for r in rows]
    return []


def json_payload(data: dict) -> str:
    """Serialise a dict to JSON string for storage."""
    return json.dumps(data)


def parse_payload(text: str) -> dict:
    """Deserialise a JSON string from storage."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


if __name__ == "__main__":
    init_db()
