from __future__ import annotations

from pathlib import Path
from jinja2 import Template
from pypdf import PdfReader

from .profile_adapter import current_title, identity, resume_path


RESUME_TEMPLATE = Template("""# {{ name }}
{{ headline }}

{{ contact }}

## Professional Summary
{{ summary }}

## Relevant Skills
{% for s in skills %}- {{ s }}
{% endfor %}
## Verified Evidence Added For This Role
{% if evidence %}{% for e in evidence %}- {{ e }}
{% endfor %}{% else %}- No new claims added; using existing master-resume evidence only.
{% endif %}
---
Source master resume: {{ master_resume }}
""")


def extract_pdf_text(pdf_path: str, out_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(text, encoding="utf-8")
    return text


def render_tailored_resume(profile: dict, job_title: str, matched_skills: list[str], confirmed_evidence: list[str], out_path: str) -> str:
    ident = identity(profile)
    name = ident.get("full_name") or f"{ident.get('first_name','')} {ident.get('last_name','')}".strip()
    contact_bits = [ident.get("email", ""), ident.get("phone", ""), ident.get("city", ""), ident.get("country", ""), ident.get("linkedin", "")]
    skill_labels = [s.replace("_", " ").title() for s in matched_skills]
    base_summary = str((profile.get("professional_summary", {}) or {}).get("summary") or "")
    summary = base_summary or f"{current_title(profile) or 'Professional'} targeting {job_title}. This draft only includes skills backed by verified profile facts."
    text = RESUME_TEMPLATE.render(
        name=name,
        headline=job_title,
        contact=" | ".join(x for x in contact_bits if x),
        summary=summary,
        skills=skill_labels,
        evidence=confirmed_evidence,
        master_resume=resume_path(profile),
    )
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p)
