from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ApplicantInfo:
    count: Optional[int]
    under_limit: Optional[bool]
    display: str


def parse_applicant_text(text: str, limit: int = 100) -> ApplicantInfo:
    raw = " ".join((text or "").split())
    low = raw.lower()
    if not low:
        return ApplicantInfo(None, None, "unknown")

    over = re.search(r"(?:over|more than)\s+(\d+)\s+(?:applicants|people)", low)
    if over:
        n = int(over.group(1))
        return ApplicantInfo(None, n < limit, f">{n}")

    exact = re.search(r"(?:^|\b)(\d{1,5})\s+(?:applicants|people clicked apply|people have clicked apply)\b", low)
    if exact:
        n = int(exact.group(1))
        return ApplicantInfo(n, n < limit, str(n))

    first = re.search(r"(?:among|be among)\s+the\s+first\s+(\d{1,5})\s+applicants", low)
    if first:
        n = int(first.group(1))
        # This wording only proves the count has not exceeded the displayed threshold yet.
        return ApplicantInfo(None, n <= limit, f"<{n}")

    return ApplicantInfo(None, None, raw[:80] or "unknown")
