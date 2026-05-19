from __future__ import annotations

import os
from typing import Any


def get_api_key(config_key: str | None = None) -> str:
    key = config_key or os.environ.get("VAST_API_KEY") or os.environ.get("VASTAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Vast.ai API key required. Set VAST_API_KEY or add vast.apiKey to curious.config.json.\n"
            "Get a key at https://cloud.vast.ai/manage-keys/"
        )
    return key


def create_client(api_key: str | None = None) -> Any:
    try:
        from vastai import VastAI
    except ImportError as exc:
        raise ImportError(
            "Vast.ai support requires: pip install 'curious-py[vast]' (installs vastai)"
        ) from exc
    return VastAI(api_key=get_api_key(api_key))


def parse_contract_id(create_result: Any) -> int:
    if isinstance(create_result, dict):
        if "new_contract" in create_result:
            return int(create_result["new_contract"])
        if "id" in create_result:
            return int(create_result["id"])
    if isinstance(create_result, str):
        import json

        try:
            data = json.loads(create_result)
            return parse_contract_id(data)
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse Vast contract id from: {create_result!r}")
