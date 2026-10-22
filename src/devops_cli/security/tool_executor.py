"""The one seam that review tools run through, and the sandbox that runs them (#772).

A review tool is a program of another project, such as Semgrep or Trivy. It reads the reviewed
tree. Code that runs a tool builds a `ToolRequest` and calls `ToolExecutor.run`. The answer is a
`ToolResult`. It holds the output of the tool and a `ToolRun`, the record of what ran. A test
installs `ToolExecutorFake` in its place (`tests/support/fakes/tool_executor.py`).

`SandboxToolExecutor` is the real executor. It does not confine or limit a process itself. It
builds one command from three programs that already do this work:

- bubblewrap, through `HostSandbox`. It gives no network, a cleared environment, a read-only tree,
  read-only inputs and a private temporary HOME. When the sandbox process ends, the process tree
  in it ends (`--die-with-parent` and the process namespace of the sandbox). No code here ends a
  process.
- `prlimit` from util-linux. It sets the CPU limit and the address space limit of the tool. No code
  of devops-cli calls `setrlimit` or `preexec_fn`.
- `run_subprocess` of `core.process`. It starts the command and ends it at the wall-clock limit.

There is no limit on the number of processes. RLIMIT_NPROC counts every process of the user, so a
limit set inside the sandbox would starve the shells and servers of the host.
`_run_sandbox_process` in `sandbox/host.py` gives the reason in full.

The record uses the names of SARIF 2.1.0 where it has one:

- `tool` is `tool.driver.name`, and `version` is `tool.driver.version`.
- `binary_sha256` is the `sha-256` hash of the artifact of the tool.
- `argv_template` is the command line of an invocation.
- `commit` is the `revisionId` of `versionControlProvenance`.

SARIF holds config, ruleset and target files as `run.artifacts`, each with `hashes` and `roles`.
`ToolRun` keeps one digest for each group of files.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from devops_cli.ai.run_store import digest, file_digest
from devops_cli.config.constants import (
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
    CONST_TOOL_CPU_LIMIT_SECONDS,
    CONST_TOOL_GO_MEMORY_LIMIT,
    CONST_TOOL_MIN_ADDRESS_SPACE_BYTES,
    CONST_TOOL_PRLIMIT_BINARY,
    CONST_TOOL_TARGETS_PLACEHOLDER,
)
from devops_cli.config.defaults import (
    DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES,
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import is_safe_subpath, nearest_checkout
from devops_cli.exceptions.sandbox import SandboxError, SandboxValidationError
from devops_cli.review.canary import resolve_tool_binary, resolve_tool_version_and_sha
from devops_cli.sandbox.host import HostSandbox


class _Frozen(BaseModel):
    """A value that cannot change after it is made and refuses a field it does not know."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolLimits(_Frozen):
    """What one tool run may use. Each process of the tool gets CPU seconds and address space. The
    whole run gets wall-clock seconds."""

    cpu_seconds: int = Field(default=CONST_TOOL_CPU_LIMIT_SECONDS, gt=0)
    address_space_bytes: int = Field(
        default=CONST_TOOL_MIN_ADDRESS_SPACE_BYTES, ge=CONST_TOOL_MIN_ADDRESS_SPACE_BYTES
    )
    wall_seconds: float = Field(default=DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS, gt=0)


class ToolRequest(_Frozen):
    """One run of a review tool.

    `tool` names the program, as `tools.lock` and the PATH of the host know it. `arguments` are the
    arguments of the program. The element `{targets}` stands for `targets`, the paths of the tree
    that the tool scans.

    `config_files` and `ruleset_files` are files outside the sandbox that the tool reads. One file
    names a ruleset, such as a rule pack or the metadata file of a database. The executor binds
    each of these files read-only and digests its content into the record. `read_only_binds` are
    the other paths that the tool needs read-only, such as its install directory and a database.
    """

    tool: str = Field(min_length=1)
    arguments: tuple[str, ...] = ()
    workdir: Path
    targets: tuple[Path, ...] = Field(min_length=1)
    config_files: tuple[Path, ...] = ()
    ruleset_files: tuple[Path, ...] = ()
    read_only_binds: tuple[Path, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)
    limits: ToolLimits = Field(default_factory=ToolLimits)


class ToolRun(_Frozen):
    """What ran: the tool, its version and binary, the files and targets it read, and the commit.

    The digests are `devops_cli.ai.run_store.digest` values. The config digest and the ruleset
    digest cover the content of the files, not their paths or their order. The targets digest
    covers the names of the targets relative to the tree.

    `commit` is the commit of the checkout that holds the tree. It ends with `-dirty` when a target
    holds a change that the commit does not. A tree outside any git checkout has no commit, and
    neither has a checkout that holds no commit yet.
    """

    tool: str
    version: str
    binary_sha256: str
    config_digest: str
    ruleset_digest: str
    argv_template: tuple[str, ...]
    targets_digest: str
    commit: str | None


class ToolResult(_Frozen):
    """How a tool run ended. A run that ran out of time ends with exit code 124 and the output the
    tool wrote before then."""

    run: ToolRun
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @model_validator(mode="after")
    def _timeout_has_its_exit_code(self) -> ToolResult:
        """A run that timed out reports the exit code of a timeout, whoever made the result."""
        if self.timed_out and self.exit_code != CONST_SANDBOX_TIMEOUT_EXIT_CODE:
            raise ValueError(
                f"a timed out run ends with exit code {CONST_SANDBOX_TIMEOUT_EXIT_CODE}"
            )
        return self


class ToolExecutor(Protocol):
    """The seam: runs a review tool and answers how it ended and what ran."""

    def run(self, request: ToolRequest) -> ToolResult:
        """Run the tool of `request`; a request that cannot run safely raises `SandboxError`."""
        ...


def _resolved_targets(request: ToolRequest) -> tuple[Path, ...]:
    """The targets of `request`, resolved, each inside the tree and none through a link out."""
    root = request.workdir.resolve()
    if not root.is_dir():
        raise SandboxValidationError(f"The tree {root} is not a directory", path=str(root))
    for target in request.targets:
        if not is_safe_subpath(root, target):
            raise SandboxValidationError(
                f"The target {target} is outside the tree {root}", path=str(target)
            )
    return tuple(sorted((root / target).resolve() for target in request.targets))


def _is_small_regular_file(path: Path) -> bool:
    """Whether `path` is a regular file that is not larger than the cap, so a read of it is bounded.

    A device or a pipe has no end to read to, and a large file fills the memory.
    """
    try:
        info = path.stat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_size <= DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES


def _files_digest(files: Sequence[Path]) -> str:
    """A digest of the content of `files`. It does not depend on their paths or their order.

    A file that is missing, is no regular file or is too large raises `SandboxValidationError`.
    """
    contents: list[str] = []
    for path in files:
        content = file_digest(path) if _is_small_regular_file(path) else None
        if content is None:
            raise SandboxValidationError(
                f"The file {path} cannot be read as a regular file of at most "
                f"{DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES} bytes",
                path=str(path),
            )
        contents.append(content)
    return digest(sorted(contents))


def _git(root: Path, *arguments: str, accepted: tuple[int, ...] = (0,)) -> str:
    """The standard output of `git` in `root`. An exit code outside `accepted` raises
    `SandboxError`, because a record with no commit must mean that the tree has none.

    `git status` refreshes the index of the checkout and writes it, unless it is told to take no
    optional lock. A run must not write to the tree it reviews.
    """
    done = run_subprocess(
        ["git", "-C", str(root), "--no-optional-locks", *arguments],
        quiet=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if done.returncode not in accepted:
        raise SandboxError(
            f"git cannot read the commit of the tree {root}",
            details={"exit_code": done.returncode, "stderr": done.stderr.strip()},
        )
    return done.stdout.strip()


def _tree_commit(root: Path, targets: Sequence[Path]) -> str | None:
    """The commit of the checkout that holds `root`, with `-dirty` added when a target differs.

    A tree outside any checkout has no commit, and neither has a checkout that holds no commit
    yet. A checkout that git cannot read raises `SandboxError`. Files that git ignores do not
    count as a difference.
    """
    if nearest_checkout(root) is None:
        return None
    # `rev-parse --verify --quiet` exits with 1 when the name is no commit, as in a new checkout.
    commit = _git(root, "rev-parse", "--verify", "--quiet", "HEAD", accepted=(0, 1))
    if not commit:
        return None
    changes = _git(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        *(str(target.relative_to(root)) for target in targets),
    )
    return f"{commit}-dirty" if changes else commit


def record_tool_run(request: ToolRequest, *, version: str, binary_sha256: str) -> ToolRun:
    """The record of running `request` with a tool at `version` whose binary is `binary_sha256`.

    Every executor builds its record here. So every executor refuses a request, and reads its
    digests and its commit, in the same way.
    """
    targets = _resolved_targets(request)
    root = request.workdir.resolve()
    return ToolRun(
        tool=request.tool,
        version=version,
        binary_sha256=binary_sha256,
        config_digest=_files_digest(request.config_files),
        ruleset_digest=_files_digest(request.ruleset_files),
        argv_template=(request.tool, *request.arguments),
        targets_digest=digest([str(target.relative_to(root)) for target in targets]),
        commit=_tree_commit(root, targets),
    )


def _expand_targets(arguments: Sequence[str], targets: Sequence[Path]) -> list[str]:
    """`arguments`, with each `{targets}` element replaced by the paths of `targets`."""
    paths = [str(target) for target in targets]
    return [
        argument
        for template in arguments
        for argument in (paths if template == CONST_TOOL_TARGETS_PLACEHOLDER else [template])
    ]


def _partial_output(output: str | bytes | None) -> str:
    """What a run wrote before it timed out; `subprocess` hands it back as bytes or text."""
    return output.decode(errors="replace") if isinstance(output, bytes) else output or ""


class SandboxToolExecutor:
    """Runs each tool in a bubblewrap sandbox, under `prlimit`, through `run_subprocess`."""

    def __init__(self, sandbox: HostSandbox | None = None) -> None:
        self._sandbox = sandbox or HostSandbox()

    def command(self, request: ToolRequest) -> list[str]:
        """The whole command that runs `request`: bubblewrap, its options, `prlimit` and the tool."""
        binary = resolve_tool_binary(request.tool)
        if binary is None:
            raise SandboxError(f"The review tool {request.tool} is not installed on this host")
        # By its full path. The PATH of the sandbox leads with the `.venv/bin` of the reviewed
        # tree. The tree could put a `prlimit` there that sets no limit.
        prlimit = shutil.which(CONST_TOOL_PRLIMIT_BINARY)
        if prlimit is None:
            raise SandboxError(
                f"{CONST_TOOL_PRLIMIT_BINARY} (util-linux) is not installed, so a review tool "
                "cannot run under its limits"
            )
        root = request.workdir.resolve()
        inputs = (*request.read_only_binds, *request.config_files, *request.ruleset_files)
        outside = dict.fromkeys(path for path in inputs if not path.resolve().is_relative_to(root))
        limits = request.limits
        tool_command = [
            prlimit,
            f"--cpu={limits.cpu_seconds}",
            f"--as={limits.address_space_bytes}",
            "--",
            str(binary),
            *_expand_targets(request.arguments, _resolved_targets(request)),
        ]
        return self._sandbox.build_bwrap_args(
            tool_command,
            root,
            repo_root=root,
            env={**request.env, "GOMEMLIMIT": CONST_TOOL_GO_MEMORY_LIMIT},
            read_only_binds=list(outside),
        )

    def run(self, request: ToolRequest) -> ToolResult:
        """Run the tool of `request` in the sandbox and answer how it ended and what ran.

        A tool, a sandbox or a limit program that the host lacks raises `SandboxError` before
        anything starts. So does a target outside the tree. A host without bubblewrap runs no tool.
        A later change decides the policy for such hosts.
        """
        command = self.command(request)
        if not self._sandbox.is_available():
            raise SandboxError(
                f"bubblewrap ({self._sandbox.bwrap_binary}) is not installed, so a review tool "
                "cannot run in its sandbox"
            )
        version, binary_sha256 = resolve_tool_version_and_sha(request.tool)
        run = record_tool_run(request, version=version, binary_sha256=binary_sha256)
        try:
            ended = run_subprocess(
                command, cwd=request.workdir, timeout=request.limits.wall_seconds
            )
        except subprocess.TimeoutExpired as expired:
            return ToolResult(
                run=run,
                exit_code=CONST_SANDBOX_TIMEOUT_EXIT_CODE,
                stdout=_partial_output(expired.stdout),
                stderr=_partial_output(expired.stderr),
                timed_out=True,
            )
        return ToolResult(
            run=run, exit_code=ended.returncode, stdout=ended.stdout, stderr=ended.stderr
        )


__all__ = [
    "SandboxToolExecutor",
    "ToolExecutor",
    "ToolLimits",
    "ToolRequest",
    "ToolResult",
    "ToolRun",
    "record_tool_run",
]
