from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Job


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    url TEXT,
    posted_at TEXT,
    description TEXT,
    applicant_text TEXT,
    applicants INTEGER,
    applicants_under_limit INTEGER,
    pakistan_eligibility TEXT,
    eligibility_reason TEXT,
    match_score REAL DEFAULT 0,
    missing_skills_json TEXT DEFAULT '[]',
    matched_skills_json TEXT DEFAULT '[]',
    status TEXT DEFAULT 'discovered',
    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_key TEXT NOT NULL,
    value_text TEXT NOT NULL,
    years REAL,
    evidence TEXT,
    source TEXT NOT NULL DEFAULT 'user_confirmation',
    confirmed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(skill_key, value_text, evidence)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    ats TEXT,
    resume_path TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);
"""


class Database:
    def __init__(self, path: str | Path = "data/job_agent.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def upsert_job(self, job: Job) -> None:
        self.conn.execute(
            """
            INSERT INTO jobs (
                job_id,title,company,location,url,posted_at,description,
                applicant_text,applicants,applicants_under_limit,
                pakistan_eligibility,eligibility_reason,match_score,
                missing_skills_json,matched_skills_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                location=excluded.location,
                url=excluded.url,
                posted_at=excluded.posted_at,
                description=excluded.description,
                applicant_text=excluded.applicant_text,
                applicants=excluded.applicants,
                applicants_under_limit=excluded.applicants_under_limit,
                pakistan_eligibility=excluded.pakistan_eligibility,
                eligibility_reason=excluded.eligibility_reason,
                match_score=excluded.match_score,
                missing_skills_json=excluded.missing_skills_json,
                matched_skills_json=excluded.matched_skills_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                job.job_id, job.title, job.company, job.location, job.url,
                job.posted_at, job.description, job.applicant_text,
                job.applicants,
                None if job.applicants_under_limit is None else int(job.applicants_under_limit),
                job.pakistan_eligibility, job.eligibility_reason, job.match_score,
                json.dumps(job.missing_skills), json.dumps(job.matched_skills),
            ),
        )
        self.conn.commit()

    def get_jobs(self, where: str = "1=1", params: Iterable = ()):  # trusted internal clauses only
        return self.conn.execute(f"SELECT * FROM jobs WHERE {where} ORDER BY match_score DESC, first_seen_at DESC", tuple(params)).fetchall()

    def set_status(self, job_id: str, status: str) -> None:
        self.conn.execute("UPDATE jobs SET status=?, updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (status, job_id))
        self.conn.commit()

    def add_fact(self, skill_key: str, value_text: str, years: float | None, evidence: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO facts(skill_key,value_text,years,evidence) VALUES (?,?,?,?)",
            (skill_key, value_text, years, evidence),
        )
        self.conn.commit()

    def upsert_application(self, job_id: str, status: str, ats: str = "", resume_path: str = "", notes: str = "") -> None:
        self.conn.execute(
            """
            INSERT INTO applications(job_id,status,ats,resume_path,notes)
            VALUES (?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
                status=excluded.status, ats=excluded.ats,
                resume_path=excluded.resume_path, notes=excluded.notes,
                updated_at=CURRENT_TIMESTAMP
            """,
            (job_id, status, ats, resume_path, notes),
        )
        self.conn.commit()
