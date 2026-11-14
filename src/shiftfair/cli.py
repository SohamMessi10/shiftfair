"""The `shiftfair` command."""

from __future__ import annotations

import argparse

from shiftfair import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shiftfair",
        description="Schedule volunteers to shifts: every hard rule holds, hours are spread as evenly as possible, "
                    "and an impossible schedule comes with the reason.")
    parser.add_argument("--version", action="version", version=f"shiftfair {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
