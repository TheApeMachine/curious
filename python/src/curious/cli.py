from __future__ import annotations

import argparse
import sys
from pathlib import Path

from curious.commands.bootstrap import run_bootstrap
from curious.commands.roadmap import run_roadmap
from curious.commands.train import run_train_dpo
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
  curious-py status | reset | harvest | train | init | hf

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
        elif args.command == "train":
            train_parser = argparse.ArgumentParser(prog="curious-py train")
            train_sub = train_parser.add_subparsers(dest="train_cmd", required=True)
            dpo_p = train_sub.add_parser("dpo", help="DPO fine-tune from harvest JSONL")
            dpo_p.add_argument("--dataset", help="Path to dpo.jsonl")
            dpo_p.add_argument("--model", help="HF base model id")
            dpo_p.add_argument("-o", "--output", help="Output directory")
            dpo_p.add_argument("--min-quality", type=float, default=0.5)
            train_args = train_parser.parse_args(rest)
            if train_args.train_cmd == "dpo":
                run_train_dpo(
                    args.config,
                    dataset_path=train_args.dataset,
                    model_id=train_args.model,
                    output_dir=train_args.output,
                    min_quality=train_args.min_quality,
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
