from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

VerdictOverall = Literal["PASS", "FAIL"]

VERDICT_FENCE = re.compile(r"```review-verdict\s*([\s\S]*?)```", re.I)


@dataclass
class ReviewVerdict:
    overall: VerdictOverall
    criteria: dict[str, Literal["PASS", "FAIL"]]
    blocking_issues: list[str]
    evidence: list[str]
    next_develop: str | None = None


def parse_review_verdict(summary: str | None) -> ReviewVerdict | None:
    if not summary or not summary.strip():
        return None
    m = VERDICT_FENCE.search(summary)
    body = m.group(1) if m else _try_unfenced_verdict(summary)
    if not body:
        return None
    overall_m = re.search(r"OVERALL:\s*(PASS|FAIL)", body, re.I)
    if not overall_m:
        return None
    overall = overall_m.group(1).upper()  # type: ignore[assignment]
    criteria: dict[str, Literal["PASS", "FAIL"]] = {}
    for line in body.split("\n"):
        cm = re.match(r"^(\d+_[\w]+):\s*(PASS|FAIL)", line, re.I)
        if cm:
            criteria[cm.group(1)] = cm.group(2).upper()  # type: ignore[assignment]
    return ReviewVerdict(
        overall=overall,
        criteria=criteria,
        blocking_issues=_parse_list_section(body, "blocking_issues"),
        evidence=_parse_list_section(body, "evidence"),
        next_develop=_parse_scalar_section(body, "next_develop"),
    )


def extract_task_id(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    m = re.search(r"\b(T\d+\.\d+|M\d+)\b", text)
    return m.group(1) if m else None


def _try_unfenced_verdict(summary: str) -> str | None:
    if not re.search(r"OVERALL:\s*(PASS|FAIL)", summary, re.I):
        return None
    return summary


def _is_section_header(line: str) -> bool:
    return bool(re.match(r"^\s*[\w][\w_]*:\s*(\S.*)?$", line)) and not re.match(
        r"^\s*[-*]", line
    )


def _parse_list_section(body: str, key: str) -> list[str]:
    lines = body.split("\n")
    header_index = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^\s*{key}:\s*$", ln, re.I)),
        -1,
    )
    if header_index == -1:
        return []
    items: list[str] = []
    for line in lines[header_index + 1 :]:
        if _is_section_header(line):
            break
        item = re.sub(r"^\s*[-*]\s*", "", line).strip()
        if item and item != "-" and not re.match(r"^none$", item, re.I):
            items.append(item)
    return items


def _parse_scalar_section(body: str, key: str) -> str | None:
    lines = body.split("\n")
    header_index = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^\s*{key}:\s*$", ln, re.I)),
        -1,
    )
    if header_index == -1:
        return None
    for line in lines[header_index + 1 :]:
        trimmed = line.strip()
        if not trimmed:
            continue
        if _is_section_header(line):
            break
        value = re.sub(r"^[-*]\s*", "", trimmed).strip()
        if value and value != "-" and not re.match(r"^none$", value, re.I):
            return value
    return None
