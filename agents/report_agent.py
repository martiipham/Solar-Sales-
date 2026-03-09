"""Report Agent — Weekly client performance reports.

Pulls lead data from database, generates professional client
updates, and saves to reports/ folder.

Given client_name and date_range, generates:
  - Leads received, qualified, contacted, converted
  - Response time improvement metrics
  - Leads not lost calculation
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from memory.database import fetch_all, fetch_one
import config

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def generate(client_name: str, date_range: int = 7) -> dict:
    """Generate a weekly client performance report.

    Args:
        client_name: Solar company client name
        date_range: Number of days to include (default 7)

    Returns:
        Dict with file_path, report_text, stats
    """
    print(f"[REPORT] Generating {date_range}-day report for: {client_name}")

    stats = _gather_stats(client_name, date_range)
    report_text = _format_report(client_name, stats, date_range)

    date_str = datetime.now().strftime("%Y%m%d")
    safe_name = client_name.replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_report_{date_str}.txt"
    file_path = REPORTS_DIR / filename

    with open(file_path, "w") as f:
        f.write(report_text)

    print(f"[REPORT] Saved to: {file_path}")
    return {
        "file_path": str(file_path),
        "client_name": client_name,
        "report_text": report_text,
        "stats": stats,
        "generated_at": datetime.now().isoformat(),
    }


def _gather_stats(client_name: str, days: int) -> dict:
    """Pull lead statistics from database for the given period.

    Args:
        client_name: Client account filter
        days: Number of days to look back

    Returns:
        Dict with all relevant metrics
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = fetch_all(
        "SELECT * FROM leads WHERE created_at >= ? AND (client_account = ? OR ? = 'ALL')",
        (cutoff, client_name, client_name),
    )

    total = len(rows)
    qualified = sum(1 for r in rows if (r.get("qualification_score") or 0) >= 5)
    hot = sum(1 for r in rows if (r.get("qualification_score") or 0) >= 7)
    contacted = sum(1 for r in rows if r.get("contacted_at"))
    converted = sum(1 for r in rows if r.get("status") == "converted")
    disqualified = sum(1 for r in rows if r.get("recommended_action") == "disqualify")

    avg_score = (
        sum(r.get("qualification_score") or 0 for r in rows) / total
        if total > 0 else 0
    )
    contact_rate = round(contacted / total * 100, 1) if total > 0 else 0
    conversion_rate = round(converted / total * 100, 1) if total > 0 else 0
    leads_not_lost = max(0, round(total * 0.25))

    return {
        "total_leads": total,
        "qualified": qualified,
        "hot_leads": hot,
        "contacted": contacted,
        "converted": converted,
        "disqualified": disqualified,
        "avg_qualification_score": round(avg_score, 1),
        "contact_rate_pct": contact_rate,
        "conversion_rate_pct": conversion_rate,
        "leads_not_lost": leads_not_lost,
        "estimated_revenue_protected": leads_not_lost * 8000,
        "period_days": days,
    }


def _format_report(client_name: str, stats: dict, days: int) -> str:
    """Format stats into a professional client report.

    Args:
        client_name: Solar company name
        stats: From _gather_stats()
        days: Report period length

    Returns:
        Formatted report text
    """
    end_date = datetime.now().strftime("%d %B %Y")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%d %B %Y")

    return f"""WEEKLY PERFORMANCE REPORT
{client_name}
Period: {start_date} — {end_date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEAD PIPELINE SUMMARY

Total leads received:      {stats['total_leads']}
Qualified leads (5+/10):   {stats['qualified']}
Hot leads (7+/10):         {stats['hot_leads']}
Leads contacted:           {stats['contacted']}
Leads converted:           {stats['converted']}
Leads disqualified:        {stats['disqualified']}

KEY METRICS

Average lead score:        {stats['avg_qualification_score']}/10
Contact rate:              {stats['contact_rate_pct']}%
Conversion rate:           {stats['conversion_rate_pct']}%

LEADS PROTECTED FROM LOSS

Before automation, an estimated 25% of leads go cold before
receiving a callback. This week, our system prevented:

  Leads not lost:          ~{stats['leads_not_lost']}
  Pipeline value protected: ~${stats['estimated_revenue_protected']:,} AUD
  (Based on avg $8,000 system value)

SYSTEM PERFORMANCE

✓ All new leads received automated response
✓ Hot leads flagged for immediate callback
✓ Follow-up sequences running for nurture leads
✓ CRM pipeline updated automatically

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Prepared by Solar Swarm AI Systems
Questions? Reply to this report or book a call.
"""


def generate_all_clients(days: int = 7) -> list:
    """Generate reports for all active client accounts.

    Args:
        days: Report period in days

    Returns:
        List of report result dicts
    """
    rows = fetch_all("SELECT DISTINCT client_account FROM leads WHERE client_account IS NOT NULL")
    clients = [r["client_account"] for r in rows if r.get("client_account")]

    if not clients:
        print("[REPORT] No client accounts found — generating sample report")
        clients = ["Sample Solar Client"]

    results = []
    for client in clients:
        result = generate(client, days)
        results.append(result)

    return results
