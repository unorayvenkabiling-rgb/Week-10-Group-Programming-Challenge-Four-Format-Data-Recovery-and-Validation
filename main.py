from __future__ import annotations

import argparse
from typing import Sequence

from src.pipeline import run_pipeline


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line arguments and execute the configured pipeline."""
    parser = argparse.ArgumentParser(
        description="Recover, compare, analyze, and export four-format data."
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the JSON processing configuration (default: config.json).",
    )
    args = parser.parse_args(argv)
    return run_pipeline(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
