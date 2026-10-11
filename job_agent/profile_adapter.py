from __future__ import annotations

import re
from typing import Any


def identity(profile: dict) -> dict[str, str]:
    new = profile.get("identity", {}) or {}
    old = profile.get("personal", {}) or {}
    loc = new.get("location", {}) or {}
    return {
        "first_name": str(new.get("first_name") or old.get("first_name") or ""),
        "last_name": str(new.get("last_name") or old.get("last_name") or ""),
        "full_name": str(new.get("full_name") or " ".join(filter(None, [old.get("first_name"), old.get("last_name")]))),
        "email": str(new.get("email") or old.get("email") or ""),
        "phone": str(new.get("phone") or old.get("phone") or ""),
        "city": str(loc.get("city") or old.get("city") or ""),
        "country": str(loc.get("country") or old.get("country") or ""),
        "linkedin": str(new.get("linkedin") or old.get("linkedin_url") or ""),
        "portfolio": str(new.get("portfolio") or old.get("portfolio_url") or ""),
        "github": str(new.get("github") or old.get("github_url") or ""),
        "headline": str(new.get("headline") or ""),
    }


def total_years(profile: dict) -> float:
    old = profile.get("career", {}) or {}
    if old.get("total_years_experience") is not None:
        try:
            return float(old.get("total_years_experience") or 0)
        except (TypeError, ValueError):
            pass
    value = (profile.get("professional_summary", {}) or {}).get("years_experience", 0)
    m = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(m.group(0)) if m else 0.0


def current_title(profile: dict) -> str:
    old = profile.get("career", {}) or {}
    if old.get("current_title"):
        return str(old["current_title"])
    for item in profile.get("experience", []) or []:
        if item.get("current"):
            return str(item.get("title") or "")
    return identity(profile).get("headline", "")


def resume_path(profile: dict) -> str:
    r = profile.get("resume", {}) or {}
    return str(r.get("master_pdf") or r.get("default") or "data/resumes/master.pdf")


def answers(profile: dict) -> dict[str, Any]:
    out = dict(profile.get("answers", {}) or {})
    prefs = profile.get("work_preferences", {}) or {}
    compensation = profile.get("compensation", {}) or {}

    if "notice_period" not in out and prefs.get("notice_period_days") is not None:
        out["notice_period"] = f"{prefs['notice_period_days']} days"
    if "willing_us_hours" not in out and prefs.get("willing_us_hours") is not None:
        out["willing_us_hours"] = "Yes" if prefs.get("willing_us_hours") else "No"
    if "expected_compensation" not in out:
        annual = compensation.get("minimum_annual_usd")
        monthly = compensation.get("minimum_monthly_usd")
        hourly = compensation.get("minimum_hourly_usd")
        if annual:
            out["expected_compensation"] = f"USD {annual}/year"
        elif monthly:
            out["expected_compensation"] = f"USD {monthly}/month"
        elif hourly:
            out["expected_compensation"] = f"USD {hourly}/hour"
    return out


def profile_corpus(profile: dict) -> str:
    """Flatten only candidate-provided/verified profile content for matching."""
    chunks: list[str] = []
    ident = identity(profile)
    chunks.extend(v for v in ident.values() if v)

    summary = profile.get("professional_summary", {}) or {}
    chunks.append(str(summary.get("summary") or ""))
    chunks.extend(str(x) for x in summary.get("primary_domains", []) or [])

    skills = profile.get("skills", {}) or {}
    for key, value in skills.items():
        if isinstance(value, dict):
            # Old schema can contain candidate skills that are intentionally unverified
            # (years=0, no evidence) so they can be surfaced for clarification. Do not
            # treat their aliases as proof until there is actual evidence.
            years = float(value.get("years", 0) or 0)
            evidence = value.get("evidence", []) or []
            if years > 0 or evidence:
                chunks.append(str(key).replace("_", " "))
                chunks.extend(str(x) for x in value.get("aliases", []) or [])
                chunks.extend(str(x) for x in evidence)
        elif isinstance(value, (list, tuple)):
            # The personalized schema groups already-verified resume skills as lists.
            chunks.append(str(key).replace("_", " "))
            chunks.extend(str(x) for x in value)
        elif value:
            chunks.append(str(key).replace("_", " "))
            chunks.append(str(value))

    for project in profile.get("verified_projects", []) or []:
        chunks.append(str(project.get("name") or ""))
        chunks.append(str(project.get("evidence") or ""))

    for exp in profile.get("experience", []) or []:
        chunks.append(str(exp.get("title") or ""))
        chunks.append(str(exp.get("company") or ""))
        chunks.extend(str(x) for x in exp.get("highlights", []) or [])

    for key, fact in (profile.get("verified_facts", {}) or {}).items():
        chunks.append(str(key).replace("_", " "))
        if isinstance(fact, dict):
            chunks.extend(str(x) for x in fact.get("aliases", []) or [])
            chunks.extend(str(x) for x in fact.get("evidence", []) or [])
        else:
            chunks.append(str(fact))
    return "\n".join(x for x in chunks if x)


def evidence_for_skill(profile: dict, skill_key: str) -> list[str]:
    out: list[str] = []
    skills = profile.get("skills", {}) or {}
    data = skills.get(skill_key)
    if isinstance(data, dict):
        out.extend(str(x) for x in data.get("evidence", []) or [])
    fact = (profile.get("verified_facts", {}) or {}).get(skill_key)
    if isinstance(fact, dict):
        out.extend(str(x) for x in fact.get("evidence", []) or [])
    return list(dict.fromkeys(out))
