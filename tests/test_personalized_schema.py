from job_agent.cli import _filters, _flatten_titles
from job_agent.matching import match_job


def test_personalized_search_schema():
    search = {
        "job_titles": {"primary": ["AI Automation Engineer"], "secondary": ["Solutions Engineer"]},
        "filters": {"remote_only": True, "posted_within_hours": 24, "max_applicants": 99},
        "runtime": {"max_queries_per_run": 3},
    }
    assert _flatten_titles(search) == ["AI Automation Engineer", "Solutions Engineer"]
    f = _filters(search)
    assert f["posted_within_hours"] == 24
    assert f["max_applicants"] == 99
    assert f["max_queries_per_run"] == 3


def test_grouped_skill_profile_matches_without_crash():
    profile = {
        "professional_summary": {"years_experience": "8+"},
        "skills": {
            "applied_ai_automation": ["OpenAI", "n8n", "workflow automation"],
            "engineering": ["Python", "SQL"],
            "integrations": ["REST APIs", "webhooks"],
        },
        "experience": [{"title": "AI Systems Engineer", "current": True, "highlights": ["Built Python API automations"]}],
    }
    m = match_job(
        "AI Automation Engineer",
        "Need Python, n8n, REST API and workflow automation experience.",
        profile,
        target_titles=["AI Automation Engineer"],
    )
    assert m.score >= 80
    assert "python" in m.matched_skills
    assert "n8n" in m.matched_skills
    assert "apis" in m.matched_skills
