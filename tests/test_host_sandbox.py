"""Unit and integration tests for bubblewrap HostSandbox confinement."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review.review_environment import execute_criterion_command
from devops_cli.config.constants import CONST_ALLOWED_CRITERIA_BINARIES
from devops_cli.sandbox.host import HostSandbox
from devops_cli.sandbox.models import SandboxPolicy

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"


def _sandbox_options(args: list[str]) -> list[str]:
    """The bubblewrap options of a compiled command line, before the `--` that ends them."""
    return args[: args.index("--")]


def _binds(args: list[str]) -> list[list[str]]:
    """Every bind option of a compiled command line, as `[flag, source, destination]`."""
    options = _sandbox_options(args)
    return [options[i : i + 3] for i, flag in enumerate(options) if flag in {"--ro-bind", "--bind"}]


def _bound_paths(args: list[str]) -> list[Path]:
    """Every path a compiled command line binds into the sandbox."""
    return [Path(destination) for _, _, destination in _binds(args)]


def _repo_binds(args: list[str]) -> list[list[str]]:
    """The bind options of a compiled command line beyond the system toolchain mounts."""
    system = _binds([*HostSandbox()._resolve_system_mounts(), "--"])
    return [bind for bind in _binds(args) if bind not in system]


def _sandbox_path(args: list[str]) -> str:
    """The PATH a compiled command line gives the sandboxed command."""
    options = _sandbox_options(args)
    return next(
        options[i + 2]
        for i, flag in enumerate(options)
        if flag == "--setenv" and options[i + 1] == "PATH"
    )


def _python_installation(prefix: Path) -> Path:
    """A minimal CPython installation under `prefix`: its interpreter and stdlib landmark."""
    (prefix / "bin").mkdir(parents=True)
    (prefix / "lib" / "python3.14").mkdir(parents=True)
    (prefix / "lib" / "python3.14" / "os.py").write_text("", encoding="utf-8")
    interpreter = prefix / "bin" / "python3.14"
    interpreter.write_text("", encoding="utf-8")
    return interpreter


def _repo_with_virtualenv(repo: Path, interpreter: Path) -> Path:
    """A repository whose `.venv/bin/python` links to `interpreter`, as `uv venv` makes it."""
    (repo / ".git").mkdir(parents=True)
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(interpreter)
    return repo


@pytest.mark.bwrap
def test_host_sandbox_reads_repo(tmp_path: Path) -> None:
    """Live test: sandboxed child can read files from the mounted repository."""
    data_file = tmp_path / "hello.txt"
    data_file.write_text("sandbox-content", encoding="utf-8")

    result = execute_criterion_command("cat hello.txt", cwd=tmp_path)
    assert (
        result.executable,
        result.passed,
        result.exit_code,
        "sandbox-content" in result.stdout,
    ) == (True, True, 0, True)


@pytest.mark.bwrap
def test_host_sandbox_cannot_list_home(tmp_path: Path) -> None:
    """Live test: sandboxed child cannot access /home."""
    sandbox = HostSandbox()
    res = sandbox.execute(["ls", "/home"], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code != 0,
        "No such file" in res.stderr or "cannot access" in res.stderr,
    ) == (False, True, True)


@pytest.mark.bwrap
def test_host_sandbox_cannot_write_repo(tmp_path: Path) -> None:
    """Live test: sandboxed child cannot mutate files in the mounted repository."""
    sandbox = HostSandbox()
    target = tmp_path / "forbidden.txt"
    res = sandbox.execute(["touch", str(target)], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code != 0,
        "Read-only file system" in res.stderr,
        target.exists(),
    ) == (False, True, True, False)


@pytest.mark.bwrap
def test_host_sandbox_cannot_connect_network(tmp_path: Path) -> None:
    """Live test: sandboxed child cannot establish non-loopback network connections."""
    sandbox = HostSandbox()
    script = (
        "import socket\ns = socket.socket()\ns.settimeout(0.5)\ns.connect(('198.51.100.1', 80))\n"
    )
    res = sandbox.execute(["python3", "-c", script], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code != 0,
        "Network is unreachable" in res.stderr or "timed out" in res.stderr,
    ) == (False, True, True)


@pytest.mark.bwrap
def test_host_sandbox_clears_sensitive_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Live test: sandboxed child inherits no host credentials and uses isolated HOME."""
    monkeypatch.setenv("GITHUB_TOKEN", "super_secret_host_token")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/host_auth.sock")
    sandbox = HostSandbox()
    script = (
        "import os\n"
        "leaks = [k for k in ['GITHUB_TOKEN', 'SSH_AUTH_SOCK'] if os.environ.get(k)]\n"
        "print('LEAKS:' + ','.join(leaks))\n"
        "print('HOME:' + os.environ.get('HOME', ''))\n"
    )
    res = sandbox.execute(["python3", "-c", script], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code,
        "LEAKS:" in res.stdout,
        "super_secret_host_token" in res.stdout,
        "/tmp/host_auth.sock" in res.stdout,
        "HOME:/tmp" in res.stdout,
    ) == (True, 0, True, False, False, True)


def test_host_sandbox_fails_closed_when_bwrap_missing(tmp_path: Path) -> None:
    """Constraint test: execution fails closed when bubblewrap is unavailable."""
    missing_sandbox = HostSandbox(bwrap_binary="/nonexistent/bwrap")
    assert missing_sandbox.is_available() is False

    result = execute_criterion_command(
        "python -c 'print(1)'",
        cwd=tmp_path,
        sandbox=missing_sandbox,
    )
    assert (
        result.executable,
        result.passed,
        result.exit_code,
        "not available" in str(result.error),
    ) == (True, False, -1, True)


def test_host_sandbox_build_args_structure(tmp_path: Path) -> None:
    """Verify bubblewrap command argument compilation structure and isolation flags."""
    sandbox = HostSandbox()
    args = sandbox.build_bwrap_args(["python3", "-V"], cwd=tmp_path)
    assert (
        "--unshare-all" in args,
        "--new-session" in args,
        "--die-with-parent" in args,
        "--clearenv" in args,
        "--dev" in args,
        "--proc" in args,
        "--tmpfs" in args,
        "--chdir" in args,
        str(tmp_path.resolve()) in args,
    ) == (True, True, True, True, True, True, True, True, True)


def test_host_sandbox_handles_namespace_refusal(tmp_path: Path) -> None:
    """Verify that bubblewrap namespace refusal is caught and reported as sandbox error."""
    stub_bwrap = tmp_path / "bwrap"
    stub_bwrap.write_text("#!/bin/sh\n", encoding="utf-8")
    stub_bwrap.chmod(0o755)
    sandbox = HostSandbox(bwrap_binary=stub_bwrap)
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (
        "",
        "bwrap: Setting up uid map: Permission denied\n",
    )
    mock_proc.returncode = 1
    mock_proc.pid = 999999

    with patch("subprocess.Popen", return_value=mock_proc):
        res = sandbox.execute(["python3", "-c", "pass"], cwd=tmp_path)

    assert (
        res.passed,
        res.exit_code,
        "Host sandbox error: bwrap: Setting up uid map: Permission denied" in str(res.error),
    ) == (False, 1, True)


def test_host_sandbox_consumes_custom_policy(tmp_path: Path) -> None:
    """Verify that HostSandbox mounts and configures according to its SandboxPolicy."""
    custom_policy = SandboxPolicy(
        read_only=False,
        tmpfs={"/tmp": "size=32m", "/var/tmp": "size=16m"},
        system_dirs=("/usr", "/bin"),
        forbidden_env_keys=frozenset({"CUSTOM_SECRET"}),
    )
    sandbox = HostSandbox(policy=custom_policy)
    args = sandbox.build_bwrap_args(
        command_args=["python3", "-c", "pass"],
        cwd=tmp_path,
        env={"CUSTOM_SECRET": "leak", "SAFE_VAR": "value"},
    )
    assert (
        sandbox.policy == custom_policy,
        "--bind" in args,
        "--tmpfs" in args,
        "--size" in args,
        "33554432" in args,
        "/var/tmp" in args,
        "CUSTOM_SECRET" not in str(args),
        "SAFE_VAR" in str(args),
    ) == (True, True, True, True, True, True, True, True)


@pytest.mark.bwrap
def test_host_sandbox_kills_process_exceeding_output_cap(tmp_path: Path) -> None:
    """Verify that process generating unbounded output is terminated and output is capped (#663)."""
    sandbox = HostSandbox()
    res = sandbox.execute(
        [
            "python3",
            "-c",
            "import sys; sys.stdout.write('A' * 50000); sys.stdout.flush()",
        ],
        cwd=tmp_path,
        max_output_bytes=1024,
    )
    assert (
        res.passed,
        len(res.stdout) <= 1024,
        "Output exceeded maximum limit" in str(res.error),
    ) == (False, True, True)


@pytest.mark.bwrap
def test_host_sandbox_nested_clone_cannot_read_parent_workspace(tmp_path: Path) -> None:
    """Verify nearest repo root is mounted so nested clone cannot traverse parent (#663)."""
    parent = tmp_path / "workspace"
    parent.mkdir()
    (parent / ".git").mkdir()
    (parent / "secret.env").write_text("HOST_SECRET=1", encoding="utf-8")

    clone = parent / "repos" / "nested"
    clone.mkdir(parents=True)
    (clone / ".git").mkdir()
    (clone / "hello.txt").write_text("hello", encoding="utf-8")

    sandbox = HostSandbox()
    res = sandbox.execute(["cat", str(parent / "secret.env")], cwd=clone)
    assert (
        res.passed,
        res.exit_code != 0,
        "No such file" in res.stderr or "cannot access" in res.stderr,
    ) == (False, True, True)


@pytest.mark.bwrap
def test_host_sandbox_linked_worktree_runs_git(tmp_path: Path) -> None:
    """Verify linked worktree binds common git directory so git commands succeed (#663)."""
    import subprocess

    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    worktree = tmp_path / "linked_worktree"

    subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main_repo, check=True)
    (main_repo / "README.md").write_text("# Main", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=main_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=main_repo, check=True)
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", "feat"],
        cwd=main_repo,
        check=True,
    )

    sandbox = HostSandbox()
    res = sandbox.execute(["git", "log", "-n", "1", "--oneline"], cwd=worktree)
    assert (
        res.passed,
        res.exit_code,
        "initial commit" in res.stdout,
    ) == (True, 0, True)


def test_terminate_process_group_guards_devcontainer() -> None:
    """Verify that _terminate_process_group safely rejects PID 1, PID 0, self, and mocks."""
    from devops_cli.sandbox.host import _terminate_process_group

    with patch("os.killpg") as mock_killpg:
        # Should guard against non-int, PID <= 1, self, and PGID <= 1
        _terminate_process_group(MagicMock())
        _terminate_process_group(0)
        _terminate_process_group(1)
        _terminate_process_group(-5)
        _terminate_process_group(os.getpid())
        assert mock_killpg.called is False


def test_every_allowlisted_criteria_binary_resolves_inside_the_sandbox_mounts() -> None:
    """Every allowlisted criteria binary is on the sandbox PATH at a path the sandbox binds (#847)."""
    args = HostSandbox().build_bwrap_args(["true"], cwd=_PROJECT_ROOT)
    bound = _bound_paths(args)
    sandbox_path = _sandbox_path(args)

    def resolves_inside_mounts(binary: str) -> bool:
        found = shutil.which(binary, path=sandbox_path)
        return found is not None and any(Path(found).resolve().is_relative_to(b) for b in bound)

    unresolved = sorted(b for b in CONST_ALLOWED_CRITERIA_BINARIES if not resolves_inside_mounts(b))
    assert unresolved == []


def _project_with_its_own_environment(root: Path) -> Path:
    """A project whose `.venv` links to this interpreter and holds a `ruff` and a dependency of its
    own, as `uv sync` leaves a reviewed project. The test builds it rather than reading this
    checkout's `.venv`, whose layout depends on how the host installed Python (GitHub CI's differs
    from the devcontainer's)."""
    interpreter = Path(sys.executable).resolve()
    venv = root / ".venv"
    site_packages = (
        venv / "lib" / f"python{sys.version_info[0]}.{sys.version_info[1]}" / "site-packages"
    )
    site_packages.mkdir(parents=True)
    (site_packages / "reviewed_dependency.py").write_text("ONE = 1\n", encoding="utf-8")
    (venv / "bin" / "python").parent.mkdir(parents=True, exist_ok=True)
    (venv / "bin" / "python").symlink_to(interpreter)
    ruff = venv / "bin" / "ruff"
    ruff.write_text("#!/bin/sh\necho 'ruff 0.0.0'\n", encoding="utf-8")
    ruff.chmod(0o755)
    (venv / "pyvenv.cfg").write_text(f"home = {interpreter.parent}\n", encoding="utf-8")
    (root / ".git").mkdir()
    return root


@pytest.mark.bwrap
def test_host_sandbox_runs_the_repo_environment_tools(tmp_path: Path) -> None:
    """Live test: ruff and python come from the reviewed repository's own virtualenv (#847)."""
    project = _project_with_its_own_environment(tmp_path)
    sandbox = HostSandbox()
    ruff = sandbox.execute(["ruff", "--version"], cwd=project)
    python = sandbox.execute(["python", "-c", "pass"], cwd=project)
    prefix = sandbox.execute(["python", "-c", "import sys; print(sys.prefix)"], cwd=project)
    assert (
        ruff.passed,
        ruff.stdout.startswith("ruff "),
        python.passed,
        python.error,
        prefix.stdout.strip(),
    ) == (True, True, True, None, str(project / ".venv"))


@pytest.mark.bwrap
def test_python_criterion_imports_the_repo_test_dependencies(tmp_path: Path) -> None:
    """Live test: a criterion importing pytest runs under the repository's interpreter (#847).

    In review session 20261002-214641 the invalidation criterion for
    `tests/test_security_bandit.py:142-154`, which imports that test module and so pytest, failed
    with `No module named 'pytest'` under the system Python.
    """
    project = _project_with_its_own_environment(tmp_path)
    result = execute_criterion_command("python -c 'import reviewed_dependency'", cwd=project)
    assert (
        result.executable,
        result.exit_code,
        result.passed,
        result.timed_out,
        result.stderr,
    ) == (True, 0, True, False, "")


def test_sandbox_path_without_a_virtualenv_is_the_system_path(tmp_path: Path) -> None:
    """A repository without `.venv/bin` keeps the system PATH and binds nothing more (#847)."""
    (tmp_path / ".git").mkdir()
    args = HostSandbox().build_bwrap_args(["true"], cwd=tmp_path)
    assert (_sandbox_path(args), _repo_binds(args)) == (
        _SYSTEM_PATH,
        [["--ro-bind", str(tmp_path), str(tmp_path)]],
    )


def test_sandbox_path_puts_the_repo_virtualenv_first(tmp_path: Path) -> None:
    """A repository's `.venv/bin` leads the PATH; an interpreter under `/usr` needs no bind (#847)."""
    repo = _repo_with_virtualenv(tmp_path / "repo", Path("/usr/bin/python3"))
    args = HostSandbox().build_bwrap_args(["true"], cwd=repo)
    assert (_sandbox_path(args), _repo_binds(args)) == (
        f"{repo / '.venv' / 'bin'}:{_SYSTEM_PATH}",
        [["--ro-bind", str(repo), str(repo)]],
    )


def test_sandbox_binds_the_virtualenv_interpreter_installation_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interpreter installed outside the mounts, as uv installs one, is bound read-only (#847)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    installation = tmp_path / "home" / ".local" / "share" / "uv" / "python" / "cpython-3.14"
    repo = _repo_with_virtualenv(tmp_path / "repo", _python_installation(installation))
    sandbox = HostSandbox(policy=SandboxPolicy(read_only=False))
    args = sandbox.build_bwrap_args(["true"], cwd=repo)
    assert (_sandbox_path(args), _repo_binds(args)) == (
        f"{repo / '.venv' / 'bin'}:{_SYSTEM_PATH}",
        [
            ["--bind", str(repo), str(repo)],
            ["--ro-bind", str(installation), str(installation)],
        ],
    )


@pytest.mark.parametrize(
    "case",
    [
        "no stdlib landmark",
        "home directory",
        "credential directory",
        "above the repository",
        "missing interpreter",
    ],
)
def test_sandbox_never_binds_an_interpreter_prefix_the_repository_could_aim_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """The repository sets where `.venv/bin/python` links, so only a Python installation is bound.

    A virtualenv whose interpreter cannot be bound would only fail, so the system PATH stands (#847).
    """
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    prefixes = {
        "no stdlib landmark": tmp_path / "opt" / "tool",
        "home directory": home,
        "credential directory": home / ".ssh" / "python",
        "above the repository": tmp_path / "workspace",
        "missing interpreter": tmp_path / "opt" / "python",
    }
    prefix = prefixes[case]
    interpreter = _python_installation(prefix)
    if case == "no stdlib landmark":
        (prefix / "lib" / "python3.14" / "os.py").unlink()
    if case == "missing interpreter":
        interpreter = prefix / "bin" / "python3.13"
    repo = _repo_with_virtualenv(tmp_path / "workspace" / "repo", interpreter)
    args = HostSandbox().build_bwrap_args(["true"], cwd=repo)
    assert (_sandbox_path(args), _repo_binds(args)) == (
        _SYSTEM_PATH,
        [["--ro-bind", str(repo), str(repo)]],
    )


def test_sandbox_ignores_a_virtualenv_linked_from_outside_the_repository(
    tmp_path: Path,
) -> None:
    """A `.venv` that links outside the bound repository is not put on the PATH (#847)."""
    outside = tmp_path / "outside-venv"
    (outside / "bin").mkdir(parents=True)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".venv").symlink_to(outside)
    args = HostSandbox().build_bwrap_args(["true"], cwd=repo)
    assert (_sandbox_path(args), _repo_binds(args)) == (
        _SYSTEM_PATH,
        [["--ro-bind", str(repo), str(repo)]],
    )


def test_host_sandbox_reports_a_timeout_apart_from_a_failure(tmp_path: Path) -> None:
    """A command stopped at its time limit is marked timed out; one that exits non-zero is not (#847)."""
    stub_bwrap = tmp_path / "bwrap"
    stub_bwrap.write_text("#!/bin/sh\n", encoding="utf-8")
    stub_bwrap.chmod(0o755)
    sandbox = HostSandbox(bwrap_binary=stub_bwrap)
    hung, failing = MagicMock(), MagicMock()
    hung.communicate.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=0.1)
    hung.pid = 999999
    failing.communicate.return_value = (b"", b"AssertionError\n")
    failing.returncode = 1
    failing.pid = 999998
    with patch("subprocess.Popen", side_effect=[hung, failing]):
        timed_out = sandbox.execute(["python", "-c", "pass"], cwd=tmp_path, timeout=0.1)
        failed = sandbox.execute(["python", "-c", "assert False"], cwd=tmp_path)
    assert (
        (timed_out.passed, timed_out.exit_code, timed_out.timed_out),
        (failed.passed, failed.exit_code, failed.timed_out),
    ) == ((False, -1, True), (False, 1, False))


def test_bwrap_marked_tests_skip_only_when_bubblewrap_unavailable(
    request: pytest.FixtureRequest,
) -> None:
    """A bwrap-marked test carries the bubblewrap skip if and only if bwrap is unavailable (#1337)."""
    bwrap_items = [item for item in request.session.items if "bwrap" in item.keywords]
    if not bwrap_items:
        pytest.skip("no bwrap-marked items collected in this session")

    is_available = HostSandbox().is_available()
    skipped_bwrap_items = [
        item.nodeid
        for item in bwrap_items
        if any(
            "bubblewrap is not installed" in str(m.kwargs.get("reason", ""))
            for m in item.iter_markers("skip")
        )
    ]

    if is_available:
        assert (len(skipped_bwrap_items), skipped_bwrap_items) == (0, [])
    else:
        all_nodeids = [item.nodeid for item in bwrap_items]
        assert skipped_bwrap_items == all_nodeids
