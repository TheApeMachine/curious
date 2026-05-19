from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from curious.types import LlmConfig

RULES_FILE = ".curious/scanner_rules.json"


@dataclass
class ScannerRule:
    rule_id: str
    description: str
    file_glob: str
    forbidden_regex: str | None
    required_regex: str | None
    severity: Literal["fail", "warn"]
    source_spec_sha: str

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class RuleViolation:
    rule_id: str
    path: str
    message: str
    severity: Literal["fail", "warn"]


def load_rules(project_root: Path) -> list[ScannerRule]:
    path = project_root / RULES_FILE
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ScannerRule(
            rule_id=r["rule_id"],
            description=r["description"],
            file_glob=r["file_glob"],
            forbidden_regex=r.get("forbidden_regex"),
            required_regex=r.get("required_regex"),
            severity=r.get("severity", "fail"),
            source_spec_sha=r.get("source_spec_sha", ""),
        )
        for r in data.get("rules", [])
    ]


def save_rules(project_root: Path, rules: list[ScannerRule]) -> None:
    path = project_root / RULES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"rules": [r.to_json() for r in rules]}, indent=2) + "\n",
        encoding="utf-8",
    )


def _extract_rule_candidates(spec_diff: str) -> list[str]:
    """Heuristic: lines that look like declarative constraints."""
    candidates = []
    for line in spec_diff.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            text = line[1:].strip()
            if re.search(
                r"\b(must not|no |forbidden|required|only |never |shall not)\b",
                text,
                re.I,
            ):
                candidates.append(text)
    return candidates


def synthesize_rules(
    spec_diff: str,
    spec_sha: str,
    cycle: int,
    llm: LlmConfig,
) -> list[ScannerRule]:
    """Compile spec diff prose into deterministic scanner rules (LLM-assisted)."""
    candidates = _extract_rule_candidates(spec_diff)
    if not candidates:
        return []

    try:
        from curious.harness.providers import create_chat_provider
        from curious.llm_resolve import resolve_llm_for_harness

        llm = resolve_llm_for_harness(llm)
        provider = create_chat_provider(llm)
        prompt = (
            "Convert these spec constraint lines into JSON scanner rules. "
            "Each rule: rule_id, description, file_glob, forbidden_regex or required_regex, severity.\n"
            "Output JSON array only.\n\n"
            + "\n".join(f"- {c}" for c in candidates[:20])
        )
        completion = provider.complete(
            [{"role": "user", "content": prompt}],
            [],
        )
        text = completion.content or "[]"
        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            return []
        raw_rules = json.loads(m.group(0))
    except Exception:
        return _heuristic_rules(candidates, spec_sha, cycle)

    rules: list[ScannerRule] = []
    for i, r in enumerate(raw_rules):
        if not isinstance(r, dict):
            continue
        rules.append(
            ScannerRule(
                rule_id=r.get("rule_id") or f"SR-{cycle}-{i}",
                description=r.get("description", ""),
                file_glob=r.get("file_glob", "**/*"),
                forbidden_regex=r.get("forbidden_regex"),
                required_regex=r.get("required_regex"),
                severity=r.get("severity", "fail"),
                source_spec_sha=spec_sha,
            )
        )
    return rules


def _heuristic_rules(candidates: list[str], spec_sha: str, cycle: int) -> list[ScannerRule]:
    rules: list[ScannerRule] = []
    for i, text in enumerate(candidates[:10]):
        glob = "**/*"
        m = re.search(r"`([^`]+)`", text)
        if m:
            glob = f"**/{m.group(1)}"
        forbidden = None
        if re.search(r"\bno\b|\bforbidden\b|\bmust not\b", text, re.I):
            forbidden = r".+"
        rules.append(
            ScannerRule(
                rule_id=f"SR-{cycle}-{i}",
                description=text[:200],
                file_glob=glob,
                forbidden_regex=forbidden,
                required_regex=None,
                severity="fail",
                source_spec_sha=spec_sha,
            )
        )
    return rules


def _glob_match(path: str, pattern: str) -> bool:
    from fnmatch import fnmatch

    return fnmatch(path.replace("\\", "/"), pattern.replace("\\", "/"))


def check_rules(workspace: Path, rules: list[ScannerRule]) -> list[RuleViolation]:
    violations: list[RuleViolation] = []
    for rule in rules:
        for file_path in workspace.rglob("*"):
            if not file_path.is_file():
                continue
            rel = str(file_path.relative_to(workspace))
            if not _glob_match(rel, rule.file_glob):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if rule.forbidden_regex and re.search(rule.forbidden_regex, content):
                violations.append(
                    RuleViolation(
                        rule_id=rule.rule_id,
                        path=rel,
                        message=rule.description,
                        severity=rule.severity,
                    )
                )
            if rule.required_regex and not re.search(rule.required_regex, content):
                violations.append(
                    RuleViolation(
                        rule_id=rule.rule_id,
                        path=rel,
                        message=f"Missing required pattern: {rule.description}",
                        severity=rule.severity,
                    )
                )
    return violations


def format_violations_for_prompt(violations: list[RuleViolation]) -> str:
    if not violations:
        return ""
    lines = ["## Scanner rule violations (deterministic)", ""]
    for v in violations[:30]:
        lines.append(f"- [{v.severity}] {v.rule_id} `{v.path}`: {v.message}")
    return "\n".join(lines)
