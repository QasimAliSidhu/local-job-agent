from job_agent.cli import _query_plan, _scoring_titles
from job_agent.matching import match_job


def test_primary_support_titles_drive_query_plan_and_scoring():
    search = {
        "job_titles": {
            "primary": ["Technical Support Engineer", "Application Support Engineer"],
            "secondary": ["AI Automation Engineer"],
        },
        "locations": ["Pakistan", "Worldwide"],
    }
    assert _scoring_titles(search) == ["Technical Support Engineer", "Application Support Engineer"]
    assert _query_plan(search, 4) == [
        ("Technical Support Engineer", "Pakistan"),
        ("Application Support Engineer", "Pakistan"),
        ("Technical Support Engineer", "Worldwide"),
        ("Application Support Engineer", "Worldwide"),
    ]


def test_unrelated_ai_engineer_title_does_not_score_like_support_title():
    profile = {
        "professional_summary": {"years_experience": "8+"},
        "skills": {"engineering": ["Python"], "support_operations": ["L2/L3 support", "root-cause analysis"]},
        "experience": [{"title": "Senior Software Support Engineer", "highlights": ["Owned enterprise SaaS incidents"]}],
    }
    support = match_job(
        "Senior Technical Support Engineer",
        "Troubleshoot enterprise SaaS incidents, APIs and production issues.",
        profile,
        target_titles=["Technical Support Engineer", "Application Support Engineer"],
    )
    ml = match_job(
        "Senior Machine Learning Engineer",
        "Build Python machine learning systems.",
        profile,
        target_titles=["Technical Support Engineer", "Application Support Engineer"],
    )
    assert support.score > ml.score
    assert support.title_score == 100.0
    assert ml.title_score == 0.0
