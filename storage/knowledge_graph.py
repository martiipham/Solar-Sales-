"""Knowledge Graph — Entity and relationship store for Solar Swarm.

Tracks companies, people, tools, markets, and the relationships between them.
Powers prospect cross-referencing, competitive mapping, and opportunity scoring.
All data stored in SQLite kg_entities and kg_relationships tables.
"""

import json
import logging
import uuid
from datetime import datetime
from memory.database import get_conn, fetch_all, fetch_one, json_payload, parse_payload

logger = logging.getLogger(__name__)


def upsert_entity(
    name: str,
    entity_type: str,
    properties: dict,
    source: str = "system",
    confidence: float = 0.8,
) -> str:
    """Create or update a knowledge graph entity.

    Args:
        name: Entity name (e.g. "SunPower Perth")
        entity_type: company|person|tool|market|location
        properties: Dict of entity attributes
        source: Where this entity was discovered
        confidence: How confident we are this entity is real (0–1)

    Returns:
        entity_id
    """
    existing = fetch_one(
        "SELECT entity_id FROM kg_entities WHERE name=? AND entity_type=?",
        (name, entity_type),
    )

    if existing:
        entity_id = existing["entity_id"]
        with get_conn() as conn:
            conn.execute(
                """UPDATE kg_entities
                   SET properties=?, confidence=?, last_seen=?, mention_count=mention_count+1
                   WHERE entity_id=?""",
                (json_payload(properties), confidence, datetime.utcnow().isoformat(), entity_id),
            )
        logger.info(f"[KG] Updated entity: {name}")
        return entity_id

    entity_id = f"ent_{uuid.uuid4().hex[:10]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO kg_entities
               (entity_id, name, entity_type, properties, source, confidence,
                mention_count, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,1,?,?)""",
            (entity_id, name, entity_type, json_payload(properties),
             source, confidence,
             datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )
    logger.info(f"[KG] Created entity: {name} ({entity_type})")
    return entity_id


def upsert_relationship(
    from_id: str,
    to_id: str,
    rel_type: str,
    properties: dict = None,
    confidence: float = 0.8,
) -> str:
    """Create or update a relationship between two entities.

    Args:
        from_id: Source entity_id
        to_id: Target entity_id
        rel_type: USES|COMPETES_WITH|LOCATED_IN|EMPLOYS|PARTNERS_WITH|REFERS
        properties: Additional relationship attributes
        confidence: Confidence in this relationship

    Returns:
        rel_id
    """
    existing = fetch_one(
        "SELECT rel_id FROM kg_relationships WHERE from_entity=? AND to_entity=? AND rel_type=?",
        (from_id, to_id, rel_type),
    )

    if existing:
        rel_id = existing["rel_id"]
        with get_conn() as conn:
            conn.execute(
                "UPDATE kg_relationships SET properties=?, confidence=? WHERE rel_id=?",
                (json_payload(properties or {}), confidence, rel_id),
            )
        return rel_id

    rel_id = f"rel_{uuid.uuid4().hex[:10]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO kg_relationships
               (rel_id, from_entity, to_entity, rel_type, properties, confidence, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (rel_id, from_id, to_id, rel_type,
             json_payload(properties or {}), confidence,
             datetime.utcnow().isoformat()),
        )
    return rel_id


def get_entity(name: str, entity_type: str = None) -> dict:
    """Fetch an entity by name (and optionally type).

    Returns entity dict or empty dict if not found.
    """
    if entity_type:
        row = fetch_one(
            "SELECT * FROM kg_entities WHERE name=? AND entity_type=?",
            (name, entity_type),
        )
    else:
        row = fetch_one("SELECT * FROM kg_entities WHERE name=?", (name,))

    if not row:
        return {}
    return {**dict(row), "properties": parse_payload(row.get("properties", "{}"))}


def get_neighbors(entity_id: str, rel_type: str = None) -> list:
    """Return all entities related to the given entity.

    Args:
        entity_id: The source entity
        rel_type: Optional filter on relationship type

    Returns:
        List of (relationship, entity) dicts
    """
    if rel_type:
        rows = fetch_all(
            """SELECT r.rel_type, r.properties, e.*
               FROM kg_relationships r
               JOIN kg_entities e ON e.entity_id = r.to_entity
               WHERE r.from_entity=? AND r.rel_type=?""",
            (entity_id, rel_type),
        )
    else:
        rows = fetch_all(
            """SELECT r.rel_type, r.properties, e.*
               FROM kg_relationships r
               JOIN kg_entities e ON e.entity_id = r.to_entity
               WHERE r.from_entity=?""",
            (entity_id,),
        )
    return [
        {**dict(r), "entity_properties": parse_payload(r.get("properties", "{}"))}
        for r in rows
    ]


def search_entities(entity_type: str, limit: int = 20) -> list:
    """Return top entities of a given type sorted by mention count."""
    rows = fetch_all(
        "SELECT * FROM kg_entities WHERE entity_type=? ORDER BY mention_count DESC LIMIT ?",
        (entity_type, limit),
    )
    return [
        {**dict(r), "properties": parse_payload(r.get("properties", "{}"))}
        for r in rows
    ]


def get_graph_summary() -> dict:
    """Return entity and relationship counts for dashboard."""
    entity_rows = fetch_all(
        "SELECT entity_type, COUNT(*) as count FROM kg_entities GROUP BY entity_type"
    )
    rel_rows = fetch_all(
        "SELECT rel_type, COUNT(*) as count FROM kg_relationships GROUP BY rel_type"
    )
    return {
        "entities": {r["entity_type"]: r["count"] for r in entity_rows},
        "relationships": {r["rel_type"]: r["count"] for r in rel_rows},
    }
