"""Knowledge Graph — Entity and relationship store.

Wraps the kg_entities and kg_relationships tables.
Used to store structured knowledge about prospects, competitors,
and market signals discovered by research agents.
"""

import logging
from datetime import datetime

from memory.database import fetch_all, fetch_one, insert, get_conn

logger = logging.getLogger(__name__)


def add_entity(entity_type: str, name: str, properties: dict = None,
               source: str = "") -> int:
    """Add or update an entity in the knowledge graph.

    Args:
        entity_type: Category (e.g. 'company', 'person', 'product')
        name:        Unique name/identifier
        properties:  Dict of extra attributes (stored as JSON)
        source:      Where this entity was found

    Returns:
        Row id (new or existing)
    """
    import json
    try:
        existing = fetch_one(
            "SELECT id FROM kg_entities WHERE name = ? AND entity_type = ?",
            (name, entity_type),
        )
        if existing:
            return existing.get("id", 0)

        return insert("kg_entities", {
            "entity_type": entity_type,
            "name":        name,
            "properties":  json.dumps(properties or {}),
            "source":      source,
        })
    except Exception as e:
        logger.error(f"[KG] add_entity failed: {e}")
        return 0


def add_relationship(from_id: int, to_id: int, rel_type: str,
                     weight: float = 1.0) -> int:
    """Add a relationship between two entities.

    Args:
        from_id:  Source entity id
        to_id:    Target entity id
        rel_type: Relationship type (e.g. 'competes_with', 'works_at')
        weight:   Relationship strength 0-1

    Returns:
        New row id
    """
    try:
        return insert("kg_relationships", {
            "from_entity_id": from_id,
            "to_entity_id":   to_id,
            "rel_type":       rel_type,
            "weight":         weight,
        })
    except Exception as e:
        logger.error(f"[KG] add_relationship failed: {e}")
        return 0


def get_graph_summary() -> dict:
    """Return entity and relationship counts by type.

    Returns:
        Dict with entities and relationships dicts
    """
    try:
        ent_rows = fetch_all(
            "SELECT entity_type, COUNT(*) as n FROM kg_entities GROUP BY entity_type"
        )
        rel_rows = fetch_all(
            "SELECT rel_type, COUNT(*) as n FROM kg_relationships GROUP BY rel_type"
        )
        return {
            "entities":      {r["entity_type"]: r["n"] for r in ent_rows},
            "relationships": {r["rel_type"]: r["n"] for r in rel_rows},
        }
    except Exception as e:
        logger.error(f"[KG] get_graph_summary failed: {e}")
        return {"entities": {}, "relationships": {}}


def search_entities(entity_type: str = None, query: str = "") -> list:
    """Search entities by type and/or name substring.

    Args:
        entity_type: Filter by type (optional)
        query:       Name substring to search

    Returns:
        List of entity dicts
    """
    try:
        conditions, params = [], []
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if query:
            conditions.append("name LIKE ?")
            params.append(f"%{query}%")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return fetch_all(
            f"SELECT * FROM kg_entities {where} ORDER BY created_at DESC LIMIT 50",
            tuple(params),
        )
    except Exception as e:
        logger.error(f"[KG] search_entities failed: {e}")
        return []
