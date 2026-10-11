from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .models import Job
from .applicant_parser import parse_applicant_text

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


class LinkedInGuestClient:
    """Best-effort public/guest collector.

    No login, cookie theft, CAPTCHA bypass, or stealth/evasion logic. The guest
    endpoint can change or become unavailable; debug mode records the response
    so failures are visible instead of silently returning zero jobs.
    """

    def __init__(self, delay_seconds: float = 1.5, timeout: int = 20, debug_dir: str | Path | None = None):
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.debug_dir = Path(debug_dir) if debug_dir else None
        if self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.last_url = ""
        self.last_status = None
        self.last_html_size = 0

    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        r = self.session.get(url, params=params, timeout=self.timeout)
        self.last_url = r.url
        self.last_status = r.status_code
        self.last_html_size = len(r.text or "")
        if r.status_code == 429:
            raise RuntimeError("LinkedIn returned HTTP 429. Stop and retry later; this PoC does not bypass rate limits.")
        r.raise_for_status()
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return r

    @staticmethod
    def _job_id_from_link(href: str) -> str | None:
        if not href:
            return None
        path = urlparse(href).path
        m = re.search(r"/jobs/view/(?:[^/]*-)?(\d+)(?:/|$)", path)
        return m.group(1) if m else None

    def _save_debug(self, name: str, html: str) -> None:
        if not self.debug_dir:
            return
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)[:120]
        (self.debug_dir / f"{safe}.html").write_text(html, encoding="utf-8", errors="ignore")

    def search(self, keyword: str, location: str, posted_hours: int = 24, remote_only: bool = True, pages: int = 1):
        found: dict[str, Job] = {}
        for page in range(max(1, pages)):
            params = {
                "keywords": keyword,
                "location": location,
                "start": page * 25,
                "f_TPR": f"r{posted_hours * 3600}",
            }
            if remote_only:
                params["f_WT"] = "2"
            html = self._get(SEARCH_URL, params=params).text
            lower = html.lower()
            if any(marker in lower for marker in ("authwall", "captcha", "challenge")):
                self._save_debug(f"blocked_{keyword}_{location}_{page}", html)
                raise RuntimeError(
                    "LinkedIn returned an authwall/challenge page. See data/debug for the captured HTML; "
                    "this PoC does not bypass access controls."
                )

            soup = BeautifulSoup(html, "html.parser")
            links = soup.select("a[href*='/jobs/view/']")
            for link in links:
                href = link.get("href", "")
                jid = self._job_id_from_link(href)
                if not jid:
                    continue
                card = link.find_parent("li") or link.find_parent("div", class_=re.compile(r"(?:base-card|job-search-card)")) or link.parent
                urn = card.get("data-entity-urn", "") if hasattr(card, "get") else ""
                m = re.search(r"jobPosting:(\d+)", urn or "")
                if m:
                    jid = m.group(1)

                title_el = card.select_one("h3.base-search-card__title, h3") if hasattr(card, "select_one") else None
                company_el = card.select_one("h4.base-search-card__subtitle, h4") if hasattr(card, "select_one") else None
                loc_el = card.select_one("span.job-search-card__location") if hasattr(card, "select_one") else None
                time_el = card.select_one("time") if hasattr(card, "select_one") else None

                title = title_el.get_text(" ", strip=True) if title_el else link.get_text(" ", strip=True)
                found[jid] = Job(
                    job_id=jid,
                    title=title,
                    company=company_el.get_text(" ", strip=True) if company_el else "",
                    location=loc_el.get_text(" ", strip=True) if loc_el else location,
                    url=href or f"https://www.linkedin.com/jobs/view/{jid}",
                    posted_at=time_el.get("datetime") if time_el else None,
                )

            if not links:
                self._save_debug(f"zero_links_{keyword}_{location}_{page}", html)
        return list(found.values())

    def enrich(self, job: Job, applicant_limit: int = 100) -> Job:
        html = self._get(DETAIL_URL.format(job_id=job.job_id)).text
        soup = BeautifulSoup(html, "html.parser")
        desc = soup.select_one(".show-more-less-html__markup, .description__text")
        job.description = desc.get_text("\n", strip=True) if desc else ""
        app = soup.select_one(".num-applicants__caption, .num-applicants__text")
        if app:
            job.applicant_text = app.get_text(" ", strip=True)
        else:
            text = soup.get_text(" ", strip=True)
            m = re.search(
                r"(?:(?:Over|More than)\s+\d+|\d+)\s+(?:applicants|people clicked apply|people have clicked apply)",
                text,
                flags=re.I,
            )
            job.applicant_text = m.group(0) if m else ""
        info = parse_applicant_text(job.applicant_text, applicant_limit)
        job.applicants = info.count
        job.applicants_under_limit = info.under_limit
        return job
