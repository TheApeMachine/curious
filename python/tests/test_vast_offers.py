from __future__ import annotations

from curious.types import VastGpuProfile
from curious.vast.offers import _offer_dph, build_search_query, select_cheapest_offer


class FakeVast:
    def search_offers(self, query: str, order: str, limit: str):
        return [
            {"id": 1, "gpu_name": "RTX_4090", "dph_total": 0.35, "gpu_ram": 24576},
            {"id": 2, "gpu_name": "RTX_3090", "dph_total": 0.22, "gpu_ram": 24576},
            {"id": 3, "gpu_name": "RTX_4090", "dph_total": 2.50, "gpu_ram": 24576},
        ]


def test_select_cheapest_under_cap() -> None:
    profile = VastGpuProfile(max_dph=1.0, min_gpu_ram_gb=20)
    offer = select_cheapest_offer(
        FakeVast(),
        profile,
        max_dph=1.0,
        interruptible=True,
    )
    assert offer["id"] == 2
    assert _offer_dph(offer) == 0.22


def test_build_search_query_includes_ram() -> None:
    q = build_search_query(VastGpuProfile(min_gpu_ram_gb=40), interruptible=True)
    assert "gpu_ram>=" in q
    assert "verified=true" in q


def test_build_search_query_gpu_names_comma_separated() -> None:
    q = build_search_query(
        VastGpuProfile(preferred_gpus=["RTX_4090", "RTX_3090"]),
        interruptible=True,
    )
    assert "gpu_name in [RTX_4090,RTX_3090]" in q
    assert "RTX_4090 RTX_3090" not in q
