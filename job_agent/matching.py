from __future__ import annotations

import re
from .models import MatchResult
from .profile_adapter import profile_corpus, total_years


# Transparent taxonomy used for support-role matching and evidence-gap detection.
# Keep this intentionally finite: unknown/specialized requirements should reduce
# confidence rather than be hallucinated as candidate experience.
SKILL_TAXONOMY: dict[str, list[str]] = {
    "ai_llm": ["ai", "artificial intelligence", "llm", "large language model", "generative ai", "openai", "chatgpt"],
    "automation": ["automation", "workflow automation", "workflow orchestration", "automated workflows"],
    "n8n": ["n8n"],
    "python": ["python"],
    "apis": ["api", "apis", "rest api", "restful", "webhook", "webhooks", "integration", "integrations"],
    "sql": ["sql", "sql server", "database queries", "relational database", "stored procedures"],
    "javascript": ["javascript", "typescript", "node.js", "nodejs"],
    "java": ["java", "j2ee"],
    "dotnet": [".net", "dotnet", "c#"],
    "powershell": ["powershell"],
    "linux": ["linux", "unix"],
    "windows_iis": ["windows server", "iis", "internet information services"],
    "cloud_azure": ["azure", "azure devops", "azure api management", "key vault", "application gateway", "apim"],
    "aws": ["aws", "amazon web services"],
    "kubernetes": ["kubernetes", "k8s", "eks"],
    "docker": ["docker", "containers", "containerization"],
    "ci_cd": ["ci/cd", "cicd", "continuous integration", "continuous delivery", "deployment pipeline"],
    "oauth_sso": ["oauth", "oidc", "saml", "sso", "single sign-on", "single sign on"],
    "salesforce": ["salesforce"],
    "zendesk": ["zendesk"],
    "service_now": ["servicenow", "service now"],
    "microsoft_365": ["microsoft 365", "office 365", "entra id", "active directory", "intune", "sharepoint online"],
    "enterprise_saas": ["enterprise saas", "saas", "enterprise software", "b2b software"],
    "technical_support": ["technical support", "software support", "application support", "production support", "product support", "l2", "l3", "tier ii", "tier iii", "customer support engineer"],
    "incident_rca": ["root cause", "root-cause", "incident", "production issue", "troubleshooting", "problem management"],
    "monitoring": ["monitoring", "observability", "datadog", "application logs", "logging", "stack traces"],
    "networking": ["network troubleshooting", "network diagnostics", "tcp/ip", "dns", "vpn", "firewall", "routing"],
    "erp_crm": ["erp", "crm", "supply chain", "billing platform", "charging platform"],
    "contact_center": ["contact center", "call center"],
    "ecommerce": ["e-commerce", "ecommerce", "order workflow", "order management"],
    "prompt_engineering": ["prompt engineering", "prompt testing", "prompt design"],
    "mcp": ["model context protocol", "mcp"],
    "voiceflow": ["voiceflow"],
    "product_management": ["product management", "product strategy", "roadmap", "product discovery", "prioritization"],
    "pricing": ["pricing", "packaging", "monetization", "subscriptions", "revenue optimization"],
    "experimentation": ["a/b test", "a/b testing", "experimentation", "product experiment", "experiments"],
    # Specialized stacks/domains that often appear as hard requirements in support JDs.
    "oracle_apex": ["oracle apex", "apex"],
    "openedge": ["openedge", "abl", "4gl"],
    "unidata": ["unidata"],
    "finacle": ["finacle"],
    "sap": ["sap"],
    "sase_security": ["sase", "prisma sd-wan", "cngfw", "next-generation firewall"],
    "payments_banking": ["ach", "payments", "banking", "capital markets", "digital assets"],
    "avionics": ["avionics"],
    "mandarin": ["mandarin", "chinese language"],
    "german": ["german language", "fluent german", "german speaker"],
    "french": ["french language", "fluent french", "french speaker"],
    "spanish": ["spanish language", "fluent spanish", "spanish speaker"],
    "japanese": ["japanese language", "fluent japanese", "japanese speaker"],
}


REQUIREMENT_HEADERS = (
    "requirements", "qualifications", "minimum qualifications", "preferred qualifications",
    "what you bring", "what you'll bring", "what you will bring", "what we're looking for",
    "what we are looking for", "skills and experience", "required skills", "preferred skills",
    "you have", "you'll need", "you will need",
)

NON_REQUIREMENT_HEADERS = (
    "responsibilities", "what you'll do", "what you will do", "about the role", "about us",
    "what we offer", "benefits", "compensation", "why join", "the opportunity",
)

REQUIREMENT_MARKERS = (
    "required", "requires", "require ", "requirement", "must have", "must be", "need to", "needs to", "you need",
    "experience with", "experience in", "experience working", "hands-on", "hands on",
    "proficiency", "proficient", "expertise", "strong knowledge", "working knowledge",
    "familiarity", "minimum of", "at least", "preferred", "nice to have", "ability to",
)


GENERIC_TITLE_WORDS = {
    "senior", "sr", "junior", "jr", "lead", "staff", "principal", "associate",
    "engineer", "engineering", "specialist", "analyst", "manager", "developer",
    "technical", "level", "remote",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+.#/ -]+", " ", (s or "").lower())


def _alias_present(text: str, alias: str) -> bool:
    t = _norm(text)
    a = _norm(alias).strip()
    if not a:
        return False
    # Avoid substring bugs such as java matching javascript or sap matching ASAP.
    return re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", t) is not None


def _contains_any(text: str, aliases: list[str]) -> bool:
    return any(_alias_present(text, a) for a in aliases if a)


def _required_years(description: str) -> int | None:
    hits = [int(x) for x in re.findall(r"(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", description.lower())]
    return max(hits) if hits else None


def _meaningful_title_words(value: str) -> set[str]:
    words = {w for w in _norm(value).split() if len(w) > 2}
    meaningful = words - GENERIC_TITLE_WORDS
    return meaningful or words


def _title_score(title: str, targets: list[str]) -> float:
    if not targets:
        return 70.0
    title_words = _meaningful_title_words(title)
    scores: list[float] = []
    for target in targets:
        words = _meaningful_title_words(target)
        if not words:
            continue
        overlap = len(words & title_words) / len(words)
        scores.append(overlap * 100.0)
    return max(scores or [0.0])


def _looks_like_header(line: str) -> bool:
    stripped = (line or "").strip()
    return bool(stripped) and len(stripped) <= 90 and len(stripped.split()) <= 10


def _requirement_mention(description: str, aliases: list[str]) -> bool:
    """Return True only when a missing skill looks like an actual JD requirement.

    This avoids asking clarification questions because a word appeared in company
    background, product copy, compensation/pricing text, or responsibilities.
    """
    lines = [x.strip() for x in (description or "").splitlines() if x.strip()]
    in_requirements = False
    for line in lines:
        low = _norm(line)
        if _looks_like_header(line):
            if any(h in low for h in REQUIREMENT_HEADERS):
                in_requirements = True
                # Header can itself contain a skill, so do not continue yet.
            elif any(h in low for h in NON_REQUIREMENT_HEADERS):
                in_requirements = False

        if not _contains_any(line, aliases):
            continue
        if in_requirements or any(marker in low for marker in REQUIREMENT_MARKERS):
            return True

    # Fallback for JDs flattened into paragraphs: stay inside the same sentence/clause
    # so an incidental term does not inherit a requirement marker from a later section.
    chunks = re.split(r"(?:\n+|(?<=[.!?;])\s+|[•▪◦]+)", description or "")
    for chunk in chunks:
        low_chunk = _norm(chunk)
        if not any(marker in low_chunk for marker in REQUIREMENT_MARKERS):
            continue
        if _contains_any(chunk, aliases):
            return True
    return False


def match_job(title: str, description: str, profile: dict, target_titles: list[str] | None = None) -> MatchResult:
    target_titles = target_titles or list((profile.get("career", {}) or {}).get("target_titles", []) or [])
    corpus = profile_corpus(profile)
    text = f"{title}\n{description}"

    matched_all: list[str] = []
    missing_required: list[str] = []
    required_keys: list[str] = []
    mentioned_keys: list[str] = []

    for key, aliases in SKILL_TAXONOMY.items():
        if not _contains_any(text, aliases):
            continue
        mentioned_keys.append(key)
        candidate_has = _contains_any(corpus, aliases)
        if candidate_has:
            matched_all.append(key)

        is_required = _contains_any(title, aliases) or _requirement_mention(description, aliases)
        if is_required:
            required_keys.append(key)
            if not candidate_has:
                missing_required.append(key)

    # Prefer explicit requirement coverage. If the JD has no detectable requirement
    # section, fall back to all recognized skill mentions but reduce confidence.
    scored_keys = required_keys or mentioned_keys
    if scored_keys:
        matched_scored = sum(1 for key in scored_keys if key in matched_all)
        raw_coverage = matched_scored / len(scored_keys)
        # A job cannot get 100% skill confidence from one generic matching phrase.
        # 1 recognized requirement => max 76, 2 => 82, 3 => 88, 4 => 94, 5+ => 100.
        depth_cap = min(100.0, 70.0 + (6.0 * min(len(scored_keys), 5)))
        skill_score = raw_coverage * depth_cap
        if not required_keys:
            skill_score *= 0.92
    else:
        # The taxonomy could not establish enough about the JD; stay conservative.
        skill_score = 58.0

    req_years = _required_years(description)
    years = total_years(profile)
    if req_years is None:
        experience_score = 80.0
    elif years >= req_years:
        experience_score = 100.0
    elif years <= 0:
        experience_score = 50.0
    else:
        experience_score = min(100.0, (years / req_years) * 100.0)

    title_score = _title_score(title, target_titles)
    score = (0.35 * title_score) + (0.50 * skill_score) + (0.15 * experience_score)

    return MatchResult(
        score=round(max(0.0, min(100.0, score)), 1),
        matched_skills=list(dict.fromkeys(matched_all)),
        missing_skills=list(dict.fromkeys(missing_required)),
        title_score=round(title_score, 1),
        skill_score=round(skill_score, 1),
        experience_score=round(experience_score, 1),
    )
