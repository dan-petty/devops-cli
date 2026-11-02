"""Google OSV-Scanner dependency vulnerability and SBOM scanner integration (#1146).

Runs osv-scanner 2.6.0 over lockfiles offline with a separately fetched database
snapshot (24 h TTL). Produces findings with AdvisoryAnchor and CycloneDX 1.5 inventory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from platformdirs import user_cache_dir

from devops_cli.ai.review_schema import DefectClass, Finding
from devops_cli.config.commands import BIN_OSV_SCANNER, build_osv_scan_cmd
from devops_cli.config.constants import (
    CONST_LOCKFILE_NAMES,
    CONST_MANIFEST_TO_LOCKFILES,
    CONST_OSV_CONFIG_FILE_NAMES,
    CONST_OSV_DB_DIR_ENV,
    CONST_OSV_DB_DIR_NAME,
    CONST_OSV_DB_FILE_NAME,
    CONST_OSV_OFFLINE_DB_TTL_SECONDS,
    CONST_SEVERITY_ALIASES,
)
from devops_cli.core.repo import list_repo_files, resolve_data_path
from devops_cli.review.anchors import AdvisoryAnchor
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome, ToolDataDir

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


def _extract_osv_severity(v: dict[str, Any]) -> str:
    """Extract and normalize severity from OSV record, never inferring from CVSS vectors (#1146)."""
    db_spec = v.get("database_specific")
    if isinstance(db_spec, dict):
        raw_sev = db_spec.get("severity")
        if isinstance(raw_sev, str) and raw_sev.strip():
            return CONST_SEVERITY_ALIASES.get(raw_sev.strip().upper(), "UNKNOWN")
    eco_spec = v.get("ecosystem_specific")
    if isinstance(eco_spec, dict):
        raw_sev = eco_spec.get("severity")
        if isinstance(raw_sev, str) and raw_sev.strip():
            return CONST_SEVERITY_ALIASES.get(raw_sev.strip().upper(), "UNKNOWN")
    return "UNKNOWN"


def _extract_fixed_versions(vuln: dict[str, Any]) -> list[str]:
    """Extract fixed version strings from an OSV vulnerability record."""
    fixed: list[str] = []
    for aff in vuln.get("affected") or []:
        for r in aff.get("ranges") or []:
            for ev in r.get("events") or []:
                if "fixed" in ev:
                    fixed.append(str(ev["fixed"]))
    return fixed


def _read_cached_snapshot_digest(stamp_file: Path, now: float) -> str | None:
    """Read unexpired cached snapshot digest from stamp file."""
    try:
        if not stamp_file.exists():
            return None
        data = json.loads(stamp_file.read_text(encoding="utf-8"))
        ts = float(data.get("timestamp", 0))
        digest = str(data.get("digest", "")).strip()
        if digest and (now - ts < CONST_OSV_OFFLINE_DB_TTL_SECONDS):
            return digest
    except OSError, ValueError:
        pass
    return None


def _compute_dir_snapshot_digest(base: Path) -> str:
    """Compute deterministic SHA-256 digest over cache directory files."""
    h = hashlib.sha256()
    has_files = False
    try:
        if base.exists() and base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.name != ".snapshot_digest":
                    h.update(p.name.encode())
                    h.update(str(p.stat().st_mtime_ns).encode())
                    has_files = True
    except OSError:
        pass

    if not has_files:
        h.update(b"osv-scanner-offline-v2.6.0")
    return f"sha256:{h.hexdigest()}"


def _save_snapshot_digest(stamp_file: Path, digest: str, timestamp: float) -> None:
    """Persist calculated snapshot digest to stamp file."""
    try:
        stamp_file.parent.mkdir(parents=True, exist_ok=True)
        stamp_file.write_text(
            json.dumps({"timestamp": timestamp, "digest": digest}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def get_or_compute_snapshot_digest(cache_dir: Path | None = None) -> str:
    """Retrieve or compute the OSV offline database snapshot SHA-256 digest with 24h TTL (#1146).

    With no `cache_dir`, it is `osv_db` under `data.cache_dir` of the loaded settings (#2447).
    """
    if cache_dir is None:
        from devops_cli.config.settings import load_settings

        cache_dir = resolve_data_path(load_settings().data.cache_dir) / "osv_db"
    base = cache_dir
    stamp_file = base / ".snapshot_digest"
    now = time.time()
    cached = _read_cached_snapshot_digest(stamp_file, now)
    if cached:
        return cached

    digest = _compute_dir_snapshot_digest(base)
    if base.exists():
        _save_snapshot_digest(stamp_file, digest, now)
    return digest


def parse_osv_scanner_output(
    data: dict[str, Any],
    snapshot_digest: str = "",
) -> tuple[list[Finding], dict[str, Any], dict[str, list[str]]]:
    """Parse osv-scanner JSON output into review findings, CycloneDX inventory, and locked packages (#1146)."""
    findings: list[Finding] = []
    locked_packages: dict[str, list[str]] = {}
    components: list[dict[str, Any]] = []

    results = data.get("results") or []
    for res in results:
        pkg_source = res.get("packageSource") or {}
        source_path = pkg_source.get("path") or ""

        for pkg_entry in res.get("packages") or []:
            pkg_info = pkg_entry.get("package") or {}
            name = pkg_info.get("name") or "unknown"
            version = pkg_info.get("version") or "unknown"
            ecosystem = pkg_info.get("ecosystem") or "generic"
            purl = pkg_info.get("purl") or f"pkg:{ecosystem.lower()}/{name}@{version}"

            locked_packages.setdefault(purl, []).append(version)
            components.append(
                {
                    "type": "library",
                    "name": name,
                    "version": version,
                    "purl": purl,
                    "bom-ref": purl,
                }
            )

            for vuln in pkg_entry.get("vulnerabilities") or []:
                vid = vuln.get("id") or "UNKNOWN"
                summary = vuln.get("summary") or vuln.get("details", "")[:120]
                severity = _extract_osv_severity(vuln)
                fixed_versions = _extract_fixed_versions(vuln)

                anchor = AdvisoryAnchor(
                    db="OSV",
                    snapshot=snapshot_digest,
                    advisory_id=vid,
                    purl=purl,
                    locked_version=version,
                )

                fix_msg = (
                    f"Upgrade '{name}' to {', '.join(fixed_versions)}"
                    if fixed_versions
                    else f"Upgrade '{name}' to a patched release"
                )

                loc = f"{source_path}:{name}" if source_path else f"{name}:{version}"
                finding = Finding(
                    severity=severity,
                    location=loc,
                    title=f"Vulnerable Dependency: {name} ({vid})",
                    description=summary,
                    fix=fix_msg,
                    confidence_score=None,
                    category=DefectClass.SUPPLY_CHAIN.value,
                )
                setattr(finding, "_tool", "osv-scanner")
                setattr(finding, "_anchor", anchor)
                if fixed_versions:
                    finding.properties["fixed_versions"] = fixed_versions
                findings.append(finding)

    cyclonedx_inventory = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"tools": [{"vendor": "Google", "name": "osv-scanner", "version": "2.6.0"}]},
        "components": components,
    }
    return findings, cyclonedx_inventory, locked_packages


def _is_lockfile(path: Path) -> bool:
    """Whether `path` has the name of a lockfile that osv-scanner reads."""
    return path.name in CONST_LOCKFILE_NAMES or path.suffix in (".lock", ".lockb")


def _tree_files(tree: Path) -> list[Path]:
    """The files of `tree` that git lists, tracked or not, and none that git ignores.

    A checkout holds large ignored trees: virtual environments, and a data directory with review
    sessions and agent worktrees that each have an environment of their own. A walk of every
    file read them all: 158 s of a one-file review (#2034).
    """
    return list_repo_files(tree) if tree.is_dir() else []


def detect_manifest_coverage_gaps(
    tree: Path,
    known_lockfiles: Sequence[Path] = (),
) -> list[str]:
    """Identify package manifests missing corresponding lockfiles (#1146).

    Only the files git lists count, so an ignored tree neither adds a gap nor hides one (#2034).
    """
    files = _tree_files(tree)
    locked = {p.name for p in known_lockfiles} | {p.name for p in files if _is_lockfile(p)}
    return [
        f"missing lockfile for {manifest}"
        for manifest, lockfiles in CONST_MANIFEST_TO_LOCKFILES.items()
        if locked.isdisjoint(lockfiles)
        for path in files
        if path.name == manifest
    ]


def _osv_db_base() -> Path:
    """The directory below which osv-scanner keeps its offline database:
    `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY`, else the user cache directory of the platform, which
    `platformdirs` names as the Go standard library does for osv-scanner."""
    configured = os.environ.get(CONST_OSV_DB_DIR_ENV)
    return Path(os.path.expanduser(configured) if configured else user_cache_dir())


class OsvScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Google OSV-Scanner (#1146)."""

    name: str = "osv-scanner"
    binary_name: str = BIN_OSV_SCANNER
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # osv-scanner reads `osv-scanner.toml` from the directory of each lockfile it scans.
    config_names: ClassVar[tuple[str, ...]] = CONST_OSV_CONFIG_FILE_NAMES

    def __init__(
        self, snapshot_digest: str | None = None, tool_executor: ToolExecutor | None = None
    ) -> None:
        super().__init__(tool_executor)
        self.snapshot_digest = snapshot_digest or get_or_compute_snapshot_digest()
        self.last_cyclonedx: dict[str, Any] = {}
        self.last_locked_packages: dict[str, list[str]] = {}

    def data_dirs(self) -> tuple[ToolDataDir, ...]:
        """The offline database of osv-scanner (#2096). The scan runs with
        `--offline-vulnerabilities`, so it reads only a database that was fetched before. The
        sandbox binds the database alone, and not the user cache directory that holds it."""
        base = _osv_db_base()
        return (ToolDataDir(CONST_OSV_DB_DIR_ENV, base, base / CONST_OSV_DB_DIR_NAME),)

    def ruleset_files(self, target_path: Any, cwd: Path, **kwargs: Any) -> tuple[Path, ...]:
        """The database file of each ecosystem in the offline database (#2130). The record
        digests their content, so its `ruleset_digest` changes when the database changes."""
        return tuple(
            path
            for directory in self.data_dirs()
            for path in sorted(directory.read.glob(f"*/{CONST_OSV_DB_FILE_NAME}"))
        )

    def build_command(
        self,
        target_path: Path,
        *,
        lockfiles: Sequence[Path] | None = None,
        offline: bool = True,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking osv-scanner."""
        targets = lockfiles or [target_path]
        return build_osv_scan_cmd(target_path, lockfiles=targets, offline=offline)

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw osv-scanner JSON payload into Finding models and inventory."""
        if not isinstance(data, dict):
            return []
        findings, cyclonedx, locked_packages = parse_osv_scanner_output(
            data, snapshot_digest=self.snapshot_digest
        )
        self.last_cyclonedx = cyclonedx
        self.last_locked_packages = locked_packages
        for f in findings:
            f.properties["cyclonedx_inventory"] = cyclonedx
        return findings

    def scan(
        self,
        target_path: Any,
        timeout: float = 300.0,
        *,
        lockfiles: Sequence[Path] | None = None,
        tree: Path | None = None,
        isolated: bool = False,
        **kwargs: Any,
    ) -> ScanOutcome:
        """Run osv-scanner over lockfiles with missing-lock coverage gap detection (#1146).

        A dry run starts no tool and gives the simulated outcome, as every other scan does.
        """
        scan_target = Path(target_path)
        if self._is_dry_run():
            return ScanOutcome(
                "dry-run", self.dry_run_scan(scan_target), "Dry-run simulation mode active"
            )
        scan_tree = tree or (scan_target if scan_target.is_dir() else scan_target.parent)
        effective_lockfiles = list(lockfiles or ())
        if not effective_lockfiles:
            if scan_target.is_file() and _is_lockfile(scan_target):
                effective_lockfiles = [scan_target]
            else:
                effective_lockfiles = [p for p in _tree_files(scan_tree) if _is_lockfile(p)]

        gaps = detect_manifest_coverage_gaps(scan_tree, known_lockfiles=effective_lockfiles)
        if not effective_lockfiles:
            if gaps:
                return ScanOutcome("coverage_gap", [], "; ".join(gaps))
            return ScanOutcome("clean", [], "No lockfiles found")

        cmd = self.build_command(effective_lockfiles[0], lockfiles=effective_lockfiles)

        def run_from(cwd: Path) -> ScanOutcome:
            files = partial(self._tool_files, effective_lockfiles, cwd, (), {})
            return self._run_scanner_command(cmd, cwd, effective_lockfiles, timeout, files)

        if isolated:
            with tempfile.TemporaryDirectory(prefix="devops-scan-osv-") as scan_dir:
                outcome = run_from(Path(scan_dir))
        else:
            outcome = run_from(scan_tree)

        if gaps and outcome.status == "ran":
            outcome.reason = "; ".join(gaps)
        return outcome


def run_osv_scan(
    targets: Sequence[Path],
    *,
    tree: Path,
    isolated: bool = False,
    snapshot_digest: str | None = None,
    tool_executor: ToolExecutor | None = None,
) -> ScanOutcome:
    """Execute osv-scanner over target lockfiles and return ScanOutcome (#1146).

    `tree` is the scanned tree that the caller gives. With no lockfile named, the scan looks for
    the lockfiles of `tree` (#2098).
    """
    scanner = OsvScanner(snapshot_digest=snapshot_digest, tool_executor=tool_executor)
    target_path = targets[0] if targets else tree
    return scanner.scan(target_path, lockfiles=targets, tree=tree, isolated=isolated)
