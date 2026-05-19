from __future__ import annotations

import re

from curious.spec_sections import extract_spec_section, strip_spec_section
from curious.types import Phase
from curious.workflow_policy import sanitize_steering

AGENT_STEERING_HEADING = "## Agent steering"

PHASE_SUBSECTION: dict[Phase, str | None] = {
    "develop": "Developer",
    "review": "Reviewer",
    "sync": "Sync",
    "overseer": None,
}

NOOP_STEERING = re.compile(
    r"^(none|n/a|—|-|\.\.\.|not applicable|no active steering|no steering needed)$",
    re.I,
)
BOILERPLATE_LINE = re.compile(
    r"^(overseer-maintained|injected into|optional\.|_optional|<!--)",
    re.I,
)


def _is_actionable_steering(text: str) -> bool:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    substantive = []
    for line in lines:
        body = re.sub(r"^[-*]\s*", "", line).strip()
        if not body or NOOP_STEERING.match(body) or BOILERPLATE_LINE.match(body):
            continue
        if body.startswith("_") and body.endswith("_"):
            continue
        if body.startswith("(") and body.endswith(")"):
            continue
        substantive.append(body)
    return len(substantive) > 0


def _extract_subsection(section: str, title: str) -> str | None:
    pattern = rf"^### {re.escape(title)}\s*$([\s\S]*?)(?=^### |\Z)"
    m = re.search(pattern, section, re.M)
    if not m:
        return None
    trimmed = m.group(1).strip()
    if not trimmed or not _is_actionable_steering(trimmed):
        return None
    return trimmed


def agent_steering_for_phase(spec_body: str, phase: Phase) -> str | None:
    if phase == "overseer":
        return None
    section = extract_spec_section(spec_body, AGENT_STEERING_HEADING)
    if not section:
        return None
    subsection_title = PHASE_SUBSECTION.get(phase)
    if subsection_title:
        phase_specific = _extract_subsection(section, subsection_title)
        if phase_specific:
            text, _ = sanitize_steering(phase_specific)
            return text if text.strip() and _is_actionable_steering(text) else None
        if re.search(r"^### ", section, re.M):
            return None
    if _is_actionable_steering(section):
        text, _ = sanitize_steering(section)
        return text if _is_actionable_steering(text) else None
    return None


def strip_agent_steering(spec_body: str) -> str:
    return strip_spec_section(spec_body, AGENT_STEERING_HEADING)


def format_steering_prompt_block(phase: Phase, steering: str) -> str:
    role = PHASE_SUBSECTION.get(phase) or phase
    return (
        f"## Agent steering (overseer → {role})\n\n"
        "Corrective guidance from the overseer — follow in addition to AGENTS.md and the spec.\n\n"
        f"{steering.strip()}"
    )
