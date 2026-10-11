from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from .application import autofill_external, detect_ats
from .clarification import clarify_job
from .config import load_yaml
from .db import Database
from .eligibility import classify_pakistan_eligibility
from .linkedin_guest import LinkedInGuestClient
from .matching import match_job
from .paths import find_project_root
from .profile_adapter import evidence_for_skill, resume_path
from .resume import extract_pdf_text, render_tailored_resume

ROOT = find_project_root()
PROFILE = ROOT / "config/profile.yaml"
SEARCH = ROOT / "config/search.yaml"
DB_PATH = ROOT / "data/job_agent.sqlite3"


def _title_groups(search: dict) -> dict[str, list[str]]:
    old = search.get("keywords", []) or []
    if old:
        return {"primary": list(dict.fromkeys(str(x) for x in old if x)), "secondary": [], "exploratory": []}
    groups = search.get("job_titles", {}) or {}
    return {
        name: list(dict.fromkeys(str(x) for x in groups.get(name, []) or [] if x))
        for name in ("primary", "secondary", "exploratory")
    }


def _flatten_titles(search: dict) -> list[str]:
    groups = _title_groups(search)
    titles: list[str] = []
    for name in ("primary", "secondary", "exploratory"):
        titles.extend(groups[name])
    return list(dict.fromkeys(titles))


def _scoring_titles(search: dict) -> list[str]:
    """Use primary titles as the role-family target when configured.

    Secondary/exploratory titles are discovery fallbacks, not equal-weight career
    goals. This keeps a temporary focus (for example Support Engineering) from
    scoring an unrelated secondary AI role as highly as a primary support role.
    """
    groups = _title_groups(search)
    return groups["primary"] or _flatten_titles(search)


def _query_plan(search: dict, query_cap: int) -> list[tuple[str, str]]:
    """Build a priority-aware query plan.

    Primary titles are searched across the highest-priority locations before
    secondary/exploratory titles. Within each priority group we rotate by
    location first, so a capped run covers many role titles instead of spending
    the whole budget on one or two titles.
    """
    locations = [str(x) for x in search.get("locations", []) or [] if x]
    groups = _title_groups(search)
    plan: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group_name in ("primary", "secondary", "exploratory"):
        titles = groups[group_name]
        for loc in locations:
            for title in titles:
                pair = (title, loc)
                if pair in seen:
                    continue
                seen.add(pair)
                plan.append(pair)
                if len(plan) >= query_cap:
                    return plan
    return plan


def _filters(search: dict) -> dict:
    f = search.get("filters", {}) or {}
    runtime = search.get("runtime", {}) or {}
    return {
        "remote_only": bool(f.get("remote_only", search.get("remote_only", True))),
        "posted_within_hours": int(f.get("posted_within_hours", search.get("posted_within_hours", 24))),
        "max_applicants": int(f.get("max_applicants", search.get("max_applicants", 99))),
        "max_pages_per_query": int(runtime.get("max_pages_per_query", search.get("max_pages_per_query", 1))),
        "request_delay_seconds": float(runtime.get("request_delay_seconds", search.get("request_delay_seconds", 1.5))),
        "max_queries_per_run": int(runtime.get("max_queries_per_run", search.get("max_queries_per_run", 30))),
        "max_details_per_run": int(runtime.get("max_details_per_run", search.get("max_details_per_run", 125))),
    }


def _match_thresholds(profile: dict, search: dict) -> tuple[float, float, float]:
    matching = search.get("matching", {}) or {}
    prefs = profile.get("preferences", {}) or {}
    return (
        float(matching.get("skip_below_score", prefs.get("minimum_match_score", 70))),
        float(matching.get("clarification_min_score", prefs.get("clarification_min_score", 70))),
        float(matching.get("clarification_max_score", prefs.get("clarification_max_score", 84))),
    )



def _candidate_where(min_score: float, max_score: float | None = None, mode: str = "strict") -> tuple[str, tuple]:
    """Build the trusted internal shortlist clause.

    strict: known < applicant cap AND eligible/likely_eligible.
    review: exclude known over-cap/ineligible but include unknowns for manual review.
    all: diagnostic view; only excludes explicitly ineligible.
    """
    clauses = ["match_score >= ?"]
    params: list[object] = [float(min_score)]
    if max_score is not None:
        clauses.append("match_score <= ?")
        params.append(float(max_score))

    if mode == "strict":
        clauses.append("applicants_under_limit = 1")
        clauses.append("pakistan_eligibility IN ('eligible','likely_eligible')")
    elif mode == "review":
        clauses.append("(applicants_under_limit = 1 OR applicants_under_limit IS NULL)")
        clauses.append("pakistan_eligibility != 'ineligible'")
    elif mode == "all":
        clauses.append("pakistan_eligibility != 'ineligible'")
    else:
        raise ValueError(f"Unknown candidate filter mode: {mode}")
    return " AND ".join(clauses), tuple(params)


def _application_gate(row, search: dict) -> list[str]:
    cfg = (search.get("application", {}) or {}).get("apply_only_if", {}) or {}
    min_score = float(cfg.get("minimum_match_score", 85))
    allowed_elig = set(cfg.get("pakistan_eligibility", ["eligible", "likely_eligible"]) or [])
    reasons: list[str] = []
    if float(row["match_score"] or 0) < min_score:
        reasons.append(f"match score {float(row['match_score'] or 0):.1f}% is below {min_score:.1f}%")
    if row["applicants_under_limit"] != 1:
        label = row["applicant_text"] or row["applicants"] or "unknown"
        reasons.append(f"applicant count is not confirmed below the configured limit ({label})")
    if row["pakistan_eligibility"] not in allowed_elig:
        reasons.append(f"Pakistan eligibility is {row['pakistan_eligibility']}")
    return reasons

def init_cmd(args):
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    if not PROFILE.exists():
        shutil.copy(ROOT / "config/profile.example.yaml", PROFILE)
        print(f"Created {PROFILE}")
    if not SEARCH.exists():
        shutil.copy(ROOT / "config/search.example.yaml", SEARCH)
        print(f"Created {SEARCH}")
    if args.resume:
        dst = ROOT / "data/resumes/master.pdf"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(args.resume, dst)
        extract_pdf_text(str(dst), str(ROOT / "data/resumes/master.txt"))
        print(f"Copied resume to {dst} and extracted text.")
    print("Next: edit config/profile.yaml, then run `python -m job_agent doctor`.")


def doctor_cmd(args):
    print(f"Python: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Virtualenv active: {'yes' if sys.prefix != sys.base_prefix else 'NO'}")
    print(f"Project root: {ROOT}")
    print(f"Current directory: {Path.cwd()}")

    try:
        import yaml
        print(f"PyYAML: OK ({getattr(yaml, '__version__', 'unknown')})")
    except Exception as e:
        print(f"PyYAML: MISSING ({e})")

    try:
        import requests
        import bs4
        print(f"requests: OK ({requests.__version__})")
        print(f"beautifulsoup4: OK ({bs4.__version__})")
    except Exception as e:
        print(f"HTTP/parser dependencies: ERROR ({e})")

    try:
        profile = load_yaml(PROFILE)
        search = load_yaml(SEARCH)
    except Exception as e:
        raise SystemExit(f"Config error: {e}")

    titles = _flatten_titles(search)
    locations = [str(x) for x in search.get("locations", []) or [] if x]
    f = _filters(search)
    groups = _title_groups(search)
    print(f"Search titles: {len(titles)} (primary: {len(groups['primary'])}, secondary: {len(groups['secondary'])}, exploratory: {len(groups['exploratory'])})")
    print(f"Search locations: {len(locations)}")
    print(f"Remote only: {f['remote_only']}; posted within: {f['posted_within_hours']}h; max applicants: {f['max_applicants']}")
    print(f"Query cap per run: {f['max_queries_per_run']}; pages/query: {f['max_pages_per_query']}")

    if not titles:
        print("ERROR: no search titles resolved from search.yaml")
    if not locations:
        print("ERROR: no search locations found in search.yaml")

    rp = ROOT / resume_path(profile)
    print(f"Resume: {'OK' if rp.exists() else 'MISSING'} ({rp})")

    if args.network and titles and locations:
        print(f"Network test: {titles[0]} — {locations[0]}")
        client = LinkedInGuestClient(delay_seconds=0, debug_dir=ROOT / "data/debug")
        try:
            jobs = client.search(titles[0], locations[0], posted_hours=f["posted_within_hours"], remote_only=f["remote_only"], pages=1)
            print(f"LinkedIn HTTP: {client.last_status}; bytes: {client.last_html_size}; parsed jobs: {len(jobs)}")
            print(f"URL: {client.last_url}")
            if not jobs:
                print("No jobs parsed. Inspect data/debug/*.html. The endpoint may have changed, returned no results, or blocked this request.")
        except Exception as e:
            print(f"Network test failed: {e}")


def discover_cmd(args):
    profile = load_yaml(PROFILE)
    search = load_yaml(SEARCH)
    titles = _flatten_titles(search)
    locations = [str(x) for x in search.get("locations", []) or [] if x]
    f = _filters(search)

    if not titles:
        raise SystemExit("No search titles resolved. Expected `keywords:` or `job_titles: primary/secondary/exploratory` in config/search.yaml.")
    if not locations:
        raise SystemExit("No `locations:` configured in config/search.yaml.")

    query_cap = int(args.limit_queries or f["max_queries_per_run"])
    query_plan = _query_plan(search, query_cap)
    client = LinkedInGuestClient(
        delay_seconds=f["request_delay_seconds"],
        debug_dir=(ROOT / "data/debug") if args.debug else None,
    )
    db = Database(DB_PATH)

    discovered: dict[str, object] = {}
    queries = 0
    failures = 0
    for kw, loc in query_plan:
        queries += 1
        print(f"[{queries}/{len(query_plan)}] Searching: {kw} — {loc}")
        try:
            jobs = client.search(
                kw,
                loc,
                posted_hours=f["posted_within_hours"],
                remote_only=f["remote_only"],
                pages=f["max_pages_per_query"],
            )
            print(f"  parsed {len(jobs)} jobs")
        except Exception as e:
            failures += 1
            print(f"  search failed: {e}")
            continue
        for job in jobs:
            discovered[job.job_id] = job

    print(f"Unique jobs discovered before detail enrichment: {len(discovered)}")
    target_titles = _scoring_titles(search)
    detail_cap = f["max_details_per_run"]
    saved = 0
    for idx, job in enumerate(list(discovered.values())[:detail_cap], start=1):
        print(f"  Enriching {idx}/{min(len(discovered), detail_cap)}: {job.company} — {job.title}")
        try:
            client.enrich(job, applicant_limit=f["max_applicants"] + 1)
        except Exception as e:
            print(f"    detail failed for {job.job_id}: {e}")
        job.pakistan_eligibility, job.eligibility_reason = classify_pakistan_eligibility(job.description, job.location)
        m = match_job(job.title, job.description, profile, target_titles=target_titles)
        job.match_score = m.score
        job.matched_skills = m.matched_skills
        job.missing_skills = m.missing_skills
        db.upsert_job(job)
        saved += 1

    db.close()
    print(f"Saved/updated {saved} unique jobs from {queries} search queries ({failures} query failures).")
    if saved == 0:
        print("Nothing was saved. Run `python -m job_agent doctor --network` and then `python -m job_agent discover --debug --limit-queries 3`.")


def list_cmd(args):
    profile = load_yaml(PROFILE)
    search = load_yaml(SEARCH)
    default_min, _, _ = _match_thresholds(profile, search)
    min_score = float(args.min_score if args.min_score is not None else default_min)
    mode = "all" if args.all else ("review" if args.review else "strict")
    where, params = _candidate_where(min_score, mode=mode)
    db = Database(DB_PATH)
    rows = db.get_jobs(where, params)
    for r in rows:
        app = r["applicants"] if r["applicants"] is not None else (r["applicant_text"] or "?")
        print(f"{r['match_score']:>5.1f}% | {app!s:>12} | {r['pakistan_eligibility']:<15} | {r['company']} — {r['title']}")
        print(f"        {r['url']}")
    if not rows:
        print(f"No jobs currently match min-score {min_score} in {mode} mode.")
        if mode == "strict":
            print("Use `python -m job_agent list --min-score 70 --review` to include unknown applicant counts / unclear Pakistan eligibility for manual review.")
    db.close()


def clarify_cmd(args):
    profile = load_yaml(PROFILE)
    search = load_yaml(SEARCH)
    _, lo, hi = _match_thresholds(profile, search)
    mode = "review" if args.review else "strict"
    where, params = _candidate_where(lo, max_score=hi, mode=mode)
    db = Database(DB_PATH)
    rows = db.get_jobs(where, params)
    changed_any = False
    for row in rows:
        if clarify_job(db, profile, str(PROFILE), row):
            changed_any = True
    db.close()
    if changed_any:
        print("Profile updated. Run `python -m job_agent rescore` to re-evaluate jobs.")
    else:
        print("No new verified facts added.")
        if mode == "strict":
            print("No strict clarification candidates may remain. Use `python -m job_agent clarify --review` only if you want to inspect unclear-eligibility/unknown-applicant jobs.")


def rescore_cmd(args):
    profile = load_yaml(PROFILE)
    search = load_yaml(SEARCH)
    target_titles = _scoring_titles(search)
    db = Database(DB_PATH)
    rows = db.get_jobs()
    for r in rows:
        m = match_job(r["title"], r["description"] or "", profile, target_titles=target_titles)
        db.conn.execute(
            "UPDATE jobs SET match_score=?, missing_skills_json=?, matched_skills_json=?, updated_at=CURRENT_TIMESTAMP WHERE job_id=?",
            (m.score, json.dumps(m.missing_skills), json.dumps(m.matched_skills), r["job_id"]),
        )
    db.conn.commit()
    db.close()
    print(f"Re-scored {len(rows)} jobs.")


def tailor_cmd(args):
    profile = load_yaml(PROFILE)
    db = Database(DB_PATH)
    rows = db.get_jobs("job_id=?", (args.job_id,))
    if not rows:
        raise SystemExit(f"Unknown job id {args.job_id}")
    r = rows[0]
    matched = json.loads(r["matched_skills_json"] or "[]")
    evidence: list[str] = []
    for skill in matched:
        evidence.extend(evidence_for_skill(profile, skill))
    out = ROOT / f"data/generated/{args.job_id}-resume.md"
    render_tailored_resume(profile, r["title"], matched, evidence, str(out))
    db.upsert_application(args.job_id, "resume_ready", detect_ats(r["url"]), str(out))
    db.close()
    print(out)


def apply_cmd(args):
    profile = load_yaml(PROFILE)
    search = load_yaml(SEARCH)
    db = Database(DB_PATH)
    rows = db.get_jobs("job_id=?", (args.job_id,))
    if not rows:
        raise SystemExit(f"Unknown job id {args.job_id}")
    r = rows[0]
    gate_reasons = _application_gate(r, search)
    if gate_reasons and not args.force:
        db.close()
        lines = "\n  - ".join(gate_reasons)
        raise SystemExit(
            "Application gate blocked this job:\n  - " + lines +
            "\nUse `--force` only for an intentional manual-review exception; external auto-submit should stay strict."
        )
    target_url = args.url or r["url"]
    ats = detect_ats(target_url)
    if ats == "linkedin":
        print("LinkedIn job detected. This PoC does not auto-submit on LinkedIn. Open the URL, review the generated resume, and submit manually.")
        print(target_url)
        db.upsert_application(args.job_id, "manual_linkedin_review", ats, args.resume or "")
        db.close()
        return

    chosen_resume = args.resume or resume_path(profile)
    chosen_resume_path = Path(chosen_resume)
    if not chosen_resume_path.is_absolute():
        chosen_resume_path = ROOT / chosen_resume_path

    async def run():
        result = await autofill_external(target_url, profile, str(chosen_resume_path), submit=args.submit, user_data_dir=str(ROOT / "browser-profile"))
        print(json.dumps(result, indent=2))
        return result

    result = asyncio.run(run())
    status = "submitted" if result.get("submitted") else "review_required"
    db.upsert_application(args.job_id, status, ats, str(chosen_resume_path), json.dumps(result))
    db.close()


def parser():
    p = argparse.ArgumentParser(prog="job-agent", description="Local-first job discovery, clarification, tailoring, and ATS autofill PoC")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("--resume", help="Path to your master resume PDF")
    s.set_defaults(func=init_cmd)

    s = sub.add_parser("doctor", help="Check Python environment, config compatibility, resume and optional LinkedIn guest connectivity")
    s.add_argument("--network", action="store_true", help="Run one public LinkedIn guest search request")
    s.set_defaults(func=doctor_cmd)

    s = sub.add_parser("discover")
    s.add_argument("--debug", action="store_true", help="Save zero-result/block HTML responses under data/debug")
    s.add_argument("--limit-queries", type=int, help="Temporarily cap title/location search combinations")
    s.set_defaults(func=discover_cmd)

    s = sub.add_parser("list")
    s.add_argument("--min-score", type=float)
    s.add_argument("--review", action="store_true", help="Include unclear Pakistan eligibility and unknown applicant counts, but still exclude known over-limit/ineligible jobs")
    s.add_argument("--all", action="store_true", help="Diagnostic view: include known over-limit jobs; still exclude explicitly ineligible jobs")
    s.set_defaults(func=list_cmd)

    s = sub.add_parser("clarify")
    s.add_argument("--review", action="store_true", help="Also clarify review-mode jobs with unclear eligibility/unknown applicant counts")
    s.set_defaults(func=clarify_cmd)

    s = sub.add_parser("rescore")
    s.set_defaults(func=rescore_cmd)

    s = sub.add_parser("tailor")
    s.add_argument("job_id")
    s.set_defaults(func=tailor_cmd)

    s = sub.add_parser("apply")
    s.add_argument("job_id")
    s.add_argument("--resume")
    s.add_argument("--url", help="Direct external ATS apply URL, if you have one")
    s.add_argument("--submit", action="store_true", help="Submit external ATS only when all fields were recognized")
    s.add_argument("--force", action="store_true", help="Override shortlist gate for an intentional manual-review exception")
    s.set_defaults(func=apply_cmd)
    return p


def main():
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
