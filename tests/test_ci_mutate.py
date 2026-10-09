"""Tests for `devops ci mutate`: changed functions mapped to mutmut globs, and its report (#853)."""

from __future__ import annotations

import shlex
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

import pathspec
import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.ci.mutate import MutationTarget, select_targets, tally
from devops_cli.commands.ci import app, get_check_specs
from devops_cli.config.constants import CONST_GITIGNORE_PATTERN_STYLE

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = "src/devops_cli/pkg/mod.py"
PACKAGE_PATH = "src/devops_cli/pkg/__init__.py"
UNTRACKED_PATH = "src/devops_cli/pkg/fresh.py"
TEST_PATH = "tests/test_mod.py"
UV_RUN = ["uv", "--preview-features", "malware-check,check-command", "run"]

BASE_MODULE = """\
import dataclasses


def changed(a, b):
    return a + b


def unchanged(a):
    return a * 2


@app.command()
def command(a):
    return a + 1


class Holder:
    def method(self, a):
        return a - 1

    @staticmethod
    def static(a):
        return a > 1


@dataclasses.dataclass
class Record:
    value: int

    def doubled(self):
        return self.value * 2
"""

HEAD_MODULE = """\
import dataclasses


def changed(a, b):
    return a + b + 1


def unchanged(a):
    return a * 2


def added(a):
    return a or 1


@app.command()
def command(a):
    return a + 2


class Holder:
    def method(self, a):
        return a - 2

    @staticmethod
    def static(a):
        return a >= 1


@dataclasses.dataclass
class Record:
    value: int

    def doubled(self):
        return self.value * 3
"""

UNTRACKED_MODULE = """\
class Fresh:
    def __new__(cls):
        return object.__new__(cls)

    def size(self):
        return 2
"""

# The (function, class) pairs mutmut mutates among HEAD_MODULE's changes, and the package's.
CHANGED_IN_MODULE = [
    ("changed", None),
    ("added", None),
    ("method", "Holder"),
    ("static", "Holder"),
    ("doubled", "Record"),
]
CHANGED_IN_PACKAGE = [("version", None)]

RESULTS = """\
    devops_cli.pkg.mod.x_changed__mutmut_1: killed
    devops_cli.pkg.mod.x_changed__mutmut_2: survived
    devops_cli.pkg.mod.x_changed_other__mutmut_1: survived
    devops_cli.pkg.mod.x_unchanged__mutmut_1: survived
    devops_cli.pkg.mod.xǁHolderǁmethod__mutmut_1: timeout
    devops_cli.pkg.mod.xǁRecordǁdoubled__mutmut_1: no tests
    devops_cli.pkg.mod.xǁRecordǁdoubled__mutmut_2: killed
"""
COUNTS = "killed 2, survived 1, timeout 1, no tests 1"
SHOW = "--- src/devops_cli/pkg/mod.py\n+++ src/devops_cli/pkg/mod.py\n-    return a + b + 1\n+    return a - b + 1\n"


def _mutmut_globs(path: str, name: str, class_name: str | None) -> list[str]:
    """The globs built from mutmut 3.8's own stats key for a function: its mutants, then the key."""
    from mutmut.mutation.trampoline_templates import mangle_function_name
    from mutmut.utils.format_utils import get_mutant_name

    key = get_mutant_name(Path(path), mangle_function_name(name=name, class_name=class_name))
    return [f"{key}__mutmut_*", f"*{key}"]


def _write(root: Path, rel_path: str, text: str) -> None:
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def mutation_repo(tmp_path: Path, git: Callable[..., None]) -> Path:
    """A repository whose `feature` branch changes the module, the package's `__init__` and
    a test module, which is no source mutmut mutates."""
    git(tmp_path, "init", "--quiet", "-b", "main")
    _write(tmp_path, MODULE_PATH, BASE_MODULE)
    _write(tmp_path, PACKAGE_PATH, "")
    _write(tmp_path, TEST_PATH, "def test_mod():\n    assert True\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    git(tmp_path, "switch", "--quiet", "-c", "feature")
    _write(tmp_path, MODULE_PATH, HEAD_MODULE)
    _write(tmp_path, PACKAGE_PATH, "def version():\n    return 1\n")
    _write(tmp_path, TEST_PATH, "def test_mod():\n    assert 1\n")
    git(tmp_path, "commit", "--quiet", "-am", "head")
    return tmp_path


@pytest.fixture
def mutmut_calls(
    mutation_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., list[list[str]]]:
    """Run from the repository with the ci subprocess seam answering as mutmut would."""
    monkeypatch.chdir(mutation_repo)

    def install(*, run_code: int = 0, results_code: int = 0) -> list[list[str]]:
        calls: list[list[str]] = []
        replies = {"run": (run_code, ""), "results": (results_code, RESULTS), "show": (0, SHOW)}

        def fake(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(list(cmd))
            code, stdout = replies[cmd[cmd.index("mutmut") + 1]]
            return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="mutmut failed")

        monkeypatch.setattr("devops_cli.commands.ci.run_subprocess", fake)
        return calls

    return install


def test_changed_functions_map_to_the_globs_mutmut_names(mutation_repo: Path) -> None:
    """Changed module functions and methods, a new function, a staticmethod, a decorated
    class's method and an untracked module's functions are selected; unchanged and decorated
    functions, and a `__new__` mutmut never mutates, are not."""
    _write(mutation_repo, UNTRACKED_PATH, UNTRACKED_MODULE)
    targets = select_targets(mutation_repo, [], changed=True, base="main")
    expected = [
        glob
        for path, name, cls in [*_changed(), (UNTRACKED_PATH, "size", "Fresh")]
        for glob in _mutmut_globs(path, name, cls)
    ]
    assert [glob for target in targets for glob in target.run_globs] == expected


def test_paths_select_every_function_and_narrow_changed_ones(mutation_repo: Path) -> None:
    """PATHS alone select every mutable function in the files they name or hold, a missing
    path naming none; with --changed, they keep the changed functions inside them."""

    def qualnames(paths: list[str], *, changed: bool) -> list[str]:
        named = [mutation_repo / path for path in paths]
        targets = select_targets(mutation_repo, named, changed=changed, base="main")
        return [f"{target.path}:{target.qualname}" for target in targets]

    in_module = [
        "changed",
        "unchanged",
        "added",
        "Holder.method",
        "Holder.static",
        "Record.doubled",
    ]
    every_in_module = [f"{MODULE_PATH}:{name}" for name in in_module]
    assert (
        qualnames([MODULE_PATH, "src/devops_cli/gone.py"], changed=False),
        qualnames(["src/devops_cli/pkg"], changed=False),
        qualnames([MODULE_PATH], changed=True),
    ) == (
        every_in_module,
        [f"{PACKAGE_PATH}:version", *every_in_module],
        [f"{MODULE_PATH}:{f'{cls}.' if cls else ''}{name}" for name, cls in CHANGED_IN_MODULE],
    )


def test_mutate_runs_mutmut_serially_on_the_changed_function_globs(
    mutmut_calls: Callable[..., list[list[str]]],
) -> None:
    """The run argv names each changed function's globs, and the suite runs without xdist."""
    calls = mutmut_calls()
    result = runner.invoke(app, ["mutate", "--changed"])
    globs = [glob for path, name, cls in _changed() for glob in _mutmut_globs(path, name, cls)]
    pytest_args = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert (result.exit_code, calls[0], calls[1]) == (
        0,
        [*UV_RUN, "mutmut", "run", *globs],
        [*UV_RUN, "mutmut", "results", "--all", "true"],
    )
    assert pytest_args["tool"]["mutmut"]["pytest_add_cli_args"] == ["-n", "0"]


def test_mutate_reports_each_survivor_and_the_counts_without_a_score(
    mutmut_calls: Callable[..., list[list[str]]],
) -> None:
    """Survivors of the selected functions are shown with their diff; siblings sharing a
    prefix and unselected functions are not, and no percentage is printed."""
    calls = mutmut_calls()
    result = runner.invoke(app, ["mutate", "--changed"])
    shown = [call[-1] for call in calls if "show" in call]
    assert (result.exit_code, shown) == (
        0,
        ["devops_cli.pkg.mod.x_changed__mutmut_2", "devops_cli.pkg.mod.xǁRecordǁdoubled__mutmut_1"],
    )
    expected = (f"{MODULE_PATH}:4 changed", f"{MODULE_PATH}:34 Record.doubled", SHOW, COUNTS)
    assert ([text for text in expected if text not in result.output], "%" in result.output) == (
        [],
        False,
    )


def test_mutate_never_calls_mutmut_when_only_a_decorated_function_changed(
    mutation_repo: Path,
    git: Callable[..., None],
    mutmut_calls: Callable[..., list[list[str]]],
) -> None:
    """mutmut skips a decorated function, so changing only one leaves nothing to mutate."""
    git(mutation_repo, "switch", "--quiet", "main")
    _write(mutation_repo, MODULE_PATH, BASE_MODULE.replace("a + 1", "a + 3"))
    calls = mutmut_calls()
    result = runner.invoke(app, ["mutate", "--changed"])
    assert (result.exit_code, calls) == (0, [])


def test_mutate_needs_paths_or_changed(mutmut_calls: Callable[..., list[list[str]]]) -> None:
    """Without PATHS or --changed there is nothing to choose from: a usage error."""
    calls = mutmut_calls()
    result = runner.invoke(app, ["mutate"])
    assert (result.exit_code, calls) == (2, [])


def test_mutate_dry_run_plans_the_mutmut_requests_and_starts_none(
    mutmut_calls: Callable[..., list[list[str]]],
) -> None:
    """--dry-run reads git but starts no mutmut process, and names the run argv."""
    calls = mutmut_calls()
    result = runner.invoke(app, ["mutate", "--changed", "--dry-run"])
    globs = [glob for path, name, cls in _changed() for glob in _mutmut_globs(path, name, cls)]
    planned = (
        shlex.join([*UV_RUN, "mutmut", "run", *globs]),
        shlex.join([*UV_RUN, "mutmut", "results", "--all", "true"]),
        shlex.join([*UV_RUN, "mutmut", "show", "<mutant>"]),
    )
    assert (result.exit_code, calls, [text for text in planned if text not in result.output]) == (
        0,
        [],
        [],
    )


@pytest.mark.parametrize(
    ("codes", "calls_made"),
    [
        pytest.param({"run_code": 1}, 1, id="run-fails"),
        pytest.param({"results_code": 1}, 2, id="results-fail"),
    ],
)
def test_mutate_exits_1_when_mutmut_fails(
    mutmut_calls: Callable[..., list[list[str]]], codes: dict[str, int], calls_made: int
) -> None:
    """A failing mutmut run or results call is the command's failure; nothing is reported."""
    calls = mutmut_calls(**codes)
    result = runner.invoke(app, ["mutate", "--changed"])
    assert (result.exit_code, len(calls)) == (1, calls_made)


@pytest.mark.parametrize(
    ("base", "error"),
    [
        pytest.param("--output=x", "Refusing to diff against '--output=x'", id="option"),
        pytest.param("no-such-ref", "Cannot diff against 'no-such-ref'", id="no-commit"),
    ],
)
def test_mutate_fails_on_a_base_that_names_no_commit(
    mutmut_calls: Callable[..., list[list[str]]], base: str, error: str
) -> None:
    """A base git would read as an option is refused, and one naming no commit is an error
    rather than an empty selection; mutmut never runs."""
    calls = mutmut_calls()
    result = runner.invoke(app, ["mutate", "--changed", f"--base={base}"])
    assert (result.exit_code, calls, error in result.output) == (1, [], True)


def test_tally_counts_only_the_selected_functions_mutants() -> None:
    """The mutant pattern keeps a sibling sharing the function's prefix out of the counts."""
    target = MutationTarget(path=MODULE_PATH, line=4, class_name=None, name="changed")
    report = tally(RESULTS, [target])
    assert (report.counts, [name for name, _ in report.survivors]) == (
        {"killed": 1, "survived": 1, "timeout": 0, "no tests": 0},
        ["devops_cli.pkg.mod.x_changed__mutmut_2"],
    )


def test_mutate_is_no_gate_step() -> None:
    """Neither the `devops ci` stage list nor ci.yml runs mutation testing."""
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text("utf-8"))
    runs = [
        str(step.get("run", ""))
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    ]
    mutating = [run for run in runs if "mutmut" in run or "ci mutate" in run]
    assert ("mutate" in {spec.name for spec in get_check_specs()}, mutating) == (False, [])


def test_gitignore_keeps_mutants_out_of_the_tree() -> None:
    """mutmut's copy of the tree is ignored, so neither git nor the CI cache sees it."""
    lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    ignored = pathspec.PathSpec.from_lines(CONST_GITIGNORE_PATTERN_STYLE, lines)
    assert ignored.match_file("mutants/x")


def _changed() -> list[tuple[str, str, str | None]]:
    return [
        *((PACKAGE_PATH, name, cls) for name, cls in CHANGED_IN_PACKAGE),
        *((MODULE_PATH, name, cls) for name, cls in CHANGED_IN_MODULE),
    ]
