from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from curious.types import VastGpuProfile

TrainKind = Literal["dpo", "verifier", "grpo", "reviewer"]

DEFAULT_PROFILES: dict[str, VastGpuProfile] = {
    "verifier": VastGpuProfile(
        min_gpu_ram_gb=12,
        max_dph=0.45,
        disk_gb=50,
        preferred_gpus=["RTX_3060", "RTX_3070", "RTX_4060", "RTX_3090"],
    ),
    "reviewer": VastGpuProfile(
        min_gpu_ram_gb=12,
        max_dph=0.45,
        disk_gb=50,
        preferred_gpus=["RTX_3060", "RTX_3070", "RTX_4060", "RTX_3090"],
    ),
    "dpo": VastGpuProfile(
        min_gpu_ram_gb=40,
        max_dph=1.25,
        disk_gb=120,
        preferred_gpus=["RTX_4090", "RTX_3090", "L40", "A6000"],
    ),
    "grpo": VastGpuProfile(
        min_gpu_ram_gb=48,
        max_dph=1.75,
        disk_gb=150,
        preferred_gpus=["RTX_4090", "L40", "A6000", "RTX_6000Ada"],
    ),
}


@dataclass
class TrainJobSpec:
    kind: TrainKind
    shell_command: str
    profile: VastGpuProfile
    label: str
    remote_output_dir: str = "/workspace/curious-output"
