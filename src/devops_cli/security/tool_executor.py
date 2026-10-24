"""The one seam that review tools run through, and the sandbox that runs them (#772).

A review tool is a program of another project, such as Semgrep or Trivy. It reads the reviewed
tree. Code that runs a tool builds a `ToolRequest` and calls `ToolExecutor.run`. The answer is a
`ToolResult`. It holds the output of the tool and a `ToolRun`, the record of what ran. A test
installs `ToolExecutorFake` in its place (`tests/support/fakes/tool_executor.py`).

`DirectToolExecutor` starts the tool as a child process of devops-cli, with no sandbox and no
limit but the wall clock. It is how every scanner ran before this seam, and it is the executor that
a scanner gets when nobody gives it another. `SandboxToolExecutor` is the executor that confines.
It does not confine or limit a process itself. It builds one command from three programs that
already do this work:

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

The SARIF export of a review (`devops_cli.security.sarif.to_sarif`) writes the records of a tool in
the SARIF 2.1.0 run of that tool:

- `tool` is `tool.driver.name`. The records of a tool go to the run whose driver has that name.
- `version` is `tool.driver.version` when no result names the version and the records of the tool
  name one version.
- The property bag of the run holds each record under `tool_runs`, with the field names of
  `ToolRun`.

SARIF has a name for three more fields. SARIF requires a value there that the record does not hold,
so the export does not write these names:

- `argv_template` is the `commandLine` of an `invocation`. An invocation must tell in
  `executionSuccessful` if the tool succeeded (section 3.20.14). The record does not tell this, and
  the exit code of a tool does not tell it either. Each placeholder of the template is then a
  redaction token of the run (sections 3.5.2 and 3.14.28).
- `binary_sha256` is the `sha-256` hash of an artifact with the role `driver`. A top-level artifact
  must have a location (section 3.24.2), and the record holds no path of the binary.
- `commit` is the `revisionId` of `versionControlProvenance`. This object must have a
  `repositoryUri` (section 3.23.3), and the record holds no repository. A commit that ends with
  `-dirty` identifies no revision of the files that the tool scanned.

The config, ruleset and targets digests have no SARIF name. A SARIF hash is the hash of one artifact
(section 3.24.11), and each of these digests covers a group of files. `executor` has no SARIF name:
it says whether the run was confined.

`RecordingToolExecutor` wraps another executor and keeps the `ToolRun` of every run. A review gives
its scanners one, and shows the records in its profile, in `review.md` and in `findings.sarif`.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from devops_cli.ai.run_store import digest, file_digest
from devops_cli.config.constants import (
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
    CONST_TOOL_CONFIG_PLACEHOLDER,
    CONST_TOOL_CPU_LIMIT_SECONDS,
    CONST_TOOL_DIGEST_UNAVAILABLE,
    CONST_TOOL_EXECUTOR_DIRECT,
    CONST_TOOL_EXECUTOR_SANDBOX,
    CONST_TOOL_GO_MEMORY_LIMIT,
    CONST_TOOL_MIN_ADDRESS_SPACE_BYTES,
    CONST_TOOL_PRLIMIT_BINARY,
    CONST_TOOL_RULESET_PLACEHOLDER,
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

if TYPE_CHECKING:
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

    `workdir` is the tree. The tool starts in `cwd`, and in the tree when `cwd` is none. A scan that
    must not read the config files of the tree starts in a scratch directory of its own. The
    sandbox binds a `cwd` outside the tree read-only.
    """

    tool: str = Field(min_length=1)
    arguments: tuple[str, ...] = ()
    workdir: Path
    cwd: Path | None = None
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
    covers the names of the targets relative to the tree. A digest is `unavailable` when the direct
    executor could not read one of the files: a scan must not fail for a record.

    `executor` says how the tool ran: `direct` is a child process of devops-cli with no confinement
    and no limit but the wall clock, and `sandbox` is the bubblewrap sandbox with the limits of
    `ToolLimits`. `argv_template` is the command with a placeholder for each path that names a
    target, a config file or a ruleset file, so the same scan records the same template.

    `commit` is the commit of the checkout that holds the tree. It ends with `-dirty` when a target
    holds a change that the commit does not. A tree outside any git checkout has no commit, and
    neither has a checkout that holds no commit yet. The sandbox executor refuses a checkout that
    git cannot read. The direct executor records no commit for it, because a scan must not fail
    for a record.
    """

    tool: str
    version: str
    binary_sha256: str
    executor: str = Field(min_length=1)
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


def _files_digest(files: Sequence[Path], *, required: bool = True) -> str:
    """A digest of the content of `files`. It does not depend on their paths or their order.

    A file that is missing, is no regular file or is too large raises `SandboxValidationError`,
    unless the digest is not `required`. Then the digest is `unavailable`.
    """
    contents: list[str] = []
    for path in files:
        content = file_digest(path) if _is_small_regular_file(path) else None
        if content is None:
            if not required:
                return CONST_TOOL_DIGEST_UNAVAILABLE
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


def _read_tree_commit(root: Path, targets: Sequence[Path]) -> str | None:
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


def _tree_commit(root: Path, targets: Sequence[Path], *, required: bool) -> str | None:
    """The commit of `root` (`_read_tree_commit`). A checkout that git cannot read raises
    `SandboxError` when the commit is `required`, and has no commit when it is not."""
    try:
        return _read_tree_commit(root, targets)
    except SandboxError:
        if required:
            raise
        return None


def _placeholders(request: ToolRequest, targets: Sequence[Path]) -> dict[str, str]:
    """The placeholder for each path that `request` names, by the normal form of the path.

    A target wins over a config file or a ruleset file, and a config file wins over the directory
    of a ruleset file. A rule pack is a directory of ruleset files, and a tool takes it by that name.
    A scan that starts in a scratch directory may name a target by its place in the tree, below that
    directory.
    """
    root = request.workdir.resolve()
    base = request.cwd or root
    named = (
        (
            CONST_TOOL_RULESET_PLACEHOLDER,
            (*request.ruleset_files, *(path.parent for path in request.ruleset_files)),
        ),
        (CONST_TOOL_CONFIG_PLACEHOLDER, request.config_files),
        (
            CONST_TOOL_TARGETS_PLACEHOLDER,
            (
                *targets,
                *(root / path for path in request.targets),
                *(base / path.relative_to(root) for path in targets),
            ),
        ),
    )
    return {os.path.normpath(path): placeholder for placeholder, paths in named for path in paths}


def _argv_template(request: ToolRequest, targets: Sequence[Path]) -> tuple[str, ...]:
    """The command of `request`, with a placeholder for each path argument that names a target, a
    config file or a ruleset file. Adjacent placeholders of one kind stand once.

    A path argument is an absolute path, or a path that starts with `./` from the directory where
    the tool starts. A scratch directory is new in each run, and a target is a path of the host. So
    the template reads the same for the same scan.
    """
    placeholders = _placeholders(request, targets)
    base = request.cwd or request.workdir
    template: list[str] = []
    for argument in request.arguments:
        is_path = os.path.isabs(argument) or argument.startswith(os.curdir + os.sep)
        placeholder = placeholders.get(os.path.normpath(os.path.join(base, argument)))
        if not (is_path and placeholder):
            template.append(argument)
        elif not template or template[-1] != placeholder:
            template.append(placeholder)
    return (request.tool, *template)


def record_tool_run(
    request: ToolRequest,
    *,
    version: str,
    binary_sha256: str,
    executor: str,
    require_commit: bool = True,
    require_files: bool = True,
) -> ToolRun:
    """The record of running `request` with a tool at `version` whose binary is `binary_sha256`,
    started by the executor that `executor` names.

    Every executor builds its record here. So every executor refuses a request, and reads its
    digests and its commit, in the same way. A checkout that git cannot read raises `SandboxError`,
    unless `require_commit` is false. Then the record holds no commit. A config file or a ruleset
    file that cannot be read as a regular file raises `SandboxValidationError`, unless
    `require_files` is false. Then its digest is `unavailable`.
    """
    targets = _resolved_targets(request)
    root = request.workdir.resolve()
    return ToolRun(
        tool=request.tool,
        version=version,
        binary_sha256=binary_sha256,
        executor=executor,
        config_digest=_files_digest(request.config_files, required=require_files),
        ruleset_digest=_files_digest(request.ruleset_files, required=require_files),
        argv_template=_argv_template(request, targets),
        targets_digest=digest([str(target.relative_to(root)) for target in targets]),
        commit=_tree_commit(root, targets, required=require_commit),
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


def _start(
    run: ToolRun,
    command: list[str],
    *,
    cwd: Path,
    wall_seconds: float,
    env: dict[str, str] | None = None,
) -> ToolResult:
    """Start `command` through `run_subprocess` and answer how it ended.

    The command gets an empty standard input, never the one of the caller. Under `devops mcp` that
    is the request stream of the client (#1079).
    """
    try:
        ended = run_subprocess(
            command, cwd=cwd, env=env, timeout=wall_seconds, check=False, input=""
        )
    except subprocess.TimeoutExpired as expired:
        return ToolResult(
            run=run,
            exit_code=CONST_SANDBOX_TIMEOUT_EXIT_CODE,
            stdout=_partial_output(expired.stdout),
            stderr=_partial_output(expired.stderr),
            timed_out=True,
        )
    return ToolResult(run=run, exit_code=ended.returncode, stdout=ended.stdout, stderr=ended.stderr)


class DirectToolExecutor:
    """Starts each tool as a child process of devops-cli, through `run_subprocess`.

    There is no sandbox, and the only limit is the wall clock of the request. This is how a
    scanner started its tool before the seam existed, and it is the executor of a scanner that
    nobody gave another, until a later part of #772 switches the review to the sandbox. A scan
    must end as it ended before, so a checkout that git cannot read does not stop it: the record
    of the run holds no commit. Otherwise the record is built as the sandbox executor builds it.
    """

    def run(self, request: ToolRequest) -> ToolResult:
        """Start the tool of `request` and answer how it ended and what ran.

        A target outside the tree raises `SandboxError` before anything starts.
        """
        version, binary_sha256 = resolve_tool_version_and_sha(request.tool)
        run = record_tool_run(
            request,
            version=version,
            binary_sha256=binary_sha256,
            executor=CONST_TOOL_EXECUTOR_DIRECT,
            require_commit=False,
            require_files=False,
        )
        command = [request.tool, *_expand_targets(request.arguments, _resolved_targets(request))]
        return _start(
            run,
            command,
            cwd=request.cwd or request.workdir,
            wall_seconds=request.limits.wall_seconds,
            env=request.env or None,
        )


class SandboxToolExecutor:
    """Runs each tool in a bubblewrap sandbox, under `prlimit`, through `run_subprocess`."""

    def __init__(self, sandbox: HostSandbox | None = None) -> None:
        # Imported here. The sandbox pulls in the container engine, which a scanner that runs
        # directly never needs.
        from devops_cli.sandbox.host import HostSandbox

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
            request.cwd or root,
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
        run = record_tool_run(
            request,
            version=version,
            binary_sha256=binary_sha256,
            executor=CONST_TOOL_EXECUTOR_SANDBOX,
        )
        return _start(run, command, cwd=request.workdir, wall_seconds=request.limits.wall_seconds)


class RecordingToolExecutor:
    """Passes each request to another executor and keeps the record of each run that started.

    A review gives its scanners one of these, so that the review can show what ran. A scanner
    reads the answer of the wrapped executor, unchanged. A request that the wrapped executor
    refuses starts no run, so it leaves no record. Scans may run on several threads. Appending a
    record to a list is atomic.
    """

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor
        self._runs: list[ToolRun] = []

    @property
    def runs(self) -> tuple[ToolRun, ...]:
        """The record of each run so far, in the order the runs started."""
        return tuple(self._runs)

    def run(self, request: ToolRequest) -> ToolResult:
        """Run `request` on the wrapped executor and keep the record of the run."""
        result = self._executor.run(request)
        self._runs.append(result.run)
        return result


__all__ = [
    "DirectToolExecutor",
    "RecordingToolExecutor",
    "SandboxToolExecutor",
    "ToolExecutor",
    "ToolLimits",
    "ToolRequest",
    "ToolResult",
    "ToolRun",
    "record_tool_run",
]
