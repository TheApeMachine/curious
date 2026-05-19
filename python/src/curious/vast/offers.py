from __future__ import annotations

from typing import Any

from curious.types import VastGpuProfile


def _offer_dph(offer: dict[str, Any]) -> float:
    for key in ("dph_total", "dph", "search", "price_gpu"):
        val = offer.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return float("inf")


def _offer_gpu_ram_gb(offer: dict[str, Any]) -> float:
    for key in ("gpu_ram", "total_flops"):  # gpu_ram often in MB
        val = offer.get(key)
        if val is None:
            continue
        try:
            v = float(val)
            if key == "gpu_ram" and v > 256:
                return v / 1024.0
            return v
        except (TypeError, ValueError):
            continue
    return 0.0


def build_search_query(profile: VastGpuProfile, *, interruptible: bool) -> str:
    parts = [
        "verified=true",
        "rentable=true",
        "direct_port_count>=1",
        "num_gpus=1",
        f"gpu_ram>={int(profile.min_gpu_ram_gb * 1024)}",
        f"cuda_vers>={profile.min_cuda_major}",
    ]
    if interruptible:
        parts.append("inet_down>50")
    if profile.preferred_gpus:
        names = " ".join(profile.preferred_gpus)
        parts.append(f"gpu_name in [{names}]")
    return " ".join(parts)


def select_cheapest_offer(
    vast: Any,
    profile: VastGpuProfile,
    *,
    max_dph: float,
    interruptible: bool = True,
    limit: int = 64,
) -> dict[str, Any]:
    """Return the cheapest offer that satisfies the profile (sorted by $/hr)."""
    query = build_search_query(profile, interruptible=interruptible)
    print(f"[curious] vast: searching offers — {query}")

    raw = vast.search_offers(query=query, order="dph_total", limit=str(limit))
    offers: list[dict[str, Any]]
    if isinstance(raw, list):
        offers = raw
    elif isinstance(raw, dict) and "offers" in raw:
        offers = raw["offers"]
    else:
        offers = list(raw) if raw else []

    if not offers:
        raise RuntimeError(
            "No Vast.ai offers matched your query. Relax vast.maxDph or gpu requirements."
        )

    cap = min(max_dph, profile.max_dph)
    eligible: list[dict[str, Any]] = []
    for offer in offers:
        dph = _offer_dph(offer)
        ram = _offer_gpu_ram_gb(offer)
        if dph > cap:
            continue
        if ram and ram < profile.min_gpu_ram_gb * 0.9:
            continue
        eligible.append(offer)

    if not eligible:
        eligible = sorted(offers, key=_offer_dph)[:5]
        print(
            f"[curious] vast: no offers under ${cap:.3f}/hr — using cheapest available"
        )

    eligible.sort(key=_offer_dph)
    best = eligible[0]
    print(
        f"[curious] vast: selected offer id={best.get('id')} "
        f"gpu={best.get('gpu_name')} ${ _offer_dph(best):.4f}/hr "
        f"ram={_offer_gpu_ram_gb(best):.1f}GB"
    )
    return best
