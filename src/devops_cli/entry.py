"""Fast CLI entrypoint dispatcher optimized for sub-100ms startup.

Dispatches help, version, and dry-run flows via dedicated fast-path modules
before importing heavy runtime frameworks or CLI command packages.
"""

from __future__ import annotations

import sys

from devops_cli.dry_run.state import is_dry_run_requested, set_dry_run
from devops_cli.help import (
    is_help_requested,
    is_version_requested,
    show_help,
    show_version,
)


def main(argv: list[str] | None = None) -> None:
    """Execute devops CLI command with sub-100ms fast-paths for help, version, and dry-run."""
    if argv is None:
        raw_args = sys.argv[1:]
    else:
        if argv and (
            argv[0] == "devops" or argv[0].endswith("/devops") or argv[0].endswith("\\devops")
        ):
            raw_args = argv[1:]
        else:
            raw_args = list(argv)

    # 1. Sub-10ms fast-path: Version queries (-v / --version)
    if is_version_requested(raw_args):
        show_version()
        return

    # 2. Sub-10ms fast-path: Root and Subcommand Help queries (-h / --help)
    if is_help_requested(raw_args):
        if show_help(raw_args):
            return

    # 3. Dry-run state activation (ensures live model structures and message syntax are preserved)
    if is_dry_run_requested(raw_args):
        set_dry_run(True)

    # 4. Standard Typer execution for delegated subcommands
    from devops_cli.main import app

    app(raw_args)


if __name__ == "__main__":
    main()
