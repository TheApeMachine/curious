from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from curious.vast import bundle, instance
from curious.vast.client import create_client
from curious.vast.offers import select_cheapest_offer
from curious.types import VastConfig
from curious.vast.types import TrainJobSpec


def run_vast_training(
    *,
    project_root: Path,
    vast_cfg: VastConfig,
    job: TrainJobSpec,
) -> None:
    """Provision cheapest suitable GPU, run training, sync outputs back, destroy."""
    vast = create_client(vast_cfg.api_key)
    profile = job.profile

    work_dir = project_root / ".curious" / "vast" / "jobs" / job.label
    work_dir.mkdir(parents=True, exist_ok=True)

    archive = bundle.package_project_bundle(project_root, bundle_dir=work_dir)
    run_script = bundle.write_remote_run_script(
        work_dir,
        train_shell=job.shell_command,
    )

    bootstrap = (
        "mkdir -p /workspace/job && "
        "echo 'waiting for job upload from curious-py...' > /workspace/job/BOOTING"
    )

    offer = select_cheapest_offer(
        vast,
        profile,
        max_dph=vast_cfg.max_dph,
        interruptible=vast_cfg.interruptible,
    )
    contract_id = instance.create_training_instance(
        vast,
        offer,
        vast_cfg=vast_cfg,
        profile=profile,
        label=f"{vast_cfg.label_prefix}-{job.label}",
        bootstrap_cmd=bootstrap,
    )

    inst = None
    try:
        inst = instance.wait_for_ssh(
            vast,
            contract_id,
            timeout_sec=vast_cfg.ssh_timeout_sec,
        )
        host, port = instance.ssh_endpoint(inst)

        print(f"[curious] vast: uploading bundle to root@{host}:{port}")
        instance.scp(host=host, port=port, local_path=str(archive), remote_path="/workspace/job/")
        instance.scp(host=host, port=port, local_path=str(run_script), remote_path="/workspace/job/run-remote-train.sh")

        print("[curious] vast: starting remote training")
        exit_code = instance.ssh_run(
            host=host,
            port=port,
            command="bash /workspace/job/run-remote-train.sh",
            timeout_sec=vast_cfg.train_timeout_sec,
        )

        local_out = project_root / ".curious" / "train-remote" / job.label
        local_out.mkdir(parents=True, exist_ok=True)
        try:
            instance.scp(
                host=host,
                port=port,
                local_path=str(local_out) + "/",
                remote_path="/workspace/curious-output/",
                recursive=True,
            )
        except subprocess.CalledProcessError:
            print("[curious] vast: warning — could not download all outputs")

        _merge_remote_outputs(local_out, project_root)

        if exit_code != 0:
            raise RuntimeError(f"Remote training exited with code {exit_code}")

        print(f"[curious] vast: training complete — outputs under {local_out}")

    finally:
        if vast_cfg.auto_destroy and contract_id:
            try:
                instance.destroy_instance(vast, contract_id)
            except Exception as exc:
                print(f"[curious] vast: destroy failed ({exc}) — stop instance {contract_id} manually")


def _merge_remote_outputs(remote_dir: Path, project_root: Path) -> None:
    """Copy downloaded train artifacts into project .curious/train."""
    src_train = remote_dir / "train"
    if not src_train.is_dir():
        for child in remote_dir.rglob("*"):
            if child.is_dir() and child.name in ("dpo", "verifier", "grpo", "reviewer"):
                dest = project_root / ".curious" / "train" / child.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(child, dest)
        return
    dest_root = project_root / ".curious" / "train"
    dest_root.mkdir(parents=True, exist_ok=True)
    for child in src_train.iterdir():
        target = dest_root / child.name
        if target.exists():
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)
