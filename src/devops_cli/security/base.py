"""Declarative base class for security and static analysis scanners."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple
from unittest.mock import NonCallableMock

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_SCAN_STATUS_PRECEDENCE,
    CONST_SCANNER_STDOUT_EXCERPT_CHARS,
)
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.core.binaries import check_binary
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import nearest_checkout
from devops_cli.dry_run import state as dry_run_state
from devops_cli.exceptions.sandbox import SandboxUnavailableError
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


def _has_builtin_patterns(scanner: Any) -> bool:
    """Check if scanner defines or enables built-in fallback patterns."""
    if getattr(scanner, "has_builtin_patterns", False):
        return True
    fb = getattr(scanner.__class__, "fallback_scan", None)
    return fb is not None and getattr(fb, "__qualname__", "") != "BaseSecurityScanner.fallback_scan"


def _parse_json_or_ndjson(raw_stdout: str) -> tuple[bool, Any]:
    """Parse stdout as standard single JSON document or multi-line NDJSON records."""
    text = raw_stdout.strip()
    if not text:
        return False, None
    try:
        return True, json.loads(text)
    except Exception:
        pass

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False, None

    records: list[Any] = []
    for ln in lines:
        try:
            records.append(json.loads(ln))
        except Exception:
            return False, None
    return True, records


def _cut(text: str, limit: int) -> str:
    """Return text cut to limit characters, ending in … when it was cut."""
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def masked_reason(reason: str) -> str:
    """Return a failure reason masked, then cut to `CONST_MAX_ERROR_DETAIL_LENGTH`.

    Masking comes first: cutting first can leave part of a secret the masking patterns no longer
    match.
    """
    return _cut(mask_secrets(reason), CONST_MAX_ERROR_DETAIL_LENGTH)


class ScanOutcome(list[Finding]):
    """The outcome of executing a security scanner.

    The reason reaches SARIF notifications, the CLI and review.md, and often quotes a scanner's
    output or an exception, so `masked_reason` masks and bounds it here, for every producer.

    The reason says why the scan as a whole fell short. `unscanned` says which files a scan that
    ran left out, each with its reason (#1144); a scan that left files out is a `coverage_gap`.
    """

    def __init__(
        self,
        status: str,
        findings: list[Finding] | None = None,
        reason: str = "",
        unscanned: Mapping[str, str] | None = None,
        failed_files: Mapping[str, str] | None = None,
        file_statuses: Mapping[str, str] | None = None,
    ) -> None:
        items = list(findings) if findings is not None else []
        super().__init__(items)
        self.status: str = status
        self.findings: list[Finding] = items
        self.reason: str = masked_reason(reason)
        self.unscanned: dict[str, str] = dict(unscanned or {})
        self.failed_files: dict[str, str] = dict(failed_files or {})
        self.file_statuses: dict[str, str] = dict(file_statuses or {})
        # When the scanner started and finished, in UTC; set by `BaseSecurityScanner.scan`.
        self.started_utc: str | None = None
        self.ended_utc: str | None = None

    def __repr__(self) -> str:
        return (
            f"ScanOutcome(status={self.status!r}, findings={self.findings!r}, "
            f"reason={self.reason!r}, unscanned={self.unscanned!r}, "
            f"failed_files={self.failed_files!r}, file_statuses={self.file_statuses!r})"
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ScanOutcome):
            return (
                self.status,
                self.findings,
                self.reason,
                self.unscanned,
                self.failed_files,
                self.file_statuses,
            ) == (
                other.status,
                other.findings,
                other.reason,
                other.unscanned,
                other.failed_files,
                other.file_statuses,
            )
        return super().__eq__(other)


def merge_outcomes(outcomes: list[ScanOutcome]) -> ScanOutcome:
    """Combine the outcomes of one scanner's runs, keeping every finding, the worst status, each
    distinct reason and every file left out, from the first run's start to the last run's end."""
    status = min(
        (o.status for o in outcomes),
        key=lambda s: (
            CONST_SCAN_STATUS_PRECEDENCE.index(s) if s in CONST_SCAN_STATUS_PRECEDENCE else 0
        ),
    )
    findings = [f for o in outcomes for f in o.findings]
    reasons = dict.fromkeys(o.reason for o in outcomes if o.reason)
    unscanned = {path: why for o in outcomes for path, why in o.unscanned.items()}
    failed_files = {
        path: why for o in outcomes for path, why in getattr(o, "failed_files", {}).items()
    }
    file_statuses = {
        path: st for o in outcomes for path, st in getattr(o, "file_statuses", {}).items()
    }
    merged = ScanOutcome(
        status,
        findings,
        "; ".join(reasons),
        unscanned,
        failed_files=failed_files,
        file_statuses=file_statuses,
    )
    starts = [o.started_utc for o in outcomes if o.started_utc]
    ends = [o.ended_utc for o in outcomes if o.ended_utc]
    merged.started_utc, merged.ended_utc = min(starts, default=None), max(ends, default=None)
    return merged


class MaterializedTargets(NamedTuple):
    """Targets linked or copied under a scan's working directory, each with the path it came from.

    A scanner names each by its path relative to the working directory, its path in the scanned
    tree, and reports what it finds under that name, which `origin` maps back (#1079).
    """

    origins: dict[str, Path]

    @property
    def names(self) -> list[str]:
        """The targets' paths relative to the working directory, in the order they were given,
        each led by `./`: a file the tree names `-`, `--autofix` or `--config=x.yml` is still a
        file to the scanner, never an option or its stdin, as an absolute path never was."""
        return [os.path.join(os.curdir, name) for name in self.origins]

    def origin(self, name: str) -> str:
        """The path a target the scanner reported as `name`, with or without the `./` it was
        named with, came from; `name` if none did."""
        return str(self.origins.get(Path(name).as_posix(), name))

    def tree_path(self, name: str) -> str:
        """The path of the target relative to the scanned tree, as a posix string; `name` if none did."""
        clean = Path(name).as_posix()
        if clean in self.origins:
            return clean
        for rel_name, orig in self.origins.items():
            if str(orig) == name or str(orig.resolve()) == clean:
                return rel_name
        return name.removeprefix("./") if name.startswith("./") else name


def _scan_root(root: Path | str) -> Path | None:
    """The directory to relativize scan paths against: `root` resolved, or None when it is no
    directory."""
    try:
        resolved = Path(root).resolve()
    except OSError, RuntimeError:
        return None
    return resolved if resolved.is_dir() else None


def _relativize_against(target: Path, candidate: Path) -> str | None:
    """Relative POSIX path if target lies inside candidate, else None."""
    try:
        p_res = target.resolve()
        if p_res.is_relative_to(candidate) and p_res != candidate:
            return p_res.relative_to(candidate).as_posix()
    except OSError, RuntimeError, ValueError:
        pass
    try:
        if target.is_relative_to(candidate) and target != candidate:
            return target.relative_to(candidate).as_posix()
    except OSError, RuntimeError, ValueError:
        pass
    return None


def relativize_scan_path(path_str: str, root: Path | str) -> str:
    """Normalize a scan finding's path string to be relative to `root`, the scanned tree that the
    caller gives.

    Strips any leading `./`, and if `path_str` is absolute, relativizes it against `root`. A path
    outside `root` is returned normalized: the working directory of the process is no root (#2098).
    """
    clean = str(path_str).strip()
    if not clean or clean.startswith(("<", "(")):
        return clean

    if clean.startswith(f".{os.sep}") or clean.startswith("./"):
        clean = clean[2:]

    p = Path(clean)
    if not p.is_absolute():
        return p.as_posix()

    scan_root = _scan_root(root)
    rel = _relativize_against(p, scan_root) if scan_root is not None else None
    return rel if rel is not None else p.as_posix()


def _file_inside(target: Path, root: Path) -> Path | None:
    """The regular file `target` resolves to when it lies inside `root`, else None.

    Resolving follows every link, so no link in the tree leads a scan out of it.
    """
    try:
        real = target.resolve(strict=True)
    except OSError, RuntimeError:
        return None
    return real if real.is_relative_to(root) and real.is_file() else None


def _link_or_copy(source: Path, destination: Path) -> bool:
    """Hard-link `source` at `destination`, or copy it when linking fails, as across
    filesystems. A file already at `destination` stays: False."""
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists(follow_symlinks=False):
            return False
        try:
            os.link(source, destination)
        except OSError:
            shutil.copyfile(source, destination)
    except OSError as exc:
        logger.debug("Could not place scan target %s: %s", source, exc)
        return False
    return True


def materialize_targets(targets: Iterable[Path], tree: Path, workdir: Path) -> MaterializedTargets:
    """Place each target file that lies in `tree` under `workdir` at its path in the tree.

    A scanner run from `workdir` then names every target relative to its working directory,
    and finds no other file of the tree there: no config, ignore or rule file it did not name
    (#972, #1079). A target that resolves outside the tree, through a link or otherwise, is left
    out, and a file named twice, directly and through a link, is placed once.
    """
    root = tree.resolve()
    origins: dict[str, Path] = {}
    for target in targets:
        if (real := _file_inside(target, root)) is None:
            continue
        name = real.relative_to(root).as_posix()
        if name not in origins and _link_or_copy(real, workdir / name):
            origins[name] = target
    return MaterializedTargets(origins)


def _scan_targets(target_path: Any) -> tuple[Path, ...]:
    """The files or directories a scan reads, as absolute paths in the scanned tree.

    A review's isolated scan links its files under a scratch directory. The tree holds the files
    it was given, so those are the targets. A relative path stands in the current directory. A
    name that is no path, such as the image `ghcr.io/org/img:latest`, stands there as a path that
    does not exist.
    """
    if isinstance(target_path, MaterializedTargets):
        paths: Iterable[Any] = target_path.origins.values()
    elif isinstance(target_path, list | tuple):
        paths = target_path
    else:
        paths = (target_path,)
    return tuple(Path(path).resolve() for path in paths)


def _scan_tree(targets: tuple[Path, ...]) -> Path:
    """The tree that holds `targets`: the checkout of their common directory, else that directory.

    The common directory is the nearest one that exists, because a target can name no file.
    """
    common = Path(os.path.commonpath(targets))
    directory = next(path for path in (common, *common.parents) if path.is_dir())
    return nearest_checkout(directory) or directory


def _named_files(
    names: Sequence[str], targets: Iterable[Path], *, up_to: Path | None = None
) -> tuple[Path, ...]:
    """The files called one of `names` in the directory of each target, nearest first, each once.

    With `up_to`, also in each directory above it that is inside `up_to`: a tool that looks for its
    config file there takes the nearest one, and any of them may change what it does.
    """
    found: dict[Path, None] = {}
    for target in targets:
        directory = target if target.is_dir() else target.parent
        ancestors = (directory, *directory.parents) if up_to else (directory,)
        for here in (d for d in ancestors if up_to is None or d.is_relative_to(up_to)):
            candidates = (here / name for name in names)
            found.update(dict.fromkeys(path for path in candidates if path.is_file()))
    return tuple(found)


class ToolFiles(NamedTuple):
    """The files a scan's tool reads besides its targets: its config files and its ruleset files.

    A review records a digest of each group (#772).
    """

    config: tuple[Path, ...] = ()
    ruleset: tuple[Path, ...] = ()


def _evaluate_preflight(
    scanner: BaseSecurityScanner, target_path: Any, **kwargs: Any
) -> ScanOutcome | None:
    """Evaluate dry-run, applicability, and binary presence prior to command execution."""
    if scanner._is_dry_run():
        applicable, reason = scanner.is_applicable(target_path, **kwargs)
        if not applicable:
            return ScanOutcome("not_applicable", [], reason)
        return ScanOutcome(
            "dry-run",
            scanner.dry_run_scan(target_path, **kwargs),
            "Dry-run simulation mode active",
        )

    applicable, reason = scanner.is_applicable(target_path, **kwargs)
    if not applicable:
        logger.debug(
            "Scanner '%s' not applicable to target %s: %s",
            scanner.name,
            target_path,
            reason,
        )
        return ScanOutcome(
            "not_applicable",
            [],
            reason or f"Scanner {scanner.name} is not applicable to target",
        )

    if not scanner._check_binary():
        if _has_builtin_patterns(scanner):
            logger.debug(
                "Scanner binary '%s' not found; executing built-in fallback patterns.",
                scanner.binary_name,
            )
            return ScanOutcome(
                "built-in patterns",
                scanner.fallback_scan(target_path),
                f"Binary '{scanner.binary_name}' not found; used built-in patterns",
            )
        logger.debug("Scanner binary '%s' not found on PATH.", scanner.binary_name)
        return ScanOutcome(
            "unavailable",
            [],
            f"Binary '{scanner.binary_name}' not found on PATH",
        )

    return None


def _one_line(text: str, limit: int) -> str:
    """Return text on one line, each run of whitespace a single space, cut to limit characters."""
    return _cut(" ".join(text.split()), limit)


def _non_json_failure_reason(proc: Any) -> str:
    """Say how the scanner exited, and when it printed something other than JSON, quote its start.

    The output is masked before the quote is cut from it, so the cut cannot split a secret;
    `ScanOutcome` masks and bounds the whole reason.
    """
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if not stdout:
        return f"Scanner exited with code {proc.returncode}: {stderr}"
    reason = (
        f"Scanner exited with code {proc.returncode}; output was not JSON, starting "
        f'"{_one_line(mask_secrets(stdout), CONST_SCANNER_STDOUT_EXCERPT_CHARS)}"'
    )
    if stderr:
        reason = f"{reason}; stderr: {stderr}"
    return " ".join(reason.split())


def _handle_non_json_output(
    scanner: BaseSecurityScanner, proc: Any, target_path: Any
) -> ScanOutcome:
    """Handle scanner execution result when stdout does not contain valid JSON."""
    if proc.returncode != 0:
        if _has_builtin_patterns(scanner):
            return ScanOutcome(
                "built-in patterns",
                scanner.fallback_scan(target_path),
                f"Scanner exited with code {proc.returncode}; used built-in patterns",
            )
        return ScanOutcome("failed", [], _non_json_failure_reason(proc))
    raw_findings = scanner.parse_output(proc.stdout, target_path)
    if raw_findings:
        return ScanOutcome("ran", raw_findings)
    if _has_builtin_patterns(scanner):
        return ScanOutcome(
            "built-in patterns",
            scanner.fallback_scan(target_path),
            "Non-JSON output; used built-in patterns",
        )
    return ScanOutcome("ran", [])


def _handle_json_output(
    scanner: BaseSecurityScanner,
    data: Any,
    returncode: int,
    stderr: str,
    target_path: Any,
) -> ScanOutcome:
    """Handle scanner execution result with parsed JSON payload."""
    findings = scanner.parse_output(data, target_path)
    if not findings and returncode != 0:
        if _has_builtin_patterns(scanner):
            fb = scanner.fallback_scan(target_path)
            if fb:
                return ScanOutcome(
                    "built-in patterns",
                    fb,
                    f"Scanner exited with code {returncode}; used built-in patterns",
                )
        return ScanOutcome("failed", [], f"Scanner exited with code {returncode}: {stderr.strip()}")
    unscanned = scanner.unscanned_files(data, target_path)
    return ScanOutcome("coverage_gap" if unscanned else "ran", findings, unscanned=unscanned)


def _utc_now() -> str:
    """Return the current UTC time in SARIF's millisecond date-time form."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_mocked(module_name: str | None, attr_name: str) -> Any:
    """Return mock object if attribute on module is a NonCallableMock, else None."""
    if not module_name:
        return None
    mod = sys.modules.get(module_name)
    if mod is None:
        return None
    target = getattr(mod, attr_name, None)
    return target if isinstance(target, NonCallableMock) else None


def _patched_run_subprocess(scanner_module: str) -> Any:
    """The `run_subprocess` a test patched in this module or in `scanner_module`, else None."""
    own = getattr(sys.modules.get(scanner_module), "run_subprocess", None)
    return next((c for c in (run_subprocess, own) if isinstance(c, NonCallableMock)), None)


class ToolDataDir(NamedTuple):
    """A directory of data that a tool reads, such as a database: the environment variable that
    names it to the tool, the directory that the variable names, and the directory that the tool
    reads, at or below it, which the sandbox binds read-only (#2096)."""

    variable: str
    directory: Path
    read: Path


class ToolCacheDir(NamedTuple):
    """A directory that a tool keeps its cache in, outside the tree, and the environment variable
    that names it to the tool. The directory stays after the run, and the sandbox binds it
    read-write (#2096)."""

    variable: str
    directory: Path


class ScannerConfigFile(NamedTuple):
    """A config or ignore file devops-cli hands a scanner, and the flag that names it."""

    flag: str
    name: str
    text: str


class BaseSecurityScanner(ABC):
    """Abstract base class for declarative security and static analysis tools."""

    name: str = "base_scanner"
    binary_name: str = "scanner"
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # The files an isolated scan hands the scanner in place of the config and ignore files it
    # would read from its working directory or the scanned tree (#972).
    isolation_files: ClassVar[tuple[ScannerConfigFile, ...]] = ()
    # The names under which the tool finds a config file of its own that a review does not hand it,
    # in the directory of each target, and in each directory above it up to the tree when
    # `config_search_upward` (#772).
    config_names: ClassVar[tuple[str, ...]] = ()
    config_search_upward: ClassVar[bool] = False

    def __init__(self, tool_executor: ToolExecutor | None = None) -> None:
        """Start the scanner's tool through `tool_executor`; without one, as a child process.

        A review gives each scanner the sandbox executor of the review. A scan outside a review,
        as `devops scan` starts one, gets no executor and runs its tool as a child process.
        """
        if tool_executor is None:
            from devops_cli.security.tool_executor import DirectToolExecutor

            tool_executor = DirectToolExecutor()
        self._tool_executor: ToolExecutor = tool_executor

    @abstractmethod
    def build_command(self, target_path: Any, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking the scanner binary.

        `kwargs` holds the scan's arguments and `cwd`, the directory that the command starts in.
        """

    @abstractmethod
    def parse_output(self, data: Any, target_path: Any) -> list[Finding]:
        """Parse raw scanner JSON/structure payload into Finding models."""

    def unscanned_files(self, data: Any, target_path: Any) -> dict[str, str]:
        """The targets the scanner's own report leaves out, each with its reason: none by default.

        A scanner that lists the files it scanned opts in here, as Semgrep does (#1144). The
        outcome of a run that leaves files out is a coverage gap.
        """
        return {}

    def is_applicable(self, target_path: Any, **kwargs: Any) -> tuple[bool, str]:
        """Determine if scanner applies to the given target and kwargs.

        Returns (True, "") if applicable, or (False, reason) if not applicable.
        """
        return True, ""

    def ruleset_files(self, target_path: Any, cwd: Path, **kwargs: Any) -> tuple[Path, ...]:
        """The rule files and the database metadata files the scan's tool reads: none by default.

        A tool whose rules are in its binary reads none, and the version of the binary names them.
        `kwargs` are those the scan passed to `build_command`, and `cwd` is where the tool starts.
        """
        return ()

    def _tool_files(
        self, target_path: Any, cwd: Path, handed: Sequence[str], scan_kwargs: Mapping[str, Any]
    ) -> ToolFiles:
        """The config files and the ruleset files of a scan: the files devops-cli handed the tool
        (`handed` holds each flag and the path after it), the config files the tool finds on its
        own, and the rule files it reads."""
        targets = _scan_targets(target_path)
        up_to = _scan_tree(targets) if self.config_search_upward else None
        return ToolFiles(
            config=(
                *(Path(path) for path in handed[1::2]),
                *_named_files(self.config_names, targets, up_to=up_to),
            ),
            ruleset=self.ruleset_files(target_path, cwd, **scan_kwargs),
        )

    def data_dirs(self) -> tuple[ToolDataDir, ...]:
        """The directories of data that the tool reads besides its targets and its rules, such as
        a database that a fetch step got before the scan: none by default.

        The sandbox has no network and a new HOME, so a tool there finds only the data that the
        request names. For each directory that the tool reads and that exists, the request names
        its directory to the tool by its variable, and binds what the tool reads read-only.
        """
        return ()

    def cache_dirs(self, tree: Path) -> tuple[ToolCacheDir, ...]:
        """The directories, outside `tree`, that the tool keeps its cache of `tree` in: none by
        default. Each directory is made before the run, named to the tool by its variable, and
        named in the request as writable."""
        return ()

    def fallback_scan(self, target_path: Any) -> list[Finding]:
        """Execute fallback scan logic when primary binary is unavailable."""
        return []

    def dry_run_scan(self, target_path: Any, **kwargs: Any) -> list[Finding]:
        """Return simulated findings for dry-run simulation mode."""
        return [
            Finding(
                severity="LOW",
                location=f"{target_path}:simulation",
                title=f"[{self.name.upper()}] [DRY-RUN] Simulated Security Scan",
                description=f"Simulation mode active for {self.name} scanner.",
                fix="No action required (simulation mode)",
            )
        ]

    def _is_dry_run(self) -> bool:
        """Determine whether dry-run mode is active, honoring module-level test mocks."""
        for mod_name in (
            "devops_cli.dry_run.state",
            "devops_cli.security.base",
            self.__class__.__module__,
        ):
            mock_dr = _is_mocked(mod_name, "is_dry_run")
            if mock_dr is not None:
                return bool(mock_dr())
        return dry_run_state.is_dry_run()

    def _check_binary(self) -> bool:
        """Verify binary presence on PATH, honoring module-level test mocks."""
        for mod_name in ("devops_cli.security.base", self.__class__.__module__):
            mock_cb = _is_mocked(mod_name, "check_binary")
            if mock_cb is not None:
                return bool(mock_cb(self.binary_name))
        if _patched_run_subprocess(self.__class__.__module__) is not None:
            return True
        return check_binary(self.binary_name)

    def _run_tool(
        self,
        cmd: list[str],
        cwd_dir: Path,
        target_path: Any,
        timeout: float,
        files: Callable[[], ToolFiles] = ToolFiles,
    ) -> Any:
        """Start `cmd` through the tool executor and answer as a finished process, honoring
        module-level test mocks. `files` names the config files and the ruleset files the tool
        reads, so the record of the run holds a digest of each.

        A run that ran out of time raises `subprocess.TimeoutExpired`, as the process would.
        """
        if (patched := _patched_run_subprocess(self.__class__.__module__)) is not None:
            return patched(cmd, cwd=cwd_dir, timeout=timeout, check=False, input="")
        # Imported here: the executor pulls in the sandbox and the canary, which a scanner that
        # never runs does not need.
        from devops_cli.security.tool_executor import ToolLimits, ToolRequest

        targets = _scan_targets(target_path)
        tree = _scan_tree(targets)
        read = files()
        data = [directory for directory in self.data_dirs() if directory.read.is_dir()]
        caches = self.cache_dirs(tree)
        for cache in caches:
            cache.directory.mkdir(parents=True, exist_ok=True)
        request = ToolRequest(
            tool=cmd[0],
            arguments=tuple(cmd[1:]),
            workdir=tree,
            cwd=cwd_dir,
            targets=targets,
            config_files=read.config,
            ruleset_files=read.ruleset,
            read_only_binds=tuple(directory.read for directory in data),
            writable_dirs=tuple(cache.directory for cache in caches),
            env={
                **{directory.variable: str(directory.directory) for directory in data},
                **{cache.variable: str(cache.directory) for cache in caches},
            },
            limits=ToolLimits.for_tool(cmd[0], wall_seconds=timeout),
        )
        result = self._tool_executor.run(request)
        if result.timed_out:
            raise subprocess.TimeoutExpired(cmd, timeout, result.stdout, result.stderr)
        return subprocess.CompletedProcess(cmd, result.exit_code, result.stdout, result.stderr)

    def _resolve_cwd(self, target_path: Any, **kwargs: Any) -> Path:
        """The directory a scan that is not isolated starts in: the nearest directory on disk that
        holds its targets, the targets that exist when some do.

        The targets are the caller's. A relative target, such as the name of an image, is a path in
        the directory that the caller runs in, so its scan starts there. A scan with no target
        starts in the temporary directory, where it finds no file of a tree. No scanner reads the
        working directory of the process for itself (#2098).

        A scanner that must run elsewhere reads its scan's `kwargs` here, as Semgrep does (#1144).
        """
        targets = _scan_targets(target_path)
        if not targets:
            return Path(tempfile.gettempdir())
        existing = [target for target in targets if target.exists()]
        common = Path(os.path.commonpath(existing or targets))
        return next(path for path in (common, *common.parents) if path.is_dir())

    def _run_scanner_command(
        self,
        cmd: list[str],
        cwd_dir: Path,
        target_path: Any,
        timeout: float,
        files: Callable[[], ToolFiles] = ToolFiles,
    ) -> ScanOutcome:
        """Execute scanner command subprocess with output parsing and fallback handling.

        The scanner gets an empty stdin, never the caller's, such as a stdio MCP server's
        request stream, so no target it is named makes it read one (#1079)."""

        @trace_span(f"security.{self.name}")
        def _run() -> ScanOutcome:
            try:
                proc = self._run_tool(cmd, cwd_dir, target_path, timeout, files)
                is_valid_json, data = _parse_json_or_ndjson(proc.stdout)
                if not is_valid_json:
                    return _handle_non_json_output(self, proc, target_path)
                return _handle_json_output(
                    self, data, proc.returncode, proc.stderr or "", target_path
                )
            except subprocess.TimeoutExpired as exc:
                timed_out = f"timed out after {exc.timeout:g} s"
                return self._failed_run(
                    target_path, timed_out, f"{timed_out}; used built-in patterns"
                )
            except SandboxUnavailableError as refused:
                # The tool did not run, in the sandbox or outside it (#2096).
                return ScanOutcome("coverage_gap", [], refused.message)
            except Exception as exc:
                return self._failed_run(
                    target_path,
                    f"Scanner execution failed: {exc}",
                    f"Scanner error: {exc}; used built-in patterns",
                )

        return _run()

    def _failed_run(self, target_path: Any, failed: str, fallen_back: str) -> ScanOutcome:
        """The outcome of a run that raised: the built-in patterns' findings with the
        `fallen_back` reason when the scanner has them, else a failure with the `failed` one.
        A timeout's reason says how long the run had, never the command (#1079)."""
        logger.debug("Scanner '%s' failed: %s", self.name, failed)
        if _has_builtin_patterns(self):
            return ScanOutcome("built-in patterns", self.fallback_scan(target_path), fallen_back)
        return ScanOutcome("failed", [], failed)

    def scan(
        self,
        target_path: Any,
        timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
        *,
        isolated: bool = False,
        **kwargs: Any,
    ) -> ScanOutcome:
        """Execute scanner with applicability pre-flight checking, timeouts, and fallback recovery.

        An `isolated` scan takes nothing from the scanned tree: a review's (#972).
        """
        started = _utc_now()
        outcome = self._execute(target_path, timeout, isolated, **kwargs)
        outcome.started_utc, outcome.ended_utc = started, _utc_now()
        return outcome

    def _execute(
        self, target_path: Any, timeout: float, isolated: bool, **kwargs: Any
    ) -> ScanOutcome:
        """Run the pre-flight checks, then the scanner command."""
        preflight = _evaluate_preflight(self, target_path, **kwargs)
        if preflight is not None:
            return preflight
        if not isolated:
            return self._run_built_command(
                target_path, self._resolve_cwd(target_path, **kwargs), timeout, [], **kwargs
            )
        with tempfile.TemporaryDirectory(prefix=f"devops-scan-{self.name}-") as scan_dir:
            workdir = Path(scan_dir)
            handed = self._hand_isolation_files(workdir)
            targets = self.isolated_targets(target_path, workdir, **kwargs)
            return self._run_built_command(targets, workdir, timeout, handed, **kwargs)

    def _run_built_command(
        self, target_path: Any, cwd: Path, timeout: float, handed: list[str], **kwargs: Any
    ) -> ScanOutcome:
        """Build the scanner's command for `target_path` and run it from `cwd`, with the flags
        that name the files devops-cli handed it."""
        cmd = self.build_command(target_path, cwd=cwd, **kwargs)
        if not cmd:
            return ScanOutcome("not_applicable", [], f"Empty command generated for {self.name}")
        files = partial(self._tool_files, target_path, cwd, handed, kwargs)
        return self._run_scanner_command([*cmd, *handed], cwd, target_path, timeout, files)

    def isolated_targets(self, target_path: Any, workdir: Path, **kwargs: Any) -> Any:
        """The targets an isolated scan names from `workdir`: as given.

        A scanner that reads a target outside its working directory differently from one
        inside it opts in to `materialize_targets` here, as Semgrep does (#1079).
        """
        return target_path

    def _hand_isolation_files(self, workdir: Path) -> list[str]:
        """Write the scanner's isolation files into `workdir`, returning the flags that name them.

        An isolated scan runs in `workdir`, a temporary directory outside the scanned tree, so
        the scanner finds no config or ignore file of the tree's in its working directory, and
        each it would look for in the tree is named explicitly: devops-cli's own (#972).
        """
        flags: list[str] = []
        for config_file in self.isolation_files:
            path = workdir / config_file.name
            path.write_text(config_file.text, encoding="utf-8")
            flags.extend((config_file.flag, str(path)))
        return flags


__all__ = [
    "BaseSecurityScanner",
    "MaterializedTargets",
    "ScanOutcome",
    "ScannerConfigFile",
    "ToolFiles",
    "materialize_targets",
    "merge_outcomes",
    "relativize_scan_path",
]
