"""`devops openspec check`, `regenerate` and `archive`: wiring, output and exit code (#1844)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.openspec import OpenSpecFake

Cli = Callable[..., Any]

ARCHIVE_COMMAND = ("archive", "1930-export-widgets", "--yes")
VALIDATE_COMMAND = ("validate", "--all", "--strict")


def _runs_after_the_settings(fake: OpenSpecFake) -> list[tuple[tuple[str, ...], Path]]:
    """The commands the fake ran after the four `config set` runs of the isolated configuration,
    each with the directory it was started in."""
    return [(call.argv, call.cwd) for call in fake.calls if call.argv[0] != "config"]


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


def test_archive_archives_the_change_then_validates_every_spec_and_change(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The order is the point: the validation reads what the archive wrote. The archive passes
    `--yes` and never `--skip-specs`, which a change that declares `skip_specs` does not need."""
    tree = openspec_fake.tree("archive-adds-a-spec")
    monkeypatch.chdir(tree)

    result = cli("openspec", "archive", "1930-export-widgets")

    assert (result.exit_code, "Archived 1930-export-widgets." in result.output) == (0, True)
    assert _runs_after_the_settings(openspec_fake) == [
        (ARCHIVE_COMMAND, tree),
        (VALIDATE_COMMAND, tree),
    ]


def test_archive_runs_under_the_opt_outs_and_a_configuration_directory_of_its_own(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A direct `openspec archive` would report usage and read the developer's own profile. Both
    runs opt out and read one scratch directory, which is gone when the command ends."""
    developer_config = tmp_path / "developer-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(developer_config))
    monkeypatch.setenv("OPENSPEC_TELEMETRY", "1")
    monkeypatch.chdir(openspec_fake.tree("archive-adds-a-spec"))

    cli("openspec", "archive", "1930-export-widgets")

    [config_home] = {Path(call.env["XDG_CONFIG_HOME"]) for call in openspec_fake.calls}
    opt_outs = {
        "DO_NOT_TRACK": "1",
        "OPENSPEC_NO_UPDATE_CHECK": "1",
        "OPENSPEC_TELEMETRY": "0",
        "OPEN_SPEC_INTERACTIVE": "0",
    }
    assert (
        [
            {key: value for key, value in call.env.items() if key != "XDG_CONFIG_HOME"}
            for call in openspec_fake.calls
        ],
        config_home == developer_config,
        config_home.exists(),
    ) == ([opt_outs] * 6, False, False)


def test_a_refused_archive_skips_the_validation_and_exits_1(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tool refuses a `MODIFIED` of a spec that does not exist and changes no file, so there is
    nothing to validate: the command stops at the archive and reports why."""
    tree = openspec_fake.tree("archive-is-refused")
    monkeypatch.chdir(tree)

    result = cli("openspec", "archive", "1931-export-json")

    assert result.exit_code == 1
    assert "target spec does not exist" in result.output
    assert "Aborted. No files were changed." in result.output
    assert "The validation did not run." in result.output
    assert _runs_after_the_settings(openspec_fake) == [
        (("archive", "1931-export-json", "--yes"), tree)
    ]


def test_an_archive_that_leaves_a_spec_the_validation_fails_exits_1(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new capability without a Purpose archives with exit 0 and a placeholder, which only the
    validation fails. The command reports it, so the author fixes the spec in the same commit."""
    tree = openspec_fake.tree("archive-leaves-a-placeholder-purpose")
    monkeypatch.chdir(tree)

    result = cli("openspec", "archive", "1932-export-widgets")

    assert result.exit_code == 1
    assert "Purpose section is still a placeholder" in result.output
    assert "The archive is applied." in result.output
    assert _runs_after_the_settings(openspec_fake) == [
        (("archive", "1932-export-widgets", "--yes"), tree),
        (VALIDATE_COMMAND, tree),
    ]


def test_a_failed_validation_names_the_failing_spec_after_a_dozen_passing_ones(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`validate` prints a line for each passing spec on standard output and the failure on
    standard error. A tree of a dozen specs fills 256 characters with the passing lines, so the
    command prints the whole output: the author sees which spec failed and why."""
    tree = openspec_fake.tree("archive-leaves-a-placeholder-purpose")
    failed = openspec_fake.scenarios["archive-leaves-a-placeholder-purpose"][VALIDATE_COMMAND]
    passing = "".join(f"✓ spec/capability-{number:02d}\n" for number in range(12))
    openspec_fake.script(VALIDATE_COMMAND, 1, passing + failed.stdout, failed.stderr)
    monkeypatch.chdir(tree)

    result = cli("openspec", "archive", "1932-export-widgets")

    assert len(passing + failed.stdout) > 256
    assert (
        result.exit_code,
        "✗ spec/widget-export" in result.output,
        "Purpose section is still a placeholder" in result.output,
        "Do not run the archive again." in result.output,
    ) == (1, True, True, True)


def test_archive_in_a_dry_run_executes_as_no_external_request(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dry run executes openspec archive normally without external requests."""
    monkeypatch.chdir(openspec_fake.tree("archive-adds-a-spec"))

    result = cli("--dry-run", "openspec", "archive", "1930-export-widgets")

    assert (
        result.exit_code,
        "Archived 1930-export-widgets" in result.output,
    ) == (0, True)


def test_the_commands_are_registered_under_openspec(cli: Cli) -> None:
    """`devops openspec --help` lists all three commands, each as the first word of a row."""
    result = cli("openspec", "--help")

    assert (result.exit_code, sorted(re.findall(r"^│ (\w+) ", result.output, re.MULTILINE))) == (
        0,
        ["archive", "check", "regenerate"],
    )
