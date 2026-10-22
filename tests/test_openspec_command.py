"""`devops openspec check` and `devops openspec regenerate`: wiring, output and exit code (#1844)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.support.fakes.openspec import OpenSpecFake

Cli = Callable[..., Any]


def test_check_passes_a_sound_tree_and_exits_0(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate reports success in one line."""
    monkeypatch.chdir(openspec_fake.tree("empty"))

    result = cli("openspec", "check")

    assert (result.exit_code, "OpenSpec check passed." in result.output) == (0, True)


def test_check_prints_each_problem_with_its_check_and_exits_1(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every finding is a line led by the check that found it, then the count."""
    monkeypatch.chdir(openspec_fake.tree("requirement-modified-twice"))

    result = cli("openspec", "check")

    assert result.exit_code == 1
    assert [line for line in result.output.splitlines() if line.strip()][:2] == [
        'overlap: widget-export: the requirement "Export widgets" is rewritten by '
        "1915-export-json (MODIFIED), 1916-export-yaml (MODIFIED): both would archive and the "
        "later would overwrite the earlier with no signal, so fold the items into one change or "
        "order them with a blocker, so that the second waits until the first archives.",
        "OpenSpec check found 1 problem(s).",
    ]


def test_check_without_openspec_exits_1_naming_the_install_command(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row fails early with the one command that installs the pinned tool."""
    monkeypatch.chdir(openspec_fake.tree("empty"))
    openspec_fake.installed = False

    result = cli("openspec", "check")

    assert result.exit_code == 1
    assert "uv run devops install-tools --tool openspec --only-missing" in result.output


def test_regenerate_writes_the_skills_under_the_isolated_profile_and_never_a_bare_update(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare `openspec update` takes the developer's own profile, which once rewrote six of the
    eight skills and added two that write the living spec."""
    tree = openspec_fake.tree("empty")
    stale = tree / ".agents/skills/openspec-archive-change/SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("Archive.\n", encoding="utf-8")
    monkeypatch.chdir(tree)

    result = cli("openspec", "regenerate")

    assert (
        result.exit_code,
        [(call.argv, call.cwd) for call in openspec_fake.calls],
        stale.exists(),
    ) == (
        0,
        [
            (("config", "set", "telemetry.enabled", "false"), openspec_fake.calls[0].cwd),
            (("config", "set", "delivery", "skills"), openspec_fake.calls[0].cwd),
            (("config", "set", "profile", "custom"), openspec_fake.calls[0].cwd),
            (
                ("config", "set", "workflows", '["propose", "explore", "apply", "update"]'),
                openspec_fake.calls[0].cwd,
            ),
            (("update", "--force"), tree),
        ],
        False,
    )


def test_regenerate_in_a_dry_run_writes_and_runs_nothing(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dry run reports the command and starts no process."""
    tree = openspec_fake.tree("empty")
    monkeypatch.chdir(tree)

    result = cli("--dry-run", "openspec", "regenerate")

    assert (result.exit_code, openspec_fake.calls) == (0, [])


def test_the_commands_are_registered_under_openspec(cli: Cli) -> None:
    """`devops openspec --help` lists both commands."""
    result = cli("openspec", "--help")

    assert (result.exit_code, "check" in result.output, "regenerate" in result.output) == (
        0,
        True,
        True,
    )
