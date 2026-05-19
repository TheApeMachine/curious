from __future__ import annotations

import os
import shutil
import tarfile
import textwrap
from pathlib import Path


def package_project_bundle(
    project_root: Path,
    *,
    bundle_dir: Path,
    include_paths: list[str] | None = None,
) -> Path:
    """Tar minimal project tree for remote training."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    staging = bundle_dir / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    defaults = [
        "python/pyproject.toml",
        "python/src",
        "curious.config.json",
        "spec",
        ".curious/harvest",
        ".curious/state.json",
    ]
    rel_paths = include_paths or defaults

    for rel in rel_paths:
        src = project_root / rel
        dest = staging / rel
        if not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        else:
            shutil.copy2(src, dest)

    archive = bundle_dir / "curious-train-bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(staging, arcname="curious-project")

    shutil.rmtree(staging)
    return archive


def write_remote_run_script(
    bundle_dir: Path,
    *,
    train_shell: str,
    project_subdir: str = "curious-project",
) -> Path:
    """Shell script executed on the Vast instance."""
    script = bundle_dir / "run-remote-train.sh"
    hf_token_line = ""
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        hf_token_line = "export HF_TOKEN=\"${HF_TOKEN:-$HUGGING_FACE_HUB_TOKEN}\""

    script.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/bash
            set -euo pipefail
            {hf_token_line}
            export PIP_DISABLE_PIP_VERSION_CHECK=1
            export PYTHONUNBUFFERED=1
            export HF_HOME=/workspace/.cache/huggingface
            mkdir -p /workspace/job /workspace/curious-output
            cd /workspace/job
            tar -xzf curious-train-bundle.tar.gz
            cd {project_subdir}
            pip install -q -e './python[train]'
            {train_shell}
            EXIT=$?
            mkdir -p /workspace/curious-output
            cp -a .curious/train /workspace/curious-output/ 2>/dev/null || true
            echo "$EXIT" > /workspace/curious-output/exit.code
            exit $EXIT
            """
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script
