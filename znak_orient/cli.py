"""Command-line entry points for local verification and serving."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import OrientationError, orient


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="znak-orient", description="Recover source-backed project orientation locally.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-demo", help="Process an evidence package and retain the deterministic result.")
    verify.add_argument("--input", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)

    serve = subparsers.add_parser("serve", help="Serve the local interface and JSON endpoint.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--allow-non-loopback", action="store_true")
    serve.add_argument("--demo", type=Path, default=Path("demo/evidence-package.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify-demo":
            package = json.loads(args.input.read_text(encoding="utf-8"))
            result = orient(package)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            receipt = result["run_receipt"]
            print(f"ORIENTATION_{receipt['status']} checkpoint={result['checkpoint']['checkpoint_id']} output={args.output}")
            return 0 if receipt["status"] == "PASS" else 1
        if args.command == "serve":
            from .server import serve

            serve(args.host, args.port, args.demo, allow_non_loopback=args.allow_non_loopback)
            return 0
    except (OSError, json.JSONDecodeError, OrientationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

