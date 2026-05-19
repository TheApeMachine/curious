from __future__ import annotations

import argparse
import sys


def cmd_hf_download(args: argparse.Namespace) -> None:
    from huggingface_hub import snapshot_download

    path = snapshot_download(
        repo_id=args.model,
        local_dir=args.output,
        local_dir_use_symlinks=False,
    )
    print(f"[curious] downloaded {args.model} → {path}")


def cmd_hf_login(args: argparse.Namespace) -> None:
    from huggingface_hub import login

    login(token=args.token)
    print("[curious] logged in to Hugging Face Hub")


def cmd_hf_whoami(_args: argparse.Namespace) -> None:
    from huggingface_hub import whoami

    info = whoami()
    print(info)


def cmd_hf_info(_args: argparse.Namespace) -> None:
    print(
        """[curious] Hugging Face stack

Libraries (install extras as needed):
  huggingface_hub  — pip install curious-py          https://huggingface.co/docs/huggingface_hub/index
  transformers     — pip install 'curious-py[transformers]'
  smolagents       — pip install 'curious-py[smolagents]'  https://huggingface.co/docs/smolagents/index
  trl + peft       — pip install 'curious-py[train]'       https://huggingface.co/docs/trl/index
                                                         https://huggingface.co/docs/peft/index

Download weights:
  curious-py hf download Qwen/Qwen3-Coder-30B-A3B-Instruct -o ./models/qwen3-coder-30b

Run agent (pick one llm.provider in curious.config.json):
  openai_compat  — Ollama / vLLM HTTP (default)
  transformers   — native loop + Transformers weights on disk
  smolagents     — smolagents ToolCallingAgent / CodeAgent + TransformersModel
  litellm        — optional hosted APIs

Train DPO from harvest:
  curious-py harvest --format dpo
  curious-py train dpo --model Qwen/Qwen3-Coder-30B-A3B-Instruct
"""
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="curious-py hf")
    sub = parser.add_subparsers(dest="hf_command", required=True)

    info = sub.add_parser("info", help="HF workflow overview")
    info.set_defaults(handler=cmd_hf_info)

    dl = sub.add_parser("download", help="snapshot_download from Hub")
    dl.add_argument("model", help="Hugging Face repo id")
    dl.add_argument("-o", "--output", required=True, help="Local directory")
    dl.set_defaults(handler=cmd_hf_download)

    login_p = sub.add_parser("login", help="huggingface-cli login wrapper")
    login_p.add_argument("--token", help="HF token (or use huggingface-cli login)")
    login_p.set_defaults(handler=cmd_hf_login)

    whoami_p = sub.add_parser("whoami", help="Show Hub identity")
    whoami_p.set_defaults(handler=cmd_hf_whoami)

    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except ImportError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
