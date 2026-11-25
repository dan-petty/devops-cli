"""Tests for CLI usage error hints, option error formatting, and the YAML hint table (#4860)."""

from __future__ import annotations

import difflib
import logging
import re
import shlex
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.commands.ci import CHECK_ROW_NAMES
from devops_cli.core.command_resolver import (
    ArgvPlaceholder,
    ArgvToken,
    resolve_devops_argv,
)
from devops_cli.core.usage_hints import command_for_path, load_usage_hints

CliRunnerFn = Callable[..., Any]

_BOX_END = re.compile(r"╰─+╯\s*\n?")
_DEVOPS_BACKTICK_CMD = re.compile(r"`(devops [^`]+)`")
_DEVOPS_INLINE_CMD = re.compile(r"\bdevops [^\n.;`]+")


def _hint_after_box(output: str) -> str:
    """Return the hint text printed after Click/Typer's Rich error panel."""
    matches = list(_BOX_END.finditer(output))
    if not matches:
        return ""
    return output[matches[-1].end() :].strip()


def _hint_command_tokens(command_line: str) -> list[ArgvToken]:
    """Convert a hint command string such as `devops pr view <n>` into resolver tokens."""
    words = shlex.split(command_line)
    assert words[0] == "devops"
    return [
        ArgvPlaceholder(expression=word, single_token=True) if "<" in word or "{" in word else word
        for word in words[1:]
    ]


def _extract_hint_commands(hint: str) -> list[str]:
    """Extract every `devops ...` command cited in a hint row."""
    backticked = _DEVOPS_BACKTICK_CMD.findall(hint)
    if backticked:
        return backticked
    return _DEVOPS_INLINE_CMD.findall(hint)


@pytest.mark.parametrize("args", [("pr", "merge", "1"), ("gh", "pr", "merge", "1")])
def test_by_design_hints_for_pr_merge(cli: CliRunnerFn, args: tuple[str, ...]) -> None:
    """By-design missing `merge` commands explain that only a person merges a pull request."""
    result = cli(*args)

    assert result.exit_code == 2
    assert "No such command 'merge'" in result.output
    hint = _hint_after_box(result.output)
    assert "only a person merges a pull request" in hint.lower()


@pytest.mark.parametrize(
    ("args", "expected_target"),
    [
        (("roadmap", "show", "1"), "devops roadmap explain <n>"),
        (("roadmap", "view", "1"), "devops roadmap explain <n>"),
        (("roadmap", "get", "1"), "devops roadmap explain <n>"),
        (("roadmap", "list"), "devops roadmap inbox"),
        (("roadmap", "status"), "devops roadmap inbox"),
    ],
)
def test_roadmap_synonym_hints(
    cli: CliRunnerFn, args: tuple[str, ...], expected_target: str
) -> None:
    """Roadmap synonym words point to `explain` or `inbox` after the error box."""
    result = cli(*args)

    assert result.exit_code == 2
    assert expected_target in _hint_after_box(result.output)


@pytest.mark.parametrize(
    ("args", "expected_fragment"),
    [
        (("pr", "show", "1"), "devops pr view <n>"),
        (("pr", "info", "1"), "devops pr view <n>"),
        (("gh", "pr", "show", "1"), "devops pr view <n>"),
        (("gh", "pr", "info", "1"), "devops pr view <n>"),
        (
            ("pr", "comment", "1"),
            "devops gh api repos/{owner}/{repo}/issues/<n>/comments -X POST -F body=@<file>",
        ),
        (
            ("gh", "pr", "comment", "1"),
            "devops gh api repos/{owner}/{repo}/issues/<n>/comments -X POST -F body=@<file>",
        ),
    ],
)
def test_pr_synonym_and_comment_hints(
    cli: CliRunnerFn, args: tuple[str, ...], expected_fragment: str
) -> None:
    """`pr` and `gh pr` synonyms and interim `comment` point to the right commands."""
    result = cli(*args)

    assert result.exit_code == 2
    assert expected_fragment in _hint_after_box(result.output)


@pytest.mark.parametrize(
    ("args", "external_cmd"),
    [
        (("openspec", "validate"), "openspec validate"),
        (("openspec", "list"), "openspec list"),
    ],
)
def test_openspec_other_tool_hints(
    cli: CliRunnerFn, args: tuple[str, ...], external_cmd: str
) -> None:
    """OpenSpec tool commands name both the OpenSpec CLI command and `devops openspec check`."""
    result = cli(*args)

    assert result.exit_code == 2
    hint = _hint_after_box(result.output)
    assert external_cmd in hint
    assert "devops openspec check" in hint


@pytest.mark.parametrize("args", [("ci", "list"), ("ci", "--list")])
def test_ci_list_and_dash_dash_list_print_all_row_names(
    cli: CliRunnerFn, args: tuple[str, ...]
) -> None:
    """`ci list` and `ci --list` print every gate row name in one line and exit 2."""
    result = cli(*args)

    assert result.exit_code == 2
    hint = _hint_after_box(result.output)
    assert "\n" not in hint
    for row_name in CHECK_ROW_NAMES:
        assert row_name in hint


@pytest.mark.parametrize(
    ("args", "expected_api"),
    [
        (
            ("gh", "issue", "view", "1", "--json", "number"),
            "devops gh api repos/{owner}/{repo}/issues/<n>",
        ),
        (
            ("gh", "issue", "view", "1", "--jq", ".number"),
            "devops gh api repos/{owner}/{repo}/issues/<n>",
        ),
        (
            ("gh", "issue", "view", "1", "--comments"),
            "devops gh api repos/{owner}/{repo}/issues/<n>/comments",
        ),
        (("gh", "issue", "view", "1", "--search", "foo"), "devops gh api search/issues"),
        (("gh", "issue", "list", "--json", "number"), "devops gh api repos/{owner}/{repo}/issues"),
        (
            ("gh", "issue", "list", "--jq", ".[].number"),
            "devops gh api repos/{owner}/{repo}/issues",
        ),
        (
            ("gh", "issue", "list", "--comments"),
            "devops gh api repos/{owner}/{repo}/issues/comments",
        ),
        (("gh", "issue", "list", "--search", "foo"), "devops gh api search/issues"),
        (("gh", "pr", "view", "1", "--search", "foo"), "devops gh api search/issues"),
        (("gh", "pr", "list", "--comments"), "devops gh api repos/{owner}/{repo}/pulls/comments"),
        (("pr", "view", "1", "--search", "foo"), "devops gh api search/issues"),
        (("pr", "list", "--comments"), "devops gh api repos/{owner}/{repo}/pulls/comments"),
    ],
)
def test_interim_gh_flag_hints(cli: CliRunnerFn, args: tuple[str, ...], expected_api: str) -> None:
    """Unsupported `gh`-style flags suggest the matching `devops gh api` endpoint."""
    result = cli(*args)

    assert result.exit_code == 2
    assert expected_api in _hint_after_box(result.output)


@pytest.mark.parametrize(
    ("args", "expected_hint"),
    [
        (("ai", "cost-report"), "Did you mean: devops ai cost report"),
        (("ai", "cost_report"), "Did you mean: devops ai cost report"),
        (("explain",), "Did you mean: devops roadmap explain"),
        (("zizmor",), "Did you mean: devops ci zizmor"),
    ],
)
def test_cross_group_lookup_matches_whole_words_and_splits(
    cli: CliRunnerFn, args: tuple[str, ...], expected_hint: str
) -> None:
    """Whole-word and hyphen/underscore split lookups suggest the matching command path."""
    result = cli(*args)

    assert result.exit_code == 2
    assert expected_hint == _hint_after_box(result.output)


@pytest.mark.parametrize("args", [("ai", "cost-rep"), ("ai", "repo"), ("expl",)])
def test_cross_group_lookup_ignores_prefixes(cli: CliRunnerFn, args: tuple[str, ...]) -> None:
    """Partial prefixes never trigger cross-group command hints."""
    result = cli(*args)

    assert result.exit_code == 2
    assert "Did you mean: devops" not in _hint_after_box(result.output)


def test_unknown_option_excludes_help_and_lists_small_option_sets(cli: CliRunnerFn) -> None:
    """`--help`/`-h` never appear in `Possible options`, and `<= 6` option sets are listed."""
    hel = cli("gh", "issue", "view", "1", "--hel")
    assert hel.exit_code == 2
    assert "--help" not in hel.output
    assert "Possible options: -h" not in hel.output
    assert "(Possible options: --repo)" in hel.output

    bogus = cli("gh", "issue", "view", "1", "--bogus")
    assert bogus.exit_code == 2
    assert "--help" not in bogus.output
    assert "(Possible options: --repo)" in bogus.output

    repp = cli("gh", "issue", "view", "1", "--repp")
    assert repp.exit_code == 2
    assert "--help" not in repp.output
    assert "(Possible options: --repo)" in repp.output

    edit_hel = cli("gh", "issue", "edit", "1", "--hel")
    assert edit_hel.exit_code == 2
    assert "--help" not in edit_hel.output
    assert "Possible options" not in edit_hel.output

    edit_bogus = cli("gh", "issue", "edit", "1", "--zzzzzz")
    assert edit_bogus.exit_code == 2
    assert "Possible options" not in edit_bogus.output


def test_missing_option_shows_option_help_line(cli: CliRunnerFn) -> None:
    """A `Missing option` error includes the option's help description."""
    result = cli("pr", "describe", "1")

    assert result.exit_code == 2
    assert "Missing option '--summary' / '-s'." in result.output
    assert "Summary of the title" in result.output


def test_hint_table_commands_resolve_with_command_resolver() -> None:
    """Every `devops` command cited by `usage_hints.yaml` resolves cleanly."""
    for entry in load_usage_hints():
        for command_line in _extract_hint_commands(entry.hint):
            tokens = _hint_command_tokens(command_line)
            assert resolve_devops_argv(tokens) is None, (
                f"{entry.command_path} {entry.typed!r}: unresolved hint command {command_line!r}"
            )


def test_hint_table_does_not_duplicate_click_difflib_targets() -> None:
    """No YAML hint suggests the same name Click's `difflib.get_close_matches` already gives."""
    for entry in load_usage_hints():
        cmd = command_for_path(entry.command_path)
        if entry.typed.startswith("-"):
            options = [
                opt
                for param in cmd.params
                for opt in getattr(param, "opts", ())
                if opt.startswith("--")
            ]
            assert entry.typed not in options, (
                f"{entry.command_path} {entry.typed!r}: option exists on the command"
            )
            close = difflib.get_close_matches(entry.typed, options)
        else:
            close = difflib.get_close_matches(entry.typed, list(cmd.commands.keys()))
        for match in close:
            for command_line in _extract_hint_commands(entry.hint):
                assert command_line.split()[-1] != match, (
                    f"{entry.command_path} {entry.typed!r}: duplicates Click match {match!r}"
                )


def test_usage_error_log_records_hinted_boolean(
    cli: CliRunnerFn,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Both `cli_usage_error` logs and the ledger JSONL file record `hinted` accurately."""
    from devops_cli.telemetry.usage_errors import UsageErrorRecord, ledger_path

    monkeypatch.setenv("DEVOPS_TELEMETRY_USAGE_LEDGER", "true")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    caplog.set_level(logging.WARNING, logger="devops_cli.telemetry.usage_errors")

    cli("pr", "merge", "1")
    cli("gh", "prr", "list")

    records = [r for r in caplog.records if r.getMessage() == "cli_usage_error"]
    assert [getattr(r, "usage.hinted", None) for r in records[-2:]] == [True, False]

    ledger_entries = [
        UsageErrorRecord.model_validate_json(line)
        for line in ledger_path().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [entry.hinted for entry in ledger_entries[-2:]] == [True, False]
