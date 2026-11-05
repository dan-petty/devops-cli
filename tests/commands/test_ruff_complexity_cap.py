"""The gate's `ruff check` flags keep the complexity and nesting caps (#586, #1876).

Four things could take a function past a cap without a marker to count: a setting in
`pyproject.toml`, a Ruff configuration file nearer the function, an ignore file that hides the
function from Ruff's walk, and a flag on the command that runs Ruff. `ruff check --config
pyproject.toml` closes the nested configuration files. The resolved settings of Ruff and the walk
of Ruff against the files that git tracks close the rest: they run in the `lint` row of
`devops ci` (`tests/gate/ruff_config.py`, #2164), and the cases below give the check
canned settings, so Ruff does not start. This file holds the flags of every `ruff check` that the
pre-commit configuration, the workflows and the rows of `devops ci` run.
Suppression comments are counted by `tests/invariants/test_architectural_invariants.py`.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from devops_cli.commands.ci import get_check_specs
from devops_cli.config.constants import (
    CONST_PYPROJECT_FILENAME,
    CONST_YAML_SUFFIXES,
)
from devops_cli.config.defaults import DEFAULT_MAX_COMPLEXITY
from tests.gate.ruff_config import (
    CONST_BANNED_HAND_ROLLED_APIS,
    MAX_NESTED_BLOCKS,
    cap_breaches,
    setting,
    tracked_sources_ruff_skips,
)
from tests.support.paths import REPO_ROOT

CONST_RUFF_CHECK_GATE_FLAGS: Final[frozenset[str]] = frozenset({"--config", "--fix"})
_CONFIG_PIN = ["--config", CONST_PYPROJECT_FILENAME]


def _settings_text(**moved: str) -> str:
    """The lines of `ruff check --show-settings` that the check reads, for a configuration that
    holds the caps; a keyword replaces the value of one key (a dot is written as `__`)."""
    banned = "\n".join(f"\t{api} => {{ msg: x }}," for api in CONST_BANNED_HAND_ROLLED_APIS)
    values = {
        "linter.rules.enabled": "[\n\t(C901) mccabe,\n\t(PLR1702) pylint,\n\t(PGH004) x,\n"
        "\t(RUF100) x,\n\t(TID251) x,\n]",
        "linter.mccabe.max_complexity": str(DEFAULT_MAX_COMPLEXITY),
        "linter.pylint.max_nested_blocks": str(MAX_NESTED_BLOCKS),
        "linter.preview": "enabled",
        "linter.explicit_preview_rules": "true",
        "formatter.preview": "disabled",
        "linter.per_file_ignores": "{}",
        "linter.exclude": "[]",
        "linter.flake8_tidy_imports.banned_api": "{\n" + banned + "\n}",
    }
    values.update({key.replace("__", "."): value for key, value in moved.items()})
    return "\n".join(f"{key} = {value}" for key, value in values.items()) + "\n"


def test_settings_that_hold_the_caps_and_the_bans_report_no_breach() -> None:
    """The control of the cases below: the resolved settings of a sound configuration."""
    assert cap_breaches(_settings_text()) == []


@pytest.mark.parametrize(
    ("moved", "breach"),
    [
        pytest.param(
            {"linter__mccabe__max_complexity": "11"},
            "linter.mccabe.max_complexity: 11, not 10",
            id="cap-raised",
        ),
        pytest.param(
            {
                "linter__rules__enabled": "[\n\t(PLR1702) x,\n\t(PGH004) x,\n\t(RUF100) x,\n\t(TID251) x,\n]"
            },
            "C901: not enabled",
            id="cap-not-enabled",
        ),
        pytest.param({"linter__exclude": '["src/**"]'}, "linter.exclude: ", id="lint-exclude"),
        pytest.param(
            {"linter__flake8_tidy_imports__banned_api": "{\n\tsocket.inet_ntoa => x,\n}"},
            "socket.inet_aton: not banned",
            id="banned-api-dropped",
        ),
        pytest.param(
            {"linter__per_file_ignores": '{"src/**": [C901]}'},
            "linter.per_file_ignores",
            id="per-file-waiver",
        ),
        pytest.param(
            {"linter__pylint__max_nested_blocks": "5"},
            "linter.pylint.max_nested_blocks: 5, not 4",
            id="nesting-cap-raised",
        ),
        pytest.param(
            {"linter__preview": "disabled"}, "linter.preview: disabled", id="lint-preview-off"
        ),
        pytest.param(
            {"linter__explicit_preview_rules": "false"},
            "linter.explicit_preview_rules: false, not true",
            id="every-preview-rule-on",
        ),
        pytest.param(
            {"formatter__preview": "enabled"},
            "formatter.preview: enabled, not disabled",
            id="formatter-preview-on",
        ),
    ],
)
def test_settings_that_weaken_a_cap_or_a_ban_are_named(moved: dict[str, str], breach: str) -> None:
    """Each change to the resolved settings that weakens a cap or a ban is named."""
    assert any(breach in line for line in cap_breaches(_settings_text(**moved)))


def test_a_setting_that_ruff_does_not_print_is_none() -> None:
    """A key that the output lacks reads as None, so the check names the missing key."""
    assert (setting("a = 1\n", "b"), setting("a = 1\n", "a")) == (None, "1")


def test_a_tracked_source_that_the_walk_of_ruff_skips_is_named(tmp_path: Path) -> None:
    """A source committed with `git add -f` under an ignore file is named, whichever file hides it."""
    for name in ("src/seen.py", "src/hidden.py"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    walked = [str(tmp_path / "src" / "seen.py")]

    assert tracked_sources_ruff_skips(tmp_path, ["src/seen.py", "src/hidden.py", ""], walked) == [
        "src/hidden.py"
    ]


def _invocation_problems(args: Sequence[str]) -> list[str]:
    """Name each flag of one `ruff check` that is not the gate's own, and a missing config pin."""
    flags = [arg.partition("=")[0] for arg in args if arg.startswith("-")]
    strays = [
        f"{flag}: not a flag the gate passes"
        for flag in flags
        if flag not in CONST_RUFF_CHECK_GATE_FLAGS
    ]
    pins = [
        args[n + 1] if arg == "--config" and n + 1 < len(args) else arg.partition("=")[2]
        for n, arg in enumerate(args)
        if arg == "--config" or arg.startswith("--config=")
    ]
    pinned = (
        [] if pins == [CONST_PYPROJECT_FILENAME] else [f"--config {pins}, not {_CONFIG_PIN[1]}"]
    )
    return [*strays, *pinned]


def _runs_ruff_check(argv: Sequence[str]) -> bool:
    """Report whether an argv runs `ruff check`."""
    return "ruff" in argv and list(argv[argv.index("ruff") + 1 :][:1]) == ["check"]


def _run_scripts(node: object) -> Iterator[str]:
    """Yield every `run` script in a parsed workflow or composite action."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key == "run" and isinstance(value, str):
                yield value
            else:
                yield from _run_scripts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _run_scripts(item)


def _hook_argv(hook: Mapping[str, Any]) -> list[str]:
    """Return the argv of a pre-commit hook: its `entry` and `args`.

    The `ruff-check` hook of ruff-pre-commit sets its `entry` in that repository, so it has none
    here, and its argv is `ruff check` followed by the `args` written in this one.
    """
    args = hook.get("args", [])
    if "entry" in hook:
        return [*shlex.split(hook["entry"]), *args]
    return ["ruff", "check", *args] if hook["id"] == "ruff-check" else []


def _file_invocations(root: Path) -> dict[str, list[str]]:
    """Map each `ruff check` in the pre-commit configuration and `.github` to its arguments."""
    found: dict[str, list[str]] = {}
    hooks = yaml.safe_load((root / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    for hook in (hook for repo in hooks["repos"] for hook in repo["hooks"]):
        argv = _hook_argv(hook)
        if _runs_ruff_check(argv):
            found[f"pre-commit {hook['id']}"] = argv[argv.index("check") + 1 :]
    for path in sorted(p for p in (root / ".github").rglob("*") if p.suffix in CONST_YAML_SUFFIXES):
        scripts = _run_scripts(yaml.safe_load(path.read_text(encoding="utf-8")))
        joined = (script.replace("\\\n", " ") for script in scripts)
        for line in (line for script in joined for line in script.splitlines()):
            if match := re.search(r"\bruff check\b(.*)", line):
                found[f"{path.relative_to(root).as_posix()}: {line.strip()}"] = shlex.split(
                    match[1]
                )
    return found


def _row_invocations() -> dict[str, list[str]]:
    """Map each `ruff check` in the rows of `devops ci` to its arguments."""
    return {
        f"devops ci row {spec.name} {field}": cmd[cmd.index("check") + 1 :]
        for spec in get_check_specs()
        for field, cmd in (("cmd", spec.cmd), ("fix_cmd", spec.fix_cmd or []))
        if _runs_ruff_check(cmd)
    }


def test_every_ruff_check_of_the_gate_is_pinned_to_pyproject_and_overrides_nothing() -> None:
    """No hook, workflow step or `devops ci` row selects, ignores, extends or isolates Ruff's rules.

    A flag such as `--ignore C901` or `--isolated` takes a function past the cap as surely as
    a setting does, and a `ruff check` with no `--config pyproject.toml` lets a nearer
    configuration file do the same.
    """
    found = {**_row_invocations(), **_file_invocations(REPO_ROOT)}
    problems = {site: _invocation_problems(args) for site, args in found.items()}

    assert (
        {"devops ci row lint cmd", "devops ci row lint fix_cmd", "pre-commit ruff-check"}
        <= found.keys(),
        {site: problem for site, problem in problems.items() if problem},
    ) == (True, {})


@pytest.mark.parametrize(
    ("args", "problem"),
    [
        pytest.param([*_CONFIG_PIN, "."], None, id="the-gate"),
        pytest.param([*_CONFIG_PIN, "--fix", "."], None, id="the-gate-with-fixes"),
        pytest.param([*_CONFIG_PIN, "--select", "E", "."], "--select", id="select"),
        pytest.param([*_CONFIG_PIN, "--ignore=C901", "."], "--ignore", id="ignore"),
        pytest.param([*_CONFIG_PIN, "--extend-ignore", "C901"], "--extend-ignore", id="extend"),
        pytest.param([*_CONFIG_PIN, "--isolated"], "--isolated", id="isolated"),
        pytest.param(["--config", "ruff.toml", "."], "--config ['ruff.toml']", id="other-config"),
        pytest.param(
            [*_CONFIG_PIN, "--config", "lint.ignore=['C901']"], "--config [", id="config-override"
        ),
        pytest.param(["."], "--config []", id="no-config"),
    ],
)
def test_a_ruff_check_that_overrides_the_configuration_is_named(
    args: list[str], problem: str | None
) -> None:
    """Each flag outside the gate's own, and a missing or second `--config`, is named."""
    problems = _invocation_problems(args)

    assert (not problems) if problem is None else any(problem in line for line in problems)


def test_a_hook_or_workflow_step_that_overrides_the_configuration_is_named(tmp_path: Path) -> None:
    """The scan reads the `args` of the ruff-check hook and the `run` lines of a workflow or action."""
    hooks = {
        "repos": [
            {"hooks": [{"id": "ruff-check", "args": [*_CONFIG_PIN, "--select", "E"]}]},
        ]
    }
    (tmp_path / ".pre-commit-config.yaml").write_text(yaml.safe_dump(hooks), encoding="utf-8")
    action: dict[str, Any] = {"runs": {"steps": [{"run": "uv run ruff check --isolated ."}]}}
    (tmp_path / ".github" / "actions").mkdir(parents=True)
    (tmp_path / ".github" / "actions" / "action.yml").write_text(
        yaml.safe_dump(action), encoding="utf-8"
    )

    found = _file_invocations(tmp_path)

    assert {site: _invocation_problems(args) for site, args in found.items()} == {
        "pre-commit ruff-check": ["--select: not a flag the gate passes"],
        ".github/actions/action.yml: uv run ruff check --isolated .": [
            "--isolated: not a flag the gate passes",
            "--config [], not pyproject.toml",
        ],
    }


def test_a_continued_ruff_check_is_read_as_one_command(tmp_path: Path) -> None:
    """A `run` script that breaks a `ruff check` over lines is read whole, and its stray flag is named."""
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    script = "uv run ruff check --config pyproject.toml \\\n  --select E \\\n  .\n"
    workflow: dict[str, Any] = {"jobs": {"lint": {"steps": [{"run": script}]}}}
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "lint.yml").write_text(
        yaml.safe_dump(workflow), encoding="utf-8"
    )

    found = _file_invocations(tmp_path)

    assert [_invocation_problems(args) for args in found.values()] == [
        ["--select: not a flag the gate passes"]
    ]
