"""CLI entrypoint dispatcher for devops-cli."""

from __future__ import annotations

import os
import sys

from devops_cli.dry_run.state import is_dry_run_requested, set_dry_run


def is_completion_requested() -> bool:
    """Return True if Typer/Click shell completion is being requested via environment variables."""
    return "_DEVOPS_COMPLETE" in os.environ or "_TYPER_COMPLETE_ARGS" in os.environ


def main(argv: list[str] | None = None) -> None:
    """Execute devops CLI command with Typer."""
    if argv is None:
        raw_args = sys.argv[1:]
    else:
        if argv and (
            argv[0] == "devops" or argv[0].endswith("/devops") or argv[0].endswith("\\devops")
        ):
            raw_args = argv[1:]
        else:
            raw_args = list(argv)

    # 1. Shell completion fast-dispatch to Typer/Click engine
    if is_completion_requested():
        from devops_cli.main import app

        app(raw_args, prog_name="devops")
        return

    # 2. Dry-run state activation
    if is_dry_run_requested(raw_args):
        set_dry_run(True)

    # 3. Standard Typer execution for delegated subcommands and help
    from devops_cli.main import app

    app(raw_args, prog_name="devops")


if __name__ == "__main__":
    main()
