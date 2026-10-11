from __future__ import annotations

import re


POSITIVE_PATTERNS = [
    r"work\s+from\s+anywhere",
    r"remote\s+worldwide",
    r"worldwide\s+remote",
    r"anywhere\s+in\s+the\s+world",
    r"global(?:ly)?\s+remote",
    r"location\s+independent",
    r"open\s+to\s+candidates\s+worldwide",
    r"pakistan",
]

NEGATIVE_PATTERNS = [
    (r"must\s+(?:be|reside|live|located)\s+in\s+(?:the\s+)?united\s+states", "US residency required"),
    (r"(?:us|u\.s\.)\s+(?:residents|candidates)\s+only", "US-only"),
    (r"must\s+(?:be|reside|live|located)\s+in\s+canada", "Canada residency required"),
    (r"canada(?:-based)?\s+candidates\s+only", "Canada-only"),
    (r"must\s+(?:be|reside|live|located)\s+in\s+(?:the\s+)?united\s+kingdom", "UK residency required"),
    (r"uk\s+(?:residents|candidates)\s+only", "UK-only"),
    (r"must\s+(?:be|reside|live|located)\s+in\s+india", "India residency required"),
    (r"india(?:-based)?\s+candidates\s+only", "India-only"),
    (r"(?:eu|european\s+union)\s+(?:residents|candidates)\s+only", "EU-only"),
    (r"must\s+have\s+(?:unrestricted\s+)?(?:us|u\.s\.)\s+work\s+authorization", "US work authorization required"),
    (r"no\s+(?:visa\s+)?sponsorship", "No sponsorship offered"),
]


def classify_pakistan_eligibility(description: str, location: str = "") -> tuple[str, str]:
    text = f"{location}\n{description}".lower()

    # Strong explicit Pakistan/worldwide language wins unless there is a direct contradiction.
    positives = [p for p in POSITIVE_PATTERNS if re.search(p, text, flags=re.I)]
    negatives = [(p, reason) for p, reason in NEGATIVE_PATTERNS if re.search(p, text, flags=re.I)]

    if negatives:
        # If Pakistan is explicitly permitted, treat contradictory boilerplate as unclear.
        if re.search(r"\bpakistan\b", text) and positives:
            return "unclear", f"Pakistan/worldwide language found, but restriction also found: {negatives[0][1]}"
        return "ineligible", negatives[0][1]

    if positives:
        if re.search(r"\bpakistan\b", text):
            return "eligible", "Pakistan is explicitly mentioned as an allowed location"
        return "likely_eligible", "Worldwide/location-independent remote language found"

    # Remote labels attached to a country are not enough to infer cross-border eligibility.
    return "unclear", "No explicit Pakistan/worldwide eligibility or exclusion found"
