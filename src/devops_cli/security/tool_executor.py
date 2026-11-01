"""The one seam that review tools run through, and the sandbox that runs them (#772).

A review tool is a program of another project, such as Semgrep or Trivy. It reads the reviewed
tree. Code that runs a tool builds a `ToolRequest` and calls `ToolExecutor.run`. The answer is a
`ToolResult`. It holds the output of the tool and a `ToolRun`, the record of what ran. A test
installs `ToolExecutorFake` in its place (`tests/support/fakes/tool_executor.py`).

A review runs its tools in `SandboxToolExecutor` (#2096). The command layer makes one for each
review and gives it to the orchestrator, which gives it to every analyzer, evidence tool and canary.
A review has no way to run its tools outside the sandbox (decision 1 of #772).
`DirectToolExecutor` starts the tool as a child process of devops-cli, with no sandbox and no limit
but the wall clock. It is the executor that a scanner gets when nobody gives it another, as the
scans of `devops scan` and the agent tools do. Those are not reviews. Popeye is the exception: it
reads the Kubernetes API, and it runs in the sandbox with the network profile `kube-api`
(`KubeApiNetwork`, decision 2 of #772, #2132). Only Popeye can select that profile, and the direct
executor refuses it. The record of each run names the network of the tool.

`SandboxToolExecutor` does not confine or limit a process itself. It builds one command from three
programs that already do this work:

- bubblewrap, through `HostSandbox`. It gives no network, a cleared environment, a read-only tree,
  read-only inputs and a private temporary HOME. A request with the network profile `kube-api`
  reaches the Kubernetes API server through `kubectl proxy` outside the sandbox and `socat` in it
  (`devops_cli.sandbox.kube_api`). When the sandbox process ends, the process tree
  in it ends (`--die-with-parent` and the process namespace of the sandbox). No code here ends a
  process.
- `prlimit` from util-linux. It sets the CPU limit and the address space limit of the tool. No code
  of devops-cli calls `setrlimit` or `preexec_fn`. Gitleaks and Semgrep reserve more address space
  than the least, so they get the value that `ToolLimits.for_tool` names.
- `run_subprocess` of `core.process`. It starts the command and ends it at the wall-clock limit.

The sandbox shows the tool only the system directories, the tree and what the request names. So it
binds the program of the tool: the virtualenv that holds it in its `bin`, else the program file. A
read-only bind that is a virtualenv also binds the Python installation that its `python` links to,
behind the guard of `HostSandbox`. A request names the directories that its tool writes, such as
the caches of mypy and Ruff, in `writable_dirs`, and the sandbox binds them read-write. The request
of golangci-lint also names the Go toolchain and the module cache of the host read-only, its Go
caches read-write, and a `go` command that fetches nothing (#2129).

Before its first run, the executor checks that the host can start the sandbox. A host without
bubblewrap or prlimit, or one whose kernel refuses bubblewrap a user namespace, fails closed: each
run raises `SandboxUnavailableError`, and no tool runs, in the sandbox or outside it. A scan
reports the cause as a coverage gap, and the review says the cause one time.

There is no limit on the number of processes. RLIMIT_NPROC counts every process of the user, so a
limit set inside the sandbox would starve the shells and servers of the host.
`_run_sandbox_process` in `sandbox/host.py` gives the reason in full.

The code that runs a tool decides if the run succeeded, from the exit code and the output together,
and settles the run with `ToolExecutor.settle`. `RecordingToolExecutor` then keeps the settled
record, which holds `exit_code` and `success` (`ToolResult.settled`). The other executors keep no
records, so their settle does nothing.

The SARIF export of a review (`devops_cli.security.sarif.to_sarif`) writes the records of a tool in
the SARIF 2.1.0 run of that tool:

- `tool` is `tool.driver.name`. The records of a tool go to the run whose driver has that name.
- `version` is `tool.driver.version` when no result names the version and the records of the tool
  name one version.
- The property bag of the run holds each record under `tool_runs`, with the field names of
  `ToolRun`.
- Each settled record is one `invocation` of the run. `success` is `executionSuccessful` (section
  3.20.14), and `exit_code` is `exitCode` (section 3.20.9). `argv_template` is `commandLine` (section
  3.20.2), with each argument quoted for a POSIX shell. Each placeholder of the template that a
  command line holds is a redaction token of the run (sections 3.5.2 and 3.14.28).

SARIF has a name for two more fields. SARIF requires a value there that the record does not hold,
so the export does not write these names:

- `binary_sha256` is the `sha-256` hash of an artifact with the role `driver`. A top-level artifact
  must have a location (section 3.24.2), and the record holds no path of the binary.
- `commit` is the `revisionId` of `versionControlProvenance`. This object must have a
  `repositoryUri` (section 3.23.3), and the record holds no repository. A commit that ends with
  `-dirty` identifies no revision of the files that the tool scanned.

The config, ruleset and targets digests have no SARIF name. A SARIF hash is the hash of one artifact
(section 3.24.11), and each of these digests covers a group of files. `executor` and `network` have
no SARIF name: they say whether the run was confined, and which network the tool had.

`RecordingToolExecutor` wraps another executor and keeps the `ToolRun` of every run. A review gives
its scanners one, and shows the records in its profile, in `review.md` and in `findings.sarif`.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from devops_cli.ai.run_store import digest, file_digest
from devops_cli.config.constants import (
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
    CONST_TOOL_ADDRESS_SPACE_BYTES,
    CONST_TOOL_CONFIG_PLACEHOLDER,
    CONST_TOOL_CPU_LIMIT_SECONDS,
    CONST_TOOL_DIGEST_UNAVAILABLE,
    CONST_TOOL_EXECUTOR_DIRECT,
    CONST_TOOL_EXECUTOR_SANDBOX,
    CONST_TOOL_GO_MEMORY_LIMIT,
    CONST_TOOL_HOST_READ_ONLY_PATHS,
    CONST_TOOL_KUBE_API_TOOL,
    CONST_TOOL_MIN_ADDRESS_SPACE_BYTES,
    CONST_TOOL_NETWORK_HOST,
    CONST_TOOL_NETWORK_KUBE_API,
    CONST_TOOL_NETWORK_NONE,
    CONST_TOOL_PRLIMIT_BINARY,
    CONST_TOOL_RULESET_PLACEHOLDER,
    CONST_TOOL_SANDBOX_CHECK_TIMEOUT_SECONDS,
    CONST_TOOL_TARGETS_PLACEHOLDER,
)
from devops_cli.config.defaults import (
    DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES,
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import is_safe_subpath, nearest_checkout
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxUnavailableError,
    SandboxValidationError,
)
from devops_cli.review.canary import resolve_tool_binary, resolve_tool_version_and_sha

if TYPE_CHECKING:
    from devops_cli.sandbox.host import HostSandbox
    from devops_cli.sandbox.kube_api import KubeApiRelay


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

    @classmethod
    def for_tool(
        cls, tool: str, *, wall_seconds: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
    ) -> ToolLimits:
        """The limits of `tool`: the address space that it was measured to need
        (`CONST_TOOL_ADDRESS_SPACE_BYTES`), else the least, and `wall_seconds`."""
        return cls(
            address_space_bytes=CONST_TOOL_ADDRESS_SPACE_BYTES.get(
                tool, CONST_TOOL_MIN_ADDRESS_SPACE_BYTES
            ),
            wall_seconds=wall_seconds,
        )


class KubeApiNetwork(_Frozen):
    """The network profile `kube-api` of the sandbox (#2132). The tool reaches the Kubernetes API
    server of one context, only to read, through `kubectl proxy` outside the sandbox
    (`devops_cli.sandbox.kube_api`).

    `context` names a context of the kubeconfig of the user. None is the current context.
    """

    name: ClassVar[str] = CONST_TOOL_NETWORK_KUBE_API
    context: str | None = Field(default=None, min_length=1)


class ToolRequest(_Frozen):
    """One run of a review tool.

    `tool` names the program, as `tools.lock` and the PATH of the host know it. `arguments` are the
    arguments of the program. The element `{targets}` stands for `targets`, the paths of the tree
    that the tool scans.

    `program` is the absolute path of the program that starts the tool, when the PATH of the host
    does not name it. Mypy runs as `python -I -m mypy` with the interpreter of the `.venv` of the
    reviewed repository, so its request names that interpreter. The executor starts `program` by
    this path, and never by the file that a link of it leads to: the `python` of a `.venv` is a
    link to the interpreter it was made from, and only the path of the link finds the `.venv`.
    `tool` still names the tool in the record. The record names the program by its file name.

    `config_files` and `ruleset_files` are files outside the sandbox that the tool reads. One file
    names a ruleset, such as a rule pack or the metadata file of a database. The executor binds
    each of these files read-only and digests its content into the record. A ruleset file at or
    below one of `read_only_binds`, such as the database file of osv-scanner, is digested at any
    size. Every other file over 50 MiB stops the run. `read_only_binds` are the other paths that
    the tool needs read-only, such as its install directory and a database.
    `writable_dirs` are the directories that the tool writes and that stay after the run, such as
    the cache of mypy. The sandbox binds each one read-write. The direct executor needs neither.

    `workdir` is the tree. The tool starts in `cwd`, and in the tree when `cwd` is none. A scan that
    must not read the config files of the tree starts in a scratch directory of its own. The
    sandbox binds a `cwd` outside the tree read-only.

    `network` selects the network profile of the sandbox. None gives the tool no network. Only
    Popeye (`CONST_TOOL_KUBE_API_TOOL`) can select `KubeApiNetwork`, and only by its name on the
    PATH: a `program` could start another binary under that name.
    """

    tool: str = Field(min_length=1)
    program: Path | None = None
    arguments: tuple[str, ...] = ()
    workdir: Path
    cwd: Path | None = None
    targets: tuple[Path, ...] = Field(min_length=1)
    config_files: tuple[Path, ...] = ()
    ruleset_files: tuple[Path, ...] = ()
    read_only_binds: tuple[Path, ...] = ()
    writable_dirs: tuple[Path, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)
    limits: ToolLimits = Field(default_factory=ToolLimits)
    network: KubeApiNetwork | None = None

    @model_validator(mode="after")
    def _program_is_absolute(self) -> ToolRequest:
        """A relative program would start another program in each directory a run starts in."""
        if self.program is not None and not self.program.is_absolute():
            raise ValueError(f"the program {self.program} of a tool is no absolute path")
        return self

    @model_validator(mode="after")
    def _only_popeye_selects_the_network(self) -> ToolRequest:
        """No tool but Popeye, started by its name, gets the network profile `kube-api`."""
        if self.network is None:
            return self
        if self.tool != CONST_TOOL_KUBE_API_TOOL:
            raise ValueError(
                f"only {CONST_TOOL_KUBE_API_TOOL} can select the network profile "
                f"{self.network.name}, not {self.tool}"
            )
        if self.program is not None:
            raise ValueError(
                f"a request that names the program {self.program} cannot select the network "
                f"profile {self.network.name}"
            )
        return self


class ToolRun(_Frozen):
    """What ran: the tool, its version and binary, the files and targets it read, and the commit.

    The digests are `devops_cli.ai.run_store.digest` values. The config digest and the ruleset
    digest cover the content of the files, not their paths or their order. The targets digest
    covers the names of the targets relative to the tree. A digest is `unavailable` when the direct
    executor could not read one of the files: a scan must not fail for a record.

    `executor` says how the tool ran: `direct` is a child process of devops-cli with no confinement
    and no limit but the wall clock, and `sandbox` is the bubblewrap sandbox with the limits of
    `ToolLimits`. `argv_template` is the command with a placeholder for each path that names a
    target, a config file or a ruleset file, so the same scan records the same template. It starts
    with the tool, or with the file name of the program of the request when it names one.

    `network` says which network the tool had: `host` under the direct executor, `none` in the
    sandbox, and the name of the network profile, `kube-api`, in the sandbox with that profile.

    `commit` is the commit of the checkout that holds the tree. It ends with `-dirty` when a target
    holds a change that the commit does not. A tree outside any git checkout has no commit, and
    neither has a checkout that holds no commit yet. The sandbox executor refuses a checkout that
    git cannot read. The direct executor records no commit for it, because a scan must not fail
    for a record.

    `exit_code` and `success` say how the run ended. An executor builds the record before the tool
    starts, so the record of its answer holds neither. The code that ran the tool decides from the
    exit code and the output together if the run succeeded, and settles the run
    (`ToolExecutor.settle`). The settled record (`ToolResult.settled`) holds both. It holds no exit
    code when the run timed out or a signal ended it: the process of the tool did not exit.
    """

    tool: str
    version: str
    binary_sha256: str
    executor: str = Field(min_length=1)
    network: str = Field(min_length=1)
    config_digest: str
    ruleset_digest: str
    argv_template: tuple[str, ...]
    targets_digest: str
    commit: str | None
    exit_code: int | None = None
    success: bool | None = None


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

    def settled(self, *, success: bool) -> ToolRun:
        """The record of this run with how it ended: its exit code, and `success` as the code
        that ran the tool decided it.

        The exit code 124 of a timeout is the executor's, and a negative exit code is the signal
        that ended the process. So the record of such a run holds no exit code.
        """
        exited = not self.timed_out and self.exit_code >= 0
        return self.run.model_copy(
            update={"exit_code": self.exit_code if exited else None, "success": success}
        )


class ToolExecutor(Protocol):
    """The seam: runs a review tool and answers how it ended and what ran.

    The code that calls `run` decides if each run succeeded, and settles the run one time with
    `settle`.
    """

    def run(self, request: ToolRequest) -> ToolResult:
        """Run the tool of `request`; a request that cannot run safely raises `SandboxError`."""

    def settle(self, result: ToolResult, *, success: bool) -> None:
        """Keep that the run of `result` succeeded or failed, when the executor keeps records."""
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


def _is_readable_file(path: Path, max_size: int | None) -> bool:
    """Whether `path` is a regular file that is not larger than `max_size`, so a read of it ends.

    A device or a pipe has no end to read to. `max_size` is None for a file that has no size
    limit.
    """
    try:
        info = path.stat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and (max_size is None or info.st_size <= max_size)


def _is_below(path: Path, directories: Sequence[Path]) -> bool:
    """Whether the file that `path` leads to lies at or below one of `directories`."""
    resolved = path.resolve()
    return any(resolved.is_relative_to(directory.resolve()) for directory in directories)


def _files_digest(
    files: Sequence[Path], *, required: bool = True, unlimited_below: Sequence[Path] = ()
) -> str:
    """A digest of the content of `files`. It does not depend on their paths or their order.

    A file at or below one of `unlimited_below` has no size limit: these are the data directories
    of the tool, such as a database that devops-cli or the user fetched, and not the reviewed
    tree. Every other file has the limit `DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES`. A file that is
    missing, is no regular file or is over its limit raises `SandboxValidationError`, unless the
    digest is not `required`. Then the digest is `unavailable`.
    """
    contents: list[str] = []
    for path in files:
        max_size = None if _is_below(path, unlimited_below) else DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES
        content = file_digest(path) if _is_readable_file(path, max_size) else None
        if content is None:
            if not required:
                return CONST_TOOL_DIGEST_UNAVAILABLE
            raise SandboxValidationError(
                f"The file {path} cannot be read as a regular file"
                + ("" if max_size is None else f" of at most {max_size} bytes"),
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
    return (request.program.name if request.program else request.tool, *template)


def record_tool_run(
    request: ToolRequest,
    *,
    version: str,
    binary_sha256: str,
    executor: str,
    network: str | None = None,
    require_commit: bool = True,
    require_files: bool = True,
) -> ToolRun:
    """The record of running `request` with a tool at `version` whose binary is `binary_sha256`,
    started by the executor that `executor` names.

    Every executor builds its record here. So every executor refuses a request, and reads its
    digests and its commit, in the same way. The network is the network profile of the request,
    else `none`. An executor that gives every tool a network of its own names it in `network`: the
    direct executor gives the network of the host. Such an executor cannot run a network profile,
    so a request that selects one raises `SandboxError`. A checkout that git cannot read raises
    `SandboxError`, unless `require_commit` is false. Then the record holds no commit. A config
    file or a ruleset file that cannot be read as a regular file within its size limit raises
    `SandboxValidationError`, unless `require_files` is false. Then its digest is `unavailable`.
    A ruleset file below one of `read_only_binds` has no size limit.
    """
    if network is not None and request.network is not None:
        raise SandboxError(
            f"The {executor} executor gives {request.tool} the network {network}, so it cannot run "
            f"the network profile {request.network.name}"
        )
    targets = _resolved_targets(request)
    root = request.workdir.resolve()
    profile = request.network.name if request.network else CONST_TOOL_NETWORK_NONE
    return ToolRun(
        tool=request.tool,
        version=version,
        binary_sha256=binary_sha256,
        executor=executor,
        network=network or profile,
        config_digest=_files_digest(request.config_files, required=require_files),
        ruleset_digest=_files_digest(
            request.ruleset_files,
            required=require_files,
            unlimited_below=request.read_only_binds,
        ),
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


def _program_binds(program: Path) -> tuple[Path, ...]:
    """What the sandbox binds so that `program` starts: the virtualenv that holds the program in
    its `bin`, with its interpreter link and its packages, else the program file."""
    environment = program.parent.parent
    return (environment,) if (environment / "pyvenv.cfg").is_file() else (program,)


def _host_paths(tool: str) -> tuple[Path, ...]:
    """The paths of the host that `tool` reads when it starts and that exist
    (`CONST_TOOL_HOST_READ_ONLY_PATHS`)."""
    paths = (Path(path) for path in CONST_TOOL_HOST_READ_ONLY_PATHS.get(tool, ()))
    return tuple(path for path in paths if path.exists())


class DirectToolExecutor:
    """Starts each tool as a child process of devops-cli, through `run_subprocess`.

    There is no sandbox, and the only limit is the wall clock of the request. It is the executor
    of a scanner that nobody gave another, except Popeye: the scans of `devops scan` and the agent
    tools, which are not reviews. A review never runs its tools here. A scan must end as it
    ended before the seam existed, so a checkout that git cannot read does not stop it: the
    record of the run holds no commit. Otherwise the record is built as the sandbox executor
    builds it.
    """

    def run(self, request: ToolRequest) -> ToolResult:
        """Start the tool of `request` and answer how it ended and what ran.

        A target outside the tree raises `SandboxError` before anything starts. So does a request
        that selects a network profile (`record_tool_run`): a child process has the whole network
        of the host, so a run here would give the tool more network than the profile. The tool
        starts from the program of the request, else by its name on the PATH of the host.
        """
        version, binary_sha256 = resolve_tool_version_and_sha(request.tool, request.program)
        run = record_tool_run(
            request,
            version=version,
            binary_sha256=binary_sha256,
            executor=CONST_TOOL_EXECUTOR_DIRECT,
            network=CONST_TOOL_NETWORK_HOST,
            require_commit=False,
            require_files=False,
        )
        program = str(request.program) if request.program else request.tool
        command = [program, *_expand_targets(request.arguments, _resolved_targets(request))]
        return _start(
            run,
            command,
            cwd=request.cwd or request.workdir,
            wall_seconds=request.limits.wall_seconds,
            env=request.env or None,
        )

    def settle(self, result: ToolResult, *, success: bool) -> None:
        """Do nothing: this executor keeps no records."""


class SandboxToolExecutor:
    """Runs each tool in a bubblewrap sandbox, under `prlimit`, through `run_subprocess`.

    Before its first run, the executor checks that the host can start the sandbox: bubblewrap and
    prlimit are installed, and bubblewrap can make a sandbox with `prlimit -- true` in it. The
    check runs one time. On a host that fails it, each run raises `SandboxUnavailableError` with
    the cause, and `refusal` keeps the cause. No tool then runs, in the sandbox or outside it.
    """

    def __init__(self, sandbox: HostSandbox | None = None) -> None:
        self._given_sandbox = sandbox
        self._built_sandbox: HostSandbox | None = None
        self._checked = False
        self._refusal: str | None = None

    @property
    def _sandbox(self) -> HostSandbox:
        """The bubblewrap sandbox, made at its first use. It pulls in the library of the container
        engine, which a review that starts no tool, such as a dry run, never needs."""
        if self._given_sandbox is not None:
            return self._given_sandbox
        if self._built_sandbox is None:
            from devops_cli.sandbox.host import HostSandbox

            self._built_sandbox = HostSandbox()
        return self._built_sandbox

    @property
    def refusal(self) -> str | None:
        """Why this executor ran no tool: the cause that it found on the host, or None."""
        return self._refusal

    def _prlimit(self) -> str:
        """The full path of `prlimit`. The PATH of the sandbox leads with the `.venv/bin` of the
        reviewed tree, and the tree could put a `prlimit` there that sets no limit."""
        prlimit = shutil.which(CONST_TOOL_PRLIMIT_BINARY)
        if prlimit is None:
            raise SandboxUnavailableError(
                f"{CONST_TOOL_PRLIMIT_BINARY} (util-linux) is not installed"
            )
        return prlimit

    def _host_cause(self) -> str | None:
        """Why this host cannot start the sandbox, or None when it can.

        The kernel can refuse bubblewrap a user namespace, as AppArmor does on Ubuntu 24.04 for a
        program with no profile that allows it. Only a start shows that, so the check starts
        `prlimit -- true` in a sandbox of an empty directory.
        """
        if not self._sandbox.is_available():
            return f"bubblewrap ({self._sandbox.bwrap_binary}) is not installed"
        try:
            prlimit = self._prlimit()
        except SandboxUnavailableError as missing:
            return missing.message
        with tempfile.TemporaryDirectory(prefix="devops-sandbox-check-") as scratch:
            empty = Path(scratch)
            command = self._sandbox.build_bwrap_args([prlimit, "--", "true"], empty, empty)
            try:
                done = run_subprocess(
                    command,
                    quiet=True,
                    check=False,
                    input="",
                    timeout=CONST_TOOL_SANDBOX_CHECK_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return (
                    "bubblewrap did not start a sandbox in "
                    f"{CONST_TOOL_SANDBOX_CHECK_TIMEOUT_SECONDS:g} s"
                )
        if done.returncode == 0:
            return None
        detail = next(iter(done.stderr.strip().splitlines()), f"exit code {done.returncode}")
        return f"bubblewrap cannot make a sandbox on this host: {detail}"

    def _check_host(self) -> None:
        """Raise `SandboxUnavailableError` when this host cannot start the sandbox. The host is
        checked one time."""
        if not self._checked:
            self._refusal = self._host_cause()
            self._checked = True
        if self._refusal is not None:
            raise SandboxUnavailableError(self._refusal)

    def command(self, request: ToolRequest, relay: KubeApiRelay | None = None) -> list[str]:
        """The whole command that runs `request`: bubblewrap, its options, `prlimit` and the tool.

        The tool starts from the program of the request, by its path, else from the binary of the
        tool on the PATH of the host. The sandbox binds the program (`_program_binds`), the paths
        of the host that the tool reads when it starts (`_host_paths`), the read-only binds of the
        request, its config and ruleset files, and its writable directories read-write.

        A request that selects the network profile `kube-api` runs through the `relay` of its run
        (`devops_cli.sandbox.kube_api`). The command then starts `kubectl proxy` outside the
        sandbox, and bubblewrap, with no network of its own, starts the relay in the sandbox before
        `prlimit` and the tool. The sandbox binds the scratch directory of the relay read-only, and
        `KUBECONFIG` names the kubeconfig in it. Without a relay, the tool has no network.

        A relay for a request that selects no network profile raises `SandboxError`: only the
        request that selects `kube-api`, which only Popeye can select, reaches the API server. A
        request that selects `kube-api` with no relay raises it too.
        """
        if relay is not None and request.network is None:
            raise SandboxError(
                f"The review tool {request.tool} selects no network profile, so it cannot run "
                "through a relay to the Kubernetes API server"
            )
        if relay is None and request.network is not None:
            raise SandboxError(
                f"The review tool {request.tool} selects the network profile "
                f"{request.network.name}, which runs only through its relay"
            )
        if request.program is not None and not request.program.is_file():
            raise SandboxError(
                f"The program {request.program} of the review tool {request.tool} is not a file "
                "on this host"
            )
        binary = request.program or resolve_tool_binary(request.tool)
        if binary is None:
            raise SandboxError(f"The review tool {request.tool} is not installed on this host")
        root = request.workdir.resolve()
        limits = request.limits
        tool_command = [
            self._prlimit(),
            f"--cpu={limits.cpu_seconds}",
            f"--as={limits.address_space_bytes}",
            "--",
            str(binary),
            *_expand_targets(request.arguments, _resolved_targets(request)),
        ]
        inputs = (
            *request.read_only_binds,
            *_program_binds(binary),
            *_host_paths(request.tool),
            *request.config_files,
            *request.ruleset_files,
        )
        env = {**request.env, "GOMEMLIMIT": CONST_TOOL_GO_MEMORY_LIMIT}
        if relay is not None:
            tool_command = relay.sandbox_command(tool_command)
            inputs = (*inputs, *relay.read_only_binds)
            env = {**env, **relay.env}
        command = self._sandbox.build_bwrap_args(
            tool_command,
            request.cwd or root,
            repo_root=root,
            env=env,
            read_only_binds=list(dict.fromkeys(inputs)),
            writable_binds=request.writable_dirs,
        )
        return command if relay is None else relay.host_command(command)

    @staticmethod
    def _relay(request: ToolRequest) -> contextlib.AbstractContextManager[KubeApiRelay | None]:
        """The relay of the run of `request` to the API server, when it selects `kube-api`."""
        if request.network is None:
            return contextlib.nullcontext()
        from devops_cli.sandbox.kube_api import kube_api_relay

        return kube_api_relay(request.network.context)

    def run(self, request: ToolRequest) -> ToolResult:
        """Run the tool of `request` in the sandbox and answer how it ended and what ran.

        A request that cannot run raises `SandboxError` before anything starts: a tool that the
        host lacks, a target outside the tree, a bind that the sandbox refuses, or a context of
        `kube-api` that the kubeconfig of the user does not have. A host that cannot start the
        sandbox raises `SandboxUnavailableError` with the cause, and runs no tool. A host without
        a program of the `kube-api` relay raises it too, and runs no `kube-api` request. Its
        `refusal` does not change: the host can still run the tools that need no network.
        """
        with self._relay(request) as relay:
            try:
                command = self.command(request, relay)
                self._check_host()
            except SandboxUnavailableError as refused:
                self._refusal = refused.message
                raise
            version, binary_sha256 = resolve_tool_version_and_sha(request.tool, request.program)
            run = record_tool_run(
                request,
                version=version,
                binary_sha256=binary_sha256,
                executor=CONST_TOOL_EXECUTOR_SANDBOX,
            )
            return _start(
                run, command, cwd=request.workdir, wall_seconds=request.limits.wall_seconds
            )

    def settle(self, result: ToolResult, *, success: bool) -> None:
        """Do nothing: this executor keeps no records."""


class RecordingToolExecutor:
    """Passes each request to another executor and keeps the record of each run that started.

    A review gives its scanners one of these, so that the review can show what ran. A scanner
    reads the answer of the wrapped executor, unchanged. A request that the wrapped executor
    refuses starts no run, so it leaves no record. When the scanner settles a run, the settled
    record takes the place of the record of the run. Scans may run on several threads. Appending a
    record to a list, and setting one item of it, are atomic.
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

    def settle(self, result: ToolResult, *, success: bool) -> None:
        """Keep the settled record of `result` in the place of the record of its run.

        The record of the run is found by identity: two runs of one tool over one file can have
        equal records. A result that this executor did not start, or that is already settled, has
        no record here, and raises `ValueError`: its caller has a defect.
        """
        index = next((i for i, run in enumerate(self._runs) if run is result.run), None)
        if index is None:
            raise ValueError(
                f"The run of {result.run.tool} did not start here, or it is already settled"
            )
        self._executor.settle(result, success=success)
        self._runs[index] = result.settled(success=success)


__all__ = [
    "DirectToolExecutor",
    "KubeApiNetwork",
    "RecordingToolExecutor",
    "SandboxToolExecutor",
    "ToolExecutor",
    "ToolLimits",
    "ToolRequest",
    "ToolResult",
    "ToolRun",
    "record_tool_run",
]
