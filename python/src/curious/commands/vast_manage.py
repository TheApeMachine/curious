from __future__ import annotations

import json

from curious.config import resolve_config
from curious.vast.client import create_client
from curious.vast.instance import _normalize_instances, destroy_instance
from curious.vast.offers import _offer_dph, build_search_query, select_cheapest_offer
from curious.vast.types import DEFAULT_PROFILES


def run_vast_offers(config_path: str | None, *, kind: str = "dpo") -> None:
    config = resolve_config(config_path=config_path, require_spec=False)
    vast_cfg = config.vast
    if not vast_cfg:
        print("[curious] vast not configured")
        return
    profile = DEFAULT_PROFILES.get(kind, DEFAULT_PROFILES["dpo"])
    vast = create_client(vast_cfg.api_key)
    query = build_search_query(profile, interruptible=vast_cfg.interruptible)
    raw = vast.search_offers(query=query, order="dph_total", limit="15")
    offers = raw if isinstance(raw, list) else raw.get("offers", [])
    print(f"[curious] vast offers ({kind}, query={query}):\n")
    for offer in offers[:15]:
        print(
            f"  id={offer.get('id')} {offer.get('gpu_name')} "
            f"${_offer_dph(offer):.4f}/hr ram={offer.get('gpu_ram')}MB"
        )


def run_vast_instances(config_path: str | None) -> None:
    config = resolve_config(config_path=config_path, require_spec=False)
    vast = create_client(config.vast.api_key if config.vast else None)
    raw = vast.show_instances()
    instances = _normalize_instances(raw)
    if not instances:
        print("[curious] no vast instances")
        return
    print(json.dumps(instances, indent=2, default=str))


def run_vast_stop(config_path: str | None, *, instance_id: int | None = None) -> None:
    config = resolve_config(config_path=config_path, require_spec=False)
    vast = create_client(config.vast.api_key if config.vast else None)
    if instance_id is not None:
        destroy_instance(vast, instance_id)
        return
    raw = vast.show_instances()
    for inst in _normalize_instances(raw):
        label = str(inst.get("label") or "")
        if label.startswith("curious-train"):
            iid = int(inst.get("id") or inst.get("instance_id"))
            destroy_instance(vast, iid)
