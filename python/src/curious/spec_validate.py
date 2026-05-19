from __future__ import annotations

from pathlib import Path

_BOOTSTRAP_SECTIONS = (
    "# Project spec",
    "## Vision",
    "## Requirements",
    "## Roadmap",
    "## Progress",
    "## Acceptance criteria",
)


def bootstrap_spec_errors(spec_path: Path) -> list[str]:
    """Return human-readable issues if bootstrap did not produce a usable spec."""
    if not spec_path.is_file():
        return [f"missing file: {spec_path}"]

    text = spec_path.read_text(encoding="utf-8").strip()
    if len(text) < 400:
        return [f"{spec_path} is too short — agent likely did not write the full spec"]

    errors: list[str] = []
    for heading in _BOOTSTRAP_SECTIONS:
        if heading not in text:
            errors.append(f"missing section: {heading}")
    return errors
