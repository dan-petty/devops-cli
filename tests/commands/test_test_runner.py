"""Tests for test runner and git-diff aware test selector."""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.test_cmd import _changed_paths
from devops_cli.commands.test_cmd import app as app_cli
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

runner = CliRunner()

_FIXTURES_ONLY = "import pytest\n\n\n@pytest.fixture\ndef stage() -> int:\n    return 1\n"
_HOOK = "\n\ndef pytest_collection_modifyitems(config, items):\n    items.reverse()\n"

# A project on `main`: a source tree with a nested subpackage, a flat test tree beside a nested
# one that mirrors the subpackage, the root and a nested conftest, a plain support module with
# the test module importing it, a support module that defines a fixture, a support subpackage
# with a module a test imports, and a test module that imports a support module by a name no
# file has yet.
_PROJECT = {
    "src/devops_cli/__init__.py": "",
    "src/devops_cli/orphan.py": "ORPHAN = 1\n",
    "src/devops_cli/ai/__init__.py": "",
    "src/devops_cli/ai/review/__init__.py": "",
    "src/devops_cli/ai/review/pipeline.py": "STAGES = 1\n",
    "src/devops_cli/commands/__init__.py": "",
    "src/devops_cli/commands/scan.py": "SCAN = 1\n",
    "tests/__init__.py": "",
    "tests/conftest.py": "",
    "tests/support/__init__.py": "",
    "tests/support/paths.py": "ROOT = None\n",
    "tests/support/stages.py": _FIXTURES_ONLY,
    "tests/support/fakes/__init__.py": "",
    "tests/support/fakes/github.py": "SESSION = None\n",
    "tests/test_paths.py": "from tests.support.paths import ROOT\n",
    "tests/test_stages.py": "from tests.support.stages import stage\n",
    "tests/test_roots.py": "from tests.support.roots import ROOT\n",
    "tests/test_fake_github.py": "from tests.support.fakes.github import SESSION\n",
    "tests/test_scan.py": "def test_scan() -> None: ...\n",
    "tests/test_scanner.py": "def test_scanner() -> None: ...\n",
    "tests/test_reports.py": "from devops_cli.commands.scan import SCAN\n",
    "tests/test_old.py": "def test_old() -> None: ...\n",
    "tests/ai/__init__.py": "",
    "tests/ai/conftest.py": _FIXTURES_ONLY,
    "tests/ai/review/__init__.py": "",
    "tests/ai/review/test_a.py": "def test_a() -> None: ...\n",
    "tests/ai/review/test_b.py": "def test_b() -> None: ...\n",
    "tests/ai/review/test_pipeline.py": "def test_pipeline() -> None: ...\n",
    "tests/ai/review/stages/__init__.py": "",
    "tests/ai/review/stages/test_c.py": "def test_c() -> None: ...\n",
}


class _TestProjectState:
    def __init__(self, root: Path, git_fake: GitFake) -> None:
        self.root = root
        self.git_fake = git_fake
        self.committed: list[str] = []
        self.staged_entries: list[str] = []
        self._setup_answers()

    def _setup_answers(self) -> None:
        self.git_fake.answer(
            lambda call: bool(
                call.argv and "diff" in call.argv and any("main...HEAD" in arg for arg in call.argv)
            ),
            self._diff_answer,
        )
        self.git_fake.answer(
            lambda call: bool(
                call.argv and "status" in call.argv and "--porcelain=v1" in call.argv
            ),
            self._status_answer,
        )

    def _diff_answer(self, _call: ProcessCall) -> ProcessAnswer:
        content = "\0".join(sorted(set(self.committed))) + ("\0" if self.committed else "")
        return ProcessAnswer(returncode=0, stdout=content)

    def _status_answer(self, _call: ProcessCall) -> ProcessAnswer:
        parts: list[str] = list(self.staged_entries)
        for p in sorted(self.root.rglob("*.py")):
            rel = p.relative_to(self.root).as_posix()
            if (
                rel not in _PROJECT
                and rel not in self.committed
                and not any(rel in s for s in self.staged_entries)
            ):
                parts.append(f"?? {rel}")
        stdout = ("\0".join(parts) + "\0") if parts else ""
        return ProcessAnswer(returncode=0, stdout=stdout)


_PROJECT_STATES: dict[Path, _TestProjectState] = {}


def _handle_git_mv(root: Path, state: _TestProjectState | None, src: str, dst: str) -> None:
    target = root / dst
    target.parent.mkdir(parents=True, exist_ok=True)
    source = root / src
    if source.is_file():
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        source.unlink()
    if state:
        state.staged_entries.append(f"D  {src}")
        state.staged_entries.append(f"A  {dst}")


def _handle_git_rm(root: Path, state: _TestProjectState | None, target_path: str) -> None:
    path = root / target_path
    if path.is_file():
        path.unlink()
    if state:
        state.staged_entries.append(f"D  {target_path}")


def _handle_git_commit(root: Path, state: _TestProjectState) -> None:
    for entry in list(state.staged_entries):
        state.committed.append(entry.split()[1])
    state.staged_entries.clear()
    for rel in _PROJECT:
        p = root / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        if "# changed" in text or (rel == "tests/ai/conftest.py" and _HOOK in text):
            state.committed.append(rel)


@pytest.fixture
def git(git_fake: GitFake) -> Callable[..., None]:
    def run(root: Path, *args: str) -> None:
        state: _TestProjectState | None = _PROJECT_STATES.get(root.resolve())
        cmd = list(args)
        if not cmd:
            return
        if cmd[0] == "mv":
            _handle_git_mv(root, state, cmd[1], cmd[2])
        elif cmd[0] == "rm":
            _handle_git_rm(root, state, cmd[-1])
        elif cmd[0] == "commit" and state:
            _handle_git_commit(root, state)

    return run


@pytest.fixture
def runner_project(tmp_path: Path, git_fake: GitFake, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The project committed on `main`, checked out on a topic branch, as the working directory."""
    root = tmp_path / "project"
    for relative, text in _PROJECT.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    (root / ".git").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/topic\n", encoding="utf-8")
    state = _TestProjectState(root, git_fake)
    _PROJECT_STATES[root.resolve()] = state
    monkeypatch.chdir(root)
    return root


def _commit(root: Path, git: Callable[..., None], *changed: str) -> None:
    """Change each of `changed` on the topic branch and commit it."""
    for relative in changed:
        path = root / relative
        path.write_text(path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "change")


def _changed_run() -> tuple[list[str], str]:
    """The pytest targets `devops test run --changed --dry-run` names, and what it printed."""
    result = runner.invoke(app_cli, ["run", "--changed", "--dry-run"])
    assert result.exit_code == 0, result.output
    (line,) = _plan_lines(result.output)
    words = shlex.split(line)
    return words[words.index("pytest") + 1 :], result.output


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


def test_a_changed_nested_test_module_is_selected(
    runner_project: Path, git: Callable[..., None]
) -> None:
    _commit(runner_project, git, "tests/ai/review/stages/test_c.py")
    assert _changed_run()[0] == ["tests/ai/review/stages/test_c.py"]


def test_a_changed_source_module_selects_the_test_module_named_for_it_not_those_beside_it(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """`devops_cli.ai.review.pipeline` selects `tests/ai/review/test_pipeline.py`, named for it at
    any depth; `test_a.py` and `test_b.py` beside it neither name nor import it, so they do not
    run (#1312)."""
    _commit(runner_project, git, "src/devops_cli/ai/review/pipeline.py")
    assert _changed_run()[0] == ["tests/ai/review/test_pipeline.py"]


def test_a_flat_tree_maps_a_source_module_by_its_name_and_its_importers(
    runner_project: Path, git: Callable[..., None]
) -> None:
    _commit(runner_project, git, "src/devops_cli/commands/scan.py")
    assert _changed_run()[0] == ["tests/test_reports.py", "tests/test_scan.py"]


def test_a_changed_conftest_of_fixtures_selects_its_directory(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """A fixture reaches every test beside and below its conftest, none of which imports it."""
    _commit(runner_project, git, "tests/ai/conftest.py")
    assert _changed_run()[0] == ["tests/ai"]


def test_a_changed_conftest_with_a_hook_selects_the_whole_suite(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """pytest calls a `pytest_*` hook of every conftest for every test, so one in `tests/ai/`
    can change the outcome of a test in any directory (#1312)."""
    conftest = runner_project / "tests" / "ai" / "conftest.py"
    conftest.write_text(conftest.read_text(encoding="utf-8") + _HOOK, encoding="utf-8")
    git(runner_project, "commit", "-q", "-am", "hook")
    assert _changed_run()[0] == ["tests"]


def test_a_changed_support_module_that_defines_a_fixture_selects_the_whole_suite(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """A support module that defines a fixture reaches any test, through the fixture its
    registration makes every test's, not only the test module importing it (#1312)."""
    _commit(runner_project, git, "tests/support/stages.py")
    assert _changed_run()[0] == ["tests"]


def test_a_changed_plain_support_module_selects_the_test_modules_importing_it(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """A support module that registers nothing reaches only the test modules importing it
    (#1312)."""
    _commit(runner_project, git, "tests/support/paths.py")
    assert _changed_run()[0] == ["tests/test_paths.py"]


@pytest.mark.parametrize("committed", [False, True], ids=["staged", "committed"])
def test_a_renamed_support_module_selects_the_whole_suite_through_its_old_path(
    runner_project: Path, git: Callable[..., None], committed: bool
) -> None:
    """A `git mv`, staged or committed, is listed as its old path deleted and its new path
    added, so a renamed support module reaches every test through the old path, which may have
    registered a fixture and whose importers the move may have broken, not only the test module
    that already imports the new name (#1312)."""
    git(runner_project, "mv", "tests/support/paths.py", "tests/support/roots.py")
    if committed:
        git(runner_project, "commit", "-q", "-m", "rename")
    changed = _changed_paths(runner_project)
    assert (
        {"tests/support/paths.py", "tests/support/roots.py"} <= set(changed),
        [path for path in changed if " -> " in path],
        _changed_run()[0],
    ) == (True, [], ["tests"])


def test_a_changed_support_subpackage_init_selects_the_test_modules_importing_its_modules(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """A support subpackage's `__init__.py` runs before any module of the subpackage, so it
    selects the test modules importing one; its directory, which holds no test module, is not
    handed to pytest (#1312)."""
    _commit(runner_project, git, "tests/support/fakes/__init__.py")
    assert _changed_run()[0] == ["tests/test_fake_github.py"]


def test_a_deleted_support_module_selects_the_whole_suite(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """A deleted support module cannot be read, so whether it registered a fixture cannot be
    known, and it selects the whole suite, not only the tests a change beside it maps to
    (#1312)."""
    git(runner_project, "rm", "-q", "tests/support/paths.py")
    _commit(runner_project, git, "tests/test_scan.py")
    assert _changed_run()[0] == ["tests"]


def test_a_renamed_source_module_selects_by_its_new_path_and_its_old_one(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """A staged `git mv` is read from `git status --porcelain --no-renames` as the old path
    deleted and the new one added: the new path selects the test module named for it, and the
    old one those still named for it or importing it, which the move may break (#1312)."""
    git(
        runner_project,
        "mv",
        "src/devops_cli/commands/scan.py",
        "src/devops_cli/commands/scanner.py",
    )
    assert _changed_run()[0] == [
        "tests/test_reports.py",
        "tests/test_scan.py",
        "tests/test_scanner.py",
    ]


def test_a_deleted_test_module_is_not_passed_to_pytest(
    runner_project: Path, git: Callable[..., None]
) -> None:
    git(runner_project, "rm", "-q", "tests/test_old.py")
    _commit(runner_project, git, "tests/test_scan.py")
    assert _changed_run()[0] == ["tests/test_scan.py"]


def test_an_unmapped_source_is_named_and_the_mapped_tests_run(
    runner_project: Path, git: Callable[..., None]
) -> None:
    _commit(runner_project, git, "src/devops_cli/commands/scan.py", "src/devops_cli/orphan.py")
    targets, output = _changed_run()
    assert (targets, "No test module covers src/devops_cli/orphan.py" in output) == (
        ["tests/test_reports.py", "tests/test_scan.py"],
        True,
    )


def test_an_untracked_test_package_is_selected_beside_a_committed_change(
    runner_project: Path, git: Callable[..., None]
) -> None:
    """Each file of a new test package not yet added is listed, not its directory: its test
    module runs, and its `__init__.py` selects its own directory, as a conftest does, instead of
    being named as a source no test module covers (#1312)."""
    _commit(runner_project, git, "src/devops_cli/commands/scan.py")
    fresh = runner_project / "tests" / "fresh"
    fresh.mkdir()
    (fresh / "__init__.py").write_text("", encoding="utf-8")
    (fresh / "test_fresh.py").write_text("def test_fresh() -> None: ...\n", encoding="utf-8")
    targets, output = _changed_run()
    assert (targets, "No test module covers tests/fresh" in output) == (
        ["tests/fresh", "tests/fresh/test_fresh.py", "tests/test_reports.py", "tests/test_scan.py"],
        False,
    )


def test_no_change_runs_the_whole_suite(runner_project: Path) -> None:
    assert _changed_run()[0] == ["tests"]


_UV = "uv --preview-features malware-check,check-command"


@pytest.mark.parametrize("flag_first", [True, False])
def test_test_run_dry_run_lists_the_pytest_command(
    cli: Any, process_fake: ProcessFake, flag_first: bool
) -> None:
    """A dry run starts no process and lists the one `uv run pytest` of the run (#2260)."""
    argv = ["test", "run", "tests/test_scan.py", "-x", "-v", "-k", "sample", "--cov"]
    result = cli(["--dry-run", *argv] if flag_first else [*argv, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert [call for call in process_fake.calls if not call.local_read] == []
    assert _plan_lines(result.output) == [
        f"{_UV} run pytest -vv -x -k sample --cov=src --cov-report=term-missing tests/test_scan.py"
    ]


def test_test_run_runs_the_request_of_its_plan(cli: Any, process_fake: ProcessFake) -> None:
    """The real run starts the command of the plan."""
    argv = ["test", "run", "tests/test_scan.py", "-x", "-k", "sample"]
    planned = _plan_lines(cli([*argv, "--dry-run"]).output)

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert [" ".join(call.argv) for call in process_fake.calls if not call.local_read] == planned


def test_test_run_execution() -> None:
    """devops test run with mocks."""
    mock_res = MagicMock(returncode=0)
    with patch("devops_cli.commands.test_cmd.run_subprocess", return_value=mock_res):
        res = runner.invoke(
            app_cli, ["run", "tests/test_scan.py", "--cov", "-v", "-x", "-k", "sample"]
        )
        assert res.exit_code == 0
        assert "Test suite passed cleanly" in res.output

    # Test run failure
    mock_fail = MagicMock(returncode=1)
    with patch("devops_cli.commands.test_cmd.run_subprocess", return_value=mock_fail):
        res_fail = runner.invoke(app_cli, ["run", "tests/test_scan.py"])
        assert res_fail.exit_code == 1


def test_test_load_missing_k6_and_failure(tmp_path: Path) -> None:
    """Verify devops test load when k6 is not installed or when test run fails."""
    # 1. Missing k6
    with patch("devops_cli.commands.test_cmd.shutil.which", return_value=None):
        res_no_k6 = runner.invoke(app_cli, ["load"])
        assert res_no_k6.exit_code == 1

    # 2. k6 failure
    export_file = tmp_path / "summary.json"
    with (
        patch("devops_cli.commands.test_cmd.shutil.which", return_value="/usr/local/bin/k6"),
        patch("devops_cli.commands.test_cmd.run_subprocess", return_value=MagicMock(returncode=2)),
    ):
        res_fail = runner.invoke(app_cli, ["load", "--summary-export", str(export_file)])
        assert res_fail.exit_code == 2


def test_parse_whitelist_and_validate_sandbox_network() -> None:
    """Verify _parse_whitelist and _validate_sandbox_network handle valid and invalid inputs."""
    import pytest
    import typer

    from devops_cli.commands.test_cmd import _parse_whitelist, _validate_sandbox_network

    # Empty raw returns empty list
    assert _parse_whitelist(None, "public") == []
    assert _parse_whitelist("", "public") == []

    # Valid tokens
    tokens = _parse_whitelist("example.com, 127.0.0.1:8080 , api.service", "public")
    assert tokens == ["example.com", "127.0.0.1:8080", "api.service"]

    # Invalid token with forbidden characters
    with pytest.raises(typer.BadParameter, match="Invalid public whitelist entry"):
        _parse_whitelist("invalid token with spaces", "public")

    # Invalid network mode
    with pytest.raises(typer.BadParameter, match="Invalid network mode"):
        _validate_sandbox_network("invalid-mode", "isolated", None, None)

    # Valid bridge mode with warning
    mode, pub, loc = _validate_sandbox_network("bridge", "bridge", "example.com", "localhost:8000")
    assert mode == "bridge"
    assert pub == ["example.com"]
    assert loc == ["localhost:8000"]


def test_test_sandbox_execution_and_failure() -> None:
    """Verify test sandbox execution outputs and error exit codes."""
    mock_runner = MagicMock()
    mock_runner.run.return_value = MagicMock(
        exit_code=0, stdout="Container output", stderr="Warning output", duration_seconds=1.23
    )

    with (
        patch("devops_cli.docker.sandbox.WorkloadSandboxRunner", return_value=mock_runner),
        patch("devops_cli.commands.test_cmd.print_info"),
        patch("devops_cli.commands.test_cmd.print_success"),
    ):
        res = runner.invoke(app_cli, ["sandbox", "echo", "hello"])
        assert res.exit_code == 0

    # Non-zero exit code
    mock_runner_fail = MagicMock()
    mock_runner_fail.run.return_value = MagicMock(
        exit_code=42, stdout="", stderr="Crash", duration_seconds=0.5
    )
    with patch("devops_cli.docker.sandbox.WorkloadSandboxRunner", return_value=mock_runner_fail):
        res_fail = runner.invoke(app_cli, ["sandbox", "false"])
        assert res_fail.exit_code == 42


def test_profile_memory_error_handling() -> None:
    """Verify profile-memory handles MemoryProfilerError with exit code 1."""
    from devops_cli.telemetry.memory_profiler import MemoryProfilerError

    with patch(
        "devops_cli.commands.test_cmd.run_memory_profiler",
        side_effect=MemoryProfilerError("profiling failed"),
    ):
        res = runner.invoke(app_cli, ["profile-memory", "devops_cli.main:app"])
        assert res.exit_code == 1
        assert "profiling failed" in res.output


@pytest.fixture
def nested_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Provide a nested worktree without starting git processes."""
    main = tmp_path / "main"
    main.mkdir(parents=True, exist_ok=True)
    (main / ".git").mkdir(parents=True, exist_ok=True)
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (main / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    nested = main / ".claude" / "worktrees" / "wt"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.mkdir(parents=True, exist_ok=True)
    (nested / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (nested / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True, exist_ok=True)
    (nested / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    (wt_git / "gitdir").write_text(f"{nested / '.git'}\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    (wt_git / "HEAD").write_text("ref: refs/heads/nested\n", encoding="utf-8")
    return main, nested


def test_test_run_runs_pytest_in_a_nested_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops test run` from a worktree under `.claude/worktrees/` runs pytest there,
    not in the checkout around it (#582)."""
    _, nested = nested_worktree
    monkeypatch.chdir(nested)

    with patch(
        "devops_cli.commands.test_cmd.run_subprocess", return_value=MagicMock(returncode=0)
    ) as run:
        result = runner.invoke(app_cli, ["run"])

    assert (result.exit_code, run.call_args.kwargs["cwd"]) == (0, nested.resolve())


def test_changed_paths_handles_spaces_non_ascii_and_renames(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """_changed_paths parses git output without quoting corrupting paths with spaces or non-ASCII characters."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    git_fake.answer(
        lambda call: bool(call.argv and "diff" in call.argv and call.cwd == repo),
        ProcessAnswer(returncode=0, stdout="first.py\0"),
    )
    git_fake.answer(
        lambda call: bool(call.argv and "status" in call.argv and call.cwd == repo),
        ProcessAnswer(
            returncode=0,
            stdout=" M first.py\0?? café.py\0?? path with space.py\0D  old.py\0A  renamed.py\0",
        ),
    )

    paths = _changed_paths(repo)
    assert paths == [
        "café.py",
        "first.py",
        "old.py",
        "path with space.py",
        "renamed.py",
    ]
