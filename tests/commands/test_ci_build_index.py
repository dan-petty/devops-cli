"""Unit tests for devops ci coverage --build-index command and lifecycle."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ci.cache import resolve_coverage_index_path
from devops_cli.commands.ci import app as ci_app
from devops_cli.commands.ci import get_check_spec
from devops_cli.core.coverage_index import INDEX_FORMAT_VERSION, load_index
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

runner = CliRunner()


def _make_git_repo(tmp_path: Path, git_fake: GitFake, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Initialize a miniature repository layout with source and test files, the current directory."""
    import hashlib

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    src_dir = tmp_path / "src" / "devops_cli"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "a.py").write_text("A = 1\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")

    orig_a = hashlib.sha1(b"blob 6\0A = 1\n", usedforsecurity=False).hexdigest()
    orig_t = hashlib.sha1(b"blob 19\0def test_a(): pass\n", usedforsecurity=False).hexdigest()

    def _ls_files_answer(_call: ProcessCall) -> ProcessAnswer:
        lines = [
            f"100644 {orig_a} 0\tsrc/devops_cli/a.py",
            f"100644 {orig_t} 0\ttests/test_a.py",
        ]
        return ProcessAnswer(returncode=0, stdout="\n".join(lines) + "\n")

    def _status_answer(_call: ProcessCall) -> ProcessAnswer:
        a_file = src_dir / "a.py"
        if a_file.is_file() and a_file.read_text(encoding="utf-8") == "A = 1\n":
            return ProcessAnswer(returncode=0, stdout="")
        return ProcessAnswer(returncode=0, stdout=" M src/devops_cli/a.py\n")

    def _hash_object_answer(call: ProcessCall) -> ProcessAnswer:
        hashes: list[str] = []
        if call.stdin and isinstance(call.stdin, str):
            for path_str in call.stdin.splitlines():
                if path_str:
                    target_path = tmp_path / path_str
                    data = target_path.read_bytes() if target_path.is_file() else b""
                    h = hashlib.sha1(
                        b"blob " + str(len(data)).encode() + b"\0" + data,
                        usedforsecurity=False,
                    ).hexdigest()
                    hashes.append(h)
        return ProcessAnswer(returncode=0, stdout="\n".join(hashes) + ("\n" if hashes else ""))

    git_fake.answer(
        lambda call: bool(call.argv and "ls-files" in call.argv),
        _ls_files_answer,
    )
    git_fake.answer(
        lambda call: bool(call.argv and "status" in call.argv),
        _status_answer,
    )
    git_fake.answer(
        lambda call: bool(call.argv and "hash-object" in call.argv),
        _hash_object_answer,
    )

    return tmp_path


def _write_minimal_coverage_db(db_path: Path, src_abs: Path, test_rel: str) -> None:
    """Write a minimal SQLite coverage database in the shape produced with --cov-context=test."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(
        "CREATE TABLE file (id INTEGER PRIMARY KEY, path TEXT);"
        "CREATE TABLE context (id INTEGER PRIMARY KEY, context TEXT);"
        "CREATE TABLE line_bits (file_id INTEGER, context_id INTEGER, numbits BLOB);"
    )
    con.execute("INSERT INTO file VALUES (1, ?)", (str(src_abs),))
    con.execute("INSERT INTO context VALUES (1, ?)", (f"{test_rel}::test_case|run",))
    con.execute("INSERT INTO line_bits VALUES (1, 1, ?)", (b"",))
    con.commit()
    con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1: Exact build command and environment
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("ci_root")
def test_coverage_build_index_runs_exact_argv_and_ctrace_env(process_fake: ProcessFake) -> None:
    """--build-index appends --cov-context=test and passes COVERAGE_CORE=ctrace to run_subprocess."""
    result = runner.invoke(ci_app, ["coverage", "--build-index"])
    executed = [(list(call.argv), call.env) for call in process_fake.calls if "pytest" in call.argv]

    base_spec = get_check_spec("test")
    expected_cmd = list(base_spec.cmd)
    if expected_cmd and expected_cmd[0] == "uv" and "--preview-features" not in expected_cmd:
        expected_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    expected_cmd.append("--cov-context=test")

    assert (
        result.exit_code,
        len(executed),
        executed[0][0],
        executed[0][1],
    ) == (
        0,
        1,
        expected_cmd,
        {"COVERAGE_CORE": "ctrace"},
    )


@pytest.mark.usefixtures("ci_root")
def test_coverage_without_build_index_preserves_standard_argv_and_env(
    process_fake: ProcessFake,
) -> None:
    """Plain devops ci coverage does not pass --cov-context or COVERAGE_CORE."""
    result = runner.invoke(ci_app, ["coverage"])
    executed = [(list(call.argv), call.env) for call in process_fake.calls if "pytest" in call.argv]

    base_spec = get_check_spec("test")
    expected_cmd = list(base_spec.cmd)
    if expected_cmd and expected_cmd[0] == "uv" and "--preview-features" not in expected_cmd:
        expected_cmd[1:1] = ["--preview-features", "malware-check,check-command"]

    assert (
        result.exit_code,
        len(executed),
        executed[0][0],
        executed[0][1],
    ) == (
        0,
        1,
        expected_cmd,
        None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2: Save index only after clean passing run
# ─────────────────────────────────────────────────────────────────────────────


def test_build_index_saves_index_after_passing_clean_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git_fake: GitFake
) -> None:
    """A passing run on an unmodified tree builds and writes the reverse coverage index."""
    repo = _make_git_repo(tmp_path, git_fake, monkeypatch)
    coverage_db = repo / ".data" / ".coverage"

    def pytest_writes_coverage(call: ProcessCall) -> ProcessAnswer:
        _write_minimal_coverage_db(
            coverage_db, repo / "src" / "devops_cli" / "a.py", "tests/test_a.py"
        )
        return ProcessAnswer(returncode=0)

    git_fake.answer(lambda call: "pytest" in call.argv, pytest_writes_coverage)

    result = runner.invoke(ci_app, ["coverage", "--build-index"])

    target_path = resolve_coverage_index_path(repo)
    index = load_index(target_path)
    assert (
        result.exit_code,
        target_path.is_file(),
        index.version,
        index.covering_tests.get("src/devops_cli/a.py"),
    ) == (
        0,
        True,
        INDEX_FORMAT_VERSION,
        ["tests/test_a.py"],
    )


def test_build_index_saves_nothing_on_failed_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git_fake: GitFake
) -> None:
    """A failing test run saves nothing and exits with a nonzero status code."""
    repo = _make_git_repo(tmp_path, git_fake, monkeypatch)
    git_fake.answer(lambda call: "pytest" in call.argv, ProcessAnswer(returncode=1))

    result = runner.invoke(ci_app, ["coverage", "--build-index"])

    target_path = resolve_coverage_index_path(repo)
    assert (result.exit_code, target_path.is_file()) == (1, False)


def test_build_index_saves_nothing_and_exits_1_when_tree_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git_fake: GitFake
) -> None:
    """When a tracked source file changes during the run, save nothing and exit 1."""
    repo = _make_git_repo(tmp_path, git_fake, monkeypatch)
    coverage_db = repo / ".data" / ".coverage"

    def pytest_changes_the_tree(call: ProcessCall) -> ProcessAnswer:
        _write_minimal_coverage_db(
            coverage_db, repo / "src" / "devops_cli" / "a.py", "tests/test_a.py"
        )
        # Mutate tracked source file during execution
        (repo / "src" / "devops_cli" / "a.py").write_text("A = 999\n", encoding="utf-8")
        return ProcessAnswer(returncode=0)

    git_fake.answer(lambda call: "pytest" in call.argv, pytest_changes_the_tree)

    result = runner.invoke(ci_app, ["coverage", "--build-index"])

    target_path = resolve_coverage_index_path(repo)
    assert (
        result.exit_code,
        target_path.is_file(),
        "src/devops_cli/a.py" in result.output,
    ) == (
        1,
        False,
        True,
    )
