from __future__ import annotations

import platform
import re

FORBIDDEN_STEERING_LINE = re.compile(
    r"\b(git add|git commit|commit first|must commit|you must commit|leave changes staged for human)\b"
    r"|\bworktree\b|github actions?\b|\bCI artifact\b|paste amd64|amd64\+avx512"
    r"|branch[- ]tip.*\bHEAD\b|uncommitted.*\bHEAD\b|pasted amd64",
    re.I,
)


def host_arch_label() -> str:
    return platform.machine().lower()


def is_arm64_host() -> bool:
    return host_arch_label() in ("arm64", "aarch64")


def sanitize_steering(text: str) -> tuple[str, int]:
    lines = text.split("\n")
    kept: list[str] = []
    stripped = 0
    for line in lines:
        body = re.sub(r"^[-*]\s*", "", line).strip()
        if body and FORBIDDEN_STEERING_LINE.search(body):
            stripped += 1
            continue
        kept.append(line)
    joined = "\n".join(kept).strip()
    if stripped > 0 and not joined:
        return "", stripped
    if stripped > 0:
        return (
            joined
            + f"\n\n_(Curious omitted {stripped} steering line(s) that required commits, CI, worktrees, or amd64-on-arm proof.)_",
            stripped,
        )
    return joined, 0


SOURCE_OF_TRUTH_SECTION = """### When in doubt — read the files

**Source of truth is on-disk content**, not prior chat, orchestrator history, review summaries, `git log` messages, or assumptions about `HEAD`.

- Unclear whether work landed, what changed, or if the spec/AGENTS.md allows something → **read** the paths and cite **file:line** evidence.
- Conflicts between a summary and the tree → **trust the files**.
- Do not FAIL or block on claims you have not verified in the working tree."""

REVIEW_FAIL_WORKFLOW_NOTE = """**Workflow override:** Ignore prior blocking issues that only demand **git commit**, **branch-tip == HEAD**, **GitHub Actions / CI artifacts**, **worktrees**, or **amd64 test output on an arm64 host**. Satisfy code and host-runnable test requirements in the working tree instead. If a prior claim is unclear, **read the files** — on-disk content is the source of truth."""

WORKFLOW_SPEC_CONSTRAINTS = (
    "Human commits only; agents must not run mutating git commands. "
    "Agents verify on the local host architecture only (no CI required for review PASS). "
    "On arm64, amd64-tagged tests are optional for agent review; host-runnable tests and code inspection suffice. "
    "When uncertain, read source files and git diff — file content is the source of truth."
)


def build_workflow_policy_section(host_arch: str) -> str:
    if host_arch in ("arm64", "aarch64"):
        host_note = (
            "\n**This run is on arm64.** Tests behind `//go:build amd64` (or OS=linux GOARCH=amd64) "
            "are **not** required to execute here. Verify via host-runnable tests, file inspection, and `git diff`."
        )
    elif host_arch in ("x64", "amd64", "x86_64"):
        host_note = (
            f"\n**This run is on {host_arch}.** Run amd64-tagged tests when present; still do not require CI or agent commits."
        )
    else:
        host_note = (
            f"\n**Host architecture:** `{host_arch}`. Run only tests that execute on this machine."
        )

    return f"""## Workflow (binding — human + host)

**Curious host:** `{host_arch}`{host_note}

### Commits (human only)

- The **human** commits, pushes, and manages branches — **not** agents.
- Judge deliverables from the **working tree** (`git diff`, `git status`, file reads). **Uncommitted** fixes are valid.
- **Do not** FAIL review because changes are not committed or not on `HEAD`.
- **Do not** tell the developer to `git add`, `git commit`, use **worktrees**, or wait for a commit.
- Agents use **read-only** git only (see Git policy).

### Verification (this machine only)

- Develop and review run tests **on this host** — no GitHub Actions, no CI URLs.
- **5_verification: PASS** when host-runnable tests pass and implementation is in the working tree.
- **5_verification: FAIL** only for wrong/missing code or failing host tests — **not** for missing amd64-only output on arm64.

{SOURCE_OF_TRUTH_SECTION}"""
