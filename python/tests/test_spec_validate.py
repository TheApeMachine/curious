from __future__ import annotations

import tempfile
from pathlib import Path

from curious.spec_validate import bootstrap_spec_errors


def test_bootstrap_spec_errors_missing_file() -> None:
    assert bootstrap_spec_errors(Path("/nonexistent/SPEC.md"))


def test_bootstrap_spec_errors_incomplete() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "SPEC.md"
        spec.write_text(
            "# Project spec\n\n## Vision\n\n" + ("x" * 500),
            encoding="utf-8",
        )
        errors = bootstrap_spec_errors(spec)
        assert any("Requirements" in e for e in errors)


def test_bootstrap_spec_errors_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "SPEC.md"
        spec.write_text(
            "\n".join(
                [
                    "# Project spec",
                    "## Vision",
                    "x" * 500,
                    "## Requirements",
                    "- [ ] R1",
                    "## Roadmap",
                    "### Phase 1",
                    "- [ ] T1.1",
                    "## Progress",
                    "## Acceptance criteria",
                ]
            ),
            encoding="utf-8",
        )
        assert bootstrap_spec_errors(spec) == []
