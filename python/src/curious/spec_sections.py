from __future__ import annotations

import re


def extract_spec_section(body: str, heading: str) -> str | None:
    escaped = re.escape(heading)
    start = re.search(rf"^{escaped}\s*$", body, re.M)
    if not start:
        return None
    after = body[start.end() :]
    nxt = re.search(r"^## ", after, re.M)
    section = after[: nxt.start()] if nxt else after
    trimmed = section.strip()
    return trimmed if trimmed else None


def strip_spec_section(body: str, heading: str) -> str:
    escaped = re.escape(heading)
    pattern = rf"^{escaped}\s*$[\s\S]*?(?=^## |\Z)"
    out = re.sub(pattern, "", body, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", out).strip()
