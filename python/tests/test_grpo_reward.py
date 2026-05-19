from __future__ import annotations

from pathlib import Path

from curious.train.grpo_reward import (
    CuriousGRPReward,
    completion_to_text,
    heuristic_develop_reward,
)


def test_heuristic_develop_reward() -> None:
    low = heuristic_develop_reward("ok")
    high = heuristic_develop_reward("ran pytest and all tests pass")
    assert high > low


def test_completion_to_text_messages() -> None:
    text = completion_to_text(
        [{"role": "assistant", "content": "done"}, {"role": "tool", "content": "ok"}]
    )
    assert "done" in text


def test_grpo_reward_without_verifier(tmp_path: Path) -> None:
    reward = CuriousGRPReward(
        tmp_path,
        verifier_checkpoint=None,
        verifier_base_model="Qwen/Qwen3-1.7B",
    )
    scores = reward(
        prompts=["p"],
        completions=["Implemented T1.1 and ran pytest successfully."],
        spec_section=["## Roadmap\n- [ ] T1.1"],
        agents_section=[""],
    )
    assert len(scores) == 1
    assert 0.0 <= scores[0] <= 1.0
