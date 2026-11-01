"""A review records each run of each tool it starts (#772).

A scanner builds a `ToolRequest` for its tool. The request names the config files and the ruleset
files that the tool reads. The executor answers with a `ToolRun`, the record of what ran. The
orchestrator keeps every record, and the review profile and `review.md` show them.

These cases give the scanners `ToolExecutorFake`. It starts nothing and builds each record from
real files and a real git tree, as the real executors do.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jsonschema
import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.profile import ReviewProfile, profiling
from devops_cli.ai.review.runner import _write_review_profile
from devops_cli.ai.review.tool_runs import TOOL_RUNS_COLUMNS, tool_runs_section
from devops_cli.ai.review_schema import ReviewSessionPayload
from devops_cli.ai.run_store import digest, file_digest
from devops_cli.config.constants import (
    CONST_CANARY_WORKDIR_PREFIX,
    CONST_OSV_DB_DIR_ENV,
    CONST_OSV_DB_DIR_NAME,
    CONST_REVIEW_SARIF_FILENAME,
    CONST_REVIEW_SCAN_BANDIT_INI,
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
)
from devops_cli.config.defaults import DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES
from devops_cli.exceptions.sandbox import SandboxValidationError
from devops_cli.review.anchors import ToolAnchor
from devops_cli.review.finding import Finding
from devops_cli.review.rules_pack import discover_pack_rules
from devops_cli.security.bandit import run_bandit_scan
from devops_cli.security.base import ScanOutcome
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.kubelinter import run_kubelinter_scan
from devops_cli.security.mypy import run_mypy_scan
from devops_cli.security.osv_scanner import run_osv_scan
from devops_cli.security.pluto import run_pluto_scan
from devops_cli.security.ruff import run_ruff_scan
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.semgrep_registry import cached_ruleset
from devops_cli.security.tool_executor import (
    RecordingToolExecutor,
    ToolExecutor,
    ToolRequest,
    ToolRun,
)
from devops_cli.security.trivy import run_trivy_scan
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.fakes.tool_executor import ToolAnswer, ToolExecutorFake
from tests.support.paths import FIXTURES
from tests.support.registry_cache import REPLACED_RULESET

if TYPE_CHECKING:
    from tests.support.fakes.git import GitFake

# The report of a scan; no group analysis, so no model sees the admitted findings.
_NO_GROUP_ANALYSIS = ReviewStageFlags(group_analysis=False)

_MANIFEST = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web\n"
_RULES = "rules:\n  - id: any\n    languages: [python]\n    severity: ERROR\n    message: m\n    pattern: eval(...)\n"

ScanOver = Callable[[Path, ToolExecutor], ScanOutcome]


@pytest.fixture(autouse=True)
def scanners_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every review tool is on PATH, so the scanners start theirs. Nothing starts: the fake runs."""
    real_which = shutil.which
    installed = {tool for tool, _ in _REVIEW_SCANS}

    def which(cmd: str, *args: Any, **kwargs: Any) -> str | None:
        return f"/opt/scanners/{cmd}" if cmd in installed else real_which(cmd, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", which)


@pytest.fixture(autouse=True)
def osv_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty directory for the offline database of osv-scanner, so a database that the host
    fetched before gives no case a ruleset file."""
    cache = tmp_path / "osv-cache"
    cache.mkdir()
    monkeypatch.setenv(CONST_OSV_DB_DIR_ENV, str(cache))
    return cache


@pytest.fixture
def osv_database(osv_cache: Path) -> Path:
    """The offline database of osv-scanner, with the file of two ecosystems. Answers the
    directory that osv-scanner reads."""
    database = osv_cache / CONST_OSV_DB_DIR_NAME
    for ecosystem in ("PyPI", "npm"):
        (database / ecosystem).mkdir(parents=True)
        (database / ecosystem / "all.zip").write_bytes(f"{ecosystem} advisories\n".encode())
    return database


@pytest.fixture
def trivy_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The cache of Trivy, with the metadata of its checks bundle and of its vulnerability database."""
    cache = tmp_path / "trivy-cache"
    for kind in ("policy", "db"):
        (cache / kind).mkdir(parents=True)
        (cache / kind / "metadata.json").write_text(f'{{"kind": "{kind}"}}\n', encoding="utf-8")
    monkeypatch.setenv("TRIVY_CACHE_DIR", str(cache))
    return cache


@pytest.fixture(autouse=True)
def _answer_tool_runs_git(git_fake: GitFake) -> None:
    def _handle_git(call: ProcessCall) -> ProcessAnswer:
        argv = call.argv
        if "rev-parse" in argv:
            if "--show-toplevel" in argv:
                cwd = call.cwd or Path.cwd()
                return ProcessAnswer(stdout=str(Path(cwd).resolve()) + "\n")
            return ProcessAnswer(stdout="1" * 40 + "\n")
        if "ls-files" in argv:
            cwd = Path(argv[argv.index("-C") + 1]) if "-C" in argv else (call.cwd or Path.cwd())
            files = [
                p.relative_to(cwd).as_posix()
                for p in sorted(cwd.rglob("*"))
                if p.is_file() and not p.is_relative_to(cwd / ".git")
            ]
            delim = "\0" if "-z" in argv else "\n"
            return ProcessAnswer(stdout=delim.join(files) + delim)
        if "diff" in argv:
            return ProcessAnswer(stdout="")
        if "status" in argv:
            return ProcessAnswer(stdout="")
        if "log" in argv:
            return ProcessAnswer(stdout="2026-01-01T00:00:00+00:00\n")
        return ProcessAnswer()

    git_fake.answer(lambda _: True, _handle_git)


@pytest.fixture
def tree(tmp_path: Path, trivy_cache: Path) -> Path:
    """A committed git tree holding one file for each review tool to read, the config files that
    Ruff and osv-scanner find on their own, and the Python version that mypy needs."""
    root = (tmp_path / "tree").resolve()
    (root / ".devops").mkdir(parents=True)
    (root / ".devops" / "review.toml").write_text(
        '[review]\nkubernetes_version = "v1.31.0"\n', encoding="utf-8"
    )
    (root / "app.py").write_text('print("hello")\n', encoding="utf-8")
    (root / "other.py").write_text('print("other")\n', encoding="utf-8")
    (root / "deploy.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (root / "osv-scanner.toml").write_text("[[IgnoredVulns]]\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.14"\n\n[tool.mypy]\npython_version = "3.14"\n',
        encoding="utf-8",
    )
    (root / "rules.yaml").write_text(_RULES, encoding="utf-8")
    (root / ".git").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def orchestrator(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake
) -> ReviewPipelineOrchestrator:
    """A review of the tree that starts its tools through the fake."""
    return ReviewPipelineOrchestrator(
        session_id="s772c",
        session_dir=tmp_path / "session",
        target_dir=tree,
        tool_executor=tool_executor_fake,
    )


class _Revision:
    """The base revision of a review: the content of a file at the commit it is compared with."""

    def read(self, path: str) -> str | None:
        return 'print("base")\n' if path == "app.py" else None


def _semgrep(tree: Path, executor: ToolExecutor) -> ScanOutcome:
    return run_semgrep_scan(
        [tree / "app.py"],
        config=str(tree / "rules.yaml"),
        reviewed_tree=tree,
        tool_executor=executor,
    )


# Each scan as a review's scanner stage starts it (`devops_cli.ai.review.pipeline`).
_REVIEW_SCANS: list[tuple[str, ScanOver]] = [
    (
        "bandit",
        lambda t, x: run_bandit_scan([t / "app.py"], isolated=True, tree=t, tool_executor=x),
    ),
    ("gitleaks", lambda t, x: run_gitleaks_scan([t / "app.py"], isolated=True, tool_executor=x)),
    ("semgrep", _semgrep),
    (
        "trivy",
        lambda t, x: run_trivy_scan(
            t / "Dockerfile", scan_type="config", isolated=True, tool_executor=x
        ),
    ),
    (
        "kube-linter",
        lambda t, x: run_kubelinter_scan(t / "deploy.yaml", isolated=True, tool_executor=x),
    ),
    (
        "pluto",
        lambda t, x: run_pluto_scan(
            t / "deploy.yaml", isolated=True, tree=t, kubernetes_version="v1.31.0", tool_executor=x
        ),
    ),
    (
        "osv-scanner",
        lambda t, x: run_osv_scan([t / "uv.lock"], tree=t, isolated=True, tool_executor=x),
    ),
    (
        "ruff",
        lambda t, x: run_ruff_scan(
            [t / "app.py"], isolated=True, tree=t, require_version=True, tool_executor=x
        ),
    ),
    (
        "mypy",
        lambda t, x: run_mypy_scan([t / "app.py"], tree=t, checkout_root=t, tool_executor=x),
    ),
]

# The file names that each review scan names for its tool, config files first and ruleset files
# second. The survey of #772 gives the reason for each: it ran the real tools under strace and
# read the files they opened.
_READS: dict[str, tuple[list[str], list[str]]] = {
    "bandit": ([".bandit"], []),
    "gitleaks": (["gitleaks.toml", ".gitleaksignore"], []),
    "semgrep": ([], ["rules.yaml"]),
    "trivy": (["trivy.yaml", ".trivyignore"], ["metadata.json"]),
    "kube-linter": (["kube-linter.yaml"], []),
    "pluto": ([], []),
    "osv-scanner": (["osv-scanner.toml"], []),
    "ruff": (["pyproject.toml"], []),
    "mypy": (["pyproject.toml"], []),
}


def _run_of(scan: ScanOver, tree: Path, executor: ToolExecutorFake) -> ToolRun:
    """The record of the one run that `scan` made over the fake."""
    recorder = RecordingToolExecutor(executor)
    assert scan(tree, recorder).status == "ran"
    [run] = recorder.runs
    return run


def _request_of(scan: ScanOver, tree: Path, executor: ToolExecutorFake) -> ToolRequest:
    """The request of the one run that `scan` made over the fake."""
    executor.requests.clear()
    scan(tree, executor)
    [request] = executor.requests
    return request


@pytest.mark.parametrize(("tool", "scan"), _REVIEW_SCANS, ids=[tool for tool, _ in _REVIEW_SCANS])
def test_each_review_scan_names_the_config_files_and_the_ruleset_files_its_tool_reads(
    tool: str, scan: ScanOver, tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The request of a scan names what the tool reads, so the two digests of the record mean
    something. A tool that reads no config file or no ruleset file names none."""
    request = _request_of(scan, tree, tool_executor_fake)

    config, ruleset = _READS[tool]
    pack = [rule.name for rule, _ in discover_pack_rules().values()]
    assert pack != []
    assert (
        [path.name for path in request.config_files],
        sorted(path.name for path in request.ruleset_files),
    ) == (config, sorted(ruleset + (pack if tool == "semgrep" else [])))


_OSV_SCAN = dict(_REVIEW_SCANS)["osv-scanner"]


def test_osv_scanner_names_the_file_of_each_ecosystem_of_its_database_as_ruleset_files(
    tree: Path, osv_database: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The ruleset of osv-scanner is its offline database: one `all.zip` for each ecosystem
    (#2130)."""
    request = _request_of(_OSV_SCAN, tree, tool_executor_fake)

    assert request.ruleset_files == (
        osv_database / "PyPI" / "all.zip",
        osv_database / "npm" / "all.zip",
    )


def test_the_ruleset_digest_of_osv_scanner_follows_the_content_of_its_database(
    tree: Path, osv_database: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The same database gives the same digest, and a changed database gives another (#2130)."""
    first = _run_of(_OSV_SCAN, tree, tool_executor_fake).ruleset_digest
    same = _run_of(_OSV_SCAN, tree, tool_executor_fake).ruleset_digest
    (osv_database / "PyPI" / "all.zip").write_bytes(b"PyPI advisories, one more\n")
    changed = _run_of(_OSV_SCAN, tree, tool_executor_fake).ruleset_digest

    assert first == same
    assert changed != first


def test_osv_scanner_with_no_database_file_names_no_ruleset_file(
    tree: Path, osv_cache: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A database directory that holds no `all.zip` gives no ruleset file (#2130)."""
    (osv_cache / CONST_OSV_DB_DIR_NAME / "PyPI").mkdir(parents=True)

    request = _request_of(_OSV_SCAN, tree, tool_executor_fake)

    assert request.ruleset_files == ()
    assert _run_of(_OSV_SCAN, tree, tool_executor_fake).ruleset_digest == digest([])


def test_a_database_file_of_osv_scanner_over_the_size_cap_still_gets_a_digest(
    tree: Path, osv_database: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The npm database is larger than the cap on the files a run reads into memory. The record
    reads it as a stream, so the scan still runs (#2130)."""
    npm = osv_database / "npm" / "all.zip"
    with npm.open("wb") as handle:
        handle.truncate(DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES + 1)

    run = _run_of(_OSV_SCAN, tree, tool_executor_fake)

    assert run.ruleset_digest == digest(
        sorted([file_digest(osv_database / "PyPI" / "all.zip"), file_digest(npm)])
    )


def test_ruff_names_every_config_file_it_may_read_from_the_nearest_directory_up_to_the_tree(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Ruff finds its config by looking in the directory of each file and in each directory above
    it. The request names them, nearest first, and stops at the tree. Ruff also applies a file above
    the tree, and the direct executor does not record it (the survey of #772)."""
    (tree / "pkg").mkdir()
    (tree / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (tree / "pkg" / "ruff.toml").write_text("line-length = 99\n", encoding="utf-8")
    (tree.parent / "ruff.toml").write_text("line-length = 98\n", encoding="utf-8")

    run_ruff_scan(
        [tree / "pkg" / "mod.py"],
        isolated=True,
        tree=tree,
        require_version=True,
        tool_executor=tool_executor_fake,
    )

    [request] = tool_executor_fake.requests
    assert request.config_files == (tree / "pkg" / "ruff.toml", tree / "pyproject.toml")


def test_ruff_over_a_directory_looks_for_its_config_file_in_that_directory(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A directory target is the place where Ruff starts to look, not a file beside which it looks."""
    (tree / "pkg").mkdir()
    (tree / "pkg" / "ruff.toml").write_text("line-length = 99\n", encoding="utf-8")

    run_ruff_scan(
        tree / "pkg",
        isolated=True,
        tree=tree,
        require_version=True,
        tool_executor=tool_executor_fake,
    )

    [request] = tool_executor_fake.requests
    assert request.config_files == (tree / "pkg" / "ruff.toml", tree / "pyproject.toml")


def test_osv_scanner_names_the_config_file_beside_each_lockfile_and_none_above_it(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """osv-scanner looks for `osv-scanner.toml` in the directory of its lockfile and nowhere else."""
    (tree / "sub").mkdir()
    (tree / "sub" / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    run_osv_scan(
        [tree / "sub" / "uv.lock"], tree=tree, isolated=True, tool_executor=tool_executor_fake
    )

    [request] = tool_executor_fake.requests
    assert request.config_files == ()


@pytest.mark.parametrize(
    ("tool", "config", "changed"),
    [
        ("ruff", "pyproject.toml", '[project]\nrequires-python = ">=3.14"\n[tool.ruff]\n'),
        ("osv-scanner", "osv-scanner.toml", "# changed\n"),
    ],
)
def test_a_changed_config_file_of_the_tree_changes_the_config_digest(
    tool: str, config: str, changed: str, tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The digest follows the content of the file that the tool finds, and only its content."""
    scan = dict(_REVIEW_SCANS)[tool]
    before = _run_of(scan, tree, tool_executor_fake).config_digest
    same = _run_of(scan, tree, tool_executor_fake).config_digest
    (tree / config).write_text(changed, encoding="utf-8")
    after = _run_of(scan, tree, tool_executor_fake).config_digest

    expected = digest([file_digest(tree / config)])
    assert (before == same, after == expected, after != before) == (True, True, True)


def test_a_config_that_devops_cli_hands_the_tool_gives_one_digest_that_follows_its_content(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A review hands Bandit its own `.bandit` in a scratch directory. The directory differs from
    run to run, so the digest must follow the content and not the path: a copy of the text in
    another place gives the digest of the record."""
    scan = dict(_REVIEW_SCANS)["bandit"]
    first = _run_of(scan, tree, tool_executor_fake).config_digest
    second = _run_of(scan, tree, tool_executor_fake).config_digest
    copy = tmp_path / "copy.ini"
    copy.write_text(CONST_REVIEW_SCAN_BANDIT_INI, encoding="utf-8")

    assert (first == second, first == digest([file_digest(copy)])) == (True, True)


def test_a_changed_ruleset_file_changes_the_ruleset_digest(
    tree: Path, trivy_cache: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Trivy reads the metadata of its checks bundle. Semgrep reads the rules file it is given."""
    trivy, semgrep = dict(_REVIEW_SCANS)["trivy"], dict(_REVIEW_SCANS)["semgrep"]
    before = (
        _run_of(trivy, tree, tool_executor_fake).ruleset_digest,
        _run_of(semgrep, tree, tool_executor_fake).ruleset_digest,
    )
    (trivy_cache / "policy" / "metadata.json").write_text('{"kind": "new"}\n', encoding="utf-8")
    (tree / "rules.yaml").write_text(_RULES + "# changed\n", encoding="utf-8")
    after = (
        _run_of(trivy, tree, tool_executor_fake).ruleset_digest,
        _run_of(semgrep, tree, tool_executor_fake).ruleset_digest,
    )

    assert (before[0] != after[0], before[1] != after[1]) == (True, True)


def _registry_semgrep(tree: Path, executor: ToolExecutor, *, in_review: bool = True) -> ScanOutcome:
    """A scan with the registry ruleset `p/default`, which the cache holds, as a review starts it
    (the files linked under a scratch directory) or as an agent tool does."""
    return run_semgrep_scan(
        [tree / "app.py"],
        config="p/default",
        reviewed_tree=tree if in_review else None,
        ruleset=cached_ruleset("p/default"),
        tool_executor=executor,
    )


@pytest.mark.usefixtures("cached_default_ruleset")
def test_semgrep_names_the_registry_ruleset_that_a_review_writes_to_its_scratch_directory(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A review's Semgrep reads the bytes of the registry ruleset from a file in its scratch
    directory, named by their digest. The request names that file."""
    ruleset = cached_ruleset("p/default")
    assert ruleset is not None

    _registry_semgrep(tree, tool_executor_fake)

    [request] = tool_executor_fake.requests
    assert request.cwd is not None
    assert request.cwd / ruleset.workdir_name in request.ruleset_files


@pytest.mark.usefixtures("cached_default_ruleset")
def test_semgrep_outside_a_review_names_the_registry_ruleset_in_the_cache_directory(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Semgrep returns plain rule ids for a config in its working directory, so a scan outside a
    review starts in the cache directory. The request names the cached file by its path there."""
    ruleset = cached_ruleset("p/default")
    assert ruleset is not None

    _registry_semgrep(tree, tool_executor_fake, in_review=False)

    [request] = tool_executor_fake.requests
    assert (request.cwd, ruleset.path in request.ruleset_files) == (ruleset.path.parent, True)


@pytest.mark.parametrize("in_review", [True, False], ids=["in-review", "outside-a-review"])
def test_the_ruleset_digest_of_a_semgrep_scan_follows_the_bytes_of_the_registry_ruleset(
    in_review: bool,
    tree: Path,
    cached_default_ruleset: Path,
    tool_executor_fake: ToolExecutorFake,
) -> None:
    """The record shows which rules Semgrep read: the rules of a registry ruleset that a fetch has
    replaced give another digest, and the same rules give the same digest."""
    recorder = RecordingToolExecutor(tool_executor_fake)
    _registry_semgrep(tree, recorder, in_review=in_review)
    _registry_semgrep(tree, recorder, in_review=in_review)
    cached_default_ruleset.write_bytes(REPLACED_RULESET)
    _registry_semgrep(tree, recorder, in_review=in_review)

    first, same, replaced = (run.ruleset_digest for run in recorder.runs)
    assert (first == same, first != replaced) == (True, True)


def test_a_scan_that_is_no_config_scan_reads_the_metadata_of_the_trivy_database(
    tree: Path, trivy_cache: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A `config` scan reads the checks bundle only. Any other scan reads the vulnerability
    database, and its metadata file names the version of the database."""
    run_trivy_scan(
        tree / "Dockerfile", scan_type="fs", isolated=True, tool_executor=tool_executor_fake
    )

    [request] = tool_executor_fake.requests
    assert request.ruleset_files == (trivy_cache / "db" / "metadata.json",)


def test_a_trivy_without_a_cache_reads_no_ruleset_file(
    tree: Path,
    tmp_path: Path,
    tool_executor_fake: ToolExecutorFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before its first run, Trivy has no metadata file. The request names none."""
    monkeypatch.setenv("TRIVY_CACHE_DIR", str(tmp_path / "no-cache"))

    request = _request_of(dict(_REVIEW_SCANS)["trivy"], tree, tool_executor_fake)

    assert request.ruleset_files == ()


@pytest.mark.parametrize(("tool", "scan"), _REVIEW_SCANS, ids=[tool for tool, _ in _REVIEW_SCANS])
def test_the_argument_template_of_a_record_holds_no_path(
    tool: str, scan: ScanOver, tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A record must read the same for the same scan. A scratch directory is new in each run, and
    the path of a reviewed file or of a rule pack is a path of the host. Semgrep names its files
    from its scratch directory with `./`."""
    run = _run_of(scan, tree, tool_executor_fake)

    assert [arg for arg in run.argv_template if arg.startswith(("/", "./"))] == []


def test_the_argument_template_marks_where_the_targets_and_the_files_of_a_scan_stand(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The flags stay in the template. A path that names a target, a config file or a ruleset file
    gives way to a placeholder, and the placeholder of the targets stands once for all of them."""
    scan = dict(_REVIEW_SCANS)["gitleaks"]

    run = _run_of(scan, tree, tool_executor_fake)

    assert run.argv_template == (
        "gitleaks",
        "dir",
        "--report-format",
        "json",
        "--report-path",
        "-",
        "--redact",
        "{targets}",
        "--config",
        "{config}",
        "--gitleaks-ignore-path",
        "{config}",
    )


def test_the_files_that_a_command_names_one_after_the_other_stand_once_in_the_template(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Bandit takes its files as arguments one after the other. The template does not count them."""
    recorder = RecordingToolExecutor(tool_executor_fake)

    run_bandit_scan(
        [tree / "app.py", tree / "other.py"], isolated=True, tree=tree, tool_executor=recorder
    )

    [run] = recorder.runs
    assert run.argv_template[:3] == ("bandit", "{targets}", "--ignore-nosec")


def test_the_record_of_mypy_names_its_interpreter_by_its_file_name(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Mypy runs as `python -I -m mypy` with an interpreter that the PATH does not name. The
    template names the interpreter by its file name and the tool after `-m`. The cache directory
    is no argument, so no path of the host stands in the template."""
    python = tree / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    recorder = RecordingToolExecutor(tool_executor_fake)

    run_mypy_scan([tree / "app.py"], tree=tree, checkout_root=tree, tool_executor=recorder)

    [run] = recorder.runs
    assert (run.tool, run.argv_template) == (
        "mypy",
        (
            "python",
            "-I",
            "-m",
            "mypy",
            "--python-version=3.14",
            "--config-file",
            "{config}",
            "--no-error-summary",
            "{targets}",
        ),
    )


@pytest.mark.parametrize("field", ["config_files", "ruleset_files"])
def test_a_path_that_is_a_target_and_a_file_the_tool_reads_stands_as_a_target_in_the_template(
    field: str, tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A rule file that a scan also scans reads as one of its targets, as the docstring of the
    placeholders says."""
    named = tree / "rules.yaml"
    request = ToolRequest(
        tool="semgrep", arguments=("--config", str(named)), workdir=tree, targets=(named,)
    ).model_copy(update={field: (named,)})

    run = tool_executor_fake.run(request).run

    assert run.argv_template == ("semgrep", "--config", "{targets}")


def test_a_pipe_in_a_record_does_not_split_its_row_in_the_report(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A version or a command may hold a pipe, which a table reads as the end of a cell."""
    tool_executor_fake.script("gitleaks", ToolAnswer(version="1.0|beta"))
    recorder = RecordingToolExecutor(tool_executor_fake)
    run_gitleaks_scan([tree / "app.py"], isolated=True, tool_executor=recorder)

    [row] = tool_runs_section(recorder.runs)[3:-1]

    cells = re.split(r"(?<!\\)\|", row.strip("|"))
    assert (len(cells), cells[1]) == (len(TOOL_RUNS_COLUMNS), " 1.0\\|beta ")


def test_a_review_profile_holds_one_row_per_tool_run_with_every_field(
    orchestrator: ReviewPipelineOrchestrator, tool_executor_fake: ToolExecutorFake
) -> None:
    """The orchestrator keeps the record of each run its analyzers make, and the profile of the
    review holds one row for each. `profile.json` holds the rows in full. A canary checks a tool on
    a fixture of its own and scans nothing of the review, so it has no row."""
    with profiling() as profiler:
        orchestrator.init_per_file_payloads(["app.py", "deploy.yaml", "Dockerfile", "uv.lock"], {})
        profile = _write_review_profile(profiler, orchestrator, "tree", 4, kept=False)

    rows = profile.tool_runs
    empty = [
        (row.tool, name)
        for row in rows
        for name, value in row.model_dump().items()
        if value in ("", None, ())
    ]
    scans = [
        request.tool
        for request in tool_executor_fake.requests
        if not request.workdir.name.startswith(CONST_CANARY_WORKDIR_PREFIX)
    ]
    assert [row.tool for row in rows] == scans
    assert ({row.tool for row in rows}, empty, {row.executor for row in rows}) == (
        {tool for tool, _ in _REVIEW_SCANS},
        [],
        {"fake"},
    )
    assert ReviewProfile.model_validate_json(profile.model_dump_json()).tool_runs == rows


def test_the_scan_of_the_base_revision_adds_its_rows_with_no_commit(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A review of a branch scans the base revision too. It writes the files of that revision to a
    scratch directory outside any checkout, so those rows record no commit."""
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s772c",
        session_dir=tmp_path / "session",
        target_dir=tree,
        base_revision=_Revision(),
        tool_executor=tool_executor_fake,
    )

    orchestrator.init_per_file_payloads(["app.py"], {})

    runs = orchestrator.tool_executor.runs
    base = {run.tool for run in runs if run.commit is None}
    head = {run.tool for run in runs if run.commit is not None}
    assert (base, head >= {"bandit", "gitleaks", "semgrep", "ruff", "mypy"}) == (
        {"bandit", "gitleaks", "semgrep"},
        True,
    )


def test_a_review_that_runs_no_tool_has_a_profile_with_no_rows(tmp_path: Path) -> None:
    """A profile written before this field existed, or by a review that ran no tool, has none."""
    assert ReviewProfile(session_id="s", target="t").tool_runs == []


def test_the_report_shows_a_row_for_each_distinct_record_and_counts_its_runs(
    tree: Path, orchestrator: ReviewPipelineOrchestrator
) -> None:
    """Gitleaks scans one file at a time, so a review of many files runs it many times with one
    record. The report holds one row for a record and counts its runs. `profile.json` keeps each.
    A row names the tool, its version, how it ran, the short digest of its binary, the digests of
    its config and ruleset, the commit, the command, the exit code and the success."""
    executor = orchestrator.tool_executor
    run_gitleaks_scan([tree / "app.py", tree / "other.py"], isolated=True, tool_executor=executor)
    run_bandit_scan([tree / "app.py"], isolated=True, tree=tree, tool_executor=executor)
    bandit = executor.runs[-1]

    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]

    section = report.split("## Tool Runs\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert section == [
        "| Tool | Version | Executor | Binary | Config | Ruleset | Commit | Command | Exit code "
        "| Succeeded | Runs |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        section[2],
        f"| bandit | {bandit.version} | fake | `{bandit.binary_sha256[:16]}` | "
        f"`{bandit.config_digest}` | `{bandit.ruleset_digest}` | `{bandit.commit}` | "
        f"`{' '.join(bandit.argv_template)}` | 0 | yes | 1 |",
    ]
    assert section[2].startswith("| gitleaks | ")
    assert section[2].endswith(" | 2 |")


def test_the_sarif_of_a_review_holds_a_run_with_the_records_of_each_tool_that_ran(
    tree: Path, orchestrator: ReviewPipelineOrchestrator
) -> None:
    """`findings.sarif` holds the records of Gitleaks in the run of Gitleaks, each in full and each
    with its invocation. Bandit gave no result and its run succeeded, so its run says that it
    looked and found nothing (#2100)."""
    executor = orchestrator.tool_executor
    run_gitleaks_scan([tree / "app.py", tree / "other.py"], isolated=True, tool_executor=executor)
    run_bandit_scan([tree / "app.py"], isolated=True, tree=tree, tool_executor=executor)
    orchestrator.admitted_scanner_findings = [
        Finding(
            anchor=ToolAnchor(run_id="r1", result_index=0, rule_id="aws-access-key-id"),
            tool="gitleaks",
            rule_id="aws-access-key-id",
            path="app.py",
            line=1,
            message="AWS access key",
            severity="HIGH",
            severity_derivation="rule",
            fingerprint_v2="fp-gitleaks-1",
        )
    ]

    orchestrator._persist_session_artifacts(ReviewSessionPayload(), ReviewSessionPayload(), "")

    sarif = orchestrator.session.staging / CONST_REVIEW_SARIF_FILENAME
    document = json.loads(sarif.read_text(encoding="utf-8"))
    bandit, run = document["runs"]
    gitleaks = [record for record in executor.runs if record.tool == "gitleaks"]
    assert (
        bandit["tool"]["driver"]["name"],
        bandit["results"],
        [invocation["executionSuccessful"] for invocation in bandit["invocations"]],
    ) == ("bandit", [], [True])
    assert (
        run["tool"]["driver"]["name"],
        run["tool"]["driver"]["version"],
        [ToolRun.model_validate(record) for record in run["properties"]["tool_runs"]],
        [invocation["executionSuccessful"] for invocation in run["invocations"]],
    ) == ("gitleaks", gitleaks[0].version, gitleaks, [True, True])
    schema = json.loads((FIXTURES / "sarif-schema-2.1.0.json").read_text(encoding="utf-8"))
    jsonschema.validators.validator_for(schema)(schema).validate(document)


def test_a_report_of_a_review_that_ran_no_tool_has_no_tool_runs_section(tmp_path: Path) -> None:
    """A table with no row would read as a review that ran its tools and recorded nothing."""
    orchestrator = ReviewPipelineOrchestrator(session_id="s772c", target_dir=tmp_path)

    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]

    assert "## Tool Runs" not in report


def test_the_recording_executor_answers_as_the_executor_it_wraps_and_keeps_each_record(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The scan reads the answer it would have read from the wrapped executor, and the records
    stay in the order of the runs."""
    tool_executor_fake.script("gitleaks", ToolAnswer(exit_code=1, stdout="found", stderr="warn"))
    recorder = RecordingToolExecutor(tool_executor_fake)
    request = ToolRequest(tool="gitleaks", workdir=tree, targets=(tree / "app.py",))

    answer = recorder.run(request)
    recorder.run(request.model_copy(update={"tool": "bandit"}))

    assert (answer == tool_executor_fake.run(request), [run.tool for run in recorder.runs]) == (
        True,
        ["gitleaks", "bandit"],
    )


def test_a_request_that_the_executor_refuses_leaves_no_record(
    tree: Path, tmp_path: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A run that never started is no run. The scan reports the refusal, as it did before."""
    recorder = RecordingToolExecutor(tool_executor_fake)
    outside = (tmp_path / "outside").resolve()
    outside.mkdir()
    request = ToolRequest(tool="gitleaks", workdir=tree, targets=(outside,))

    with pytest.raises(SandboxValidationError, match="outside the tree"):
        recorder.run(request)

    assert recorder.runs == ()


# How a run ended: the code that ran the tool settles its record (#2100).

_GITLEAKS_FINDING = '[{"RuleID": "aws-access-key-id", "File": "app.py", "StartLine": 1}]'


@pytest.mark.parametrize(
    ("answer", "settled"),
    [
        (ToolAnswer(exit_code=1, stdout=_GITLEAKS_FINDING), (1, True)),
        (ToolAnswer(), (0, True)),
        (ToolAnswer(exit_code=2, stdout="panic: no config", stderr="bad"), (2, False)),
        (ToolAnswer(exit_code=CONST_SANDBOX_TIMEOUT_EXIT_CODE, timed_out=True), (None, False)),
        (ToolAnswer(exit_code=-9), (None, False)),
    ],
    ids=["found", "clean", "not-json", "timed-out", "signal"],
)
def test_a_scan_settles_its_run_with_the_exit_code_and_the_success_of_its_outcome(
    answer: ToolAnswer,
    settled: tuple[int | None, bool],
    tree: Path,
    tool_executor_fake: ToolExecutorFake,
) -> None:
    """Gitleaks exits with 1 when it finds a secret, so the exit code does not tell success. The
    scan decides from the exit code and the output together. A run that timed out, or that a
    signal ended, has no exit code of its own (SARIF 2.1.0, 3.20.9)."""
    tool_executor_fake.script("gitleaks", answer)
    recorder = RecordingToolExecutor(tool_executor_fake)

    run_gitleaks_scan([tree / "app.py"], isolated=True, tool_executor=recorder)

    [run] = recorder.runs
    assert (run.exit_code, run.success) == settled


@pytest.mark.parametrize(("exit_code", "success"), [(0, True), (1, True), (2, False)])
def test_mypy_settles_its_run_as_succeeded_when_it_finished_its_check(
    exit_code: int, success: bool, tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """mypy exits with 1 when it finds an error, and with 2 when it cannot check the files."""
    tool_executor_fake.script("mypy", ToolAnswer(exit_code=exit_code))
    recorder = RecordingToolExecutor(tool_executor_fake)

    run_mypy_scan([tree / "app.py"], tree=tree, checkout_root=tree, tool_executor=recorder)

    [run] = recorder.runs
    assert (run.exit_code, run.success) == (exit_code, success)


def test_the_recorder_keeps_the_settled_record_in_the_place_of_the_run(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """The records stay in the order the runs started. A run that its caller has not settled yet
    has no exit code and no success."""
    recorder = RecordingToolExecutor(tool_executor_fake)
    request = ToolRequest(tool="gitleaks", workdir=tree, targets=(tree / "app.py",))
    first = recorder.run(request)
    recorder.run(request.model_copy(update={"tool": "bandit"}))

    recorder.settle(first, success=True)

    assert [(run.tool, run.exit_code, run.success) for run in recorder.runs] == [
        ("gitleaks", 0, True),
        ("bandit", None, None),
    ]
    assert recorder.runs[0] == first.run.model_copy(update={"exit_code": 0, "success": True})


def test_the_recorder_refuses_a_result_that_is_settled_or_that_it_did_not_start(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """A second settle of one result is a defect of its caller, so the first settle stays."""
    recorder = RecordingToolExecutor(tool_executor_fake)
    request = ToolRequest(tool="gitleaks", workdir=tree, targets=(tree / "app.py",))
    result = recorder.run(request)
    recorder.settle(result, success=True)

    with pytest.raises(ValueError, match="gitleaks"):
        recorder.settle(result, success=False)
    with pytest.raises(ValueError, match="gitleaks"):
        recorder.settle(tool_executor_fake.run(request), success=True)

    assert [run.success for run in recorder.runs] == [True]


def test_the_report_shows_a_row_for_each_way_that_the_runs_of_a_record_ended(
    tree: Path, tool_executor_fake: ToolExecutorFake
) -> None:
    """Two runs that read the same files and ended in different ways make two rows. Without the
    exit code and the success, the two rows would read the same."""
    recorder = RecordingToolExecutor(tool_executor_fake)
    tool_executor_fake.script("gitleaks", ToolAnswer(exit_code=1, stdout=_GITLEAKS_FINDING))
    run_gitleaks_scan([tree / "app.py"], isolated=True, tool_executor=recorder)
    tool_executor_fake.script("gitleaks", ToolAnswer(exit_code=2, stdout="panic"))
    run_gitleaks_scan([tree / "app.py"], isolated=True, tool_executor=recorder)

    rows = tool_runs_section(recorder.runs)[3:-1]

    ended = [re.split(r"(?<!\\)\|", row.strip("|"))[-3:-1] for row in rows]
    assert (TOOL_RUNS_COLUMNS[-3:], ended) == (
        ("Exit code", "Succeeded", "Runs"),
        [[" 1 ", " yes "], [" 2 ", " no "]],
    )
