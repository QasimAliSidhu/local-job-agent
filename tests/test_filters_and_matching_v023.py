from job_agent.cli import _candidate_where
from job_agent.matching import match_job


def _support_profile():
    return {
        "professional_summary": {"years_experience": "8+"},
        "skills": {
            "support_operations": ["technical support", "L2/L3 support", "root-cause analysis", "application logs"],
            "engineering": ["Python", "SQL"],
            "integrations": ["REST APIs", "webhooks"],
            "cloud_devops": ["Azure", "Kubernetes", "Linux"],
        },
        "experience": [
            {"title": "Senior Software Support Engineer", "highlights": ["Owned enterprise SaaS incidents"]}
        ],
    }


def test_strict_filter_requires_under_limit_and_eligibility():
    where, params = _candidate_where(70, mode="strict")
    assert "applicants_under_limit = 1" in where
    assert "eligible','likely_eligible" in where
    assert params == (70.0,)


def test_review_filter_excludes_known_over_limit_but_allows_unknowns():
    where, _ = _candidate_where(70, mode="review")
    assert "applicants_under_limit = 1 OR applicants_under_limit IS NULL" in where
    assert "pakistan_eligibility != 'ineligible'" in where


def test_single_generic_match_no_longer_saturates_to_100():
    m = match_job(
        "Technical Support Engineer",
        "We need a technical support engineer to help customers.",
        _support_profile(),
        target_titles=["Technical Support Engineer"],
    )
    assert 70 <= m.score < 95


def test_incidental_pricing_mention_does_not_create_clarification_gap():
    profile = _support_profile()
    m = match_job(
        "Application Support Engineer",
        "Our pricing platform supports enterprise customers.\nResponsibilities\nTroubleshoot production issues.\nRequirements\nExperience with SQL and REST APIs.",
        profile,
        target_titles=["Application Support Engineer"],
    )
    assert "pricing" not in m.missing_skills


def test_explicit_java_requirement_is_a_real_gap_not_javascript_false_positive():
    profile = _support_profile()
    profile["skills"]["engineering"].append("JavaScript")
    m = match_job(
        "Product Support Engineer",
        "Requirements\n3+ years of experience with Java and SQL.\nStrong troubleshooting skills.",
        profile,
        target_titles=["Product Support Engineer"],
    )
    assert "java" in m.missing_skills
