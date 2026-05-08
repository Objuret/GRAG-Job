"""CLI for data-access raw stage.

Usage:
    python -m data_access.raw sync --data-root data
    python -m data_access.raw build --data-root data
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .api import build_dataset_run, sync_sources
from shared.config import DEFAULT_DATA_ROOT, resolve_data_root


def make_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m data_access.raw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_p = subparsers.add_parser("sync", help="Download datasets into raw/")
    sync_p.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    sync_p.add_argument("--hf-token", default=os.getenv("HF_TOKEN"))

    build_p = subparsers.add_parser("build", help="Build raw_dataset_run catalog")
    build_p.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    build_p.add_argument("--run-id", default=None)

    return parser


def main() -> None:
    args = make_arg_parser().parse_args()
    data_root = resolve_data_root(args.data_root)

    if args.command == "sync":
        result = sync_sources({"output_root": str(data_root), "hf_token": args.hf_token})
    elif args.command == "build":
        result = build_dataset_run(data_root=data_root, run_id=args.run_id)
    else:
        raise SystemExit(f"Unknown command: {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

