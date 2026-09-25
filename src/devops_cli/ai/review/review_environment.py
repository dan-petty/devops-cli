"""Review execution environment and conventions discovery helpers."""

from __future__ import annotations

import ast
import os
import shlex
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_ALLOWED_CRITERIA_BINARIES,
    CONST_ALLOWED_GIT_SUBCOMMANDS,
    CONST_DISALLOWED_SHELL_TOKENS,
    CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES,
    CONST_REVIEW_CONVENTIONS_FILE,
)
from devops_cli.config.defaults import (
    DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS,
    DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
)

_TARGET_CONVENTIONS_CANDIDATES: tuple[str, ...] = (
    CONST_AGENTS_MD_FILENAME,
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".cursorrules",
    ".cursor/rules",
)


def _repo_root(directory: Path) -> Path | None:
    for candidate in (directory, *directory.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _nearest(start: Path, read: Callable[[Path], str]) -> str:
    """The first non-empty `read` result from the start directory up to its repo root.

    The nearest file wins, as for AGENTS.md generally: a subproject's conventions override its
    repository's. Outside a repository only the start directory is read.
    """
    start_resolved = start.resolve()
    directory = start_resolved if start_resolved.is_dir() else start_resolved.parent
    repo_root = _repo_root(directory)
    for candidate in (directory, *directory.parents):
        if content := read(candidate):
            return content
        if repo_root is None or candidate == repo_root:
            break
    return ""


def nearest_conventions(start: Path) -> str:
    """The nearest general conventions file (AGENTS.md and its peers) for a review target."""
    return _nearest(start, _read_candidate_conventions_file)


def _read_review_conventions_file(directory: Path) -> str:
    path = directory / CONST_REVIEW_CONVENTIONS_FILE
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        return ""


def nearest_review_conventions(start: Path) -> str:
    """The nearest `.devops/review.md`: rules a project keeps for reviews of its own code."""
    return _nearest(start, _read_review_conventions_file).strip()


def _read_candidate_conventions_file(directory: Path | None) -> str:
    """Read first matching project conventions file from directory."""
    if not directory or not directory.is_dir():
        return ""
    for name in _TARGET_CONVENTIONS_CANDIDATES:
        cand = directory / name
        if not cand.is_file():
            continue
        try:
            content = cand.read_text(encoding="utf-8")
            if content.strip():
                return content
        except OSError:
            continue
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
    is_py = bool(args and args[0] in {"python", "python3"})
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


def _check_python_script(script: str) -> str | None:
    try:
        tree = ast.parse(script)
    except SyntaxError as exc:
        return f"SyntaxError in python script: {exc}"
    for node in ast.walk(tree):
        if not _is_safe_ast_node(node):
            return "Python script contains forbidden module or mutating call"
    return None


def _check_python_command(args: list[str]) -> str | None:
    if len(args) < 2:
        return "Python invocation requires arguments (e.g. -c <script>)"
    if "-c" in args:
        idx = args.index("-c")
        if idx + 1 >= len(args):
            return "Missing script argument after -c"
        return _check_python_script(args[idx + 1])
    if "-m" in args:
        idx = args.index("-m")
        if idx + 1 >= len(args) or args[idx + 1] in CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES:
            return "Forbidden or missing module argument after -m"
        return None
    return "Python invocation must specify -c or -m"


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

    if binary == "git" and (git_err := _check_git_subcommand(args)):
        return False, git_err, None

    if binary in {"python", "python3"} and (py_err := _check_python_command(args)):
        return False, py_err, None

    return True, None, args


def _terminate_process_group(pid: int) -> None:
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        pass


def execute_criterion_command(
    command: str,
    cwd: Path,
    timeout: float = DEFAULT_CRITERIA_EXECUTION_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_CRITERIA_MAX_OUTPUT_BYTES,
) -> Any:
    """Execute an allowlisted criterion in the bounded subprocess sandbox."""
    from devops_cli.ai.review_schema import CriterionExecutionResult

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

    t_start = time.monotonic()
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        exit_code: int | None = proc.returncode
        err_msg = None
    except subprocess.TimeoutExpired:
        if proc is not None:
            _terminate_process_group(proc.pid)
            stdout, stderr = proc.communicate()
        else:
            stdout, stderr = "", ""
        exit_code = -1
        err_msg = f"Criterion execution timed out after {timeout}s"
    except Exception as exc:
        if proc is not None:
            _terminate_process_group(proc.pid)
        stdout, stderr = "", ""
        exit_code = -1
        err_msg = f"Subprocess error: {exc}"

    duration = time.monotonic() - t_start
    stdout_bounded = (stdout or "")[:max_output_bytes]
    stderr_bounded = (stderr or "")[:max_output_bytes]
    passed = exit_code == 0

    return CriterionExecutionResult(
        command=command,
        description=command,
        executable=True,
        exit_code=exit_code,
        stdout=stdout_bounded,
        stderr=stderr_bounded,
        duration_seconds=round(duration, 3),
        passed=passed,
        error=err_msg,
    )


def _reconcile_finding_from_criteria(
    finding: Any,
    exec_results: list[Any],
    matched_ver: list[str],
    matched_inv: list[str],
) -> Any:
    all_results = list(dict.fromkeys(finding.criteria_execution_results + exec_results))
    all_ver = list(dict.fromkeys(finding.verified_criteria_matched + matched_ver))
    all_inv = list(dict.fromkeys(finding.invalidated_criteria_matched + matched_inv))

    updates: dict[str, Any] = {
        "criteria_execution_results": all_results,
        "verified_criteria_matched": all_ver,
        "invalidated_criteria_matched": all_inv,
    }

    executable_ver = [
        c
        for c in finding.verification_criteria
        if getattr(c, "executable", False) and getattr(c, "command", None)
    ]
    if matched_inv:
        updates.update(
            {
                "status": "INVALIDATED",
                "verified": False,
                "reportable": False,
                "confidence_score": 0.0,
                "invalidation_reason": f"Invalidation criterion verified: {matched_inv[0]}",
            }
        )
    elif executable_ver:
        cmd_set = {c.command for c in executable_ver}
        ver_passed = sum(1 for r in exec_results if r.command in cmd_set and r.passed)
        score = round(ver_passed / len(executable_ver), 2)
        updates["confidence_score"] = score
        if ver_passed > 0:
            updates.update({"status": "VERIFIED", "verified": True})
        else:
            updates.update({"status": "UNVERIFIED", "verified": False})

    return finding.model_copy(update=updates)


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
        finding, ver_results + inv_results, matched_ver, matched_inv
    )
