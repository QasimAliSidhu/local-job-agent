from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    location: str
    url: str
    posted_at: Optional[str] = None
    description: str = ""
    applicant_text: str = ""
    applicants: Optional[int] = None
    applicants_under_limit: Optional[bool] = None
    pakistan_eligibility: str = "unclear"
    eligibility_reason: str = ""
    match_score: float = 0.0
    missing_skills: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    title_score: float
    skill_score: float
    experience_score: float
