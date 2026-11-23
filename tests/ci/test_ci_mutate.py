"""Tests for `devops ci mutate`: changed functions mapped to mutmut globs, and its report (#853)."""

from __future__ import annotations

import shlex
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ci.mutate import MutationTarget, prepare_mutants_tree, select_targets, tally
from devops_cli.commands.ci import app, get_check_specs
from devops_cli.k8s.environment import find_repository
from devops_cli.telemetry.tracer import resolve_git_dir
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall

runner = CliRunner()
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


_SWITCHED_TO_MAIN: set[Path] = set()


_LS_TREE_RESPONSES = {
    MODULE_PATH: f"100644 blob sha_mod\t{MODULE_PATH}\0",
    PACKAGE_PATH: f"100644 blob sha_pkg\t{PACKAGE_PATH}\0",
    TEST_PATH: f"100644 blob sha_test\t{TEST_PATH}\0",
}

_CAT_FILE_RESPONSES = {
    "sha_mod": BASE_MODULE,
    "sha_pkg": "",
    "sha_test": "def test_mod():\n    assert True\n",
}


def _mutate_merge_base(call: ProcessCall) -> ProcessAnswer:
    base = call.argv[call.argv.index("merge-base") + 1]
    if base == "main":
        return ProcessAnswer(returncode=0, stdout="deadbeef\n")
    return ProcessAnswer(returncode=1, stderr=f"fatal: Not a valid object name {base}\n")


def _mutate_rev_parse(call: ProcessCall) -> ProcessAnswer:
    for arg in call.argv:
        if "main^{commit}" in arg:
            return ProcessAnswer(returncode=0, stdout="deadbeef\n")
        if "^{commit}" in arg:
            return ProcessAnswer(returncode=1, stderr="fatal: Not a valid object name\n")
    return ProcessAnswer(returncode=0, stdout="deadbeef\n")


def _mutate_diff(root: Path) -> Callable[[ProcessCall], ProcessAnswer]:
    def _diff(_call: ProcessCall) -> ProcessAnswer:
        if root.resolve() in _SWITCHED_TO_MAIN:
            return ProcessAnswer(returncode=0, stdout=f"M\0{MODULE_PATH}\0")
        return ProcessAnswer(
            returncode=0,
            stdout=f"M\0{PACKAGE_PATH}\0M\0{MODULE_PATH}\0M\0{TEST_PATH}\0",
        )

    return _diff


def _mutate_ls_tree(call: ProcessCall) -> ProcessAnswer:
    rel = call.argv[-1]
    if rel in _LS_TREE_RESPONSES:
        return ProcessAnswer(returncode=0, stdout=_LS_TREE_RESPONSES[rel])
    return ProcessAnswer(returncode=1)


def _mutate_cat_file(call: ProcessCall) -> ProcessAnswer:
    return ProcessAnswer(returncode=0, stdout=_CAT_FILE_RESPONSES.get(call.argv[-1], ""))


def _mutate_ls_files(root: Path) -> Callable[[ProcessCall], ProcessAnswer]:
    def _ls_files(_call: ProcessCall) -> ProcessAnswer:
        if (root / UNTRACKED_PATH).is_file():
            return ProcessAnswer(returncode=0, stdout=f"{UNTRACKED_PATH}\0")
        return ProcessAnswer(returncode=0, stdout="")

    return _ls_files


def _setup_mutate_git_fake(git_fake: GitFake, root: Path) -> None:
    git_fake.answer(lambda call: bool(call.argv and "merge-base" in call.argv), _mutate_merge_base)
    git_fake.answer(lambda call: bool(call.argv and "rev-parse" in call.argv), _mutate_rev_parse)
    git_fake.answer(lambda call: bool(call.argv and "diff" in call.argv), _mutate_diff(root))
    git_fake.answer(lambda call: bool(call.argv and "ls-tree" in call.argv), _mutate_ls_tree)
    git_fake.answer(lambda call: bool(call.argv and "cat-file" in call.argv), _mutate_cat_file)
    git_fake.answer(
        lambda call: bool(call.argv and "ls-files" in call.argv), _mutate_ls_files(root)
    )
    git_fake.answer(
        lambda call: bool(call.argv and "init" in call.argv), lambda call: ProcessAnswer(0, "", "")
    )


@pytest.fixture
def git() -> Callable[..., None]:
    def run(root: Path, *args: str) -> None:
        if args and args[0] == "switch":
            _SWITCHED_TO_MAIN.add(root.resolve())
            _write(root, MODULE_PATH, BASE_MODULE)
            _write(root, PACKAGE_PATH, "")

    return run


@pytest.fixture
def mutation_repo(tmp_path: Path, git_fake: GitFake) -> Path:
    """A repository whose `feature` branch changes the module, the package's `__init__` and
    a test module, which is no source mutmut mutates."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/feature\n", encoding="utf-8")
    _write(tmp_path, MODULE_PATH, HEAD_MODULE)
    _write(tmp_path, PACKAGE_PATH, "def version():\n    return 1\n")
    _write(tmp_path, TEST_PATH, "def test_mod():\n    assert 1\n")
    _setup_mutate_git_fake(git_fake, tmp_path)
    return tmp_path


@pytest.fixture
def mutmut_calls(
    mutation_repo: Path, monkeypatch: pytest.MonkeyPatch, git_fake: GitFake
) -> Callable[..., list[list[str]]]:
    """Run from the repository with the process fake answering as mutmut would."""
    monkeypatch.chdir(mutation_repo)

    def install(*, run_code: int = 0, results_code: int = 0) -> list[list[str]]:
        calls: list[list[str]] = []
        replies = {"run": (run_code, ""), "results": (results_code, RESULTS), "show": (0, SHOW)}

        def answer(call: ProcessCall) -> ProcessAnswer:
            calls.append(list(call.argv))
            code, stdout = replies[call.argv[call.argv.index("mutmut") + 1]]
            return ProcessAnswer(returncode=code, stdout=stdout, stderr="mutmut failed")

        git_fake.answer(lambda call: "mutmut" in call.argv, answer)
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
    """The run argv names each changed function's globs, and the results run follows it."""
    calls = mutmut_calls()
    result = runner.invoke(app, ["mutate", "--changed"])
    globs = [glob for path, name, cls in _changed() for glob in _mutmut_globs(path, name, cls)]
    assert (result.exit_code, calls[0], calls[1]) == (
        0,
        [*UV_RUN, "mutmut", "run", *globs],
        [*UV_RUN, "mutmut", "results", "--all", "true"],
    )


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
    """The `devops ci` stage list runs no mutation testing."""
    assert "mutate" not in {spec.name for spec in get_check_specs()}


def _changed() -> list[tuple[str, str, str | None]]:
    return [
        *((PACKAGE_PATH, name, cls) for name, cls in CHANGED_IN_PACKAGE),
        *((MODULE_PATH, name, cls) for name, cls in CHANGED_IN_MODULE),
    ]


def test_mutants_root_preparation_in_linked_worktree(tmp_path: Path, git_fake: GitFake) -> None:
    """The preparation creates .git directory in mutants root and leaves parent .git file unchanged (#6448)."""
    git_fake.answer(
        lambda call: bool(call.argv and "init" in call.argv), lambda call: ProcessAnswer(0, "", "")
    )
    checkout = tmp_path / "worktree"
    checkout.mkdir()
    git_file = checkout / ".git"
    git_file.write_text("gitdir: /some/path/to/main/.git/worktrees/worktree\n", encoding="utf-8")

    mutants_dir = prepare_mutants_tree(checkout)

    assert (mutants_dir / ".git").is_dir()
    assert git_file.is_file()
    assert (
        git_file.read_text(encoding="utf-8")
        == "gitdir: /some/path/to/main/.git/worktrees/worktree\n"
    )


def test_nearest_git_dir_is_inside_mutants_root(tmp_path: Path, git_fake: GitFake) -> None:
    """_resolve_git_dir finds the mutants root .git and does not escape to parent (#6448)."""
    git_fake.answer(
        lambda call: bool(call.argv and "init" in call.argv), lambda call: ProcessAnswer(0, "", "")
    )
    checkout = tmp_path / "worktree"
    checkout.mkdir()
    (checkout / ".git").write_text("gitdir: /outside\n", encoding="utf-8")

    mutants_dir = prepare_mutants_tree(checkout)
    subfolder = mutants_dir / "tests" / "core"
    subfolder.mkdir(parents=True)

    resolved = resolve_git_dir(start_dir=subfolder)
    assert resolved == mutants_dir / ".git"


def test_mutants_tree_outside_checkout_finds_repository(tmp_path: Path, git_fake: GitFake) -> None:
    """_repository returns the mutants root for any folder under it (#6448)."""
    git_fake.answer(
        lambda call: bool(call.argv and "init" in call.argv), lambda call: ProcessAnswer(0, "", "")
    )
    standalone = tmp_path / "standalone"
    standalone.mkdir()

    mutants_dir = prepare_mutants_tree(standalone)
    subfolder = mutants_dir / "src" / "devops_cli"
    subfolder.mkdir(parents=True)

    repo = find_repository(subfolder)
    assert repo == mutants_dir
