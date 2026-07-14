"""CLI entry point for an explicitly operated Selection Service Companion."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .server import create_server
from .state import CompanionState, DEFAULT_STATE_DIRECTORY


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="selection-service")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_STATE_DIRECTORY,
        help="operator-owned Companion state directory",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    install = commands.add_parser("install", help="record a locked Companion release")
    install.add_argument("--release", required=True)
    install.add_argument("--lock-digest", required=True)

    models = commands.add_parser("models", help="manage separately installed Model Manifests")
    model_commands = models.add_subparsers(dest="models_command", required=True)
    model_install = model_commands.add_parser("install", help="verify and register externally stored weights")
    model_install.add_argument("--manifest", type=Path, required=True)
    model_install.add_argument("--weights", type=Path, required=True)

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
        if arguments.command == "install":
            state.install_release(arguments.release, arguments.lock_digest)
            print(f"recorded locked Companion release {arguments.release}")
            return 0

        if arguments.command == "models" and arguments.models_command == "install":
            model = state.install_model(arguments.manifest, arguments.weights)
            print(f"installed separately stored Model Manifest {model['digest']}")
            return 0

        if arguments.command == "start":
            state.require_release()
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
                server.server_close()
            return 0
    except ValueError as error:
        _parser().error(str(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
