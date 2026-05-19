from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from curious.scanner_rules import check_rules, load_rules
from curious.verifier.model import VerifierModel, load_verifier

_DIFF_HUNK = re.compile(r"^@@", re.M)


def completion_to_text(completion: str | list[dict[str, Any]]) -> str:
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list):
        parts: list[str] = []
        for msg in completion:
            if isinstance(msg, dict):
                content = msg.get("content") or ""
                if content:
                    parts.append(str(content))
                for tc in msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    parts.append(
                        f"{fn.get('name', '')}: {fn.get('arguments', '')}"
                    )
        return "\n".join(parts)
    return str(completion)


def looks_like_unified_diff(text: str) -> bool:
    """True when completion contains unified-diff hunks (verifier training distribution)."""
    return bool(_DIFF_HUNK.search(text))


def heuristic_develop_reward(text: str) -> float:
    score = 0.15
    lower = text.lower()
    if any(k in lower for k in ("pytest", "go test", "npm test", "cargo test", "make test")):
        score += 0.25
    if "pass" in lower and "fail" not in lower[-200:]:
        score += 0.1
    if len(text) > 400:
        score += 0.15
    if "error" in lower and "fixed" not in lower:
        score -= 0.1
    return max(0.0, min(1.0, score))


class CuriousGRPReward:
    """
    Composite reward for GRPO: verifier (diff proxy) + scanner heuristics + develop heuristics.
    Dataset columns `spec_section` and `agents_section` are passed through by TRL.
    """

    def __init__(
        self,
        project_root: Path,
        *,
        verifier_checkpoint: str | None = None,
        verifier_base_model: str,
        verifier_weight: float = 0.65,
        heuristic_weight: float = 0.25,
        scanner_penalty_weight: float = 0.10,
        default_spec_section: str = "",
        default_agents_section: str = "",
    ) -> None:
        self.project_root = project_root
        self.verifier_weight = verifier_weight
        self.heuristic_weight = heuristic_weight
        self.scanner_penalty_weight = scanner_penalty_weight
        self.default_spec = default_spec_section
        self.default_agents = default_agents_section
        self._verifier: VerifierModel | None = None
        self._verifier_checkpoint = verifier_checkpoint
        self._verifier_base_model = verifier_base_model
        self._rules = load_rules(project_root)

    def _get_verifier(self) -> VerifierModel | None:
        if self._verifier is not None:
            return self._verifier
        if not self._verifier_checkpoint and not self._verifier_base_model:
            return None
        try:
            self._verifier = load_verifier(
                self._verifier_checkpoint,
                self._verifier_base_model,
            )
        except Exception as exc:
            print(f"[curious] grpo reward: verifier unavailable ({exc})")
            return None
        return self._verifier

    def __call__(
        self,
        prompts: list,
        completions: list,
        completion_ids: list | None = None,
        spec_section: list[str] | None = None,
        agents_section: list[str] | None = None,
        **kwargs: Any,
    ) -> list[float]:
        verifier = self._get_verifier()
        rewards: list[float] = []

        for i, completion in enumerate(completions):
            text = completion_to_text(completion)
            spec = (
                (spec_section[i] if spec_section and i < len(spec_section) else None)
                or self.default_spec
            )
            agents = (
                (agents_section[i] if agents_section and i < len(agents_section) else None)
                or self.default_agents
            )

            score = self.heuristic_weight * heuristic_develop_reward(text)

            # Verifier was trained on git diffs (<|diff|>); skip verifier signal for
            # prose/tool-call rollouts until GRPO runs in a worktree with real diffs.
            if verifier is not None and looks_like_unified_diff(text):
                try:
                    v = verifier.score(
                        diff=text,
                        spec_section=spec,
                        agents_section=agents,
                    )
                    score += self.verifier_weight * v.overall
                except Exception:
                    score += self.verifier_weight * 0.0

            # Scanner rules are workspace-based; at train time penalize forbidden patterns in text
            for rule in self._rules:
                if rule.forbidden_regex and re.search(rule.forbidden_regex, text):
                    score -= self.scanner_penalty_weight

            rewards.append(float(max(0.0, min(1.0, score))))

        return rewards


def make_grpo_reward_fn(
    project_root: Path,
    *,
    verifier_checkpoint: str | None,
    verifier_base_model: str,
    spec_path: str | None = None,
    agents_path: str | None = None,
) -> CuriousGRPReward:
    default_spec = ""
    default_agents = ""
    if spec_path and Path(spec_path).is_file():
        default_spec = Path(spec_path).read_text(encoding="utf-8")[:8000]
    if agents_path and Path(agents_path).is_file():
        default_agents = Path(agents_path).read_text(encoding="utf-8")[:4000]
    return CuriousGRPReward(
        project_root,
        verifier_checkpoint=verifier_checkpoint,
        verifier_base_model=verifier_base_model,
        default_spec_section=default_spec,
        default_agents_section=default_agents,
    )
