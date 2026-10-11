from __future__ import annotations

import os
from pathlib import Path


def find_project_root() -> Path:
    """Find the job-agent project directory.

    Priority:
    1) JOB_AGENT_HOME
    2) cwd and its parents (lets installed `job-agent` work from config/ etc.)
    3) source checkout containing this package
    """
    env = os.getenv("JOB_AGENT_HOME")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser().resolve())

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])
    candidates.append(Path(__file__).resolve().parent.parent)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "config").is_dir() and (
            (candidate / "job_agent").is_dir() or (candidate / "pyproject.toml").exists()
        ):
            return candidate

    return Path(__file__).resolve().parent.parent
