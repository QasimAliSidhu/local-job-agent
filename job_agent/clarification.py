from __future__ import annotations

from .config import save_yaml
from .db import Database
from .matching import SKILL_TAXONOMY


QUESTION_TEMPLATES = {
    "sql": "Have you personally used SQL for analysis, reporting, troubleshooting, migration, or application/database work?",
    "pricing": "Have you worked on pricing, packaging, subscriptions, monetization, or revenue optimization?",
    "enterprise_saas": "Have you worked directly with enterprise/B2B SaaS products or customers?",
    "apis": "Have you built or supported REST APIs, webhooks, SaaS integrations, or partner integrations?",
    "experimentation": "Have you designed or interpreted A/B tests, experiments, or controlled product tests?",
    "ai_llm": "Have you built or supported systems using AI/LLMs/generative AI?",
    "product_management": "Do you have direct product-management ownership such as roadmap, discovery, prioritization, or product strategy?",
    "javascript": "Have you used JavaScript/TypeScript/Node.js hands-on in production or substantial projects?",
    "aws": "Have you used AWS hands-on beyond coursework?",
}


def clarify_job(db: Database, profile: dict, profile_path: str, row) -> bool:
    import json

    missing = json.loads(row["missing_skills_json"] or "[]")
    if not missing:
        return False
    changed = False
    print(f"\n{row['company']} — {row['title']} ({row['match_score']:.1f}%)")
    print(row["url"])
    for skill in missing:
        prompt = QUESTION_TEMPLATES.get(skill, f"Do you have real, hands-on experience with {skill.replace('_',' ')}?")
        ans = input(f"\n{prompt} [y/N]: ").strip().lower()
        if ans not in {"y", "yes"}:
            continue
        years_raw = input("Approximately how many years? (blank if unknown): ").strip()
        try:
            years = float(years_raw) if years_raw else None
        except ValueError:
            years = None
        evidence = input("Give one truthful example (company/project + what you did): ").strip()
        if not evidence:
            print("Skipped: evidence is required before adding a resume fact.")
            continue

        facts = profile.setdefault("verified_facts", {})
        fact = facts.setdefault(skill, {"aliases": SKILL_TAXONOMY.get(skill, [skill.replace("_", " ")]), "years": 0, "evidence": []})
        if years is not None:
            fact["years"] = max(float(fact.get("years", 0) or 0), years)
        ev = fact.setdefault("evidence", [])
        if evidence not in ev:
            ev.append(evidence)

        # Backwards compatibility for older profile schema where skills are dict objects.
        old_skill = (profile.get("skills", {}) or {}).get(skill)
        if isinstance(old_skill, dict):
            if years is not None:
                old_skill["years"] = max(float(old_skill.get("years", 0) or 0), years)
            old_skill.setdefault("evidence", [])
            if evidence not in old_skill["evidence"]:
                old_skill["evidence"].append(evidence)

        db.add_fact(skill, "confirmed", years, evidence)
        changed = True
        print("Saved as a verified fact.")
    if changed:
        save_yaml(profile_path, profile)
    return changed
