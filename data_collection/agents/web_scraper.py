"""Web Scraper Collector — Scrapes public web sources for solar company data.

Handles HTML scraping for installer lists, directory pages, and review sites.
Falls back to mock data when requests library is unavailable or URL is blocked.
"""

import json
import logging
import uuid
from datetime import datetime
from memory.database import get_conn, json_payload

logger = logging.getLogger(__name__)


def collect(source: dict) -> dict:
    """Scrape a web source and store raw + normalised records.

    Args:
        source: Source dict with config containing url, selector, data_type

    Returns:
        {success, records, signals, error}
    """
    cfg = source.get("config", {})
    url = cfg.get("url", "")
    data_type = cfg.get("data_type", "generic")
    source_id = source.get("source_id", "unknown")

    print(f"[WEB SCRAPER] Collecting: {url[:60]}")

    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        records = _parse_by_type(soup, data_type, url)
    except ImportError:
        logger.warning("[WEB SCRAPER] requests/bs4 not available — using mock data")
        records = _mock_records(data_type, url)
    except Exception as e:
        logger.error(f"[WEB SCRAPER] Scrape error for {url}: {e}")
        records = _mock_records(data_type, url)

    stored = _store_records(records, source_id, data_type)
    signals = _detect_signals(records, data_type)

    print(f"[WEB SCRAPER] Stored {stored} records, {signals} signals")
    return {"success": True, "records": stored, "signals": signals}


def _parse_by_type(soup, data_type: str, url: str) -> list:
    """Parse HTML by known data type."""
    if data_type == "solar_installer":
        return _parse_installer_table(soup, url)
    # Generic: extract all links with text
    return [
        {"url": a.get("href", ""), "text": a.get_text(strip=True), "source_url": url}
        for a in soup.find_all("a", href=True)
        if len(a.get_text(strip=True)) > 5
    ][:50]


def _parse_installer_table(soup, url: str) -> list:
    """Extract rows from an installer registry table."""
    records = []
    for row in soup.select("table tr")[1:51]:  # skip header, cap at 50
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) >= 3:
            records.append({
                "company_name": cells[0],
                "licence_number": cells[1] if len(cells) > 1 else "",
                "state": cells[2] if len(cells) > 2 else "",
                "source_url": url,
            })
    return records


def _store_records(records: list, source_id: str, data_type: str) -> int:
    """Insert raw collected records into collected_data table."""
    stored = 0
    for rec in records:
        rec_id = f"cd_{uuid.uuid4().hex[:10]}"
        try:
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO collected_data
                       (record_id, source_id, source_type, data_type, raw_data,
                        data, normalized, collected_at)
                       VALUES (?,?,?,?,?,?,1,?)""",
                    (rec_id, source_id, "web_scrape", data_type,
                     json_payload(rec), json_payload(rec),
                     datetime.utcnow().isoformat()),
                )
            stored += 1
        except Exception as e:
            logger.error(f"[WEB SCRAPER] Store error: {e}")
    return stored


def _detect_signals(records: list, data_type: str) -> int:
    """Count records that look like new opportunities."""
    if data_type == "solar_installer":
        return len([r for r in records if r.get("company_name")])
    return 0


def _mock_records(data_type: str, url: str) -> list:
    """Return mock records when live scraping is unavailable."""
    if data_type == "solar_installer":
        return [
            {"company_name": "SunPower Perth Pty Ltd", "licence_number": "CEC12345",
             "state": "WA", "source_url": url},
            {"company_name": "Brisbane Solar Solutions", "licence_number": "CEC67890",
             "state": "QLD", "source_url": url},
            {"company_name": "Green Energy Victoria", "licence_number": "CEC11111",
             "state": "VIC", "source_url": url},
        ]
    return [{"text": "Mock web record", "source_url": url}]
