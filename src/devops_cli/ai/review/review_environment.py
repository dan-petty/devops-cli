"""Review execution environment and conventions discovery helpers."""

from __future__ import annotations

import ast
import os
import shlex
import signal
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from devops_cli.ai.review.criteria_evidence import counts_as_evidence, python_invocation
from devops_cli.ai.review.verdicts import apply_verdict
from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_ALLOWED_CRITERIA_BINARIES,
    CONST_ALLOWED_GIT_SUBCOMMANDS,
    CONST_CRITERIA_NON_DISCRIMINATING,
    CONST_DISALLOWED_SHELL_TOKENS,
    CONST_FORBIDDEN_FIND_ACTIONS,
    CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES,
    CONST_IMPORT_BY_NAME_CALLS,
    CONST_PYTEST_MODULES,
    CONST_PYTEST_RUNNER_FUNCTIONS,
    CONST_PYTHON_CRITERIA_BINARIES,
    CONST_REVIEW_CONVENTIONS_FILE,
)
from devops_cli.config.defaults import (
    DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS,
    DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
    DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS,
)

_TARGET_CONVENTIONS_CANDIDATES: tuple[str, ...] = (
    CONST_AGENTS_MD_FILENAME,
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".cursorrules",
    ".cursor/rules",
)


# A file's text by its path, or None when there is no such file.
_FileReader = Callable[[Path], str | None]


def _repo_root(directory: Path) -> Path | None:
    for candidate in (directory, *directory.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _is_corpus_root(directory: Path, read_file: _FileReader) -> bool:
    """Whether a defect corpus's manifest marks the directory as the root of a corpus.

    A corpus is reviewed as a project of its own, under the conventions it carries and no
    others. The manifest must load as one, since many projects keep a `manifest.json`. It is
    read as the conventions are: at their revision, so a branch cannot add one to end the walk
    before its base's conventions, and on disk only as a regular file, so a FIFO or a link to
    `/dev/zero` named `manifest.json` cannot hang the walk or exhaust memory.
    """
    from devops_cli.ai.review.defects import CORPUS_MANIFEST, DefectCorpus

    if (manifest := read_file(directory / CORPUS_MANIFEST)) is None:
        return False
    try:
        DefectCorpus.model_validate_json(manifest)
    except ValueError:
        return False
    return True


def _disk_reader(root: Path) -> _FileReader:
    """Read regular files on disk that lie within `root`, the resolved tree under review.

    A file reached through a link, at the file or at any directory below `root`, is absent,
    as the chunker refuses links for reviewed files: the tree must not bring a file from
    outside it into the prompts. Refusing links inside the tree too keeps a path review and a
    branch review of one tree reading the same files, since git stores a link as a link.
    """

    def read_on_disk(path: Path) -> str | None:
        try:
            resolved = path.resolve()
            if resolved != path.absolute() or not resolved.is_relative_to(root):
                return None
            if not resolved.is_file():
                return None
            return path.read_text(encoding="utf-8")
        except OSError, RuntimeError, UnicodeDecodeError:
            return None

    return read_on_disk


def _file_reader(directory: Path, repo_root: Path | None, revision: str | None) -> _FileReader:
    """Read files on disk, or as they were at `revision` of the repository at `repo_root`.

    On disk, files are read within the repository, or outside one within `directory`, the only
    directory read. Outside a repository nothing exists at a revision, so nothing is read.
    """
    if revision is None:
        return _disk_reader(repo_root or directory)
    from devops_cli.git.operations import read_file_at_revision

    def read_at_revision(path: Path) -> str | None:
        if repo_root is None:
            return None
        return read_file_at_revision(repo_root, revision, path.relative_to(repo_root).as_posix())

    return read_at_revision


def _nearest(
    start: Path, read: Callable[[Path, _FileReader], str], revision: str | None = None
) -> str:
    """The first non-empty `read` result from the start directory up to its repo root.

    The nearest file wins, as for AGENTS.md generally: a subproject's conventions override its
    repository's. Outside a repository only the start directory is read, and the walk ends at
    a defect corpus's root. With `revision`, each file is read as it was at that git revision.
    Only a regular file is read: a link is absent, on disk and at a revision alike.
    """
    start_resolved = start.resolve()
    directory = start_resolved if start_resolved.is_dir() else start_resolved.parent
    repo_root = _repo_root(directory)
    read_file = _file_reader(directory, repo_root, revision)
    for candidate in (directory, *directory.parents):
        if content := read(candidate, read_file):
            return content
        if repo_root is None or candidate == repo_root or _is_corpus_root(candidate, read_file):
            break
    return ""


def nearest_conventions(start: Path, revision: str | None = None) -> str:
    """The nearest general conventions file (AGENTS.md and its peers) for a review target.

    With `revision`, the files are read as they were at that git revision, not from disk.
    """
    return _nearest(start, _read_candidate_conventions_file, revision)


def _read_review_conventions_file(directory: Path, read_file: _FileReader) -> str:
    return read_file(directory / CONST_REVIEW_CONVENTIONS_FILE) or ""


def nearest_review_conventions(start: Path, revision: str | None = None) -> str:
    """The nearest `.devops/review.md`: rules a project keeps for reviews of its own code.

    With `revision`, the files are read as they were at that git revision, not from disk.
    """
    return _nearest(start, _read_review_conventions_file, revision).strip()


def _read_candidate_conventions_file(directory: Path, read_file: _FileReader) -> str:
    """Read first non-blank project conventions file from directory."""
    for name in _TARGET_CONVENTIONS_CANDIDATES:
        if (content := read_file(directory / name)) and content.strip():
            return content
    return ""


def _get_reviews_base_dir() -> Path:
    """Resolve and ensure the review data storage directory."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_data_dir:
        d = Path(env_data_dir) / "reviews"
    else:
        settings = load_settings()
        d = settings.data.reviews_dir
    d = resolve_data_path(d)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Executable Verification Criteria Sandbox ─────────────────────────────────


def _check_shell_tokens(args: list[str]) -> str | None:
    is_py = bool(args and args[0] in CONST_PYTHON_CRITERIA_BINARIES)
    for arg in args:
        if arg in CONST_DISALLOWED_SHELL_TOKENS:
            return f"Command contains forbidden shell operator: {arg!r}"
        if any(c in arg for c in ("`", "$(")):
            return "Command contains forbidden command substitution or shell expansion"
        if not is_py and any(c in arg for c in (">", "<", "|", ";", "&")):
            return f"Command argument contains forbidden shell character: {arg!r}"
    return None


def _check_git_subcommand(args: list[str]) -> str | None:
    subcmd: str | None = None
    for arg in args[1:]:
        if not arg.startswith("-"):
            subcmd = arg
            break
    if not subcmd or subcmd not in CONST_ALLOWED_GIT_SUBCOMMANDS:
        return f"Git subcommand {subcmd!r} is not in allowed read-only subcommands"
    return None


def _is_safe_ast_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return not any(
            alias.name.split(".")[0] in CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES
            for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        mod = node.module.split(".")[0] if node.module else ""
        return mod not in CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in {"exec", "eval", "open"}:
            return False
        if isinstance(func, ast.Attribute) and func.attr in {
            "remove",
            "unlink",
            "rmdir",
            "mkdir",
            "rename",
            "system",
            "popen",
            "spawn",
        }:
            return False
    return True


def _is_pytest_module(name: str) -> bool:
    """Whether a module is pytest, its implementation package `_pytest`, or one of theirs."""
    return name.partition(".")[0] in CONST_PYTEST_MODULES


def _imports_pytest_by_name(node: ast.AST) -> bool:
    """Whether a call imports a pytest module by its name as a string, as in
    `__import__('pytest')` or `importlib.import_module('_pytest.config')`."""
    if not isinstance(node, ast.Call) or not node.args:
        return False
    func, name = node.func, node.args[0]
    called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    return (
        called in CONST_IMPORT_BY_NAME_CALLS
        and isinstance(name, ast.Constant)
        and isinstance(name.value, str)
        and _is_pytest_module(name.value)
    )


def _reaches_pytest(node: ast.expr, pytest_names: set[str]) -> bool:
    """Whether an attribute chain starts at a pytest module: a name the script binds to one, or
    a call that imports one by its name."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return (isinstance(node, ast.Name) and node.id in pytest_names) or _imports_pytest_by_name(node)


def _names_pytest_runner(node: ast.AST, pytest_names: set[str]) -> bool:
    """Whether a node imports pytest's test runner, or refers to it through a pytest module."""
    if isinstance(node, ast.ImportFrom):
        return (
            node.module is not None
            and _is_pytest_module(node.module)
            and any(alias.name in CONST_PYTEST_RUNNER_FUNCTIONS | {"*"} for alias in node.names)
        )
    return (
        isinstance(node, ast.Attribute)
        and node.attr in CONST_PYTEST_RUNNER_FUNCTIONS
        and _reaches_pytest(node.value, pytest_names)
    )


def _pytest_names(nodes: list[ast.AST]) -> set[str]:
    """The names a script binds to pytest modules: `pytest` and `_pytest` themselves, and what it
    imports them or their submodules as (`import pytest as p`, `from _pytest import config`)."""
    names = set(CONST_PYTEST_MODULES)
    for node in nodes:
        if isinstance(node, ast.Import):
            names.update(
                alias.asname
                for alias in node.names
                if alias.asname and _is_pytest_module(alias.name)
            )
        elif isinstance(node, ast.ImportFrom) and node.module and _is_pytest_module(node.module):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _starts_pytest(tree: ast.AST) -> bool:
    """Whether a script reaches pytest's test runner (`pytest.main`, `from pytest import main`,
    `from _pytest.config import main`, `__import__('pytest').main`), under any name it imports a
    pytest module as. Importing pytest for `pytest.raises` is fine.

    Only names the script spells out are read: one it builds at run time
    (`getattr(pytest, 'ma' + 'in')`) or a module run by name (`runpy`) is not seen."""
    nodes = list(ast.walk(tree))
    pytest_names = _pytest_names(nodes)
    return any(_names_pytest_runner(node, pytest_names) for node in nodes)


def _check_python_script(script: str) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(script)
    except SyntaxError as exc:
        return f"SyntaxError in python script: {exc}"
    for node in ast.walk(tree):
        if not _is_safe_ast_node(node):
            return "Python script contains forbidden module or mutating call"
    if _starts_pytest(tree):
        return "Python script runs pytest; a criterion asserts on the cited code itself"
    return None


def _check_python_command(args: list[str]) -> str | None:
    # Read as the evidence rule reads it: a `-c` or `-m` later in the command, or inside an
    # option cluster such as `-Bc`, would leave unchecked what Python runs.
    invocation = python_invocation(args)
    if invocation is None:
        return (
            "A python criterion is `python -c <script>` or `python -m <module>`, "
            "with -c or -m as its first argument"
        )
    option, argument = invocation
    if option == "-c":
        return _check_python_script(argument)
    if argument.partition(".")[0] in CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES:
        return "Forbidden module after -m"
    if _is_pytest_module(argument):
        return "Python module pytest runs tests; a criterion asserts on the cited code itself"
    return None


def _check_find_actions(args: list[str]) -> str | None:
    action = next((arg for arg in args[1:] if arg in CONST_FORBIDDEN_FIND_ACTIONS), None)
    if action is None:
        return None
    return f"find action {action!r} runs a command or writes a file; a criterion only searches"


# The checks an allowlisted binary's arguments must pass, by the binary's name.
_ARGUMENT_CHECKS: dict[str, Callable[[list[str]], str | None]] = {
    "find": _check_find_actions,
    "git": _check_git_subcommand,
    **dict.fromkeys(CONST_PYTHON_CRITERIA_BINARIES, _check_python_command),
}


def validate_criteria_command(command: str) -> tuple[bool, str | None, list[str] | None]:
    """Validate whether a command belongs to the closed read-only allowlist."""
    cmd_str = command.strip()
    if not cmd_str:
        return False, "Command string is empty", None

    try:
        args = shlex.split(cmd_str)
    except ValueError as exc:
        return False, f"Malformed command syntax: {exc}", None

    if not args:
        return False, "Command has no tokens", None

    if token_err := _check_shell_tokens(args):
        return False, token_err, None

    binary = Path(args[0]).name
    if binary not in CONST_ALLOWED_CRITERIA_BINARIES:
        return False, f"Binary {binary!r} is not in allowed criteria binaries", None

    if (check := _ARGUMENT_CHECKS.get(binary)) and (argument_err := check(args)):
        return False, argument_err, None

    return True, None, args


def _terminate_process_group(pid: int) -> None:
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        pass


def _criterion_argv(args: list[str]) -> tuple[list[str], float]:
    """The argv a validated criterion runs as in the sandbox, and its default time limit.

    A python or python3 criterion runs with SyntaxWarning ignored and under the Python criteria
    limit, since it imports the reviewed code; any other command gets the general one. A
    validated python criterion has no options of its own before its `-c` or `-m`.
    """
    exec_args = list(args)
    if Path(exec_args[0]).name not in CONST_PYTHON_CRITERIA_BINARIES:
        return exec_args, DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS
    exec_args[1:1] = ["-W", "ignore::SyntaxWarning"]
    return exec_args, DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS


def execute_criterion_command(
    command: str,
    cwd: Path,
    timeout: float | None = None,
    max_output_bytes: int = DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
    sandbox: Any = None,
) -> Any:
    """Execute an allowlisted criterion in the bubblewrap host sandbox.

    Without a `timeout`, the criterion gets its binary's default limit (see `_criterion_argv`).
    """
    from devops_cli.ai.review_schema import CriterionExecutionResult
    from devops_cli.sandbox.host import HostSandbox

    is_valid, reason, args = validate_criteria_command(command)
    if not is_valid or not args:
        return CriterionExecutionResult(
            command=command,
            description=command,
            executable=False,
            exit_code=None,
            passed=False,
            error=reason,
        )

    sb: HostSandbox = sandbox if sandbox is not None else HostSandbox()
    if not sb.is_available():
        return CriterionExecutionResult(
            command=command,
            description=command,
            executable=True,
            exit_code=-1,
            passed=False,
            error=f"bubblewrap binary {sb.bwrap_binary} is not available on host system",
        )

    exec_args, default_timeout = _criterion_argv(args)

    src_dir = cwd / "src"
    py_path = f"{src_dir}:{cwd}" if src_dir.is_dir() else str(cwd)
    res = sb.execute(
        args=exec_args,
        cwd=cwd,
        timeout=default_timeout if timeout is None else timeout,
        max_output_bytes=max_output_bytes,
        env={"PYTHONPATH": py_path},
    )
    return CriterionExecutionResult(
        command=command,
        description=command,
        executable=True,
        exit_code=res.exit_code,
        stdout=res.stdout,
        stderr=res.stderr,
        duration_seconds=res.duration_seconds,
        passed=res.passed,
        error=res.error,
        timed_out=res.timed_out,
    )


class _CriteriaVerdict(NamedTuple):
    """A verdict the criteria settle, and what `apply_verdict` records with it."""

    status: str
    by: str | None = None
    confidence: float | None = None
    reason: str | None = None
    note: str | None = None


def _evaluate_criteria_verdict(
    matched_ver: list[str], matched_inv: list[str], refuting: list[str]
) -> _CriteriaVerdict | None:
    """The verdict the criteria settle, or None when they leave the finding for the verifier.

    `matched_ver` and `matched_inv` hold every passing verification and invalidation command,
    and `refuting` those invalidation commands that count as evidence
    (`criteria_evidence.counts_as_evidence`). Criteria that pass on both sides, counting or
    not, cannot tell the defect from its absence. A refuting command settles INVALIDATED.
    Nothing settles VERIFIED: the evidence rule shows that a command checks the cited code, not
    which side of the claim its pass supports, and a verification criterion that asserts the
    code's correct behaviour passes because the claim is false (#1043). A passing verification
    command that counts is recorded as matched, and the verifier judges the finding.
    """
    if matched_ver and matched_inv:
        return _CriteriaVerdict("UNVERIFIED", note=CONST_CRITERIA_NON_DISCRIMINATING)
    if refuting:
        return _CriteriaVerdict(
            "INVALIDATED", "criteria", 0.0, f"Invalidation criterion verified: {refuting[0]}"
        )
    return None


def _evidence(passed: list[str], location: str, repo_root: Path) -> list[str]:
    """The passing commands, once each, that count as evidence about the code at `location`."""
    return [c for c in dict.fromkeys(passed) if counts_as_evidence(c, location, repo_root)]


def _reconcile_finding_from_criteria(
    finding: Any,
    exec_results: list[Any],
    matched_ver: list[str],
    matched_inv: list[str],
    repo_root: Path,
) -> Any:
    """Record the criteria results on the finding, with the verdict their evidence settles.

    `matched_ver` and `matched_inv` are the commands that passed. Each is recorded in
    `criteria_execution_results`; only those that count as evidence are recorded as matched.
    """
    proving = _evidence(matched_ver, finding.location, repo_root)
    refuting = _evidence(matched_inv, finding.location, repo_root)
    records: dict[str, Any] = {
        "criteria_execution_results": list(
            dict.fromkeys(finding.criteria_execution_results + exec_results)
        ),
        "verified_criteria_matched": list(
            dict.fromkeys(finding.verified_criteria_matched + proving)
        ),
        "invalidated_criteria_matched": list(
            dict.fromkeys(finding.invalidated_criteria_matched + refuting)
        ),
    }
    verdict = _evaluate_criteria_verdict(matched_ver, matched_inv, refuting)
    if verdict is None:
        return finding.model_copy(update=records)
    return apply_verdict(
        finding,
        verdict.status,
        by=verdict.by,
        reason=verdict.reason,
        confidence_score=verdict.confidence,
        verification_note=verdict.note,
        **records,
    )


def _run_criteria_group(criteria: list[Any], repo_root: Path) -> tuple[list[Any], list[str]]:
    results: list[Any] = []
    matched: list[str] = []
    for crit in criteria:
        cmd = getattr(crit, "command", None)
        if getattr(crit, "executable", False) and cmd:
            res = execute_criterion_command(cmd, cwd=repo_root)
            results.append(res)
            if res.passed:
                matched.append(cmd)
    return results, matched


def execute_finding_criteria(finding: Any, repo_root: Path) -> Any:
    """Execute all allowable criteria for a finding and reconcile confidence and status."""
    if not repo_root or not repo_root.is_dir():
        return finding

    ver_crit = getattr(finding, "verification_criteria", [])
    inv_crit = getattr(finding, "invalidation_criteria", [])

    ver_results, matched_ver = _run_criteria_group(ver_crit, repo_root)
    inv_results, matched_inv = _run_criteria_group(inv_crit, repo_root)

    return _reconcile_finding_from_criteria(
        finding, ver_results + inv_results, matched_ver, matched_inv, repo_root
    )
