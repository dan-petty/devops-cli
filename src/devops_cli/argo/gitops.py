"""Automated GitOps drift detection, debounced change aggregation, and webhook synchronization.

Cross-Platform Observability & Watch Architecture:
- Uses resilient, debounced filesystem polling (configurable via `--interval` / `-i` down to 0.1s)
  to ensure cross-platform compatibility across Docker devcontainers, Kubernetes sidecars,
  and remote NFS/SMB mounts where OS-level inotify notifications do not propagate across
  hypervisor or network boundary interfaces.
- For application-targeted reconciliation, the default authenticated REST API (`mode="api"`)
  dispatches directly to `/api/v1/applications/{app_name}/sync`.
- When `mode="webhook"` is selected, dispatches Git-provider push payloads to `/api/webhook`.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from devops_cli.config import load_settings
from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.config.settings import get_argocd_token
from devops_cli.core.repo import find_repo_root, is_ignored_by_git
from devops_cli.http.validation import validate_service_url
from devops_cli.models.argo import GitOpsDriftEvent, GitOpsSyncTriggerResult
from devops_cli.security.sanitizer import mask_secrets, mask_uri_credentials
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span

if TYPE_CHECKING:
    from devops_cli.output.models import TablePayload

_MANIFEST_EXTENSIONS = {".yaml", ".yml"}
_MANIFEST_NAMES = {"chart.yaml", "kustomization.yaml", "values.yaml"}


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file content."""
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""


def is_manifest_file(path: Path) -> bool:
    """Determine whether a file qualifies as a Kubernetes or Helm manifest."""
    name_lower = path.name.lower()
    suffix_lower = path.suffix.lower()
    if suffix_lower in _MANIFEST_EXTENSIONS:
        return True
    return name_lower in _MANIFEST_NAMES


def should_ignore_dir(path_or_name: str | Path, repo_root: Path | None = None) -> bool:
    """Check whether a directory segment should be ignored during traversal."""
    p = Path(path_or_name)
    root = repo_root or find_repo_root(p)
    return is_ignored_by_git(root, p)


def _scan_directory_manifests(root: Path, state: dict[Path, tuple[float, str]]) -> None:
    """Recursively scan a directory tree and record manifest modification timestamps and hashes."""
    repo_root = find_repo_root(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not is_ignored_by_git(repo_root, dp / d)]
        for fname in filenames:
            fpath = dp / fname
            if is_ignored_by_git(repo_root, fpath) or not is_manifest_file(fpath):
                continue
            try:
                resolved = fpath.resolve()
                mtime = resolved.stat().st_mtime
                sha = compute_file_hash(resolved)
                state[resolved] = (mtime, sha)
            except OSError:
                continue


def compute_manifest_state(
    paths: Sequence[Path | str],
) -> dict[Path, tuple[float, str]]:
    """Scan designated manifest paths and return a mapping of resolved Path to (mtime, sha256)."""
    state: dict[Path, tuple[float, str]] = {}
    for p in paths:
        target = Path(p).resolve()
        if not target.exists():
            continue
        if target.is_file() and is_manifest_file(target):
            try:
                state[target] = (target.stat().st_mtime, compute_file_hash(target))
            except OSError:
                continue
        elif target.is_dir():
            _scan_directory_manifests(target, state)
    return state


def scan_manifest_drift(
    prev_state: dict[Path, tuple[float, str]],
    curr_state: dict[Path, tuple[float, str]],
) -> list[GitOpsDriftEvent]:
    """Compare previous and current manifest states to produce a list of drift events."""
    events: list[GitOpsDriftEvent] = []
    now = time.time()

    # Detect created and modified
    for path, (mtime, sha) in curr_state.items():
        prev = prev_state.get(path)
        if prev is None:
            events.append(
                GitOpsDriftEvent(
                    path=str(path),
                    change_type="created",
                    timestamp=now,
                    file_hash=sha,
                )
            )
        elif prev[1] != sha or prev[0] != mtime:
            events.append(
                GitOpsDriftEvent(
                    path=str(path),
                    change_type="modified",
                    timestamp=now,
                    file_hash=sha,
                )
            )

    # Detect deleted
    for path in prev_state:
        if path not in curr_state:
            events.append(
                GitOpsDriftEvent(
                    path=str(path),
                    change_type="deleted",
                    timestamp=now,
                    file_hash="",
                )
            )

    events.sort(key=lambda e: e.path)
    return events


def _get_baseline_cache_file(paths: Sequence[Path | str]) -> Path:
    """Resolve deterministic cache path for manifest baseline state under data directory."""
    key_source = "|".join(sorted(str(Path(p).resolve()) for p in paths))
    key_hash = hashlib.sha256(key_source.encode()).hexdigest()[:16]
    settings = load_settings()
    cache_dir = Path(settings.data.dir).resolve() / "gitops"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"manifest_baseline_{key_hash}.json"


def load_persisted_manifest_state(
    paths: Sequence[Path | str],
) -> dict[Path, tuple[float, str]] | None:
    """Load saved manifest baseline state from cache if available."""
    cache_file = _get_baseline_cache_file(paths)
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        state: dict[Path, tuple[float, str]] = {}
        for p_str, (mtime, sha) in data.items():
            state[Path(p_str)] = (float(mtime), str(sha))
        return state
    except Exception:
        return None


def save_persisted_manifest_state(
    paths: Sequence[Path | str], state: dict[Path, tuple[float, str]]
) -> None:
    """Persist manifest state snapshot to disk."""
    try:
        cache_file = _get_baseline_cache_file(paths)
        data = {str(p): list(val) for p, val in state.items()}
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def inspect_git_manifest_drift(paths: Sequence[Path | str]) -> list[GitOpsDriftEvent]:
    """Inspect working tree for uncommitted or modified manifests using git status."""
    from devops_cli.core.process import run_subprocess

    resolved_paths = [str(Path(p).resolve()) for p in paths if Path(p).exists()]
    if not resolved_paths:
        return []
    try:
        cmd = ["git", "status", "--porcelain", "--", *resolved_paths]
        res = run_subprocess(cmd, check=False, capture_output=True, timeout=5.0)
        if res.returncode != 0:
            return []
        events: list[GitOpsDriftEvent] = []
        now = time.time()
        for line in res.stdout.strip().splitlines():
            if len(line) < 4:
                continue
            status_code = line[:2].strip()
            rel_path = line[3:].strip().strip('"')
            fpath = Path(rel_path).resolve()
            if not is_manifest_file(fpath):
                continue
            if "D" in status_code:
                ctype = "deleted"
                fhash = ""
            elif "??" in status_code or "A" in status_code:
                ctype = "created"
                fhash = compute_file_hash(fpath) if fpath.exists() else ""
            else:
                ctype = "modified"
                fhash = compute_file_hash(fpath) if fpath.exists() else ""
            events.append(
                GitOpsDriftEvent(
                    path=str(fpath),
                    change_type=ctype,
                    timestamp=now,
                    file_hash=fhash,
                )
            )
        return events
    except Exception:
        return []


def _build_sync_request_params(
    app_name: str,
    base_url: str,
    sync_mode: Literal["api", "webhook"],
    prune: bool,
    force: bool,
    repo_url: str = "",
    branch: str = "main",
) -> tuple[str, dict[str, str], dict[str, object]]:
    """Construct destination URL, headers, and payload dictionary for sync trigger."""
    if sync_mode == "webhook":
        url = f"{base_url}/api/webhook"
        headers = {
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
        }
        resolved_repo_url = repo_url or f"https://example.com/{app_name}"
        payload: dict[str, object] = {
            "ref": f"refs/heads/{branch}",
            "repository": {
                "name": app_name,
                "html_url": resolved_repo_url,
                "default_branch": branch,
            },
        }
    else:
        url = f"{base_url}/api/v1/applications/{app_name}/sync"
        headers = {"Content-Type": "application/json"}
        payload = {"sync": {"prune": prune, "force": force}}
    return url, headers, payload


def trigger_argocd_sync(
    app_name: str,
    changed_files: Sequence[Path | str] | None = None,
    prune: bool = False,
    force: bool = False,
    dry_run: bool = False,
    sync_mode: Literal["api", "webhook"] = "api",
) -> GitOpsSyncTriggerResult:
    """Dispatch automated synchronization request to ArgoCD application or webhook endpoint."""
    start = time.monotonic()
    now = time.time()
    files_str = [str(f) for f in (changed_files or [])]

    if dry_run:
        duration = round(time.monotonic() - start, 3)
        return GitOpsSyncTriggerResult(
            app_name=app_name,
            changed_files=files_str,
            status="DryRun",
            sync_mode=sync_mode,
            message="Simulated GitOps synchronization trigger succeeded",
            duration_seconds=duration,
            timestamp=now,
            success=True,
        )

    with trace_span("argo.gitops.sync", {"app": app_name, "mode": sync_mode}):
        import httpx2

        settings = load_settings()
        if not settings.argocd.url:
            return GitOpsSyncTriggerResult(
                app_name=app_name,
                changed_files=files_str,
                status="Failed",
                sync_mode=sync_mode,
                message="ArgoCD URL is not configured in settings",
                duration_seconds=round(time.monotonic() - start, 3),
                timestamp=now,
                success=False,
            )

        try:
            validate_service_url(
                settings.argocd.url, "ArgoCD", allow=settings.ai.allow_private_network
            )
            base = settings.argocd.url.rstrip("/")
            url, headers, payload = _build_sync_request_params(
                app_name, base, sync_mode, prune, force
            )
            token = get_argocd_token(settings)
            if token and not token.startswith("*"):
                headers["Authorization"] = f"Bearer {token}"

            with httpx2.Client() as client:
                resp = client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()

            duration = round(time.monotonic() - start, 3)
            status_text: Literal["Synced", "Triggered"] = (
                "Triggered" if sync_mode == "webhook" else "Synced"
            )
            GLOBAL_METRICS.increment_counter(
                "devops_cli_argo_gitops_sync_total",
                value=1.0,
                labels={"app": app_name, "status": status_text, "mode": sync_mode},
            )
            return GitOpsSyncTriggerResult(
                app_name=app_name,
                changed_files=files_str,
                status=status_text,
                sync_mode=sync_mode,
                message=f"GitOps synchronization {status_text.lower()} successfully",
                duration_seconds=duration,
                timestamp=now,
                success=True,
            )
        except Exception as exc:
            duration = round(time.monotonic() - start, 3)
            sanitized_error = mask_secrets(mask_uri_credentials(str(exc)))[:256]
            GLOBAL_METRICS.increment_counter(
                "devops_cli_argo_gitops_sync_total",
                value=1.0,
                labels={"app": app_name, "status": "Failed", "mode": sync_mode},
            )
            return GitOpsSyncTriggerResult(
                app_name=app_name,
                changed_files=files_str,
                status="Failed",
                sync_mode=sync_mode,
                message=sanitized_error,
                duration_seconds=duration,
                timestamp=now,
                success=False,
            )


class GitOpsWatcher:
    """Continuous filesystem manifest watcher and debounced GitOps reconciliation engine."""

    def __init__(
        self,
        paths: Sequence[Path | str],
        app_name: str,
        *,
        debounce_ms: int = 500,
        poll_interval_seconds: float = 0.5,
        dry_run: bool = False,
        prune: bool = False,
        force: bool = False,
        sync_mode: Literal["api", "webhook"] = "api",
        baseline_state: dict[Path, tuple[float, str]] | None = None,
        on_drift: Callable[[list[GitOpsDriftEvent]], None] | None = None,
        on_sync: Callable[[GitOpsSyncTriggerResult], None] | None = None,
    ) -> None:
        self.paths = [Path(p) for p in paths]
        self.app_name = app_name
        self.debounce_seconds = max(0.05, debounce_ms / 1000.0)
        self.poll_interval_seconds = max(0.05, poll_interval_seconds)
        self.dry_run = dry_run
        self.prune = prune
        self.force = force
        self.sync_mode = sync_mode
        self.on_drift = on_drift
        self.on_sync = on_sync
        self._running = False

        if baseline_state is not None:
            self._last_state = baseline_state
        else:
            persisted = load_persisted_manifest_state(self.paths)
            self._last_state = (
                persisted if persisted is not None else compute_manifest_state(self.paths)
            )

    def scan_drift(self, detect_cold_drift: bool = False) -> list[GitOpsDriftEvent]:
        """Scan watched manifest paths, update state, and return detected drift."""
        current_state = compute_manifest_state(self.paths)
        events = scan_manifest_drift(self._last_state, current_state)
        if not events and detect_cold_drift:
            events = inspect_git_manifest_drift(self.paths)
        self._last_state = current_state
        save_persisted_manifest_state(self.paths, current_state)
        return events

    def sync_now(self, events: list[GitOpsDriftEvent] | None = None) -> GitOpsSyncTriggerResult:
        """Trigger immediate synchronization against the target ArgoCD application."""
        changed_files = [e.path for e in events] if events else []
        return trigger_argocd_sync(
            app_name=self.app_name,
            changed_files=changed_files,
            prune=self.prune,
            force=self.force,
            dry_run=self.dry_run,
            sync_mode=self.sync_mode,
        )

    def stop(self) -> None:
        """Signal the continuous watch loop to terminate."""
        self._running = False

    def _process_drift_cycle(self, drift: list[GitOpsDriftEvent]) -> GitOpsSyncTriggerResult:
        """Process detected drift through debounce window and trigger synchronization."""
        time.sleep(self.debounce_seconds)
        # Re-scan to include any rapid subsequent writes during debounce window
        additional_drift = self.scan_drift()
        combined_drift = drift + additional_drift

        if self.on_drift:
            self.on_drift(combined_drift)

        result = self.sync_now(combined_drift)
        if self.on_sync:
            self.on_sync(result)
        return result

    def watch(
        self,
        *,
        max_events: int | None = None,
        max_iterations: int | None = None,
    ) -> list[GitOpsSyncTriggerResult]:
        """Run the monitoring loop and process manifest change cycles with tracing."""
        self._running = True
        sync_results: list[GitOpsSyncTriggerResult] = []
        iterations = 0
        watch_start = time.monotonic()

        with trace_span(
            "argo.gitops.watch",
            attributes={
                "app": self.app_name,
                "paths": [str(p) for p in self.paths],
                "debounce_ms": int(self.debounce_seconds * 1000),
                "interval_seconds": self.poll_interval_seconds,
            },
        ) as span_h:
            GLOBAL_METRICS.increment_counter(
                "devops_cli_argo_gitops_watch_total",
                value=1.0,
                labels={"app": self.app_name},
            )
            try:
                while self._running:
                    drift = self.scan_drift()
                    if drift:
                        span_h.add_event(
                            "manifest_drift",
                            {"count": len(drift), "app": self.app_name},
                        )
                        GLOBAL_METRICS.increment_counter(
                            "devops_cli_argo_gitops_drift_events_total",
                            value=float(len(drift)),
                            labels={"app": self.app_name},
                        )
                        result = self._process_drift_cycle(drift)
                        sync_results.append(result)
                        if max_events is not None and len(sync_results) >= max_events:
                            break

                    iterations += 1
                    if max_iterations is not None and iterations >= max_iterations:
                        break
                    time.sleep(self.poll_interval_seconds)
            except KeyboardInterrupt:
                self._running = False
            finally:
                self._running = False
                total_duration = round(time.monotonic() - watch_start, 2)
                span_h.set_attribute("iterations", iterations)
                span_h.set_attribute("duration_seconds", total_duration)
                GLOBAL_METRICS.record_histogram(
                    "devops_cli_argo_gitops_watch_duration_seconds",
                    total_duration,
                    labels={"app": self.app_name},
                )
                GLOBAL_METRICS.increment_counter(
                    "devops_cli_argo_gitops_watch_iterations_total",
                    value=float(iterations),
                    labels={"app": self.app_name},
                )

        return sync_results


def render_gitops_drift_table(events: list[GitOpsDriftEvent]) -> TablePayload:
    """Render TablePayload representing detected manifest drift."""
    from devops_cli.output import format_gitops_drift_table

    return format_gitops_drift_table(events)


def render_gitops_sync_table(results: list[GitOpsSyncTriggerResult]) -> TablePayload:
    """Render TablePayload representing GitOps synchronization triggers."""
    from devops_cli.output import format_gitops_sync_table

    return format_gitops_sync_table(results)
