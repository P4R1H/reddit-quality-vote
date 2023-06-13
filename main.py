"""Entry point.

Usage:
    python main.py [--config config.toml] [--once] [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from qualityvote.config import Config, ConfigError  # noqa: E402
from qualityvote.reddit_client import build_reddit  # noqa: E402
from qualityvote.service import QualityVoteService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the quality-vote bot.")
    parser.add_argument("--config", default="config.toml", help="path to config.toml")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log the actions that would be taken without taking them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    try:
        config = Config.load(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 1

    service = QualityVoteService(build_reddit(config.credentials), config, dry_run=args.dry_run)
    try:
        if args.once:
            service.run_once()
        else:
            service.run_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
