# Changelog

## 0.2.2
- Make Support Engineering the primary job family for Qasim.
- Keep AI automation/integration roles as secondary discovery targets.
- Use primary titles (not all discovery titles) for role-family match scoring.
- Improve title matching so generic words such as `Senior` and `Engineer` do not make unrelated roles look like strong title matches.
- Add a priority-aware query planner: primary titles are spread across priority locations before secondary/exploratory searches consume the query budget.
- Preserve the newest AI Automation & Integration resume as the default application resume.

## 0.2.1
- Add compatibility with personalized nested `search.yaml` and grouped-skill `profile.yaml`.
- Add `doctor` and debug diagnostics.

## 0.2.3 - Strict shortlist + requirement-aware matching

- Enforces the configured applicant cap in the default `list` and `clarify` flows.
- Default shortlist now requires Pakistan eligibility to be `eligible` or `likely_eligible`.
- Added `list --review` / `clarify --review` for unknown applicant counts or unclear Pakistan eligibility.
- Added `list --all` as a diagnostic view that can show known over-limit jobs.
- Added an application gate: `apply` refuses low-score, over/unknown-applicant, or unclear/ineligible jobs unless `--force` is intentionally supplied.
- Reduced 97-100% score saturation by requiring deeper recognized JD evidence before assigning near-perfect skill scores.
- Missing-skill clarification now uses requirement context (Requirements/Qualifications/must-have/etc.) instead of asking about every incidental word in a JD.
- Fixed token matching so `java` does not match `javascript`.
- Expanded support-role taxonomy for Linux/UNIX, Windows/IIS, networking, Microsoft 365, ERP/CRM, contact center, Java, .NET, and several common specialized support stacks/domains.
- Added resume-supported Linux, logs/stack traces, ERP/CRM, contact-center, network-diagnostic and database-troubleshooting evidence to Qasim's personalized profile.
