"""Ruff holds the complexity and nesting caps, and the gate's own flags and settings keep them.

Ruff's C901 is the cap of 10 (#586). Ruff's PLR1702 caps a function at 4 nested blocks (#1876): it
is a preview rule, so lint preview is on with `explicit-preview-rules`, and no other preview rule
runs unless `select` names it; the formatter stays out of preview. Four things could take a function past it without
a marker to count: a setting in `pyproject.toml`, a Ruff configuration file nearer the
function, an ignore file that hides the function from Ruff's walk, and a flag on the command
that runs Ruff. `ruff check --config pyproject.toml` closes the nested configuration files, the
resolved settings of Ruff itself show the rest of the configuration, Ruff and git together show
whether any tracked source escapes the walk, and one test holds every `ruff check` to those flags.
Suppression comments are counted by `tests/test_architectural_invariants.py`.
"""

from __future__ import annotations

import itertools
import json
import re
import shlex
import subprocess
import tomllib
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec, get_check_specs
from devops_cli.config.constants import (
    CONST_PYPROJECT_FILENAME,
    CONST_YAML_SUFFIXES,
)
from devops_cli.config.defaults import DEFAULT_MAX_COMPLEXITY
from tests.support.paths import REPO_ROOT

CONST_BANNED_HAND_ROLLED_APIS: Final[tuple[str, ...]] = (
    "socket.inet_aton",
    "socket.inet_ntoa",
    "socket.inet_pton",
    "socket.inet_ntop",
)
CONST_COMPLEXITY_LINT_RULES: Final[frozenset[str]] = frozenset(
    {"C901", "PLR1702", "PGH004", "RUF100"}
)
CONST_RUFF_CHECK_GATE_FLAGS: Final[frozenset[str]] = frozenset({"--config", "--fix"})
CONST_RUFF_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".ipynb"})

_RUFF_TIMEOUT_SECONDS = 60
# The deepest nesting a function may have: four nested blocks pass, five fail (#1876).
_MAX_NESTED_BLOCKS = 4
_BANNED_API_RULE = "TID251"
_CONFIG_PIN = ["--config", CONST_PYPROJECT_FILENAME]
_COMPLEXITY_ELEVEN = "def over(x):\n" + "".join(
    f"    if x == {n}:\n        return {n}\n" for n in range(10)
)

# A Ruff configuration file in each spelling and place Ruff discovers one, each ignoring the cap.
_NESTED_CONFIGURATIONS = {
    "src/pkg/ruff.toml": '[lint]\nignore = ["C901"]\n',
    "src/pkg/.ruff.toml": '[lint]\nignore = ["C901"]\n',
    "src/pkg/pyproject.toml": '[tool.ruff.lint]\nignore = ["C901"]\n',
    "ruff.toml": '[lint]\nignore = ["C901"]\n',
}


def _gate_ruff_args() -> list[str]:
    """Return the arguments the lint row of `devops ci` passes to `ruff`."""
    cmd = get_check_spec("lint").cmd
    return cmd[cmd.index("ruff") + 1 :]


def _ruff(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the `ruff` on PATH inside one project directory."""
    return subprocess.run(
        ["ruff", *args],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        timeout=_RUFF_TIMEOUT_SECONDS,
    )


def _setting(settings: str, key: str) -> str:
    """Read one value of `ruff check --show-settings`, a list or table up to its closing line."""
    lines = settings.splitlines()
    opening = next((n for n, line in enumerate(lines) if line.startswith(f"{key} = ")), None)
    if opening is None:
        pytest.fail(f"`ruff check --show-settings` printed no {key}")
    value = lines[opening].removeprefix(f"{key} = ")
    closing = {"[": "]", "{": "}"}.get(value)
    if closing is None:
        return value
    return "\n".join(itertools.takewhile(lambda line: line != closing, lines[opening + 1 :]))


def _cap_breaches(settings: str) -> list[str]:
    """Name each way the resolved settings let a function past the cap, or drop the banned APIs."""
    enabled = _setting(settings, "linter.rules.enabled")
    unenforced = [
        f"{rule}: not enabled"
        for rule in sorted({*CONST_COMPLEXITY_LINT_RULES, _BANNED_API_RULE})
        if f"({rule})" not in enabled
    ]
    wanted = {
        "linter.mccabe.max_complexity": str(DEFAULT_MAX_COMPLEXITY),
        "linter.pylint.max_nested_blocks": str(_MAX_NESTED_BLOCKS),
        "linter.preview": "enabled",
        "linter.explicit_preview_rules": "true",
        "formatter.preview": "disabled",
        "linter.per_file_ignores": "{}",
        "linter.exclude": "[]",
    }
    moved = [
        f"{key}: {found}, not {value}"
        for key, value in wanted.items()
        if (found := _setting(settings, key)) != value
    ]
    banned = _setting(settings, "linter.flake8_tidy_imports.banned_api")
    unbanned = [
        f"{api}: not banned" for api in sorted(CONST_BANNED_HAND_ROLLED_APIS) if api not in banned
    ]
    return [*unenforced, *moved, *unbanned]


def _write_project(project: Path, pyproject: str, files: Mapping[str, str]) -> None:
    """Write a pyproject.toml and the named files into a project directory."""
    (project / CONST_PYPROJECT_FILENAME).write_text(pyproject, encoding="utf-8")
    for name, text in files.items():
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        (project / name).write_text(text, encoding="utf-8")


def _real_pyproject() -> str:
    """Read the repository's own pyproject.toml."""
    return (REPO_ROOT / CONST_PYPROJECT_FILENAME).read_text(encoding="utf-8")


def _real_ruff_table() -> dict[str, Any]:
    """Parse the `tool.ruff` table of the repository's own pyproject.toml, as a fresh dict."""
    ruff: dict[str, Any] = tomllib.loads(_real_pyproject())["tool"]["ruff"]
    return ruff


def _toml_tables(table: Mapping[str, Any], path: Sequence[str]) -> Iterator[str]:
    """Yield the TOML of a table, then of its sub-tables, with every key and header part quoted.

    The project depends on no TOML writer, and `tool.ruff` holds only strings, numbers, booleans,
    lists of them and tables. The escapes of a JSON string and list are the escapes of a TOML one.
    """
    pairs = [(key, value) for key, value in table.items() if not isinstance(value, Mapping)]
    if pairs:
        yield f"[{'.'.join(json.dumps(part) for part in path)}]\n"
        yield from (
            f"{json.dumps(key)} = {json.dumps(value, ensure_ascii=False)}\n" for key, value in pairs
        )
    for key, value in table.items():
        if isinstance(value, Mapping):
            yield from _toml_tables(value, (*path, key))


def _pyproject_text(ruff: Mapping[str, Any]) -> str:
    """Write a pyproject.toml that holds only the given `tool.ruff` table."""
    return "".join(_toml_tables(ruff, ("tool", "ruff")))


def _reported_codes(run: subprocess.CompletedProcess[str]) -> set[str]:
    """List the rule codes a `ruff check --output-format json` run reported."""
    return {finding["code"] for finding in json.loads(run.stdout)}


def _tracked_sources_ruff_skips(project: Path) -> list[str]:
    """List each tracked Python source that the gate's `ruff check` walk does not reach."""
    tracked = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--",
            *(f"*{suffix}" for suffix in sorted(CONST_RUFF_SOURCE_SUFFIXES)),
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
        timeout=_RUFF_TIMEOUT_SECONDS,
    ).stdout.split("\0")
    walked = _ruff(project, *_gate_ruff_args(), "--show-files").stdout.splitlines()
    reached = {Path(name).resolve() for name in walked}
    return [
        name
        for name in tracked
        if name and (project / name).is_file() and (project / name).resolve() not in reached
    ]


@pytest.mark.live("ruff")
def test_the_resolved_ruff_settings_hold_the_complexity_cap() -> None:
    """Ruff itself reports C901 enabled at 10 and PLR1702 at 4 through explicit lint preview, with
    no waiver, no lint exclusion and the banned APIs.

    The resolved settings answer what `select`, `ignore`, `extend-*`, `extend`, and prefix
    resolution add up to, which a test of the keys in `pyproject.toml` can only guess at.
    """
    settings = _ruff(
        REPO_ROOT, "check", *_CONFIG_PIN, "--show-settings", "src/devops_cli/__init__.py"
    ).stdout

    assert _cap_breaches(settings) == []


def test_the_writer_gives_back_the_real_ruff_table() -> None:
    """The TOML the weakened projects are written in parses to the table it was written from."""
    ruff = _real_ruff_table()

    assert tomllib.loads(_pyproject_text(ruff)) == {"tool": {"ruff": ruff}}


@pytest.mark.live("ruff")
def test_a_rebuilt_pyproject_that_weakens_nothing_holds_the_cap(tmp_path: Path) -> None:
    """The control of the weakened projects: the real table, written again, breaks no rule."""
    _write_project(tmp_path, _pyproject_text(_real_ruff_table()), {"src/mod.py": "x = 1\n"})
    settings = _ruff(tmp_path, "check", *_CONFIG_PIN, "--show-settings", "src/mod.py").stdout

    assert _cap_breaches(settings) == []


@pytest.mark.live("ruff")
@pytest.mark.parametrize(
    ("weaken", "breach"),
    [
        pytest.param(
            lambda ruff: ruff["lint"]["mccabe"].update({"max-complexity": 11}),
            "linter.mccabe.max_complexity: 11, not 10",
            id="cap-raised",
        ),
        pytest.param(
            lambda ruff: ruff["lint"]["select"].remove("C901"),
            "C901: not enabled",
            id="cap-not-selected",
        ),
        pytest.param(
            lambda ruff: ruff["lint"]["ignore"].append("C901"),
            "C901: not enabled",
            id="cap-ignored",
        ),
        pytest.param(
            lambda ruff: ruff["lint"].update({"exclude": ["src/**"]}),
            "linter.exclude: ",
            id="lint-exclude",
        ),
        pytest.param(
            lambda ruff: ruff["lint"]["flake8-tidy-imports"]["banned-api"].pop("socket.inet_aton"),
            "socket.inet_aton: not banned",
            id="banned-api-dropped",
        ),
        pytest.param(
            lambda ruff: ruff["lint"].update({"per-file-ignores": {"src/**": ["C901"]}}),
            "linter.per_file_ignores",
            id="per-file-waiver",
        ),
        pytest.param(
            lambda ruff: ruff["lint"]["pylint"].update({"max-nested-blocks": 5}),
            "linter.pylint.max_nested_blocks: 5, not 4",
            id="nesting-cap-raised",
        ),
        pytest.param(
            lambda ruff: ruff["lint"]["select"].remove("PLR1702"),
            "PLR1702: not enabled",
            id="nesting-cap-not-selected",
        ),
        pytest.param(
            lambda ruff: ruff["lint"].update({"preview": False}),
            "PLR1702: not enabled",
            id="lint-preview-off",
        ),
        pytest.param(
            lambda ruff: ruff["lint"].update({"explicit-preview-rules": False}),
            "linter.explicit_preview_rules: false, not true",
            id="every-preview-rule-on",
        ),
        pytest.param(
            lambda ruff: ruff.update({"preview": True}),
            "formatter.preview: enabled, not disabled",
            id="formatter-preview-on",
        ),
    ],
)
def test_a_weakened_pyproject_is_reported_by_the_resolved_settings(
    tmp_path: Path, weaken: Callable[[dict[str, Any]], object], breach: str
) -> None:
    """Each change to the parsed Ruff table that weakens the cap or the banned APIs is named."""
    ruff = _real_ruff_table()
    weaken(ruff)
    _write_project(tmp_path, _pyproject_text(ruff), {"src/mod.py": "x = 1\n"})
    settings = _ruff(tmp_path, "check", *_CONFIG_PIN, "--show-settings", "src/mod.py").stdout

    assert any(breach in line for line in _cap_breaches(settings))


def _nested_ifs(blocks: int) -> str:
    """A function whose innermost statement sits inside `blocks` nested `if` blocks."""
    lines = ["def nested(x):"]
    for depth in range(blocks):
        lines.append(f"{'    ' * (depth + 1)}if x > {depth}:")
    lines.append(f"{'    ' * (blocks + 1)}return x")
    lines.append("    return 0")
    return "\n".join(lines) + "\n"


@pytest.mark.live("ruff")
def test_the_nesting_cap_fails_five_nested_blocks_and_passes_four(tmp_path: Path) -> None:
    """With the real Ruff table, five nested `if` blocks fail PLR1702 and four pass."""
    _write_project(
        tmp_path,
        _real_pyproject(),
        {
            "src/deep.py": _nested_ifs(_MAX_NESTED_BLOCKS + 1),
            "src/shallow.py": _nested_ifs(_MAX_NESTED_BLOCKS),
        },
    )
    result = _ruff(tmp_path, "check", *_CONFIG_PIN, "--output-format", "json", "src")
    findings = sorted(
        (Path(finding["filename"]).name, finding["code"]) for finding in json.loads(result.stdout)
    )

    assert findings == [("deep.py", "PLR1702")]


@pytest.mark.live("ruff")
@pytest.mark.parametrize("name", sorted(_NESTED_CONFIGURATIONS))
def test_a_ruff_configuration_file_cannot_silence_the_cap(tmp_path: Path, name: str) -> None:
    """The gate's `--config` keeps C901 on a function that another configuration file ignores.

    The same tree passes without the flag, which shows the escape is real: the gated run cannot
    report C901 for want of a function over the cap.
    """
    files = {"src/pkg/mod.py": _COMPLEXITY_ELEVEN, name: _NESTED_CONFIGURATIONS[name]}
    _write_project(tmp_path, _real_pyproject(), files)
    extra = ["--no-cache", "--output-format", "json"]
    gated = _ruff(tmp_path, *_gate_ruff_args(), *extra)
    flagless = _ruff(tmp_path, "check", ".", *extra)

    assert (_reported_codes(gated), _reported_codes(flagless)) == ({"C901"}, set())


@pytest.mark.live("ruff")
def test_the_gate_lints_every_tracked_python_source() -> None:
    """Ruff's walk, with the gate's own flags, reaches every Python source git tracks.

    Together with `--config`, this closes the ignore files: one that hid a tracked source from
    the walk would hide its functions from C901 as well.
    """
    assert _tracked_sources_ruff_skips(REPO_ROOT) == []


@pytest.mark.live("ruff")
@pytest.mark.parametrize(
    "ignore_files",
    [
        pytest.param({".gitignore": "src/pkg/\n"}, id="project-gitignore"),
        pytest.param({".ignore": "src/pkg/mod.py\n"}, id="project-ignore-file"),
        pytest.param({"src/pkg/.gitignore": "mod.py\n"}, id="nested-gitignore"),
        pytest.param({"src/pkg/.ignore": "mod.py\n"}, id="nested-ignore-file"),
    ],
)
def test_an_ignore_file_that_hides_a_tracked_source_from_ruff_is_reported(
    tmp_path: Path, ignore_files: Mapping[str, str]
) -> None:
    """A source committed with `git add -f` under an ignore file is named, whichever file hides it."""
    _write_project(tmp_path, _real_pyproject(), {"src/pkg/mod.py": _COMPLEXITY_ELEVEN})
    for name, text in ignore_files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=_RUFF_TIMEOUT_SECONDS)
    subprocess.run(
        ["git", "add", "-f", "src/pkg/mod.py"],
        cwd=tmp_path,
        check=True,
        timeout=_RUFF_TIMEOUT_SECONDS,
    )

    assert _tracked_sources_ruff_skips(tmp_path) == ["src/pkg/mod.py"]


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
