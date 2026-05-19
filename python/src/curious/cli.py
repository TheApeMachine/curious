from __future__ import annotations

import argparse
import sys
from pathlib import Path

from curious.commands.bootstrap import run_bootstrap
from curious.commands.roadmap import run_roadmap
from curious.commands.spec_history import run_spec_history_correlate
from curious.commands.train import run_train_dpo
from curious.commands.train_grpo import run_train_grpo
from curious.commands.train_reviewer import run_train_reviewer
from curious.commands.train_verifier import run_train_verifier
from curious.commands.vast_manage import run_vast_instances, run_vast_offers, run_vast_stop
from curious.config import resolve_config
from curious.harvest import run_harvest
from curious import hf_cli
from curious.orchestrator import Orchestrator, OrchestratorOptions, print_status, reset_state


def print_help() -> None:
    print(
        """curious-py — spec-driven agent workflow (Python harness)

Workflow:
  1. bootstrap   Agent explores repo → writes spec/SPEC.md
  2. roadmap     Agent expands spec → Roadmap + Progress
  3. run         develop → review → sync → overseer → …

Commands:
  curious-py bootstrap [--verbose]
  curious-py roadmap [--verbose]
  curious-py run [options]
  curious-py status | reset | harvest | train | vast | spec-history | init | hf

Run modes (curious-py run):
  (default)           Until roadmap complete
  --continuous        Ctrl+C to stop
  --cycle / --cycles N
  --once              Single phase only

Environment (local default — Ollama/vLLM):
  LLM_MODEL=qwen3-coder
  LLM_BASE_URL=http://127.0.0.1:11434/v1
  CURIOUS_LLM_PROVIDER=openai_compat   # or litellm → e.g. openai/gpt-5.5
  Optional: curious.config.json at project root
"""
    )


def cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.directory or ".").resolve()
    spec_dir = target / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    example = Path(__file__).resolve().parents[2] / "curious.config.example.json"
    if example.is_file():
        dest = target / "curious.config.json"
        if not dest.exists():
            dest.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[curious] wrote {dest}")
    print(f"[curious] init at {target} — run bootstrap next")


def cmd_harvest(args: argparse.Namespace) -> None:
    config = resolve_config(config_path=args.config, require_spec=False)
    out, count, skipped = run_harvest(
        config,
        fmt=args.format,
        output_path=args.output,
        min_quality=args.min_quality,
        include_rejected=args.include_rejected,
    )
    print(f"[curious] harvest: wrote {count} example(s) → {out}")
    if skipped:
        print(f"[curious] harvest: skipped {skipped} below min quality")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="curious-py", add_help=False)
    parser.add_argument("command", nargs="?", default="help")
    parser.add_argument("-c", "--config", dest="config")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--cycle", action="store_true")
    parser.add_argument("--cycles", type=int)
    parser.add_argument("-h", "--help", action="store_true")

    # harvest flags (parsed loosely via remainder for subcommands)
    sub = argparse.ArgumentParser(add_help=False)
    sub.add_argument("--format", default="dpo")
    sub.add_argument("-o", "--output")
    sub.add_argument("--min-quality", type=float, default=0.5)
    sub.add_argument("--include-rejected", action="store_true")

    init_p = argparse.ArgumentParser(add_help=False)
    init_p.add_argument("directory", nargs="?")

    args, rest = parser.parse_known_args(argv)

    if args.help or args.command == "help":
        print_help()
        return

    mode_flags = sum([args.once, args.cycle, args.cycles is not None, args.continuous])
    if mode_flags > 1:
        print("Use only one of --once, --cycle, --cycles, --continuous", file=sys.stderr)
        sys.exit(1)

    try:
        if args.command == "bootstrap":
            run_bootstrap(args.config, args.verbose)
        elif args.command == "roadmap":
            run_roadmap(args.config, args.verbose)
        elif args.command == "run":
            config = resolve_config(config_path=args.config, require_spec=True)
            until_done = not args.continuous and args.cycles is None and not args.cycle
            cycles = 1 if args.cycle else args.cycles
            Orchestrator(
                config,
                OrchestratorOptions(
                    verbose=args.verbose,
                    once=args.once,
                    cycles=cycles,
                    until_done=until_done,
                ),
            ).run()
        elif args.command == "status":
            print_status(resolve_config(config_path=args.config, require_spec=False))
        elif args.command == "reset":
            reset_state(resolve_config(config_path=args.config, require_spec=False))
        elif args.command == "init":
            init_args = init_p.parse_args(rest)
            cmd_init(init_args)
        elif args.command == "harvest":
            harvest_args = sub.parse_args(rest)
            args.format = harvest_args.format
            args.output = harvest_args.output
            args.min_quality = harvest_args.min_quality
            args.include_rejected = harvest_args.include_rejected
            cmd_harvest(args)
        elif args.command == "hf":
            hf_cli.main(rest)
        elif args.command == "vast":
            vast_parser = argparse.ArgumentParser(prog="curious-py vast")
            vast_sub = vast_parser.add_subparsers(dest="vast_cmd", required=True)
            offers_p = vast_sub.add_parser("offers", help="List cheapest GPU offers")
            offers_p.add_argument("--kind", default="dpo", choices=["dpo", "grpo", "verifier", "reviewer"])
            vast_sub.add_parser("instances", help="Show running instances")
            stop_p = vast_sub.add_parser("stop", help="Destroy curious-train instances")
            stop_p.add_argument("--id", type=int, dest="instance_id")
            vast_args = vast_parser.parse_args(rest)
            if vast_args.vast_cmd == "offers":
                run_vast_offers(args.config, kind=vast_args.kind)
            elif vast_args.vast_cmd == "instances":
                run_vast_instances(args.config)
            elif vast_args.vast_cmd == "stop":
                run_vast_stop(args.config, instance_id=vast_args.instance_id)
        elif args.command == "spec-history":
            sh = argparse.ArgumentParser(prog="curious-py spec-history")
            sh_sub = sh.add_subparsers(dest="sh_cmd", required=True)
            sh_sub.add_parser("correlate", help="Correlate overseer edits with review pass rates")
            sh_args = sh.parse_args(rest)
            if sh_args.sh_cmd == "correlate":
                run_spec_history_correlate(args.config)
        elif args.command == "train":
            train_parser = argparse.ArgumentParser(prog="curious-py train")
            train_sub = train_parser.add_subparsers(dest="train_cmd", required=True)
            dpo_p = train_sub.add_parser("dpo", help="DPO fine-tune from harvest JSONL")
            dpo_p.add_argument("--dataset", help="Path to dpo.jsonl")
            dpo_p.add_argument("--model", help="HF base model id")
            dpo_p.add_argument("-o", "--output", help="Output directory")
            dpo_p.add_argument("--min-quality", type=float, default=0.5)
            dpo_p.add_argument("--local", action="store_true", help="Force local GPU")
            dpo_p.add_argument("--vast", action="store_true", help="Force Vast.ai")
            ver_p = train_sub.add_parser("verifier", help="Train diff classifier verifier")
            ver_p.add_argument("--dataset")
            ver_p.add_argument("--model")
            ver_p.add_argument("-o", "--output")
            ver_p.add_argument("--local", action="store_true")
            ver_p.add_argument("--vast", action="store_true")
            grpo_p = train_sub.add_parser("grpo", help="GRPO fine-tune with verifier reward")
            grpo_p.add_argument("--tasks-file", help="grpo.jsonl prompts (or harvest --format grpo)")
            grpo_p.add_argument("--model")
            grpo_p.add_argument("-o", "--output")
            grpo_p.add_argument("--rollouts", type=int, default=4)
            grpo_p.add_argument("--max-completion-length", type=int, default=2048)
            grpo_p.add_argument("--epochs", type=int, default=1)
            grpo_p.add_argument("--local", action="store_true")
            grpo_p.add_argument("--vast", action="store_true")
            rev_p = train_sub.add_parser("reviewer", help="Train reviewer on downstream outcomes")
            rev_p.add_argument("--dataset")
            rev_p.add_argument("--model")
            rev_p.add_argument("-o", "--output")
            rev_p.add_argument("--local", action="store_true")
            rev_p.add_argument("--vast", action="store_true")
            train_args = train_parser.parse_args(rest)
            force_local = getattr(train_args, "local", False)
            force_vast = True if getattr(train_args, "vast", False) else None
            if train_args.train_cmd == "dpo":
                run_train_dpo(
                    args.config,
                    dataset_path=train_args.dataset,
                    model_id=train_args.model,
                    output_dir=train_args.output,
                    min_quality=train_args.min_quality,
                    force_local=force_local,
                    force_vast=force_vast,
                )
            elif train_args.train_cmd == "verifier":
                run_train_verifier(
                    args.config,
                    base_model=train_args.model,
                    dataset_path=train_args.dataset,
                    output_dir=train_args.output,
                    force_local=force_local,
                    force_vast=force_vast,
                )
            elif train_args.train_cmd == "grpo":
                run_train_grpo(
                    args.config,
                    base_model=train_args.model,
                    tasks_file=train_args.tasks_file,
                    output_dir=train_args.output,
                    n_rollouts_per_task=train_args.rollouts,
                    max_completion_length=train_args.max_completion_length,
                    num_epochs=train_args.epochs,
                    force_local=force_local,
                    force_vast=force_vast,
                )
            elif train_args.train_cmd == "reviewer":
                run_train_reviewer(
                    args.config,
                    base_model=train_args.model,
                    dataset_path=train_args.dataset,
                    output_dir=train_args.output,
                    force_local=force_local,
                    force_vast=force_vast,
                )
            else:
                raise ValueError(f"Unknown train command: {train_args.train_cmd}")
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            print_help()
            sys.exit(1)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
