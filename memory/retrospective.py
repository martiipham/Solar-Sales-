"""Weekly retrospective — summarises swarm activity from the past 7 days.

Called by the scheduler every Monday 22:00 UTC and via the CLI.
Reads recent agent run logs and prints a summary to stdout.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def run() -> None:
    """Run the weekly retrospective and print a summary."""
    print("\n" + "=" * 60)
    print("  WEEKLY RETROSPECTIVE")
    print(f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    try:
        from memory.database import fetch_all
        since = (datetime.utcnow() - timedelta(days=7)).isoformat()

        rows = fetch_all(
            "SELECT job_id, status, notes, ran_at FROM agent_run_log WHERE ran_at >= ? ORDER BY ran_at DESC",
            (since,),
        )

        if not rows:
            print("  No agent runs recorded in the past 7 days.")
        else:
            ok    = [r for r in rows if r["status"] == "ok"]
            error = [r for r in rows if r["status"] == "error"]
            print(f"\n  Total runs:  {len(rows)}")
            print(f"  Successful:  {len(ok)}")
            print(f"  Errors:      {len(error)}")

            if error:
                print("\n  Recent errors:")
                for r in error[:5]:
                    print(f"    [{r['ran_at']}] {r['job_id']}: {r['notes']}")

        print("\n" + "=" * 60 + "\n")
        logger.info("[RETROSPECTIVE] Weekly retrospective complete.")

    except Exception as exc:
        logger.error(f"[RETROSPECTIVE] Failed: {exc}")
        print(f"  ERROR: {exc}")
