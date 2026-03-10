"""SQLite database setup and helpers for Solar Admin AI.

Provides the single source of truth for all persistent storage:
leads, call logs, email logs, CRM cache, knowledge base,
users, auth tokens, API keys, settings, and agent run log.
"""

import sqlite3
import json
import logging
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
            -- Leads: inbound prospects from GHL webhooks, forms, or manual entry
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
                transcript_turns INTEGER DEFAULT 0,
                transcript_text TEXT
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
                notes TEXT,
                company_name TEXT,
                phone TEXT,
                email TEXT,
                service_areas TEXT,
                years_in_business INTEGER DEFAULT 0,
                num_installers INTEGER DEFAULT 0,
                certifications TEXT,
                retell_agent_id TEXT,
                elevenlabs_voice_id TEXT,
                ghl_location_id TEXT,
                active INTEGER DEFAULT 1
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

            -- Knowledge base: products/services offered by client
            CREATE TABLE IF NOT EXISTS company_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                client_id TEXT NOT NULL,
                product_type TEXT,
                name TEXT NOT NULL,
                description TEXT,
                price_from_aud REAL,
                price_to_aud REAL,
                features TEXT,
                brands TEXT,
                active INTEGER DEFAULT 1
            );

            -- Knowledge base: FAQs for the AI voice agent
            CREATE TABLE IF NOT EXISTS company_faqs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                client_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                priority INTEGER DEFAULT 5
            );

            -- Knowledge base: objection handling scripts
            CREATE TABLE IF NOT EXISTS company_objections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                client_id TEXT NOT NULL,
                objection TEXT NOT NULL,
                response TEXT NOT NULL,
                priority INTEGER DEFAULT 5
            );

            -- Key-value settings store (agent config, feature flags, etc.)
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            -- Agent scheduler run log
            CREATE TABLE IF NOT EXISTS agent_run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                ran_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'ok',
                notes TEXT
            );

            -- Solar installation proposals generated for leads
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                lead_id INTEGER NOT NULL,
                html_content TEXT,
                system_size_kw REAL,
                est_annual_savings REAL,
                payback_years REAL,
                stc_rebate_aud REAL,
                status TEXT DEFAULT 'draft'
                    CHECK(status IN ('draft','sent','accepted','declined'))
            );

            -- Swarm experiments (capital allocation, A/B tests, strategy ideas)
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                status TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','running','complete','killed','rejected')),
                idea_text TEXT,
                bucket TEXT CHECK(bucket IN ('exploit','explore','moonshot')),
                confidence_score REAL DEFAULT 0,
                devil_score REAL DEFAULT 0,
                kelly_fraction REAL DEFAULT 0,
                budget_allocated REAL DEFAULT 0,
                approved_by TEXT,
                approved_at TEXT,
                failure_mode TEXT
            );

            -- Agent task queue (inter-agent job dispatch)
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                job_type TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                tier INTEGER DEFAULT 3,
                status TEXT DEFAULT 'queued'
                    CHECK(status IN ('queued','processing','complete','failed')),
                context_payload TEXT,
                output TEXT
            );

            -- Pheromone signals (ant-colony routing signals between agents)
            CREATE TABLE IF NOT EXISTS pheromone_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                signal_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                vertical TEXT,
                channel TEXT,
                experiment_id INTEGER,
                decay_factor REAL DEFAULT 1.0
            );

            -- Circuit breaker log (yellow/orange/red halt states)
            CREATE TABLE IF NOT EXISTS circuit_breaker_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                triggered_at TEXT DEFAULT (datetime('now')),
                resolved_at TEXT,
                level TEXT NOT NULL CHECK(level IN ('yellow','orange','red')),
                reason TEXT
            );

            -- CRM stats snapshot (written by crm_sync every 30 min)
            CREATE TABLE IF NOT EXISTS crm_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                updated_at TEXT DEFAULT (datetime('now')),
                total_leads INTEGER DEFAULT 0,
                hot_leads INTEGER DEFAULT 0,
                booked_assessments INTEGER DEFAULT 0,
                proposals_sent INTEGER DEFAULT 0
            );

            -- Inbound email records (written by email_processing/email_agent)
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT DEFAULT (datetime('now')),
                from_email TEXT,
                from_name TEXT,
                subject TEXT,
                body TEXT,
                classification TEXT,
                urgency_score REAL DEFAULT 0,
                draft_reply TEXT,
                status TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','sent','discarded')),
                ghl_contact_id TEXT
            );

            -- A/B tests (managed by ab_tester agent)
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'running'
                    CHECK(status IN ('running','complete','cancelled')),
                winner TEXT,
                winner_stats TEXT
            );

            -- Discovered opportunities (managed by scout_agent + opportunity_store)
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                title TEXT NOT NULL,
                opp_type TEXT,
                status TEXT DEFAULT 'discovered'
                    CHECK(status IN ('discovered','actioned','won','lost')),
                effort TEXT DEFAULT 'medium'
                    CHECK(effort IN ('low','medium','high')),
                impact TEXT DEFAULT 'medium'
                    CHECK(impact IN ('low','medium','high')),
                priority_score REAL DEFAULT 5.0,
                source TEXT,
                notes TEXT
            );

            -- Inter-agent message bus (managed by bus/message_bus.py)
            CREATE TABLE IF NOT EXISTS message_bus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                to_agent TEXT NOT NULL,
                from_agent TEXT DEFAULT 'system',
                msg_type TEXT NOT NULL,
                priority INTEGER DEFAULT 3,
                payload TEXT,
                status TEXT DEFAULT 'queued'
                    CHECK(status IN ('queued','processing','complete','failed'))
            );

            -- Knowledge graph entities (companies, people, products)
            CREATE TABLE IF NOT EXISTS kg_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT,
                source TEXT
            );

            -- Knowledge graph relationships between entities
            CREATE TABLE IF NOT EXISTS kg_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                from_entity_id INTEGER NOT NULL,
                to_entity_id INTEGER NOT NULL,
                rel_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0
            );
        """)
    _apply_migrations()
    print("[DB] Database ready.")


def _apply_migrations():
    """Add any columns that may be missing from an existing database.

    Safe to run on every startup — ALTER TABLE ADD COLUMN is a no-op if the
    column already exists (caught and ignored).
    """
    migrations = [
        # company_profiles — extended fields used by KB API, voice, and onboarding
        ("company_profiles", "company_name TEXT"),
        ("company_profiles", "phone TEXT"),
        ("company_profiles", "email TEXT"),
        ("company_profiles", "service_areas TEXT"),
        ("company_profiles", "years_in_business INTEGER DEFAULT 0"),
        ("company_profiles", "num_installers INTEGER DEFAULT 0"),
        ("company_profiles", "certifications TEXT"),
        ("company_profiles", "retell_agent_id TEXT"),
        ("company_profiles", "elevenlabs_voice_id TEXT"),
        ("company_profiles", "ghl_location_id TEXT"),
        ("company_profiles", "active INTEGER DEFAULT 1"),
        # call_logs — full transcript text
        ("call_logs", "transcript_text TEXT"),
        # leads — call reference and numeric score alias
        ("leads", "call_id TEXT"),
        ("leads", "score REAL"),
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


def sanitise_input(value: str, max_length: int = 1000) -> str:
    """Sanitise a user-provided string for safe storage.

    Strips leading/trailing whitespace, removes null bytes, and truncates
    to max_length. Does NOT HTML-escape (handled at render time by the frontend).

    Args:
        value: Raw string from user input or external source
        max_length: Maximum allowed length (default 1000)

    Returns:
        Sanitised string safe for parameterized query values
    """
    if not isinstance(value, str):
        return ""
    cleaned: str = value.strip().replace("\x00", "")
    return cleaned if len(cleaned) <= max_length else cleaned[:max_length]  # type: ignore[misc]


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
