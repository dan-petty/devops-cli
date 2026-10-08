"""Roadmap job evaluation, scheduling, checkout management, and execution."""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_GIT_CLI,
    CONST_RELEASE_BRANCH_PREFIX,
    CONST_ROADMAP_CLOSURE_BATCH_KEYS,
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_DOCUMENT_PATH,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
    CONST_ROADMAP_P0_PRIORITY,
    CONST_ROADMAP_RENDER_FILE_MODE,
    CONST_ROADMAP_RUN_BOARD_FILTER,
    CONST_ROADMAP_RUN_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_STATE_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_DATA_DIR,
    DEFAULT_ROADMAP_CLOSURE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES,
)
from devops_cli.config.env import ENV_DATA_DIR
from devops_cli.core.paths import (
    is_forbidden_system_path,
    safe_resolve_subpath,
    validate_no_path_traversal,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError, RoadmapRunError, SecurityError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.reprioritize import current_release
from devops_cli.roadmap.store import (
    RELEASE_CHANGE_KINDS,
    Change,
    ChangeKind,
    Release,
    RoadmapStore,
    in_release,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.server.service import TriggerBatch

if TYPE_CHECKING:
    from devops_cli.roadmap.config import RoadmapConfig

logger = logging.getLogger(__name__)


def parse_due_tuple(output: str) -> tuple[str, ...]:
    """Extract due job names from 'Due: ...' output."""
    for line in output.splitlines():
        if line.startswith("Due:"):
            content = line[4:].strip()
            if not content or content in ("(none)", "none", "()"):
                return ()
            cleaned = content.strip("()[]")
            parts = [p.strip().strip("'\"") for p in cleaned.split(",") if p.strip().strip("'\"")]
            return tuple(parts)
    return ()


@dataclass(frozen=True)
class JobOutcome:
    """Outcome of running one roadmap job."""

    changes: tuple[Change, ...] = ()
    placed_critical_or_p0: bool = False
    critical_fix_or_p0_items: tuple[int, ...] = ()
    closed_items: tuple[int, ...] = ()

    @property
    def has_critical_or_p0(self) -> bool:
        """Whether this outcome placed a critical fix or P0 feature."""
        return self.placed_critical_or_p0 or bool(self.critical_fix_or_p0_items)


@dataclass(frozen=True)
class JobRow:
    """One row in the roadmap due table."""

    name: str
    interval: timedelta | None = None
    batch_keys: tuple[tuple[str, str, str], ...] = ()
    runner: Callable[..., JobOutcome] = field(default_factory=lambda: lambda **_: JobOutcome())
    needs_clone: bool = False
    first_run_due: bool = False
    change_predicate: Callable[[Change, RoadmapStore, Release | None], bool] | None = None
    cross_job_predicate: (
        Callable[[dict[str, JobOutcome], RoadmapStore, Release | None], bool] | None
    ) = None


def _resolve_data_dir(data_dir: Path | str | None = None) -> Path:
    """Resolve data directory path defensively."""
    raw: Path | str = (
        data_dir if data_dir is not None else (os.environ.get(ENV_DATA_DIR) or DEFAULT_DATA_DIR)
    )
    path = Path(raw).resolve()
    try:
        validate_no_path_traversal(path, label="Data directory")
    except SecurityError as exc:
        raise GitOperationError(str(exc)) from exc
    if is_forbidden_system_path(path):
        raise GitOperationError(f"Data directory resolves to forbidden system path: {path}")
    return path


def _read_schedule(schedule_path: Path) -> dict[str, datetime]:
    """Read the last successful run time for each job from schedule.json."""
    if not schedule_path.is_file():
        return {}
    try:
        data = json.loads(schedule_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        schedule: dict[str, datetime] = {}
        for key, val in data.items():
            if isinstance(val, str):
                try:
                    dt = datetime.fromisoformat(val)
                    schedule[key] = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
                except ValueError:
                    continue
        return schedule
    except OSError, json.JSONDecodeError:
        return {}


def _write_schedule(schedule_path: Path, schedule: Mapping[str, datetime]) -> None:
    """Write the last successful run time for each job to schedule.json atomically."""
    from devops_cli.output.file_writer import write_json_file

    payload = {job: dt.isoformat() for job, dt in schedule.items()}
    write_json_file(schedule_path, payload, indent=2, atomic=True)


def _get_session_login() -> str:
    """Account login of the process GitHub identity."""
    try:
        from devops_cli.github.session import get_github_session

        return get_github_session().login
    except Exception:
        return "devops-cli"


def _current_actor(store: RoadmapStore) -> str | None:
    """The actor whose writes should be dropped from triggers to prevent self-triggering."""
    actor = getattr(store, "actor", None) or getattr(store, "_actor", None)
    if actor:
        return str(actor)
    return _get_session_login()


def _resolve_roadmap_repo_path(
    base_dir: Path,
    repo: str,
    leaf_filename: str,
    *,
    error_cls: type[GitOperationError] = GitOperationError,
) -> Path:
    """Safely validate repository format and resolve path under <base_dir>/roadmap/<owner>/<name>/<leaf>."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise error_cls(f"Invalid repository format (expected 'owner/name'): {repo}")
    owner, name = parts
    if owner.startswith(("/", "\\", ".")) or name.startswith(("/", "\\", ".")):
        raise error_cls(f"Invalid repository slug components: '{repo}'")
    root = (base_dir / "roadmap").resolve()
    target = safe_resolve_subpath(root, Path(owner) / name / leaf_filename, error_cls=error_cls)
    if is_forbidden_system_path(target):
        raise error_cls(f"Target path resolves to forbidden system path: {target}")
    return target


def _select_tracked_branch(clone_dir: Path, repo: str, current_rel: Release | None) -> str:
    """Fetch origin with pruning and return the branch the clone tracks (#1366).

    That is the current release's `release/<v>` while origin has it, and origin's default branch
    otherwise, including when no release is open. The default branch is origin's HEAD as git
    reports it. A release branch counts as absent only when `rev-parse --verify` exits 1 after the
    pruning fetch, which a ship's deleted branch and a release not yet started both do; that case
    logs one INFO line. Any other git failure raises `subprocess.CalledProcessError`.
    """
    for step in (("fetch", "--prune", "origin"), ("remote", "set-head", "origin", "--auto")):
        run_subprocess([CONST_GIT_CLI, *step], cwd=clone_dir, check=True, quiet=True)
    default_branch = (
        run_subprocess(
            [CONST_GIT_CLI, "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=clone_dir,
            check=True,
            quiet=True,
        )
        .stdout.strip()
        .removeprefix("refs/remotes/origin/")
    )
    if current_rel is None:
        return default_branch
    title = current_rel.title if current_rel.title.startswith("v") else f"v{current_rel.version}"
    release_branch = f"{CONST_RELEASE_BRANCH_PREFIX}{title}"
    probe = run_subprocess(
        [
            CONST_GIT_CLI,
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/remotes/origin/{release_branch}",
        ],
        cwd=clone_dir,
        check=False,
        quiet=True,
    )
    if probe.returncode == 1:
        logger.info(
            "Roadmap clone of %s tracks %s: release %s has no %s on origin",
            repo,
            default_branch,
            title,
            release_branch,
        )
        return default_branch
    probe.check_returncode()
    return release_branch


def ensure_checkout(
    repo: str,
    data_dir: Path,
    remote_url: str | None = None,
    current_rel: Release | None = None,
) -> Path:
    """Clone the repository to <data dir>/roadmap/<owner>/<name>/clone, update it, return its path.

    The clone rows (`needs_clone`) rely on this contract:

    - Origin is fetched with `--prune`, so the remote-tracking branches are origin's branches and
      no others. Tags follow git's defaults: the clone takes every tag, a later fetch takes each
      tag on a commit the clone then has, and the prune removes none.
    - HEAD is a named local branch, never detached, reset hard to origin's tip of the tracked
      branch; a tracked change a failed job left in the clone is discarded (`checkout --force`).
      Branches and origin's HEAD are read as full ref names, so no tag can shadow them. That is the current release's `release/<v>` while origin has it, and origin's
      default branch (its HEAD, re-read with `remote set-head --auto`) otherwise (#1366): when
      `current_rel` is None, and when the release has no branch, because a ship deleted it or
      reprioritize has not created it yet. The last case logs one INFO line.
    - `user.name` and `user.email` are the session's login.
    - A git command that exits non-zero raises `GitOperationError` naming the command and git's
      reason, credentials masked. Only a release branch `rev-parse --verify` finds absent after
      a successful pruning fetch selects the default branch. A timeout or a missing `git` binary
      propagates as `run_subprocess` raises it.
    """
    clone_dir = _resolve_roadmap_repo_path(
        data_dir, repo, CONST_ROADMAP_RUN_CLONE_DIRNAME, error_cls=GitOperationError
    )
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    url = remote_url or f"https://github.com/{repo}.git"
    try:
        if not (clone_dir / ".git").exists():
            run_subprocess([CONST_GIT_CLI, "clone", url, str(clone_dir)], check=True, quiet=True)
        branch = _select_tracked_branch(clone_dir, repo, current_rel)
        login = _get_session_login()
        for step in (
            ("checkout", "--force", "-B", branch, f"refs/remotes/origin/{branch}"),
            ("reset", "--hard", f"refs/remotes/origin/{branch}"),
            ("config", "user.name", login),
            ("config", "user.email", f"{login}@users.noreply.github.com"),
        ):
            run_subprocess([CONST_GIT_CLI, *step], cwd=clone_dir, check=True, quiet=True)
    except subprocess.CalledProcessError as exc:
        reason = str(exc.stderr or exc.stdout or "").strip()
        raise GitOperationError(
            mask_secrets(f"{shlex.join(exc.cmd)} failed: {reason}"), operation=exc.cmd[1]
        ) from exc
    return clone_dir


def _intake_change_predicate(change: Change, _store: RoadmapStore, _cur: Release | None) -> bool:
    """Intake is due on REOPENED issue change."""
    return change.kind is ChangeKind.REOPENED


def _reprioritize_change_predicate(
    change: Change, store: RoadmapStore, cur: Release | None
) -> bool:
    """Reprioritization is due on release events or current release item changes."""
    if change.kind in RELEASE_CHANGE_KINDS:
        return True
    if change.kind not in (
        ChangeKind.JOINED_RELEASE,
        ChangeKind.LEFT_RELEASE,
        ChangeKind.LABELED,
        ChangeKind.UNLABELED,
        ChangeKind.CLOSED,
        ChangeKind.REOPENED,
    ):
        return False
    if cur is None:
        return False
    if change.release is not None and in_release(change.release, cur.version):
        return True
    item = store.item(change.number)
    return item is not None and in_release(item.release, cur.version)


def _reprioritize_cross_job(
    outcomes: dict[str, JobOutcome], store: RoadmapStore, cur: Release | None
) -> bool:
    """Reprioritization is due if closure closed a current-release item."""
    if "close" not in outcomes or cur is None:
        return False
    close_outcome = outcomes["close"]
    for num in close_outcome.closed_items:
        item = store.item(num)
        if item is not None and in_release(item.release, cur.version):
            return True
    for ch in close_outcome.changes:
        if ch.kind is ChangeKind.CLOSED:
            if ch.release is not None and in_release(ch.release, cur.version):
                return True
            item = store.item(ch.number)
            if item is not None and in_release(item.release, cur.version):
                return True
    return False


def _refine_cross_job(
    outcomes: dict[str, JobOutcome], _store: RoadmapStore, _cur: Release | None
) -> bool:
    """Refinement is due if reprioritization ran or intake placed critical/P0 item."""
    if "reprioritize" in outcomes:
        return True
    intake_outcome = outcomes.get("intake")
    return intake_outcome is not None and intake_outcome.has_critical_or_p0


def _run_intake_adapter(
    store: RoadmapStore,
    *,
    repo: str,
    config: RoadmapConfig | None = None,
    **_: Any,
) -> JobOutcome:
    """Run intake on `repo` and return JobOutcome."""
    from devops_cli.config.constants import CONST_ROADMAP_CRITICAL_FIX_LABELS
    from devops_cli.roadmap.config import read_roadmap_config
    from devops_cli.roadmap.intake import (
        Outcome,
        apply_intake,
        plan_intake,
    )
    from devops_cli.roadmap.intake_model import build_intake_model

    active_config = config or read_roadmap_config(store, ref=None)
    model = build_intake_model()
    plan = plan_intake(store, repo=repo, config=active_config, model=model)
    has_crit_or_p0 = False
    for dec in plan.decisions:
        if dec.outcome is Outcome.PLACE:
            if dec.priority in (
                CONST_ROADMAP_CRITICAL_PRIORITY,
                CONST_ROADMAP_P0_PRIORITY,
            ) or not CONST_ROADMAP_CRITICAL_FIX_LABELS.isdisjoint(dec.labels):
                has_crit_or_p0 = True
                break
    if plan.has_writes:
        applied = apply_intake(store, plan)
        return JobOutcome(
            placed_critical_or_p0=has_crit_or_p0,
            closed_items=tuple(range(1, applied.closed + 1)) if applied.closed else (),
        )
    return JobOutcome(placed_critical_or_p0=has_crit_or_p0)


def _run_close_adapter(
    store: RoadmapStore,
    repo: str = "",
    clone_path: Path | None = None,
    config: RoadmapConfig | None = None,
    **_: Any,
) -> JobOutcome:
    """Run closure job and return JobOutcome."""
    from devops_cli.github.check_verdict import fetch_pr_check_verdicts
    from devops_cli.roadmap.close import apply_close, plan_close
    from devops_cli.roadmap.store import MergedPullRequest

    def checks(pull_request: MergedPullRequest) -> Any:
        return fetch_pr_check_verdicts(
            pull_request.number, repo=repo, head_sha=pull_request.head_commit
        )

    plan = plan_close(store, repo=repo, checks=checks)
    closed_items = tuple(c.number for c in plan.closings)
    if plan.has_writes and clone_path is not None:
        from devops_cli.commands.release import cut_release
        from devops_cli.output.file_writer import write_text_file
        from devops_cli.roadmap.config import read_roadmap_config
        from devops_cli.roadmap.render import render_roadmap

        active_config = config or read_roadmap_config(store, ref=None)

        def cut(planned: Any) -> None:
            def write_roadmap(clone: Path) -> None:
                text = render_roadmap(store, repo=repo, config=active_config)
                write_text_file(
                    clone / CONST_ROADMAP_DOCUMENT_PATH,
                    text,
                    mode=CONST_ROADMAP_RENDER_FILE_MODE,
                )

            cut_release(
                version=planned.version,
                base=planned.base,
                draft=False,
                sync_docs=False,
                is_prepare=True,
                repo_root=clone_path.resolve(),
                edits=write_roadmap,
            )

        apply_close(store, plan, cut)
    elif plan.has_writes:
        apply_close(store, plan, lambda _: None)

    changes = tuple(
        Change(
            kind=ChangeKind.CLOSED,
            number=num,
            actor=_current_actor(store),
            at=datetime.now(UTC),
        )
        for num in closed_items
    )
    return JobOutcome(changes=changes, closed_items=closed_items)


def _run_reprioritize_adapter(
    store: RoadmapStore,
    repo: str = "",
    config: RoadmapConfig | None = None,
    **_: Any,
) -> JobOutcome:
    """Run reprioritization job and return JobOutcome."""
    from devops_cli.roadmap.config import read_roadmap_config
    from devops_cli.roadmap.reprioritize import (
        apply_reprioritization,
        plan_reprioritization,
    )

    active_config = config or read_roadmap_config(store, ref=None)
    now = datetime.now(UTC)
    plan = plan_reprioritization(store, repo=repo, config=active_config, now=now)
    if plan.has_writes:
        apply_reprioritization(store, plan)
    actor = _current_actor(store)
    changes = tuple(
        Change(
            kind=ChangeKind.LABELED,
            number=d.item.number,
            actor=actor,
            at=now,
            release=d.release,
        )
        for d in plan.changes
    )
    return JobOutcome(changes=changes)


def _job_clone(job: str, clone_path: Path | None) -> Path:
    """The clone `job` reads its repository in. A row that gives it none is a due-table error,
    never a reason to read the working directory instead (#1358)."""
    if clone_path is None:
        raise GitOperationError(
            MESSAGES.roadmap.run_job_needs_clone.format(job=job), operation="checkout"
        )
    return clone_path


def _run_refine_adapter(
    store: RoadmapStore,
    repo: str = "",
    clone_path: Path | None = None,
    config: RoadmapConfig | None = None,
    **_: Any,
) -> JobOutcome:
    """Run refine job and return JobOutcome; it fails, once the other items are written, when the
    model call failed for any item."""
    from devops_cli.roadmap.config import read_roadmap_config
    from devops_cli.roadmap.refine import apply_refine, plan_refine, raise_for_failed_items

    active_config = config or read_roadmap_config(store, ref=None)
    source = _job_clone("refine", clone_path)
    plan = plan_refine(store, repo=repo, source=source, config=active_config)
    if plan.has_writes:
        apply_refine(store, plan)
    raise_for_failed_items(plan)
    return JobOutcome()


def _run_metrics_adapter(
    repo: str = "",
    clone_path: Path | None = None,
    **_: Any,
) -> JobOutcome:
    """Collect the project metrics, walking the release tags of the job's clone of `repo`, and the
    GitHub and Cloudflare status, into the in-memory registry and OTLP (#1358). A failed
    collection or status read is logged and skipped; a missing clone fails the job."""
    from devops_cli.github.metrics import (
        collect_project_metrics_report,
        emit_project_metrics_telemetry,
        record_project_metrics_in_registry,
    )
    from devops_cli.telemetry.service_status import (
        emit_service_status_telemetry,
        fetch_cloudflare_status,
        fetch_github_status,
        record_service_status_in_registry,
    )

    clone = _job_clone("metrics", clone_path)
    try:
        target_repo = repo or None
        report = collect_project_metrics_report(root=clone, repo=target_repo)
        record_project_metrics_in_registry(report)
        emit_project_metrics_telemetry(report)
    except Exception as exc:
        logger.warning("Project metrics collection failed for %s: %s", repo, exc)

    try:
        gh_status = fetch_github_status()
        record_service_status_in_registry(gh_status, "github")
        emit_service_status_telemetry(gh_status, "github")
    except Exception as exc:
        logger.warning("GitHub service status collection failed: %s", exc)

    try:
        cf_status = fetch_cloudflare_status()
        record_service_status_in_registry(cf_status, "cloudflare")
        emit_service_status_telemetry(cf_status, "cloudflare")
    except Exception as exc:
        logger.warning("Cloudflare service status collection failed: %s", exc)

    return JobOutcome()


DEFAULT_DUE_TABLE: tuple[JobRow, ...] = (
    JobRow(
        name="intake",
        interval=timedelta(minutes=DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES),
        batch_keys=CONST_ROADMAP_INTAKE_BATCH_KEYS,
        runner=_run_intake_adapter,
        first_run_due=True,
        change_predicate=_intake_change_predicate,
    ),
    JobRow(
        name="close",
        interval=timedelta(minutes=DEFAULT_ROADMAP_CLOSURE_INTERVAL_MINUTES),
        batch_keys=CONST_ROADMAP_CLOSURE_BATCH_KEYS,
        runner=_run_close_adapter,
        needs_clone=True,
    ),
    JobRow(
        name="reprioritize",
        runner=_run_reprioritize_adapter,
        change_predicate=_reprioritize_change_predicate,
        cross_job_predicate=_reprioritize_cross_job,
    ),
    JobRow(
        name="refine",
        runner=_run_refine_adapter,
        needs_clone=True,
        cross_job_predicate=_refine_cross_job,
    ),
    JobRow(
        name="metrics",
        interval=timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES),
        runner=_run_metrics_adapter,
        needs_clone=True,
        first_run_due=True,
    ),
)


def build_stub_table(
    runners: Mapping[str, Callable[..., JobOutcome]] | None = None,
    *,
    needs_clone: bool = False,
    include_refine: bool | None = None,
    include_metrics: bool | None = None,
) -> tuple[JobRow, ...]:
    """Construct a stub table for testing (landed jobs, plus refine/metrics when requested)."""
    r = runners or {}
    add_refine = include_refine if include_refine is not None else ("refine" in r)
    add_metrics = include_metrics if include_metrics is not None else ("metrics" in r)
    rows: list[JobRow] = [
        JobRow(
            name="intake",
            interval=timedelta(minutes=DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES),
            batch_keys=CONST_ROADMAP_INTAKE_BATCH_KEYS,
            runner=r.get("intake", lambda **_: JobOutcome()),
            first_run_due=True,
            change_predicate=_intake_change_predicate,
        ),
        JobRow(
            name="close",
            interval=timedelta(minutes=DEFAULT_ROADMAP_CLOSURE_INTERVAL_MINUTES),
            batch_keys=CONST_ROADMAP_CLOSURE_BATCH_KEYS,
            runner=r.get("close", lambda **_: JobOutcome()),
            needs_clone=needs_clone,
        ),
        JobRow(
            name="reprioritize",
            runner=r.get("reprioritize", lambda **_: JobOutcome()),
            change_predicate=_reprioritize_change_predicate,
            cross_job_predicate=_reprioritize_cross_job,
        ),
    ]
    if add_refine:
        rows.append(
            JobRow(
                name="refine",
                runner=r.get("refine", lambda **_: JobOutcome()),
                needs_clone=needs_clone,
                cross_job_predicate=_refine_cross_job,
            )
        )
    if add_metrics:
        rows.append(
            JobRow(
                name="metrics",
                interval=timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES),
                runner=r.get("metrics", lambda **_: JobOutcome()),
                needs_clone=needs_clone,
                first_run_due=True,
            )
        )
    return tuple(rows)


def _batch_matches(
    batch_counts: Mapping[tuple[str, str, str], int],
    row: JobRow,
) -> bool:
    """Whether any trigger key in batch matches row's registered batch keys."""
    if not batch_counts:
        return False
    if any(k in batch_counts for k in row.batch_keys):
        return True
    if row.name == "reprioritize":
        return any(
            src == "webhook" and evt in ("milestone", "milestones")
            for (src, evt, _act) in batch_counts
        )
    return False


def _is_interval_due(
    row: JobRow,
    last_run: datetime | None,
    now: datetime,
) -> bool:
    """Whether row is due by interval."""
    if last_run is None:
        return row.first_run_due
    if row.interval is None:
        return False
    return (now - last_run) >= row.interval


def _oldest_cutoff(
    rows: Sequence[JobRow],
    schedule: Mapping[str, datetime],
    now: datetime,
) -> datetime:
    """Oldest last-success cutoff across rows that need changes."""
    cutoffs: list[datetime] = []
    for row in rows:
        if row.change_predicate is not None:
            last = schedule.get(row.name)
            cutoffs.append(last if last is not None else now)
    return min(cutoffs) if cutoffs else now


def _evaluate_row_due(
    row: JobRow,
    schedule: Mapping[str, datetime],
    batch_counts: Mapping[tuple[str, str, str], int],
    changes: Sequence[Change],
    store: RoadmapStore,
    cur: Release | None,
    now: datetime,
) -> bool:
    """Evaluate whether row is initially due without cross-job triggers."""
    if _is_interval_due(row, schedule.get(row.name), now):
        return True
    if _batch_matches(batch_counts, row):
        return True
    if row.change_predicate is not None and changes:
        return any(row.change_predicate(ch, store, cur) for ch in changes)
    return False


def _get_current_release(store: RoadmapStore) -> Release | None:
    """Retrieve current release from store."""
    return current_release(store.releases())


def _is_initial_idle(
    rows: Sequence[JobRow],
    schedule: Mapping[str, datetime],
    active_batch: Mapping[tuple[str, str, str], int],
    current_time: datetime,
) -> bool:
    """Whether run is completely idle with no batch triggers and no interval due."""
    interval_due_any = any(_is_interval_due(r, schedule.get(r.name), current_time) for r in rows)
    return not active_batch and not interval_due_any


def _fetch_filtered_changes(
    rows: Sequence[JobRow],
    schedule: Mapping[str, datetime],
    active_batch: Mapping[tuple[str, str, str], int],
    store: RoadmapStore,
    current_time: datetime,
) -> list[Change]:
    """Fetch recent store changes excluding writes authored by the current session, which the
    store leaves out before it reads any job record (#1361)."""
    has_poll = any(src == "poll" for (src, _evt, _act) in active_batch)
    if not has_poll and not any(r.change_predicate is not None for r in rows):
        return []
    cutoff = _oldest_cutoff(rows, schedule, current_time)
    return store.changes_since(cutoff, except_actor=_current_actor(store))


def _simulate_dry_run(
    rows: Sequence[JobRow],
    initially_due: Mapping[str, bool],
    store: RoadmapStore,
    cur: Release | None,
) -> tuple[str, ...]:
    """Simulate due jobs without executing them."""
    due_list: list[str] = []
    simulated_outcomes: dict[str, JobOutcome] = {}
    for row in rows:
        is_due = initially_due[row.name]
        if not is_due and row.cross_job_predicate is not None:
            is_due = row.cross_job_predicate(simulated_outcomes, store, cur)
        if is_due:
            due_list.append(row.name)
            simulated_outcomes[row.name] = JobOutcome()
    return tuple(due_list)


def _prepare_clone(
    row: JobRow,
    repo: str,
    base_data: Path,
    remote_url: str | None,
    cur: Release | None,
    clone_path: Path | None,
    clone_error: Exception | None,
) -> tuple[Path | None, Exception | None]:
    """Ensure git clone is ready for a job requiring checkout."""
    if not row.needs_clone:
        return clone_path, clone_error
    if clone_error is not None:
        return None, clone_error
    if clone_path is not None:
        return clone_path, None
    try:
        path = ensure_checkout(repo, base_data, remote_url, cur)
        return path, None
    except Exception as exc:
        return None, exc


def _execute_due_rows(
    rows: Sequence[JobRow],
    initially_due: Mapping[str, bool],
    store: RoadmapStore,
    cur: Release | None,
    repo: str,
    base_data: Path,
    remote_url: str | None,
    changes: Sequence[Change],
    active_batch: Mapping[tuple[str, str, str], int],
    schedule: dict[str, datetime],
    schedule_path: Path,
    current_time: datetime,
) -> tuple[str, ...]:
    """Execute all due jobs in order with failure tracking."""
    succeeded_jobs: list[str] = []
    failed_jobs: list[str] = []
    outcomes: dict[str, JobOutcome] = {}
    clone_path: Path | None = None
    clone_error: Exception | None = None

    for row in rows:
        is_due = initially_due[row.name]
        if not is_due and row.cross_job_predicate is not None:
            is_due = row.cross_job_predicate(outcomes, store, cur)
        if not is_due:
            continue

        if row.needs_clone:
            clone_path, clone_error = _prepare_clone(
                row, repo, base_data, remote_url, cur, clone_path, clone_error
            )
            if clone_error is not None:
                failed_jobs.append(row.name)
                continue

        try:
            outcome = row.runner(
                store=store,
                clone_path=clone_path,
                changes=changes,
                batch=active_batch,
                repo=repo,
            )
            outcomes[row.name] = outcome or JobOutcome()
            succeeded_jobs.append(row.name)
            schedule[row.name] = current_time
            _write_schedule(schedule_path, schedule)
        except Exception:
            logger.exception("Roadmap job %s failed", row.name)
            failed_jobs.append(row.name)

    if failed_jobs:
        raise RoadmapRunError(
            f"Roadmap jobs failed: {', '.join(failed_jobs)}",
            failed_jobs=failed_jobs,
        )
    return tuple(succeeded_jobs)


def run_due_jobs(
    repo: str,
    store: RoadmapStore,
    batch: Mapping[tuple[str, str, str], int] | TriggerBatch | None = None,
    *,
    table: Sequence[JobRow] | None = None,
    data_dir: Path | str | None = None,
    remote_url: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Evaluate and execute due roadmap jobs."""
    current_time = now or datetime.now(UTC)
    base_data = _resolve_data_dir(data_dir)
    schedule_path = _resolve_roadmap_repo_path(
        base_data, repo, CONST_ROADMAP_RUN_STATE_FILENAME, error_cls=GitOperationError
    )
    schedule = _read_schedule(schedule_path)
    rows = table if table is not None else DEFAULT_DUE_TABLE

    batch_counts = batch.counts if isinstance(batch, TriggerBatch) else dict(batch or {})
    active_batch = {k: v for k, v in batch_counts.items() if v > 0}

    if _is_initial_idle(rows, schedule, active_batch, current_time):
        return ()

    changes = _fetch_filtered_changes(rows, schedule, active_batch, store, current_time)
    has_webhook = any(src == "webhook" for (src, _evt, _act) in active_batch)
    interval_due_any = any(_is_interval_due(r, schedule.get(r.name), current_time) for r in rows)
    if not changes and not has_webhook and not interval_due_any:
        return ()

    cur: Release | None = None
    if changes or any(r.cross_job_predicate is not None for r in rows):
        cur = _get_current_release(store)

    initially_due = {
        row.name: _evaluate_row_due(row, schedule, active_batch, changes, store, cur, current_time)
        for row in rows
    }

    if dry_run:
        return _simulate_dry_run(rows, initially_due, store, cur)

    return _execute_due_rows(
        rows,
        initially_due,
        store,
        cur,
        repo,
        base_data,
        remote_url,
        changes,
        active_batch,
        schedule,
        schedule_path,
        current_time,
    )


def service_job(
    repo_or_batch: str | TriggerBatch,
    batch: TriggerBatch | None = None,
) -> None:
    """Service mode adapter that runs due roadmap jobs for a coalesced trigger batch."""
    from devops_cli.commands.roadmap import _open_roadmap

    if isinstance(repo_or_batch, TriggerBatch):
        active_batch = repo_or_batch
        repo = repo_or_batch.repo
    elif batch is not None:
        active_batch = batch
        repo = repo_or_batch
    else:
        raise RoadmapRunError("TriggerBatch is required")

    _target, _config, store = _open_roadmap(repo, None, CONST_ROADMAP_RUN_BOARD_FILTER)
    run_due_jobs(repo, store, batch=active_batch)


__all__ = [
    "DEFAULT_DUE_TABLE",
    "JobOutcome",
    "JobRow",
    "build_stub_table",
    "ensure_checkout",
    "parse_due_tuple",
    "run_due_jobs",
    "service_job",
]
