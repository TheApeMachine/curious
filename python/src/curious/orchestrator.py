from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from curious.config import ResolvedConfig, print_config_summary
from curious.workspace import prepare_agent_workspace
from curious.harness import run_harness
from curious.harness.best_of_n import develop_best_of_n
from curious.scanner_rules import (
    check_rules,
    format_violations_for_prompt,
    load_rules,
    save_rules,
    synthesize_rules,
)
from curious.spec_history import (
    OverseerLabel,
    append_overseer_label,
    count_diff_lines,
    overseer_diff_for_cycle,
    snapshot_agents,
    snapshot_spec,
)
from curious.spec_sections import extract_spec_section
from curious.review_verdict import parse_review_verdict
from curious.verifier.model import load_verifier, log_disagreement
from curious.orchestrator_cycles import (
    should_abort_cycles_mode_on_phase_error,
    should_stop_after_requested_cycles,
    should_stop_at_config_max_cycles,
)
from curious.orchestrator_roadmap import (
    should_skip_until_done_loop,
    should_stop_until_done_after_phase,
)
from curious.overseer import overseer_trigger_reason, should_run_overseer
from curious.project import load_agents_document, relative_to_root
from curious.prompts import build_prompt
from curious.spec_roadmap import analyze_roadmap
from curious.state import initial_state, load_state, next_phase, save_state
from curious.types import CycleRecord, CuriousState, Phase

REMAINING_TASK_PREVIEW = 8


@dataclass
class OrchestratorOptions:
    verbose: bool = False
    once: bool = False
    cycles: int | None = None
    until_done: bool = True


class Orchestrator:
    def __init__(self, config: ResolvedConfig, opts: OrchestratorOptions | None = None):
        self.config = config
        self.opts = opts or OrchestratorOptions()
        self.stopping = False
        self.last_summary: str | None = None

    def request_stop(self) -> None:
        self.stopping = True

    def run(self) -> None:
        prepare_agent_workspace(self.config)
        print_config_summary(self.config)
        state = load_state(self.config.project_root)
        state.running = True
        save_state(self.config.project_root, state)

        def shutdown(_signum=None, _frame=None) -> None:
            self.request_stop()
            nonlocal state
            state.running = False
            save_state(self.config.project_root, state)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        try:
            cycle_at_start = state.cycle
            cycles_limit = self.opts.cycles
            skip_loop = False
            spec_path = Path(self.config.spec_path)

            if self.opts.once:
                print("[curious] mode: single phase (--once)")
            elif self.opts.until_done:
                initial = analyze_roadmap(spec_path.read_text(encoding="utf-8"))
                self._log_roadmap_status(initial)
                if should_skip_until_done_loop(initial):
                    print("[curious] roadmap already complete — nothing to do")
                    skip_loop = True
                else:
                    print(
                        "[curious] mode: until done (stops when all ## Roadmap tasks are checked)"
                    )
            elif cycles_limit is not None:
                print(
                    f"[curious] mode: {cycles_limit} full cycle(s), then stop"
                )
            else:
                print("[curious] mode: continuous (Ctrl+C to stop)")

            if not skip_loop:
                while not self.stopping:
                    state = self._run_phase(state)
                    if self.stopping:
                        break

                    if self.opts.once:
                        self._print_next_step_hint(state)
                        break

                    if should_stop_after_requested_cycles(
                        state, cycle_at_start, cycles_limit
                    ):
                        print(
                            f"[curious] finished {state.cycle - cycle_at_start} cycle(s)"
                        )
                        break

                    if self.opts.until_done and self._should_stop_until_done(state):
                        break

                    if should_abort_cycles_mode_on_phase_error(
                        cycles_limit, state.last_error
                    ):
                        print("[curious] cycle aborted due to phase error")
                        break

                    if should_stop_at_config_max_cycles(
                        state.cycle, self.config.max_cycles
                    ):
                        print(
                            f"[curious] reached maxCycles={self.config.max_cycles}"
                        )
                        break

                    if state.phase == "develop" and state.cycle > cycle_at_start:
                        print(
                            f"[curious] next: cycle {state.cycle} · develop"
                        )
                        if self.config.cycle_delay_ms > 0:
                            time.sleep(self.config.cycle_delay_ms / 1000)
        finally:
            state = load_state(self.config.project_root)
            state.running = False
            save_state(self.config.project_root, state)

    def _run_phase(self, state: CuriousState) -> CuriousState:
        phase = state.phase
        spec_body = Path(self.config.spec_path).read_text(encoding="utf-8")
        agents = load_agents_document(
            Path(self.config.project_root), Path(self.config.cwd)
        )

        if phase == "develop" and not agents:
            print(
                "[curious] warning: no AGENTS.md — developer lacks style guidelines"
            )
        elif agents and phase in ("develop", "review", "overseer"):
            print(f"[curious] including AGENTS.md ({agents.rel_path})")

        if phase == "overseer":
            print(
                f"[curious] overseer triggered: {overseer_trigger_reason(state, self.config)}"
            )

        root = Path(self.config.project_root)
        spec_sha = snapshot_spec(root, state.cycle, spec_body, phase)
        agents_sha = None
        if agents and agents.content:
            agents_sha = snapshot_agents(root, state.cycle, phase, agents.content)

        prompt = build_prompt(
            phase=phase,
            spec_path=self.config.spec_path,
            spec_rel_path=relative_to_root(
                Path(self.config.project_root), Path(self.config.spec_path)
            ),
            spec_body=spec_body,
            cycle=state.cycle,
            cwd=self.config.cwd,
            project_root=self.config.project_root,
            config=self.config,
            agents=agents,
            last_summary=self.last_summary,
            history=state.history,
        )

        if phase == "review":
            violations = check_rules(Path(self.config.cwd), load_rules(root))
            block = format_violations_for_prompt(violations)
            if block:
                prompt = prompt + "\n\n" + block

        llm = self.config.llm_for_phase(phase)
        spec_section = extract_spec_section(spec_body, "## Roadmap") or spec_body[:4000]
        agents_section = (agents.content[:4000] if agents else "")

        print(f"\n[curious] ── cycle {state.cycle} · {phase} ──")

        started_at = _now()
        run_id = ""
        status: str = "error"
        summary: str | None = None
        result = None

        try:
            if (
                phase == "develop"
                and self.config.harness.best_of_n.enabled
                and self.config.verifier.enabled
            ):
                verifier = load_verifier(
                    self.config.verifier.model_path,
                    self.config.verifier.base_model,
                )
                result = develop_best_of_n(
                    prompt,
                    Path(self.config.cwd),
                    llm,
                    self.config.harness,
                    verifier,
                    cycle=state.cycle,
                    spec_section=spec_section,
                    agents_section=agents_section,
                    verbose=self.opts.verbose,
                    bon=self.config.harness.best_of_n,
                )
            else:
                result = run_harness(
                    prompt,
                    Path(self.config.cwd),
                    llm,
                    self.config.harness,
                    verbose=self.opts.verbose,
                )
            run_id = result.run_id
            print(f"[curious] run {run_id}")
            status = result.status
            summary = result.summary
            self.last_summary = summary

            if result.status == "error":
                state.last_error = result.error or "harness error"
                print(f"[curious] run error: {state.last_error}")
            elif result.status == "finished":
                state.last_error = None
                preview = (summary or "")[:400]
                if len(summary or "") > 400:
                    preview += "…"
                print(f"[curious] result: {preview}")
        except Exception as exc:
            state.last_error = str(exc)
            print(f"[curious] phase error: {exc}")

        overseer_intervened = False
        if phase == "overseer" and status == "finished":
            after_spec = Path(self.config.spec_path).read_text(encoding="utf-8")
            diff = overseer_diff_for_cycle(root, state.cycle)
            if diff:
                added, removed = count_diff_lines(diff)
                sha_after = snapshot_spec(root, state.cycle, after_spec, phase)
                append_overseer_label(
                    root,
                    OverseerLabel(
                        cycle=state.cycle,
                        sha_before=spec_sha,
                        sha_after=sha_after,
                        lines_added=added,
                        lines_removed=removed,
                        summary=(summary or "")[:500],
                    ),
                )
                new_rules = synthesize_rules(
                    diff, spec_sha, state.cycle, self.config.llm
                )
                if new_rules:
                    existing = load_rules(root)
                    save_rules(root, existing + new_rules)
                overseer_intervened = True

        if (
            phase == "review"
            and status == "finished"
            and self.config.verifier.enabled
            and summary
        ):
            try:
                from curious.harvest.verifier import _git_diff

                verifier = load_verifier(
                    self.config.verifier.model_path,
                    self.config.verifier.base_model,
                )
                diff = _git_diff(self.config.project_root, self.config.cwd)
                scores = verifier.score(
                    diff=diff,
                    spec_section=spec_section,
                    agents_section=agents_section,
                )
                verdict = parse_review_verdict(summary)
                reviewer_pass = bool(verdict and verdict.overall == "PASS")
                log_disagreement(
                    root,
                    self.config.verifier.disagreement_log,
                    cycle=state.cycle,
                    verifier_scores=scores,
                    reviewer_pass=reviewer_pass,
                    diff_excerpt=diff,
                )
            except Exception as exc:
                print(f"[curious] verifier check skipped: {exc}")

        record = CycleRecord(
            cycle=state.cycle,
            phase=phase,
            run_id=run_id or "unknown",
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            finished_at=_now(),
            summary=summary,
            trajectory=result.trajectory or [] if result else [],
            spec_snapshot_sha=spec_sha,
            agents_snapshot_sha=agents_sha,
            overseer_intervened=overseer_intervened,
        )
        state.history.append(record)
        if len(state.history) > 100:
            state.history = state.history[-100:]
        state.last_run_id = run_id or state.last_run_id

        if status == "finished":
            if phase == "sync":
                state.cycle += 1
                state.phase = (
                    "overseer"
                    if should_run_overseer(state, self.config)
                    else next_phase("sync")
                )
            else:
                state.phase = next_phase(phase)
        else:
            print(
                f'[curious] staying on phase "{phase}" until a run finishes successfully'
            )

        save_state(self.config.project_root, state)
        return state

    def _should_stop_until_done(self, state: CuriousState) -> bool:
        spec_body = Path(self.config.spec_path).read_text(encoding="utf-8")
        if not should_stop_until_done_after_phase(state, spec_body):
            return False
        status = analyze_roadmap(spec_body)
        print(
            f"[curious] roadmap complete — all {status.total_tasks} tasks checked off"
        )
        return True

    def _log_roadmap_status(self, status) -> None:
        if status.total_tasks == 0:
            print("[curious] roadmap: no T*/M* tasks found")
            return
        remaining = status.unchecked_task_ids
        if len(remaining) > REMAINING_TASK_PREVIEW:
            head = ", ".join(remaining[:REMAINING_TASK_PREVIEW])
            rem = f", … (+{len(remaining) - REMAINING_TASK_PREVIEW} more)"
        else:
            head = ", ".join(remaining)
            rem = ""
        print(
            f"[curious] roadmap: {status.checked_tasks}/{status.total_tasks} done"
            + (f" (remaining: {head}{rem})" if head else "")
        )

    def _print_next_step_hint(self, state: CuriousState) -> None:
        if not state.history:
            return
        last = state.history[-1]
        if last.status != "finished":
            print(
                f'[curious] phase "{last.phase}" did not finish — fix and re-run'
            )
            return
        print(
            f'[curious] phase "{last.phase}" done — next: "{state.phase}" (cycle {state.cycle})'
        )


def print_status(config: ResolvedConfig) -> None:
    import json

    state = load_state(config.project_root)
    print(
        json.dumps(
            {
                "config": {
                    "projectRoot": config.project_root,
                    "cwd": config.cwd,
                    "specPath": config.spec_path,
                    "model": config.llm.model,
                },
                "state": state.to_json(),
            },
            indent=2,
        )
    )


def reset_state(config: ResolvedConfig) -> None:
    save_state(config.project_root, initial_state())
    print("[curious] state reset")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
