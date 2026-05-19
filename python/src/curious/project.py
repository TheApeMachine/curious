from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SPEC_REL = "spec/SPEC.md"
CONFIG_FILENAME = "curious.config.json"
AGENTS_FILENAME = "AGENTS.md"
README_FILENAME = "README.md"


@dataclass
class AgentsDocument:
    path: Path
    rel_path: str
    content: str


@dataclass
class DiscoveredProject:
    project_root: Path
    spec_path: Path
    has_spec: bool
    config_path: Path | None = None


def path_exists(path: Path) -> bool:
    return path.is_file() or path.is_dir()


def resolve_project_at_directory_sync(directory: str | Path) -> DiscoveredProject:
    project_root = Path(directory).resolve()
    spec_path = project_root / DEFAULT_SPEC_REL
    config_path = project_root / CONFIG_FILENAME
    return DiscoveredProject(
        project_root=project_root,
        spec_path=spec_path,
        has_spec=spec_path.is_file(),
        config_path=config_path if config_path.is_file() else None,
    )


def discover_project_in_parents(start_dir: str | Path) -> DiscoveredProject | None:
    directory = Path(start_dir).resolve()
    while True:
        resolved = resolve_project_at_directory_sync(directory)
        if resolved.has_spec:
            return resolved
        if (directory / README_FILENAME).is_file():
            return resolved
        parent = directory.parent
        if parent == directory:
            return None
        directory = parent


def should_discover_parents() -> bool:
    return os.environ.get("CURIOUS_DISCOVER") == "parents"


def load_agents_document(
    project_root: Path, agent_cwd: Path
) -> AgentsDocument | None:
    for candidate in (
        project_root / AGENTS_FILENAME,
        agent_cwd / AGENTS_FILENAME,
    ):
        if candidate.is_file():
            return AgentsDocument(
                path=candidate,
                rel_path=relative_to_root(project_root, candidate),
                content=candidate.read_text(encoding="utf-8"),
            )
    return None


def relative_to_root(project_root: Path, absolute_path: Path) -> str:
    rel = absolute_path.relative_to(project_root)
    return str(rel) if str(rel) != "." else "."


def slug_from_path(project_root: Path) -> str:
    base = project_root.name
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or "project"
