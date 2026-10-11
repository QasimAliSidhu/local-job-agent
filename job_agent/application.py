from __future__ import annotations

import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

from .profile_adapter import answers, identity


def detect_ats(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "greenhouse" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    if "workday" in host or "myworkdayjobs.com" in host:
        return "workday"
    if "linkedin.com" in host:
        return "linkedin"
    return "generic"


def _answer_for_label(label: str, profile: dict) -> str | None:
    l = re.sub(r"\s+", " ", label.lower()).strip()
    p = identity(profile)
    a = answers(profile)
    mappings = [
        (("first name", "given name"), p.get("first_name")),
        (("last name", "family name", "surname"), p.get("last_name")),
        (("email", "e-mail"), p.get("email")),
        (("phone", "mobile"), p.get("phone")),
        (("city",), p.get("city")),
        (("country",), p.get("country")),
        (("linkedin",), p.get("linkedin")),
        (("portfolio", "website"), p.get("portfolio")),
        (("github",), p.get("github")),
        (("notice period",), a.get("notice_period")),
        (("expected salary", "salary expectation", "expected compensation"), a.get("expected_compensation")),
    ]
    for needles, value in mappings:
        if value and any(n in l for n in needles):
            return str(value)
    return None


async def autofill_external(
    url: str,
    profile: dict,
    resume_path: str,
    submit: bool = False,
    user_data_dir: str = "browser-profile",
    pause_for_review: bool = True,
) -> dict:
    """Visible Playwright autofill for external ATS pages.

    No CAPTCHA solving, stealth plugins, fingerprint spoofing, or access-control bypasses.
    """
    from playwright.async_api import async_playwright

    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    result = {"filled": [], "unknown": [], "submitted": False}
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(user_data_dir, headless=False)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")

        for el in await page.locator("input:not([type=hidden]):not([type=file]), textarea").all():
            try:
                if not await el.is_visible() or await el.is_disabled():
                    continue
                label_parts = [
                    await el.get_attribute("aria-label"),
                    await el.get_attribute("placeholder"),
                    await el.get_attribute("name"),
                    await el.get_attribute("id"),
                ]
                eid = await el.get_attribute("id")
                if eid:
                    lab = page.locator(f"label[for='{eid}']")
                    if await lab.count():
                        label_parts.append(await lab.first.inner_text())
                label = " ".join(x for x in label_parts if x)
                answer = _answer_for_label(label, profile)
                if answer:
                    await el.fill(answer)
                    result["filled"].append(label.strip()[:120])
                else:
                    t = (await el.get_attribute("type") or "text").lower()
                    if t not in {"checkbox", "radio", "submit", "button"}:
                        result["unknown"].append(label.strip()[:120] or "unlabelled field")
            except Exception:
                continue

        if resume_path and Path(resume_path).exists():
            files = page.locator("input[type=file]")
            file_count = await files.count()
            for i in range(file_count):
                el = files.nth(i)
                try:
                    label = " ".join(filter(None, [
                        await el.get_attribute("name"),
                        await el.get_attribute("aria-label"),
                        await el.get_attribute("id"),
                    ])).lower()
                    if "resume" in label or "cv" in label or file_count == 1:
                        await el.set_input_files(str(Path(resume_path).resolve()))
                        result["filled"].append("resume upload")
                        break
                except Exception:
                    pass

        if result["unknown"]:
            submit = False

        if submit:
            buttons = page.get_by_role("button", name=re.compile(r"^(submit|submit application|apply)$", re.I))
            if await buttons.count():
                await buttons.first.click()
                result["submitted"] = True

        if pause_for_review:
            print("Browser is open for review. Unknown fields automatically prevented auto-submit.")
            await asyncio.to_thread(input, "Press Enter here when you are finished reviewing the browser... ")
        await context.close()
    return result
