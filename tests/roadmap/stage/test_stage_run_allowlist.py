"""The allow-list of the commands that the stage planner may run in the sandbox (#4004).

The allow-list is built from the read-only rows of `CONST_MCP_EXPOSURE_TABLE`, narrowed by the
`allowed` set of `_PATH_PARAM_RESTRICTIONS` and by the path confinement table, and it leaves out
each command whose permitted parameters hold a path. ADR 0018 decides that a command that the
allow-list does not name does not run, so a refusal names the path and one reason word.
"""

from __future__ import annotations

from typing import Annotated, Any

import pytest
import typer

from devops_cli.ai.mcp.path_confinement import PATH_CONFINEMENTS
from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.roadmap.stage.stage_run_allowlist import (
    REASON_NOT_READ_ONLY,
    REASON_OPTION_NOT_PERMITTED,
    REASON_PATH_OPTION,
    REASON_UNKNOWN_COMMAND,
    RunRefusal,
    build_allowlist,
    check_command,
)

# The rows of the exposure table at this commit. The census fails when a row is added or removed,
# because each new row needs a decision and the count is the record of that walk.
ROW_COUNT = 144


def _demo_command() -> Any:
    """A Click command whose one parameter is the text option `config`.

    Typer types a `str` annotation as a string, so no type shows that the option names a file. A
    run of `devops scan sast --config` reads such an option, and only the path confinement table
    names it.
    """
    app = typer.Typer()

    @app.command("show")
    def show(config: Annotated[str, typer.Option()] = "") -> None:
        """Print the configuration that `config` names."""

    return typer.main.get_command(app)


def _refusal(path: tuple[str, ...], *options: str) -> RunRefusal | None:
    """The refusal of a run of `path` with `options`, which the caller asserts on."""
    return check_command(path, options)


def test_a_text_path_option_leaves_its_command_out(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _demo_command()
    monkeypatch.setitem(PATH_CONFINEMENTS, "demo_show", frozenset({"config"}))
    row = (("demo", "show"), 30.0, True, False)
    allowlist = build_allowlist((row,), lambda _path: command)
    refusal = check_command(("demo", "show"), rows=(row,), resolver=lambda _path: command)

    assert ("demo", "show") not in allowlist
    assert refusal is not None
    assert (refusal.path, refusal.reason, refusal.option) == (
        ("demo", "show"),
        REASON_PATH_OPTION,
        None,
    )


def test_a_read_only_command_with_no_path_parameter_is_an_entry() -> None:
    allowlist = build_allowlist()

    assert "repo" in allowlist[("gh", "label", "list")]


def test_a_write_command_is_not_an_entry() -> None:
    allowlist = build_allowlist()
    refusal = _refusal(("valkey", "flush"))

    assert ("valkey", "flush") not in allowlist
    assert refusal is not None
    assert (refusal.path, refusal.reason) == (("valkey", "flush"), REASON_NOT_READ_ONLY)


@pytest.mark.parametrize("path", [("tf", "plan"), ("ai", "read"), ("scan", "sast")])
def test_a_command_whose_permitted_parameter_holds_a_path_is_not_an_entry(
    path: tuple[str, ...],
) -> None:
    allowlist = build_allowlist()
    refusal = _refusal(path)

    assert path not in allowlist
    assert refusal is not None
    assert (refusal.path, refusal.reason) == (path, REASON_PATH_OPTION)


def test_a_restricted_command_permits_only_its_allowed_options() -> None:
    allowlist = build_allowlist()

    assert allowlist[("telemetry", "profile")] == frozenset({"trace_id"})


def test_the_help_form_of_a_write_command_is_permitted() -> None:
    assert _refusal(("valkey", "flush"), "help") is None


def test_the_help_form_of_a_command_that_the_click_tree_lacks_is_refused() -> None:
    refusal = _refusal(("valkey", "nosuch"), "help")

    assert refusal is not None
    assert refusal.reason == REASON_UNKNOWN_COMMAND


def test_a_command_path_that_no_row_names_is_refused() -> None:
    refusal = _refusal(("config", "unset"))

    assert refusal is not None
    assert (refusal.path, refusal.reason, refusal.option) == (
        ("config", "unset"),
        REASON_UNKNOWN_COMMAND,
        None,
    )


def test_an_option_outside_the_permitted_set_is_refused() -> None:
    refusal = _refusal(("ai", "benchmark"), "output")

    assert refusal is not None
    assert (refusal.path, refusal.reason, refusal.option) == (
        ("ai", "benchmark"),
        REASON_OPTION_NOT_PERMITTED,
        "output",
    )


def test_a_permitted_option_of_a_read_only_command_runs() -> None:
    assert _refusal(("gh", "label", "list"), "repo") is None


def test_vault_get_stays_in_the_allow_list_without_its_show_option() -> None:
    allowlist = build_allowlist()
    refusal = _refusal(("vault", "get"), "show")

    assert allowlist[("vault", "get")] == frozenset({"path", "key", "dry_run"})
    assert refusal is not None
    assert (refusal.reason, refusal.option) == (REASON_OPTION_NOT_PERMITTED, "show")


def test_the_census_decides_every_row_of_the_exposure_table() -> None:
    allowlist = build_allowlist()
    decisions = {path: check_command(path) for path, *_ in CONST_MCP_EXPOSURE_TABLE}
    permitted = {path for path, refusal in decisions.items() if refusal is None}
    reasons = {refusal.reason for refusal in decisions.values() if refusal is not None}

    assert len(CONST_MCP_EXPOSURE_TABLE) == ROW_COUNT
    assert set(decisions) == {row[0] for row in CONST_MCP_EXPOSURE_TABLE}
    assert set(allowlist) == permitted
    assert reasons <= {
        REASON_UNKNOWN_COMMAND,
        REASON_NOT_READ_ONLY,
        REASON_PATH_OPTION,
        REASON_OPTION_NOT_PERMITTED,
    }
