"""Warm Memory — JSON knowledge base for Solar Swarm.

Stores all experiments, outcomes, and learnings in the memory/
folder as structured JSON files. Slower than SQLite but richer
for pattern recognition and retrospective analysis.
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path("memory/knowledge")
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

EXPERIMENTS_FILE = KNOWLEDGE_DIR / "experiments.json"
LEARNINGS_FILE = KNOWLEDGE_DIR / "learnings.json"
VERTICAL_FILE = KNOWLEDGE_DIR / "verticals.json"


def _read_file(path: Path) -> dict | list:
    """Read a JSON file, returning empty structure if not found."""
    if not path.exists():
        return {} if path.suffix == ".json" and "vertical" in path.name else []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[WARM] Failed to read {path}: {e}")
        return {}


def _write_file(path: Path, data):
    """Write data to a JSON file atomically."""
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
    except Exception as e:
        logger.error(f"[WARM] Failed to write {path}: {e}")


def save_experiment_outcome(experiment_id: int, idea_text: str, outcome: dict):
    """Save a completed experiment and its outcome to warm memory.

    Args:
        experiment_id: Database id
        idea_text: The original experiment idea
        outcome: Dict with status, revenue, roi, learnings, failure_mode
    """
    experiments = _read_file(EXPERIMENTS_FILE)
    if not isinstance(experiments, list):
        experiments = []
    experiments.append({
        "id": experiment_id,
        "idea_text": idea_text,
        "recorded_at": datetime.utcnow().isoformat(),
        **outcome,
    })
    _write_file(EXPERIMENTS_FILE, experiments)
    logger.info(f"[WARM] Experiment {experiment_id} outcome saved")


def save_learning(topic: str, insight: str, source: str, confidence: float = 0.7):
    """Save a new learning insight to the knowledge base.

    Args:
        topic: Subject area (e.g. 'solar_ads', 'lead_nurture')
        insight: The actionable learning
        source: Which agent or process generated this
        confidence: How confident we are (0.0–1.0)
    """
    learnings = _read_file(LEARNINGS_FILE)
    if not isinstance(learnings, list):
        learnings = []
    learnings.append({
        "topic": topic,
        "insight": insight,
        "source": source,
        "confidence": confidence,
        "recorded_at": datetime.utcnow().isoformat(),
    })
    _write_file(LEARNINGS_FILE, learnings)
    logger.info(f"[WARM] Learning saved: {topic}")


def get_learnings_for_topic(topic: str) -> list:
    """Retrieve all learnings for a given topic, sorted by confidence."""
    learnings = _read_file(LEARNINGS_FILE)
    if not isinstance(learnings, list):
        return []
    filtered = [l for l in learnings if l.get("topic") == topic]
    return sorted(filtered, key=lambda x: x.get("confidence", 0), reverse=True)


def get_all_learnings() -> list:
    """Return all learnings from the knowledge base."""
    result = _read_file(LEARNINGS_FILE)
    return result if isinstance(result, list) else []


def update_vertical_knowledge(vertical: str, data: dict):
    """Update knowledge about a specific vertical market.

    Args:
        vertical: e.g. 'solar_australia', 'solar_perth'
        data: Dict with signals, patterns, opportunities
    """
    verticals = _read_file(VERTICAL_FILE)
    if not isinstance(verticals, dict):
        verticals = {}
    if vertical not in verticals:
        verticals[vertical] = {"created_at": datetime.utcnow().isoformat(), "signals": []}
    verticals[vertical]["updated_at"] = datetime.utcnow().isoformat()
    verticals[vertical].update(data)
    _write_file(VERTICAL_FILE, verticals)
    logger.info(f"[WARM] Vertical knowledge updated: {vertical}")


def get_vertical_knowledge(vertical: str) -> dict:
    """Get knowledge about a specific vertical."""
    verticals = _read_file(VERTICAL_FILE)
    if not isinstance(verticals, dict):
        return {}
    return verticals.get(vertical, {})


def get_experiment_history(limit: int = 50) -> list:
    """Return recent experiment history from warm memory."""
    experiments = _read_file(EXPERIMENTS_FILE)
    if not isinstance(experiments, list):
        return []
    return sorted(experiments, key=lambda x: x.get("recorded_at", ""), reverse=True)[:limit]


def get_winning_patterns() -> list:
    """Extract patterns from successful experiments."""
    experiments = _read_file(EXPERIMENTS_FILE)
    if not isinstance(experiments, list):
        return []
    winners = [e for e in experiments if e.get("status") == "complete" and e.get("roi", 0) > 0]
    return winners
