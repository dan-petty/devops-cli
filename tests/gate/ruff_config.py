"""The ruff configuration checks of the `lint` row of `devops ci` (#2164).

Ruff holds the complexity cap of 10 (C901, #586), the nesting cap of 4 (PLR1702, #1876) and the
bans of the hand-rolled address APIs (TID251). Three things could take a function past a cap
without a marker to count: a setting of `pyproject.toml`, a Ruff configuration file nearer the
function, and an ignore file that hides the function from the walk of Ruff. The gate's
`ruff check --config pyproject.toml` closes the nested configuration files. These checks close
the other two with the resolved settings of Ruff itself, and with Ruff and git together, which
show whether a tracked source escapes the walk.

The checks run as a row, so a pull request pays for them once and not on every pytest worker.
"""

from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import CONST_PYPROJECT_FILENAME
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
CONST_RUFF_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".ipynb"})

_RUFF_TIMEOUT_SECONDS = 60
# The deepest nesting a function may have: four nested blocks pass, five fail (#1876).
MAX_NESTED_BLOCKS = 4
_BANNED_API_RULE = "TID251"
_CONFIG_PIN = ["--config", CONST_PYPROJECT_FILENAME]


def gate_ruff_args() -> list[str]:
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


def setting(settings: str, key: str) -> str | None:
    """Read one value of `ruff check --show-settings`, a list or table up to its closing line.

    Returns None when Ruff printed no such key.
    """
    lines = settings.splitlines()
    opening = next((n for n, line in enumerate(lines) if line.startswith(f"{key} = ")), None)
    if opening is None:
        return None
    value = lines[opening].removeprefix(f"{key} = ")
    closing = {"[": "]", "{": "}"}.get(value)
    if closing is None:
        return value
    return "\n".join(itertools.takewhile(lambda line: line != closing, lines[opening + 1 :]))


def cap_breaches(settings: str) -> list[str]:
    """Name each way the resolved settings let a function past the cap, or drop the banned APIs."""
    enabled = setting(settings, "linter.rules.enabled")
    if enabled is None:
        return ["`ruff check --show-settings` printed no linter.rules.enabled"]
    unenforced = [
        f"{rule}: not enabled"
        for rule in sorted({*CONST_COMPLEXITY_LINT_RULES, _BANNED_API_RULE})
        if f"({rule})" not in enabled
    ]
    wanted = {
        "linter.mccabe.max_complexity": str(DEFAULT_MAX_COMPLEXITY),
        "linter.pylint.max_nested_blocks": str(MAX_NESTED_BLOCKS),
        "linter.preview": "enabled",
        "linter.explicit_preview_rules": "true",
        "formatter.preview": "disabled",
        "linter.per_file_ignores": "{}",
        "linter.exclude": "[]",
    }
    moved = [
        f"{key}: {found}, not {value}"
        for key, value in wanted.items()
        if (found := setting(settings, key)) != value
    ]
    banned = setting(settings, "linter.flake8_tidy_imports.banned_api") or ""
    unbanned = [
        f"{api}: not banned" for api in sorted(CONST_BANNED_HAND_ROLLED_APIS) if api not in banned
    ]
    return [*unenforced, *moved, *unbanned]


def tracked_sources_ruff_skips(
    project: Path, tracked: Sequence[str], walked: Sequence[str]
) -> list[str]:
    """List each tracked Python source that the gate's `ruff check` walk does not reach.

    `tracked` holds the names that git tracks, and `walked` the files that `ruff check --show-files`
    prints.
    """
    reached = {Path(name).resolve() for name in walked}
    return [
        name
        for name in tracked
        if name and (project / name).is_file() and (project / name).resolve() not in reached
    ]


def _tracked_python_sources(project: Path) -> list[str]:
    """Name the Python sources that git tracks under `project`."""
    pathspecs = (f"*{suffix}" for suffix in sorted(CONST_RUFF_SOURCE_SUFFIXES))
    done = subprocess.run(
        ["git", "ls-files", "-z", "--", *pathspecs],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
        timeout=_RUFF_TIMEOUT_SECONDS,
    )
    return done.stdout.split("\0")


def _nested_ifs(blocks: int) -> str:
    """A function whose innermost statement sits inside `blocks` nested `if` blocks."""
    lines = ["def nested(x):"]
    lines.extend(f"{'    ' * (depth + 1)}if x > {depth}:" for depth in range(blocks))
    lines.append(f"{'    ' * (blocks + 1)}return x")
    lines.append("    return 0")
    return "\n".join(lines) + "\n"


_COMPLEXITY_ELEVEN = "def over(x):\n" + "".join(
    f"    if x == {n}:\n        return {n}\n" for n in range(DEFAULT_MAX_COMPLEXITY)
)


def cap_probe_problems(project: Path) -> list[str]:
    """Lint three functions with the real Ruff table: five nested blocks and a complexity of 11
    must fail (PLR1702, C901), and four nested blocks must pass."""
    with tempfile.TemporaryDirectory() as scratch:
        probe = Path(scratch)
        shutil.copyfile(project / CONST_PYPROJECT_FILENAME, probe / CONST_PYPROJECT_FILENAME)
        (probe / "src").mkdir()
        (probe / "src" / "deep.py").write_text(_nested_ifs(MAX_NESTED_BLOCKS + 1), encoding="utf-8")
        (probe / "src" / "shallow.py").write_text(_nested_ifs(MAX_NESTED_BLOCKS), encoding="utf-8")
        (probe / "src" / "over.py").write_text(_COMPLEXITY_ELEVEN, encoding="utf-8")
        done = _ruff(probe, "check", *_CONFIG_PIN, "--no-cache", "--output-format", "json", "src")
    found = sorted((Path(f["filename"]).name, f["code"]) for f in json.loads(done.stdout or "[]"))
    expected = [("deep.py", "PLR1702"), ("over.py", "C901")]
    return [] if found == expected else [f"the probe functions gave {found}, not {expected}"]


def problems(project: Path = REPO_ROOT) -> list[str]:
    """Every way the ruff configuration of `project` lets a function past a cap."""
    settings = _ruff(
        project, "check", *_CONFIG_PIN, "--show-settings", "src/devops_cli/__init__.py"
    ).stdout
    walked = _ruff(project, *gate_ruff_args(), "--show-files").stdout.splitlines()
    skipped = tracked_sources_ruff_skips(project, _tracked_python_sources(project), walked)
    return [
        *cap_breaches(settings),
        *cap_probe_problems(project),
        *(f"{name}: tracked, but the walk of `ruff check` does not reach it" for name in skipped),
    ]


def main(argv: list[str] | None = None) -> int:
    """Print each problem and return 1 when there is one."""
    found = problems()
    for line in found:
        print(f"ruff configuration: {line}", file=sys.stderr)
    return 1 if found else 0
