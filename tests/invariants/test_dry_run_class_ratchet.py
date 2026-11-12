"""Ratchet invariant: command dry-run classification and gaps list (#2230).

Every command reachable from `_COMMAND_SPECS` must either declare a dry-run class
('request-plan' or 'no-external-request') or appear in `tests/fixtures/dry_run_gaps.json`.
The MCP tool of a 'no-external-request' command is read-only exactly when the command writes no
local state and no file (#3642).
"""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import Iterable
from typing import Annotated, Any, Final

import click
import typer

from devops_cli import main as main_module
from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.core.cli import new_typer
from devops_cli.dry_run.decorator import (
    CONST_DRY_RUN_CLASSES,
    dry_run_class,
    get_dry_run_class,
)
from tests.support.paths import FIXTURES

CONST_GAPS_FILE = FIXTURES / "dry_run_gaps.json"
# A form of the verb "post": a command that makes no external request posts nothing (#3644).
CONST_POST_WORD = re.compile(r"\bpost(?:s|ed|ing)?\b", re.IGNORECASE)

# The `no-external-request` commands that write local state or a file. The dry-run class names
# external requests only, so their MCP tools are not read-only (#3642).
CONST_MCP_LOCAL_WRITERS: Final[frozenset[str]] = frozenset(
    {
        "ai failover",  # writes the constellation snapshot file
        "ai gateway failover",  # --reset and --no-simulate write the gateway state file
        "ai ingest library",  # writes the contract of the package to the library contracts directory
        "ai quiesce",  # writes the constellation snapshot file
        "ai resume",  # writes the constellation snapshot file
        "review export-feedback",  # appends review verdicts to the feedback dataset
    }
)


def _extract_commands(cmd: Any, prefix: str) -> dict[str, Any]:
    """Recursively collect leaf commands and runnable group callbacks."""
    results: dict[str, Any] = {}
    subcommands = getattr(cmd, "commands", None)
    if subcommands:
        if getattr(cmd, "invoke_without_command", False) and getattr(cmd, "callback", None):
            results[prefix] = cmd
        for sub_name, subcmd in sorted(subcommands.items()):
            child_prefix = f"{prefix} {sub_name}".strip()
            results.update(_extract_commands(subcmd, child_prefix))
    else:
        results[prefix] = cmd
    return results


def _collect_reachable_commands() -> dict[str, Any]:
    """Traverse all CLI entrypoints in main_app and collect commands."""
    all_cmds: dict[str, Any] = {}
    click_cmd = typer.main.get_command(main_module.app)
    ctx = click.Context(click_cmd)
    for name in click_cmd.list_commands(ctx):
        cmd = click_cmd.get_command(ctx, name)
        cb = getattr(cmd, "callback", None)
        target = getattr(cb, "target", None)
        if target is None and cb and hasattr(cb, "__closure__") and cb.__closure__:
            if "callback" in cb.__code__.co_freevars:
                idx = cb.__code__.co_freevars.index("callback")
                target = getattr(cb.__closure__[idx].cell_contents, "target", None)
        if target:
            mod_path, _, app_name = target.partition(":")
            mod = importlib.import_module(mod_path)
            sub_app = getattr(mod, app_name)
            sub_click_cmd = typer.main.get_command(sub_app)
            all_cmds.update(_extract_commands(sub_click_cmd, name))
    return all_cmds


def _command_declares_dry_run(cmd: Any) -> bool:
    """Check if a Click command declares a --dry-run option."""
    params = getattr(cmd, "params", [])
    return any(
        getattr(p, "name", "") == "dry_run" or "--dry-run" in getattr(p, "opts", []) for p in params
    )


def audit_dry_run_ratchet(commands: dict[str, Any], gaps: set[str]) -> list[str]:
    """Audit commands against the gap list according to ratchet invariants."""
    errors: list[str] = []

    # Criterion 3: check for stale gap entries that no longer match any command.
    for gap in sorted(gaps):
        if gap not in commands:
            errors.append(
                f"Entry '{gap}' in tests/fixtures/dry_run_gaps.json does not match any reachable command path."
            )

    for path, cmd in sorted(commands.items()):
        cls = get_dry_run_class(cmd)

        # Criterion 1: command with no class and not in gaps list.
        if cls is None:
            if path not in gaps:
                classes_str = ", ".join(repr(c) for c in CONST_DRY_RUN_CLASSES)
                errors.append(
                    f"Command '{path}' has no dry-run class ({classes_str}) and is not in tests/fixtures/dry_run_gaps.json."
                )
        else:
            # Criterion 2: command has class but is still in gaps list.
            if path in gaps:
                errors.append(
                    f"Command '{path}' has dry-run class '{cls}' but is still listed in tests/fixtures/dry_run_gaps.json. Remove this entry from the list."
                )

            # Criterion 4: request-plan command must declare --dry-run.
            if cls == "request-plan" and not _command_declares_dry_run(cmd):
                errors.append(
                    f"Command '{path}' has class 'request-plan' but does not declare --dry-run."
                )

    return errors


def audit_no_request_help(commands: dict[str, Any]) -> list[str]:
    """Return one error for each help text of a no-external-request command that says it posts."""
    errors: list[str] = []
    for path, cmd in sorted(commands.items()):
        if get_dry_run_class(cmd) != "no-external-request":
            continue
        texts = [cmd.help or "", *(getattr(param, "help", None) or "" for param in cmd.params)]
        for text in texts:
            match = CONST_POST_WORD.search(text)
            if match:
                errors.append(
                    f"Command '{path}' makes no external request, but its help says "
                    f"'{match.group(0)}': {text}"
                )
    return errors


def test_ratchet_fails_when_command_lacks_class_and_not_in_gaps() -> None:
    """Criterion 1: unclassified command not in gaps list fails with class names and fixture path."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="unclassified")
    def unclassified() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo dummy"})

    assert len(errors) == 1
    assert "Command 'demo unclassified' has no dry-run class" in errors[0]
    assert "'request-plan'" in errors[0]
    assert "'no-external-request'" in errors[0]
    assert "tests/fixtures/dry_run_gaps.json" in errors[0]


def test_ratchet_fails_when_classified_command_remains_in_gaps() -> None:
    """Criterion 2: classified command still in gap list tells author to remove entry."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="classified")
    @dry_run_class("no-external-request")
    def classified() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo classified", "demo dummy"})

    assert len(errors) == 1
    assert "Command 'demo classified' has dry-run class 'no-external-request'" in errors[0]
    assert "Remove this entry from the list" in errors[0]


def test_ratchet_fails_when_gap_entry_is_not_a_command() -> None:
    """Criterion 3: stale entry in gaps list fails."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="existing")
    @dry_run_class("no-external-request")
    def existing() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo non_existent", "demo dummy"})

    assert len(errors) == 1
    assert (
        "Entry 'demo non_existent' in tests/fixtures/dry_run_gaps.json does not match any reachable command path."
        in errors[0]
    )


def test_ratchet_fails_when_request_plan_lacks_dry_run() -> None:
    """Criterion 4: request-plan command without --dry-run option fails."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="missing-option")
    @dry_run_class("request-plan")
    def missing_option() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo dummy"})

    assert len(errors) == 1
    assert (
        "Command 'demo missing-option' has class 'request-plan' but does not declare --dry-run."
        in errors[0]
    )


def test_dry_run_class_ratchet_repository_invariant() -> None:
    """Repository invariant: every reachable command conforms to the ratchet and gaps file."""
    assert CONST_GAPS_FILE.is_file(), f"Missing fixture file: {CONST_GAPS_FILE}"
    raw_gaps = json.loads(CONST_GAPS_FILE.read_text(encoding="utf-8"))
    assert isinstance(raw_gaps, list), "Gaps fixture must be a JSON array"
    assert raw_gaps == sorted(raw_gaps), "Gaps fixture must be lexicographically sorted"
    assert len(raw_gaps) == len(set(raw_gaps)), "Gaps fixture must not contain duplicates"

    commands = _collect_reachable_commands()
    gaps_set = set(raw_gaps)

    errors = audit_dry_run_ratchet(commands, gaps_set)
    assert errors == []


def test_no_external_request_command_that_says_post_fails_the_help_check() -> None:
    """A no-external-request command whose help says "post" fails; a request-plan command may say it."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="notify")
    @dry_run_class("no-external-request")
    def notify(
        pr_number: Annotated[int, typer.Option("--pr", help="Pull request number to post to.")] = 0,
    ) -> None:
        """Post the plan comment to the pull request."""

    @app.command(name="publish")
    @dry_run_class("request-plan")
    def publish(dry_run: Annotated[bool, typer.Option("--dry-run")] = False) -> None:
        """Post the comment."""

    @app.command(name="render")
    @dry_run_class("no-external-request")
    def render() -> None:
        """Print the comment. The command sends no request."""

    cmds = _extract_commands(typer.main.get_command(app), "demo")

    assert audit_no_request_help(cmds) == [
        "Command 'demo notify' makes no external request, but its help says 'Post': "
        "Post the plan comment to the pull request.",
        "Command 'demo notify' makes no external request, but its help says 'post': "
        "Pull request number to post to.",
    ]


def test_no_external_request_commands_do_not_say_they_post() -> None:
    """Repository invariant: no command of the class no-external-request says that it posts."""
    assert audit_no_request_help(_collect_reachable_commands()) == []


def audit_mcp_read_only(
    table: Iterable[tuple[tuple[str, ...], float, bool, bool]],
    commands: dict[str, Any],
    local_writers: frozenset[str],
) -> list[str]:
    """Audit the read-only flag of each MCP tool of a `no-external-request` command (#3642).

    The class names external requests only. The tool of a command in `local_writers` is not
    read-only, and the tool of each other `no-external-request` command is read-only. Each entry of
    `local_writers` is a `no-external-request` command of `table`.
    """
    mismatches: list[str] = []
    audited: set[str] = set()
    for path_tuple, _timeout, read_only, _format_json in table:
        cmd_path = " ".join(path_tuple)
        cmd = commands.get(cmd_path)
        if cmd is None or get_dry_run_class(cmd) != "no-external-request":
            continue
        audited.add(cmd_path)
        if read_only and cmd_path in local_writers:
            mismatches.append(
                f"MCP tool for '{cmd_path}' has read_only=True but the command writes local state or a file."
            )
        elif not read_only and cmd_path not in local_writers:
            mismatches.append(
                f"MCP tool for '{cmd_path}' has read_only=False but the command is 'no-external-request' and is not in CONST_MCP_LOCAL_WRITERS. Add it there if it writes local state or a file."
            )
    mismatches.extend(
        f"CONST_MCP_LOCAL_WRITERS names '{path}', which is not a 'no-external-request' command of the MCP exposure table."
        for path in sorted(local_writers - audited)
    )
    return mismatches


def _writer_and_reader() -> dict[str, Any]:
    """Two `no-external-request` commands: `demo writer` and `demo reader`."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="writer")
    @dry_run_class("no-external-request")
    def writer() -> None:
        pass

    @app.command(name="reader")
    @dry_run_class("no-external-request")
    def reader() -> None:
        pass

    return _extract_commands(typer.main.get_command(app), "demo")


def test_a_local_writer_with_a_read_only_tool_is_reported() -> None:
    table = ((("demo", "writer"), 60.0, True, False), (("demo", "reader"), 60.0, True, False))

    mismatches = audit_mcp_read_only(table, _writer_and_reader(), frozenset({"demo writer"}))

    assert mismatches == [
        "MCP tool for 'demo writer' has read_only=True but the command writes local state or a file."
    ]


def test_a_command_that_writes_nothing_with_a_tool_that_is_not_read_only_is_reported() -> None:
    table = ((("demo", "writer"), 60.0, False, False), (("demo", "reader"), 60.0, False, False))

    mismatches = audit_mcp_read_only(table, _writer_and_reader(), frozenset({"demo writer"}))

    assert mismatches == [
        "MCP tool for 'demo reader' has read_only=False but the command is 'no-external-request' and is not in CONST_MCP_LOCAL_WRITERS. Add it there if it writes local state or a file."
    ]


def test_a_local_writer_outside_the_exposure_table_is_reported() -> None:
    table = ((("demo", "writer"), 60.0, False, False), (("demo", "reader"), 60.0, True, False))

    mismatches = audit_mcp_read_only(
        table, _writer_and_reader(), frozenset({"demo writer", "demo gone"})
    )

    assert mismatches == [
        "CONST_MCP_LOCAL_WRITERS names 'demo gone', which is not a 'no-external-request' command of the MCP exposure table."
    ]


def test_a_no_external_request_tool_is_read_only_exactly_when_its_command_writes_nothing() -> None:
    mismatches = audit_mcp_read_only(
        CONST_MCP_EXPOSURE_TABLE, _collect_reachable_commands(), CONST_MCP_LOCAL_WRITERS
    )

    assert mismatches == []
