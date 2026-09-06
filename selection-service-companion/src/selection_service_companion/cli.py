"""CLI entry point for an explicitly operated Selection Service Companion."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .server import create_server
from .state import DEFAULT_STATE_DIRECTORY, CompanionState


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="selection-service")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_STATE_DIRECTORY,
        help="operator-owned Companion state directory",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", help="start the operator-owned Companion control plane")
    start.add_argument("--endpoint", default="http://127.0.0.1:8787")
    start.add_argument("--profile", choices=("loopback", "trusted-lan"), default="loopback")
    start.add_argument("--allow-origin", action="append", default=[], required=True)
    start.add_argument("--cert", type=Path)
    start.add_argument("--key", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    state = CompanionState(arguments.data_dir)
    try:
        if arguments.command == "start":
            server = create_server(
                state=state,
                endpoint=arguments.endpoint,
                profile=arguments.profile,
                allowed_origins=arguments.allow_origin,
                certificate=arguments.cert,
                private_key=arguments.key,
            )
            print(f"Selection Service Companion listening at {arguments.endpoint}")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("Selection Service Companion stopped by operator")
            finally:
                state.release_runtime_state()
                server.server_close()
            return 0
    except ValueError as error:
        _parser().error(str(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
