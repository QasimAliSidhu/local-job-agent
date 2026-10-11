"""Optional MCP wrapper around the local SQLite-backed job agent."""
from __future__ import annotations

import json

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise SystemExit("Install dependencies with: python -m pip install -e .") from e

from .db import Database
from .paths import find_project_root

mcp = FastMCP("job-agent")
DB_PATH = find_project_root() / "data/job_agent.sqlite3"


@mcp.tool()
def matching_jobs(min_score: float = 70.0, include_unclear: bool = True) -> str:
    """Return locally collected jobs above a match score, excluding known-ineligible roles."""
    db = Database(DB_PATH)
    elig = "('eligible','likely_eligible','unclear')" if include_unclear else "('eligible','likely_eligible')"
    rows = db.get_jobs(f"match_score >= ? AND pakistan_eligibility IN {elig}", (min_score,))
    payload = [dict(r) for r in rows]
    db.close()
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool()
def clarification_queue(min_score: float = 70.0, max_score: float = 84.0) -> str:
    """Return jobs that are close matches and contain possible missing skill evidence."""
    db = Database(DB_PATH)
    rows = db.get_jobs(
        "match_score BETWEEN ? AND ? AND missing_skills_json != '[]' AND pakistan_eligibility != 'ineligible'",
        (min_score, max_score),
    )
    payload = [dict(r) for r in rows]
    db.close()
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool()
def application_status(job_id: str) -> str:
    """Return saved application status for a job."""
    db = Database(DB_PATH)
    row = db.conn.execute("SELECT * FROM applications WHERE job_id=?", (job_id,)).fetchone()
    db.close()
    return json.dumps(dict(row) if row else {"job_id": job_id, "status": "not_started"})


if __name__ == "__main__":
    mcp.run()
