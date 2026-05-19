from __future__ import annotations

import json
import subprocess
import time
from typing import Any

from curious.vast.client import parse_contract_id
from curious.vast.offers import _offer_dph
from curious.types import VastConfig, VastGpuProfile


def create_training_instance(
    vast: Any,
    offer: dict[str, Any],
    *,
    vast_cfg: VastConfig,
    profile: VastGpuProfile,
    label: str,
    bootstrap_cmd: str,
) -> int:
    offer_id = int(offer["id"])
    disk = vast_cfg.disk_gb or profile.disk_gb
    kwargs: dict[str, Any] = {
        "id": offer_id,
        "image": vast_cfg.image,
        "disk": disk,
        "ssh": True,
        "direct": True,
        "label": label,
        "onstart_cmd": bootstrap_cmd,
        "env": "-e HF_HOME=/workspace/.cache/huggingface",
    }
    if vast_cfg.interruptible:
        dph = _offer_dph(offer)
        kwargs["price"] = round(dph * 0.97, 4)

    print(f"[curious] vast: creating instance from offer {offer_id} (disk={disk}GB)")
    result = vast.create_instance(**kwargs)
    contract_id = parse_contract_id(result)
    print(f"[curious] vast: contract id={contract_id}")
    return contract_id


def _normalize_instances(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if "instances" in raw:
            return raw["instances"]
        return [raw]
    return []


def wait_for_ssh(
    vast: Any,
    contract_id: int,
    *,
    timeout_sec: int = 600,
    poll_sec: int = 10,
) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last_status = ""
    while time.time() < deadline:
        raw = vast.show_instances()
        instances = _normalize_instances(raw)
        match = None
        for inst in instances:
            iid = inst.get("id") or inst.get("instance_id")
            if int(iid) == contract_id:
                match = inst
                break
        if match is None:
            time.sleep(poll_sec)
            continue

        status = str(match.get("actual_status") or match.get("status") or "")
        if status != last_status:
            print(f"[curious] vast: instance {contract_id} status={status}")
            last_status = status

        ssh_host = match.get("ssh_host") or match.get("public_ipaddr")
        ssh_port = match.get("ssh_port")
        if ssh_host and ssh_port and status.lower() in ("running", "success", "active"):
            return match

        if status.lower() in ("exited", "failed", "error", "stopped"):
            raise RuntimeError(
                f"Vast instance {contract_id} failed to start (status={status})"
            )
        time.sleep(poll_sec)

    raise TimeoutError(
        f"Vast instance {contract_id} did not become SSH-ready within {timeout_sec}s"
    )


def ssh_endpoint(instance: dict[str, Any]) -> tuple[str, int]:
    host = instance.get("ssh_host") or instance.get("public_ipaddr")
    port = int(instance.get("ssh_port") or 22)
    if not host:
        raise RuntimeError(f"No SSH endpoint in instance record: {json.dumps(instance)[:300]}")
    return str(host), port


def destroy_instance(vast: Any, contract_id: int) -> None:
    print(f"[curious] vast: destroying instance {contract_id}")
    try:
        vast.destroy_instance(id=contract_id)
    except AttributeError:
        vast.destroy_instances(ids=[contract_id])


def scp(
    *,
    host: str,
    port: int,
    local_path: str,
    remote_path: str,
    recursive: bool = False,
) -> None:
    target = f"root@{host}:{remote_path}"
    cmd = [
        "scp",
        "-P",
        str(port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
    ]
    if recursive:
        cmd.append("-r")
    cmd.extend([local_path, target])
    subprocess.run(cmd, check=True)


def ssh_run(
    *,
    host: str,
    port: int,
    command: str,
    timeout_sec: int | None = None,
) -> int:
    cmd = [
        "ssh",
        "-p",
        str(port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        f"root@{host}",
        command,
    ]
    result = subprocess.run(cmd, check=False, timeout=timeout_sec)
    return int(result.returncode)
