from __future__ import annotations

import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

from curious.types import ResolvedConfig
from curious.vast.remote import run_vast_training
from curious.types import VastConfig, VastGpuProfile
from curious.vast.types import DEFAULT_PROFILES, TrainJobSpec


def should_use_vast(
    config: ResolvedConfig,
    *,
    force_vast: bool | None = None,
    force_local: bool = False,
) -> bool:
    if force_local:
        return False
    if force_vast is True:
        return True
    vast_cfg = config.vast
    return vast_cfg.enabled if vast_cfg else False


def profile_for_kind(config: ResolvedConfig, kind: str) -> VastGpuProfile:
    vast_cfg = config.vast or VastConfig()
    if vast_cfg.profiles and kind in vast_cfg.profiles:
        return vast_cfg.profiles[kind]
    if kind in DEFAULT_PROFILES:
        return DEFAULT_PROFILES[kind]
    return DEFAULT_PROFILES["dpo"]


def build_train_shell_command(
    kind: str,
    config_path: str | None,
    **flags: Any,
) -> str:
    parts = ["curious-py", "train", kind, "--local"]
    if config_path:
        parts.extend(["-c", shlex.quote(config_path)])
    for key, value in flags.items():
        if value is None:
            continue
        flag = key if key.startswith("--") else "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                parts.append(flag)
        else:
            parts.extend([flag, shlex.quote(str(value))])
    return " ".join(parts)


def dispatch_training(
    config: ResolvedConfig,
    *,
    kind: str,
    label: str,
    local_runner: Callable[[], None],
    config_path: str | None = None,
    force_vast: bool | None = None,
    force_local: bool = False,
    train_flags: dict[str, Any] | None = None,
) -> None:
    """
    Run training locally or on Vast.ai (cheapest matching offer).
    Remote runs re-invoke `curious-py train <kind> --local` on the instance.
    """
    if not should_use_vast(config, force_vast=force_vast, force_local=force_local):
        local_runner()
        return

    vast_cfg = config.vast or VastConfig()
    profile = profile_for_kind(config, kind)
    shell = build_train_shell_command(kind, config_path, **(train_flags or {}))

    job = TrainJobSpec(
        kind=kind,  # type: ignore[arg-type]
        shell_command=shell,
        profile=profile,
        label=label,
    )
    run_vast_training(
        project_root=Path(config.project_root),
        vast_cfg=vast_cfg,
        job=job,
    )
