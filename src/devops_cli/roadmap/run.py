"""Roadmap job evaluation, scheduling, checkout management, and execution.

The due table runs the status lane's rows, metrics, implement and stage_ready, before the model
lane's, intake, refine, stage and alternatives, so a burst of candidates never holds back the
metrics (#1360), and a slow model never holds back the implement or stage_ready row (#2757,
#2865). The row stage_ready marks a green stage draft pull request ready. `devops roadmap run`
runs the whole table in one round. The Service runs each lane in its own worker and its own clone
(`service_jobs`), so a status-lane round never waits for a model-bound one (#1532); both lanes
read and write the repository's one `schedule.json`. The Service's ledger of failed rounds is
kept beside the repositories' schedules (`service_state_dir`), so a restart keeps it (#2474).
Each row is due by its interval, by a webhook hint in the batch, or by its due rule, which
judges the changes made since the row last succeeded: intake's is an issue reopened, or a fresh
candidate its last round left (`IntakeRecord`, kept beside `schedule.json`). A round's intake
decides at most `DEFAULT_ROADMAP_INTAKE_LIMIT` candidates. Refine is due every 31 minutes, on a first
run, and in a round where intake placed a critical fix or a P0 item (#1515). Stage, the row after
refine, is due every 37 minutes, on a first run, and in a round where refine set an item Ready (#2659).
The alternatives row is due every 719 minutes and on a first run, and checks at most
`roadmap.alternatives.limit` items (#2652). Every clone tracks origin's default branch.

A subscribed webhook event runs the update scoped to it at once (`run_scoped_update`, ADR 0017):
`issues` opened, edited or reopened runs intake of that one issue on the model lane. A scoped
update writes no job's last success, so the poll still judges every change since then; it
records the issue it decided in `IntakeRecord`, so the poll does not decide it again.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shlex
import subprocess
import threading
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter
from pydantic import ValidationError as MalformedRecordError

from devops_cli.config.constants import (
    CONST_GIT_CLI,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
    CONST_ROADMAP_INTAKE_RECORD_FILENAME,
    CONST_ROADMAP_P0_PRIORITIES,
    CONST_ROADMAP_REFINE_DUE_STAMP,
    CONST_ROADMAP_RUN_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_STATE_FILENAME,
    CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME,
    CONST_SERVICE_CAUSE_UNKNOWN,
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_LANE_TRIAGE,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
    CONST_SERVICE_SOURCE_POLL,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_INTAKE_LIMIT,
    DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_STAGE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES,
    DEFAULT_SERVICE_MAX_FAILED_ROUNDS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.paths import (
    is_forbidden_system_path,
    safe_resolve_subpath,
    validate_no_path_traversal,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import (
    GitOperationError,
    RoadmapRefineError,
    RoadmapRunError,
    SecurityError,
    ServiceStoppingError,
)
from devops_cli.exceptions.git import GitHubUnauthenticatedError
from devops_cli.github.request_scope import request_scope
from devops_cli.lang import MESSAGES

# `alternatives` imports pydantic_ai too: import it here for the same reason (#2535).
from devops_cli.roadmap.alternatives import (
    apply_alternatives,
    plan_alternatives,
    raise_for_failed_checks,
)
from devops_cli.roadmap.implement_submit import run_implement_round
from devops_cli.roadmap.intake import (
    IntakeApplied,
    IntakePlan,
    IntakeRecord,
    Outcome,
    apply_intake,
    plan_intake,
    raise_for_failed_placements,
)

# `refine` imports pydantic_ai. The Python 3.14 import lock deadlocks when two worker threads
# import it for the first time together, so import it at module level, in the Service's main
# thread, before any worker starts (#2535).
from devops_cli.roadmap.refine import apply_refine, plan_refine, raise_for_failed_items

# `stage` imports the model client, which imports pydantic_ai too: import it here for the same
# reason (#2659).
from devops_cli.roadmap.stage import (
    apply_stage,
    emit_stage_results,
    parse_filters,
    plan_stage,
    raise_for_failed,
)
from devops_cli.roadmap.stage_ready import mark_stage_ready
from devops_cli.roadmap.status_sync import sync_statuses
from devops_cli.roadmap.store import Change, ChangeKind, RoadmapStore
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.server.service import (
    LaneJob,
    TriggerBatch,
    keep_state_record,
    read_state_record,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS

if TYPE_CHECKING:
    from devops_cli.roadmap.intake_model import IntakeModel

logger = logging.getLogger(__name__)

_SCHEDULE_LOCK = threading.Lock()
"""Held while a job's success is written to `schedule.json`, which the Service's lanes share."""


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
    """Outcome of running one roadmap job: whether it placed a critical fix or a P0 item (intake),
    and whether it set an item Ready (refine)."""

    placed_critical_or_p0: bool = False
    set_ready: bool = False


@dataclass(frozen=True)
class DueCheck:
    """What a row's due rule judges at a poll or a webhook (#1360): the changes made at or after
    the row's last success (none before its first), the time, that last success, and the
    repository's data directory, which holds `schedule.json`."""

    changes: tuple[Change, ...]
    now: datetime
    last_success: datetime | None
    repo_dir: Path


@dataclass(frozen=True)
class JobRow:
    """One row in the roadmap due table."""

    name: str
    interval: timedelta | None = None
    batch_keys: tuple[tuple[str, str, str], ...] = ()
    runner: Callable[..., JobOutcome] = field(default_factory=lambda: lambda **_: JobOutcome())
    needs_clone: bool = False
    first_run_due: bool = False
    due_rule: Callable[[DueCheck], bool] | None = None
    cross_job_predicate: Callable[[Mapping[str, JobOutcome]], bool] | None = None


def _resolve_data_dir(data_dir: Path | str | None = None) -> Path:
    """Resolve data directory path defensively: `data_dir`, else `data.dir` of the loaded
    settings, which its variable or the config file sets (#2447)."""
    if data_dir is None:
        from devops_cli.core.repo import resolve_data_path

        data_dir = resolve_data_path(load_settings().data.dir)
    path = Path(data_dir).resolve()
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


def _record_success(schedule_path: Path, job: str, at: datetime) -> None:
    """Record `at` as `job`'s last success in schedule.json, keeping every other job's as the
    file holds it now: the Service's lanes write the same file while each other's rounds run
    (#1532)."""
    with _SCHEDULE_LOCK:
        schedule = _read_schedule(schedule_path)
        schedule[job] = at
        _write_schedule(schedule_path, schedule)


def read_intake_record(path: Path) -> IntakeRecord:
    """The Service's intake record, empty before its first round; one that exists and can't be
    read raises, naming it and the remedy, rather than reading as empty (#1360)."""
    if not path.exists():
        return IntakeRecord()
    try:
        return IntakeRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, MalformedRecordError) as exc:
        reason = str(exc).splitlines()[0][:200]
        raise RoadmapRunError(
            MESSAGES.roadmap.run_intake_record_unreadable.format(path=path, reason=reason),
            details={"path": str(path)[:256]},
        ) from exc


def _write_intake_record(path: Path, record: IntakeRecord) -> None:
    """Write the Service's intake record atomically."""
    from devops_cli.output.file_writer import write_json_file

    write_json_file(path, record.model_dump(mode="json"), indent=2, atomic=True)


def _get_session_login() -> str:
    """Account login of the process GitHub identity."""
    from devops_cli.github.session import get_github_session

    return get_github_session().login


def _commit_author() -> tuple[str, str]:
    """The name and email the job clone commits as: the session's login, and the email GitHub
    links to that account, `<id>+<login>@users.noreply.github.com` (a GitHub App's bot too)."""
    from devops_cli.github.session import get_github_session

    session = get_github_session()
    return session.login, session.commit_email


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


def _default_branch(clone_dir: Path) -> str:
    """Fetch origin with pruning and return origin's default branch, its HEAD as git reports it
    (#1366). Any git failure raises `subprocess.CalledProcessError`."""
    for step in (("fetch", "--prune", "origin"), ("remote", "set-head", "origin", "--auto")):
        run_subprocess([CONST_GIT_CLI, *step], cwd=clone_dir, check=True, quiet=True)
    return (
        run_subprocess(
            [CONST_GIT_CLI, "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=clone_dir,
            check=True,
            quiet=True,
        )
        .stdout.strip()
        .removeprefix("refs/remotes/origin/")
    )


def ensure_checkout(
    repo: str,
    data_dir: Path,
    remote_url: str | None = None,
    dirname: str = CONST_ROADMAP_RUN_CLONE_DIRNAME,
) -> Path:
    """Clone the repository to <data dir>/roadmap/<owner>/<name>/<dirname>, update it, return its
    path. `clone` is the status lane's and the CLI's, `model-clone` the Service's model lane's,
    so one lane's update never touches the other's checkout (#1532).

    The clone rows (`needs_clone`) rely on this contract:

    - Origin is fetched with `--prune`, so the remote-tracking branches are origin's branches and
      no others. Tags follow git's defaults: the clone takes every tag, a later fetch takes each
      tag on a commit the clone then has, and the prune removes none.
    - HEAD is a named local branch, never detached, reset hard to origin's tip of its default
      branch (origin's HEAD, read again with `remote set-head --auto`); a tracked change a failed
      job left in the clone is discarded (`checkout --force`). Branches and origin's HEAD are read
      as full ref names, so no tag can shadow them.
    - `user.name` is the session's login, and `user.email` the email GitHub links to that
      account, `<id>+<login>@users.noreply.github.com`.
    - A git command that exits non-zero raises `GitOperationError` naming the command and git's
      reason, credentials masked. A timeout or a missing `git` binary propagates as
      `run_subprocess` raises it.
    """
    clone_dir = _resolve_roadmap_repo_path(data_dir, repo, dirname, error_cls=GitOperationError)
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    url = remote_url or f"https://github.com/{repo}.git"
    try:
        if not (clone_dir / ".git").exists():
            run_subprocess([CONST_GIT_CLI, "clone", url, str(clone_dir)], check=True, quiet=True)
        branch = _default_branch(clone_dir)
        name, email = _commit_author()
        for step in (
            ("checkout", "--force", "-B", branch, f"refs/remotes/origin/{branch}"),
            ("reset", "--hard", f"refs/remotes/origin/{branch}"),
            ("config", "user.name", name),
            ("config", "user.email", email),
        ):
            run_subprocess([CONST_GIT_CLI, *step], cwd=clone_dir, check=True, quiet=True)
    except subprocess.CalledProcessError as exc:
        reason = str(exc.stderr or exc.stdout or "").strip()
        raise GitOperationError(
            mask_secrets(f"{shlex.join(exc.cmd)} failed: {reason}"), operation=exc.cmd[1]
        ) from exc
    return clone_dir


def model_clone(repo: str) -> Path:
    """The model lane's clone of `repo`, cloned or updated: the clone the stage job works in when
    a person gives no `--source` (#2654)."""
    return ensure_checkout(repo, _resolve_data_dir(), dirname=CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME)


def _intake_due(check: DueCheck) -> bool:
    """Intake is due when an issue reopens, or when its last round left a fresh candidate. A
    record that can't be read makes it due, so its run raises, naming the record."""
    if any(change.kind is ChangeKind.REOPENED for change in check.changes):
        return True
    try:
        return read_intake_record(check.repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME).pending
    except RoadmapRunError:
        return True


def _refine_cross_job(outcomes: Mapping[str, JobOutcome]) -> bool:
    """Refinement is due in a round where intake placed a critical fix or a P0 item."""
    intake_outcome = outcomes.get("intake")
    return intake_outcome is not None and intake_outcome.placed_critical_or_p0


def _stage_cross_job(outcomes: Mapping[str, JobOutcome]) -> bool:
    """Staging is due in a round where refine set an item Ready (#2659)."""
    refine_outcome = outcomes.get("refine")
    return refine_outcome is not None and refine_outcome.set_ready


def _outcome_of_failure(exc: Exception) -> JobOutcome:
    """What a failed job still did that a later row follows: a refine run that failed for one
    item has set the others Ready, and the stage row is due in that round (#2659)."""
    if isinstance(exc, RoadmapRefineError):
        return JobOutcome(set_ready=exc.readied_count > 0)
    return JobOutcome()


def _places_critical_or_p0(plan: IntakePlan) -> bool:
    """Whether intake placed a critical fix or a P0 item (#1540). A round with a failed
    placement fails before it judges this."""
    return any(
        decision.outcome is Outcome.PLACE and decision.priority in CONST_ROADMAP_P0_PRIORITIES
        for decision in plan.decisions
    )


def _run_intake_adapter(
    store: RoadmapStore,
    *,
    repo: str,
    repo_dir: Path,
    now: datetime,
    model: IntakeModel | None = None,
    limit: int = DEFAULT_ROADMAP_INTAKE_LIMIT,
    **_: Any,
) -> JobOutcome:
    """Decide at most `limit` of `repo`'s candidates, fresh ones first, and place them (#1360).
    The record of what it decided is written before any placement, so intake keeps the round's
    skips when a placement raises, and a candidate whose placement raised is
    decided again after the fresh ones. A candidate whose write fails is skipped, the round's
    others are placed, and the job then fails naming it (#1443)."""
    from devops_cli.roadmap.intake_model import build_intake_model

    record_path = repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME
    record = read_intake_record(record_path)
    plan = plan_intake(
        store,
        repo=repo,
        model=model or build_intake_model(),
        limit=limit,
        waiting=record.waiting,
    )
    _write_intake_record(record_path, record.after(plan, now))
    applied = apply_intake(store, plan) if plan.has_writes else IntakeApplied()
    if plan.has_writes:
        raise_for_failed_placements(applied)
    placed_p0 = _places_critical_or_p0(plan)
    if placed_p0:
        _record_success(
            repo_dir / CONST_ROADMAP_RUN_STATE_FILENAME, CONST_ROADMAP_REFINE_DUE_STAMP, now
        )
    return JobOutcome(placed_critical_or_p0=placed_p0)


@dataclass(frozen=True)
class WebhookDelivery:
    """What a webhook delivery of a subscribed event carries that its scoped update reads: the
    repository, the event, its action and the number of the issue it is about (ADR 0017)."""

    repo: str
    event: str
    action: str
    number: int


def _intake_one(
    store: RoadmapStore,
    delivery: WebhookDelivery,
    *,
    repo_dir: Path,
    now: datetime,
    model: IntakeModel | None = None,
) -> JobOutcome:
    """Decide and place the one issue `delivery` names, when it is a candidate, with intake's
    own decision code (ADR 0017). The record of what it decided is merged into the intake record
    before any placement, as the intake job writes it; an issue that is no candidate, such as
    an Item a person edited, is decided by no one and writes nothing."""
    from devops_cli.roadmap.intake_model import build_intake_model

    record_path = repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME
    record = read_intake_record(record_path)
    plan = plan_intake(
        store,
        repo=delivery.repo,
        model=model or build_intake_model(),
        issues=(delivery.number,),
        waiting=record.waiting,
    )
    merged = record.merged(plan, now)
    if merged != record:
        _write_intake_record(record_path, merged)
    applied = apply_intake(store, plan) if plan.has_writes else IntakeApplied()
    if plan.has_writes:
        raise_for_failed_placements(applied)
    placed_p0 = _places_critical_or_p0(plan)
    if placed_p0:
        _record_success(
            repo_dir / CONST_ROADMAP_RUN_STATE_FILENAME, CONST_ROADMAP_REFINE_DUE_STAMP, now
        )
    return JobOutcome(placed_critical_or_p0=placed_p0)


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
    **_: Any,
) -> JobOutcome:
    """Run refine job and return JobOutcome; it fails, once the other items are written, when the
    model call failed for any item. The stop of the Service ends the run, but the items that
    failed before it still fail the run (#2753)."""
    source = _job_clone("refine", clone_path)
    plan = plan_refine(store, repo=repo, source=source)
    try:
        readied = apply_refine(store, plan).readied_count if plan.has_writes else 0
    except ServiceStoppingError:
        raise_for_failed_items(plan)
        raise
    raise_for_failed_items(plan, readied)
    return JobOutcome(set_ready=readied > 0)


def _run_stage_adapter(
    store: RoadmapStore,
    repo: str = "",
    clone_path: Path | None = None,
    **_: Any,
) -> JobOutcome:
    """Run the stage job as `devops roadmap stage --confirm` runs it, with the filter, the limit
    and the step budget of the settings: stage the Ready items they name in the job's clone, count
    each item by its result, and fail, once the other items are written, when an item failed
    (#2659)."""
    source = _job_clone("stage", clone_path)
    plan = plan_stage(store, repo=repo, source=source, filters=parse_filters(()))
    applied = apply_stage(store, plan, source=source)
    emit_stage_results(plan, applied)
    synced = (
        sync_statuses(store, repo=repo, planned=plan.planned) if plan.planned is not None else None
    )
    raise_for_failed([*plan.failed, *applied.failed])
    if synced is not None:
        raise_for_failed(synced.failed, summary=MESSAGES.roadmap.status_sync_failed)
    return JobOutcome()


def _run_implement_adapter(
    store: RoadmapStore,
    repo: str = "",
    clone_path: Path | None = None,
    **_: Any,
) -> JobOutcome:
    """Submit the implement Job of one Staged or Planned item, report the Jobs that ended, and wait
    while a Job of the repository runs. The Service runs no step: the runner Job does (#2667)."""
    source = _job_clone("implement", clone_path)
    result = run_implement_round(store, repo=repo, source=source)
    logger.info(
        "The implement row of %s reported %d Job(s), cleared %d stop(s), waited %s, created %s",
        repo,
        len(result.reported),
        len(result.cleared),
        result.waiting,
        result.created,
    )
    if result.left is not None:
        logger.info(MESSAGES.roadmap.implement_round_left.format(number=result.left))
    raise_for_failed(result.status_failed, summary=MESSAGES.roadmap.status_sync_failed)
    return JobOutcome()


def _run_stage_ready_adapter(store: RoadmapStore, repo: str = "", **_: Any) -> JobOutcome:
    """Mark each green draft pull request that the stage job recorded ready for review, and fail,
    once the others are done, when a pull request failed (#2865). A round with no recorded draft
    sends no request of its own."""
    mark_stage_ready(store, repo=repo)
    return JobOutcome()


def _run_alternatives_adapter(store: RoadmapStore, repo: str = "", **_: Any) -> JobOutcome:
    """Check at most `roadmap.alternatives.limit` open items for an open tool that covers them
    (#2652). The check writes the others when one fails, and then the job fails naming it. A
    repository the check is off for, such as a private one, costs a visibility read and nothing
    else."""
    plan = plan_alternatives(store, repo=repo, limit=load_settings().roadmap.alternatives.limit)
    if plan.off_reason:
        logger.info("The alternatives check of %s is off: %s", repo, plan.off_reason)
    if plan.has_writes:
        apply_alternatives(store, plan)
    raise_for_failed_checks(plan)
    return JobOutcome()


def _run_metrics_adapter(
    store: RoadmapStore,
    repo: str = "",
    clone_path: Path | None = None,
    **_: Any,
) -> JobOutcome:
    """Collect the project metrics, walking the version tags of the job's clone of `repo` and
    counting the Items of `store`, and the GitHub and Cloudflare status, into OTLP
    (#1358). A failed collection or status read is logged and skipped; a missing clone fails the
    job."""
    from devops_cli.github.metrics import (
        collect_project_metrics_report,
        emit_project_metrics_telemetry,
    )
    from devops_cli.telemetry.service_status import (
        emit_service_status_telemetry,
        fetch_cloudflare_status,
        fetch_github_status,
    )

    clone = _job_clone("metrics", clone_path)
    try:
        target_repo = repo or None
        report = collect_project_metrics_report(root=clone, repo=target_repo, store=store)
        emit_project_metrics_telemetry(report)
    except Exception as exc:
        logger.warning("Project metrics collection failed for %s: %s", repo, exc)

    try:
        gh_status = fetch_github_status()
        emit_service_status_telemetry(gh_status, "github")
    except Exception as exc:
        logger.warning("GitHub service status collection failed: %s", exc)

    try:
        cf_status = fetch_cloudflare_status()
        emit_service_status_telemetry(cf_status, "cloudflare")
    except Exception as exc:
        logger.warning("Cloudflare service status collection failed: %s", exc)

    return JobOutcome()


STATUS_LANE_ROWS: tuple[JobRow, ...] = (
    JobRow(
        name="metrics",
        interval=timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES),
        runner=_run_metrics_adapter,
        needs_clone=True,
        first_run_due=True,
    ),
    JobRow(
        name="implement",
        interval=timedelta(minutes=DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES),
        runner=_run_implement_adapter,
        needs_clone=True,
        first_run_due=True,
    ),
    JobRow(
        name="stage_ready",
        interval=timedelta(minutes=DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES),
        runner=_run_stage_ready_adapter,
        first_run_due=True,
    ),
)
"""The rows that call no model: the one that refreshes the metrics, the one that submits the
implement Job, which only talks to the Kubernetes API and GitHub, and the one that marks a green
stage pull request ready, which only talks to GitHub. The model runs in the Job, so a model-lane
round that is still running never delays the rows (#2757, #2865). `stage_ready` follows
`implement`, so a Staged item with a green draft gets its Job first, and the row leaves a pull
request that a Job works on alone."""

TRIAGE_LANE_ROWS: tuple[JobRow, ...] = (
    JobRow(
        name="intake",
        interval=timedelta(minutes=DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES),
        batch_keys=CONST_ROADMAP_INTAKE_BATCH_KEYS,
        runner=_run_intake_adapter,
        first_run_due=True,
        due_rule=_intake_due,
    ),
)
"""The row that runs intake on the fast devops-triage model in its own triage lane (#1534)."""

MODEL_LANE_ROWS: tuple[JobRow, ...] = (
    JobRow(
        name="refine",
        interval=timedelta(minutes=DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES),
        runner=_run_refine_adapter,
        needs_clone=True,
        first_run_due=True,
        cross_job_predicate=_refine_cross_job,
    ),
    JobRow(
        name="stage",
        interval=timedelta(minutes=DEFAULT_ROADMAP_STAGE_INTERVAL_MINUTES),
        runner=_run_stage_adapter,
        needs_clone=True,
        first_run_due=True,
        cross_job_predicate=_stage_cross_job,
    ),
    JobRow(
        name="alternatives",
        interval=timedelta(minutes=DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES),
        runner=_run_alternatives_adapter,
        first_run_due=True,
    ),
)
"""The rows that call the model, which answers one call at a time: intake, refine, stage and the
daily check for alternative tools (#2652)."""

DEFAULT_DUE_TABLE: tuple[JobRow, ...] = (*STATUS_LANE_ROWS, *TRIAGE_LANE_ROWS, *MODEL_LANE_ROWS)
"""Every row, the status lane's first: what `devops roadmap run` runs in one round."""


@dataclass(frozen=True)
class ScopedUpdate:
    """The update that one subscribed event runs at once, scoped to its delivery: the job whose
    decision code it narrows, the lane it runs on, and its runner (ADR 0017)."""

    job: str
    lane: str
    runner: Callable[..., JobOutcome]


_SCOPED_INTAKE = ScopedUpdate(job="intake", lane=CONST_SERVICE_LANE_TRIAGE, runner=_intake_one)

SCOPED_UPDATES: Mapping[tuple[str, str], ScopedUpdate] = MappingProxyType(
    {("issues", action): _SCOPED_INTAKE for action in ("opened", "edited", "reopened")}
)
"""The scoped update of each event and action that has one (ADR 0017). An event or action that
is not here keeps its delivery a hint that makes a whole round due."""


def run_scoped_update(
    delivery: WebhookDelivery,
    store: RoadmapStore,
    *,
    data_dir: Path | str | None = None,
    now: datetime | None = None,
    model: IntakeModel | None = None,
) -> JobOutcome | None:
    """Run the update scoped to `delivery` on `store`, the roadmap of its repository, or return
    None when its event and action have none (ADR 0017).

    The update reads the repository's intake record beside its `schedule.json` in `data_dir`,
    and writes no job's last success: the reconciling poll still judges every change made since
    each job's last round, so a scoped update never hides a change it did not handle."""
    update = SCOPED_UPDATES.get((delivery.event, delivery.action))
    if update is None:
        return None
    schedule_path = _resolve_roadmap_repo_path(
        _resolve_data_dir(data_dir),
        delivery.repo,
        CONST_ROADMAP_RUN_STATE_FILENAME,
        error_cls=GitOperationError,
    )
    return update.runner(
        store,
        delivery,
        repo_dir=schedule_path.parent,
        now=now or datetime.now(UTC),
        model=model,
    )


def build_stub_table(
    runners: Mapping[str, Callable[..., JobOutcome]] | None = None,
    *,
    needs_clone: bool = False,
    include_refine: bool | None = None,
    include_metrics: bool | None = None,
    include_alternatives: bool | None = None,
    include_stage: bool | None = None,
    include_implement: bool | None = None,
    include_stage_ready: bool | None = None,
) -> tuple[JobRow, ...]:
    """The due table's rows, in its order, each running `runners`' stub for its job: metrics,
    implement, stage_ready, intake, refine, stage and alternatives. Intake is always in; the
    others are added when asked for or given a stub."""
    r = runners or {}
    add_refine = include_refine if include_refine is not None else ("refine" in r)
    add_metrics = include_metrics if include_metrics is not None else ("metrics" in r)
    add_stage = include_stage if include_stage is not None else ("stage" in r)
    add_implement = include_implement if include_implement is not None else ("implement" in r)
    add_stage_ready = (
        include_stage_ready if include_stage_ready is not None else ("stage_ready" in r)
    )
    add_alternatives = (
        include_alternatives if include_alternatives is not None else ("alternatives" in r)
    )
    kept = {
        "metrics": add_metrics,
        "refine": add_refine,
        "stage": add_stage,
        "implement": add_implement,
        "stage_ready": add_stage_ready,
        "alternatives": add_alternatives,
    }
    return tuple(
        replace(
            row,
            runner=r.get(row.name, lambda **_: JobOutcome()),
            needs_clone=needs_clone and row.needs_clone,
        )
        for row in DEFAULT_DUE_TABLE
        if kept.get(row.name, True)
    )


def _batch_matches(
    batch_counts: Mapping[tuple[str, str, str], int],
    row: JobRow,
) -> bool:
    """Whether any trigger key in batch matches row's registered batch keys."""
    return any(key in batch_counts for key in row.batch_keys)


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
    """The oldest last success among the rows with a due rule: one read covers every row's
    changes."""
    cutoffs = [schedule.get(row.name, now) for row in rows if row.due_rule is not None]
    return min(cutoffs, default=now)


@dataclass(frozen=True)
class _Poll:
    """What every row of one round is judged by: the schedule, the batch, the changes read, the
    time and the repository's data directory."""

    schedule: Mapping[str, datetime]
    batch: Mapping[tuple[str, str, str], int]
    changes: Sequence[Change]
    now: datetime
    repo_dir: Path

    def is_due(self, row: JobRow) -> bool:
        """Whether `row` is due before any other row runs: by its interval, a hint in the
        batch, or its due rule over the changes since its own last success."""
        last = self.schedule.get(row.name)
        if _is_interval_due(row, last, self.now) or _batch_matches(self.batch, row):
            return True
        if row.name == "refine":
            refine_due = self.schedule.get(CONST_ROADMAP_REFINE_DUE_STAMP)
            if refine_due is not None and (last is None or refine_due > last):
                return True
        if row.due_rule is None:
            return False
        since = last or self.now
        mine = tuple(change for change in self.changes if change.at >= since)
        return row.due_rule(DueCheck(mine, self.now, last, self.repo_dir))


def _lane_reads_changes(rows: Sequence[JobRow]) -> bool:
    """Whether a row of the lane has a due rule: only a due rule judges changes."""
    return any(row.due_rule is not None for row in rows)


def _fetch_filtered_changes(
    rows: Sequence[JobRow],
    schedule: Mapping[str, datetime],
    store: RoadmapStore,
    current_time: datetime,
) -> list[Change]:
    """Fetch recent store changes excluding writes authored by the current session, which the
    store leaves out before it reads any job record (#1361). Only a due rule judges changes, so
    a lane with no row that has one, such as the status lane, reads none."""
    if not _lane_reads_changes(rows):
        return []
    cutoff = _oldest_cutoff(rows, schedule, current_time)
    return store.changes_since(cutoff, except_actor=_current_actor(store))


def _simulate_dry_run(rows: Sequence[JobRow], initially_due: Mapping[str, bool]) -> tuple[str, ...]:
    """Simulate due jobs without executing them."""
    due_list: list[str] = []
    simulated_outcomes: dict[str, JobOutcome] = {}
    for row in rows:
        is_due = initially_due[row.name]
        if not is_due and row.cross_job_predicate is not None:
            is_due = row.cross_job_predicate(simulated_outcomes)
        if is_due:
            due_list.append(row.name)
            simulated_outcomes[row.name] = JobOutcome()
    return tuple(due_list)


_FailedRounds = TypeAdapter(list[tuple[str, str, int, str]])
"""A ledger record: each repository and job with the rounds it failed in a row and the input of
the last."""


class FailureLedger:
    """How many rounds in a row each roadmap job failed, and the input it failed on (#2161).

    A job that fails `limit` rounds in a row does not run again until its input is not the one it
    failed on: a webhook trigger, or a change to an item the job reads. A poll alone brings no
    new input, so a failing job stops costing GitHub requests at every round. A success clears
    the job's record. With a `record`, the ledger is kept in that file at each change and read
    back when the ledger is made, so a restart of the Service keeps it (#2474). The Service's
    /metrics shows each job that failed its limit of rounds in a row (#2475).

    The ledger also holds the cause of each failed round, the class of its error, for the log
    line that suspends a job. The causes stay in memory: the record keeps its format, because
    the version that runs now reads it as it is and would not start on another one (#2753).
    """

    def __init__(
        self, limit: int = DEFAULT_SERVICE_MAX_FAILED_ROUNDS, record: Path | None = None
    ) -> None:
        self._limit = limit
        self._record = record
        self._lock = threading.Lock()
        kept = [] if record is None else read_state_record(record, _FailedRounds, [])
        self._failed: dict[tuple[str, str], tuple[int, str]] = {
            (repo, job): (rounds, failed_on) for repo, job, rounds, failed_on in kept
        }
        self._causes: dict[tuple[str, str], deque[str]] = {}
        for repo, job in self._failed:
            self._report_locked(repo, job)

    @property
    def limit(self) -> int:
        """How many failed rounds in a row suspend a job."""
        return self._limit

    def suspended(self, repo: str, job: str, current: str) -> bool:
        """Whether `job` failed `limit` rounds in a row on this same input."""
        with self._lock:
            rounds, failed_on = self._failed.get((repo, job), (0, None))
            return rounds >= self._limit and failed_on == current

    def failed(self, repo: str, job: str, current: str, cause: str) -> int:
        """Count a failed round on `current` with its `cause`; the rounds in a row, which
        restart at 1 when the input is not the one of the last failure."""
        with self._lock:
            rounds, failed_on = self._failed.get((repo, job), (0, None))
            rounds = rounds + 1 if failed_on == current or rounds < self._limit else 1
            self._failed[(repo, job)] = (rounds, current)
            causes = self._causes.get((repo, job), deque(maxlen=self._limit))
            if rounds == 1:
                causes.clear()
            causes.append(cause)
            self._causes[(repo, job)] = causes
            self._keep_locked()
            self._report_locked(repo, job)
            return rounds

    def causes(self, repo: str, job: str) -> tuple[str, ...]:
        """The cause of each of the last rounds in a row that `job` failed, oldest first. A round
        that a process before the last restart counted has the cause `unknown`."""
        with self._lock:
            rounds, _ = self._failed.get((repo, job), (0, None))
            known = tuple(self._causes.get((repo, job), ()))
            return (CONST_SERVICE_CAUSE_UNKNOWN,) * (min(rounds, self._limit) - len(known)) + known

    def succeeded(self, repo: str, job: str) -> None:
        """Clear the record of `job`."""
        with self._lock:
            self._causes.pop((repo, job), None)
            if self._failed.pop((repo, job), None) is not None:
                self._keep_locked()
                self._report_locked(repo, job)

    def _report_locked(self, repo: str, job: str) -> None:
        """Show on the Service's /metrics whether `job` failed its limit of rounds in a row; the
        caller holds the lock, or the ledger is still being made."""
        rounds, _ = self._failed.get((repo, job), (0, None))
        GLOBAL_METRICS.set_gauge(
            CONST_SERVICE_METRIC_JOB_SUSPENDED,
            1.0 if rounds >= self._limit else 0.0,
            labels={"repo": repo, "row": job},
        )

    def _keep_locked(self) -> None:
        """Write the ledger to its record, if it has one; the caller holds the lock."""
        if self._record is not None:
            kept = [(repo, job, *entry) for (repo, job), entry in self._failed.items()]
            keep_state_record(self._record, _FailedRounds.dump_python(kept, mode="json"))


def service_state_dir(data_dir: Path | str | None = None) -> Path:
    """Where the Service keeps what a restart must not clear (#2474): the `roadmap` directory of
    the data directory, which holds each repository's `schedule.json`, on the Service's volume."""
    return _resolve_data_dir(data_dir) / "roadmap"


def _round_input(
    changes: Sequence[Change],
    batch: Mapping[tuple[str, str, str], int],
    at: datetime,
    reads_changes: bool = True,
) -> str:
    """What the round's jobs read, as one digest a ledger record can keep: the changes since the
    oldest last success and, when the batch holds a trigger other than a poll, the time of the
    round, so such a trigger is new input to every job. A lane that reads no change has no input
    that a poll can change, so its input holds the hour of the round: a suspended row tries again
    in a later hour, once its fault is fixed (#2757)."""
    seen = [(change.kind.value, change.number, change.at.isoformat()) for change in changes]
    pushed = any(key[0] != CONST_SERVICE_SOURCE_POLL for key in batch)
    hour = None if reads_changes else at.strftime("%Y-%m-%dT%H")
    read = json.dumps([seen, at.isoformat() if pushed else None, hour])
    return hashlib.sha256(read.encode("utf-8")).hexdigest()


def ended_by_stop(exc: BaseException) -> bool:
    """Whether `exc` is the error of a request that ended because the Service is stopping
    (`ServiceStoppingError`), or has it as its cause. A group is a stop when each member is: a
    group that holds a real failure is a failure (#2753)."""
    if isinstance(exc, ServiceStoppingError):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return all(ended_by_stop(sub) for sub in exc.exceptions)
    return exc.__cause__ is not None and ended_by_stop(exc.__cause__)


def _count_failure(
    failures: FailureLedger, repo: str, job: str, current: str, exc: BaseException
) -> None:
    """Count a failed round of `job`, and log once when it reaches the limit. A round that the
    stop of the Service ends is not at fault, so it leaves the count as it was (#2753)."""
    if ended_by_stop(exc):
        return
    rounds = failures.failed(repo, job, current, type(exc).__name__)
    if rounds == failures.limit:
        message = MESSAGES.serve.job_suspended.format(
            job=job, repo=repo, rounds=rounds, causes=", ".join(failures.causes(repo, job))
        )
        logger.warning(message, extra={"repo": repo})


def identity_refused(exc: BaseException) -> bool:
    """Whether `exc`, or a member of the failures it groups, says GitHub refused the Service's
    identity: HTTP 401, or 403 with an account suspension (#2161)."""
    if isinstance(exc, RoadmapRunError) and isinstance(exc.__cause__, BaseExceptionGroup):
        return any(identity_refused(sub) for sub in exc.__cause__.exceptions)
    if isinstance(exc, BaseExceptionGroup):
        return any(identity_refused(sub) for sub in exc.exceptions)
    return isinstance(exc, GitHubUnauthenticatedError) or (
        exc.__cause__ is not None and identity_refused(exc.__cause__)
    )


def _format_error_line(exc: BaseException) -> str:
    """The first line of an exception's message, masked and capped at 256 chars."""
    lines = str(exc).strip().splitlines()
    first = lines[0] if lines else type(exc).__name__
    return mask_secrets(first)[:256]


def _execute_due_rows(
    rows: Sequence[JobRow],
    initially_due: Mapping[str, bool],
    store: RoadmapStore,
    repo: str,
    base_data: Path,
    remote_url: str | None,
    changes: Sequence[Change],
    active_batch: Mapping[tuple[str, str, str], int],
    schedule_path: Path,
    current_time: datetime,
    clone_dirname: str,
    failures: FailureLedger,
) -> tuple[str, ...]:
    """Execute all due jobs in order with failure tracking, the clone rows in `clone_dirname`.
    Each runner also gets the repository's data directory and the round's time. With the
    `failures` ledger, a job that failed its limit of rounds in a row on the same input does not
    run (#2161). A refusal of the identity ends the round at once: no later job sends a
    request. Each row runs in the request scope of its name, so its GitHub requests count under
    it (#2475)."""
    succeeded_jobs: list[str] = []
    failed_jobs: list[str] = []
    outcomes: dict[str, JobOutcome] = {}
    clone_path: Path | None = None
    clone_error: Exception | None = None
    clone_jobs: list[str] = []
    error_entries: list[tuple[list[str], Exception]] = []
    current = _round_input(changes, active_batch, current_time, _lane_reads_changes(rows))

    for row in rows:
        is_due = initially_due[row.name] or (
            row.cross_job_predicate is not None and row.cross_job_predicate(outcomes)
        )
        if not is_due or failures.suspended(repo, row.name, current):
            continue

        if row.needs_clone and clone_error is not None:
            failed_jobs.append(row.name)
            clone_jobs.append(row.name)
            continue

        try:
            if row.needs_clone and clone_path is None:
                clone_path = ensure_checkout(repo, base_data, remote_url, clone_dirname)

            with request_scope(row=row.name):
                outcome = row.runner(
                    store=store,
                    clone_path=clone_path,
                    changes=changes,
                    batch=active_batch,
                    repo=repo,
                    repo_dir=schedule_path.parent,
                    now=current_time,
                )
            outcomes[row.name] = outcome or JobOutcome()
            succeeded_jobs.append(row.name)
            _record_success(schedule_path, row.name, current_time)
            failures.succeeded(repo, row.name)
        except Exception as exc:
            failed_jobs.append(row.name)
            outcomes[row.name] = _outcome_of_failure(exc)
            _count_failure(failures, repo, row.name, current, exc)
            if row.needs_clone and clone_path is None:
                clone_error = exc
                clone_jobs.append(row.name)
                error_entries.append((clone_jobs, exc))
            else:
                error_entries.append(([row.name], exc))
            if identity_refused(exc):
                break

    if failed_jobs:
        error_parts: list[str] = []
        exceptions: list[Exception] = []
        for job_names, entry_exc in error_entries:
            entry_exc.add_note(", ".join(job_names))
            error_parts.append(f"{', '.join(job_names)}: {_format_error_line(entry_exc)}")
            exceptions.append(entry_exc)

        msg = f"Roadmap jobs failed: {'; '.join(error_parts)}"
        cause = ExceptionGroup("Roadmap jobs failed", exceptions)
        raise RoadmapRunError(msg, failed_jobs=failed_jobs) from cause
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
    clone_dirname: str = CONST_ROADMAP_RUN_CLONE_DIRNAME,
    failures: FailureLedger | None = None,
) -> tuple[str, ...]:
    """Evaluate and execute due roadmap jobs, the clone rows in `clone_dirname`.

    With no trigger in the batch, rows are judged on no changes, which reads nothing; a round
    whose rows are all not due reads no more than its changes. Each row is judged by
    `schedule.json` as the round found it, and each success is written as it happens.
    """
    current_time = now or datetime.now(UTC)
    base_data = _resolve_data_dir(data_dir)
    schedule_path = _resolve_roadmap_repo_path(
        base_data, repo, CONST_ROADMAP_RUN_STATE_FILENAME, error_cls=GitOperationError
    )
    schedule = _read_schedule(schedule_path)
    rows = table if table is not None else DEFAULT_DUE_TABLE

    batch_counts = batch.counts if isinstance(batch, TriggerBatch) else dict(batch or {})
    active_batch = {k: v for k, v in batch_counts.items() if v > 0}

    quiet = _Poll(schedule, active_batch, (), current_time, schedule_path.parent)
    if not active_batch and not any(quiet.is_due(row) for row in rows):
        return ()

    changes = _fetch_filtered_changes(rows, schedule, store, current_time)
    polled = replace(quiet, changes=changes)
    initially_due = {row.name: polled.is_due(row) for row in rows}
    if not any(initially_due.values()):
        return ()

    if dry_run:
        return _simulate_dry_run(rows, initially_due)

    return _execute_due_rows(
        rows,
        initially_due,
        store,
        repo,
        base_data,
        remote_url,
        changes,
        active_batch,
        schedule_path,
        current_time,
        clone_dirname,
        failures or FailureLedger(),
    )


def service_job(
    batch: TriggerBatch,
    *,
    table: Sequence[JobRow],
    clone_dirname: str,
    failures: FailureLedger | None = None,
) -> None:
    """Service mode adapter that runs one lane's due roadmap jobs, `table`, in its clone
    `clone_dirname` for a coalesced trigger batch, on the roadmap store of the batch's
    repository, counting its failed rounds in `failures`. The store reads no repository file: a
    repository needs no roadmap configuration (ADR 0016)."""
    from devops_cli.roadmap import store as roadmap_store

    repo = batch.repo
    run_due_jobs(
        repo,
        roadmap_store.get_roadmap_store(repo),
        batch=batch,
        table=table,
        clone_dirname=clone_dirname,
        failures=failures,
    )


def service_jobs(state_dir: Path) -> Mapping[str, LaneJob]:
    """Each lane's job, which `devops serve --service` runs in one worker per lane of each
    repository (#1532). Every lane of every repository shares one ledger of failed rounds, kept
    in `state_dir`, so a restart keeps it (#2474)."""
    failures = FailureLedger(record=state_dir / CONST_SERVICE_FAILURES_FILENAME)
    return {
        CONST_SERVICE_LANE_STATUS: partial(
            service_job,
            table=STATUS_LANE_ROWS,
            clone_dirname=CONST_ROADMAP_RUN_CLONE_DIRNAME,
            failures=failures,
        ),
        CONST_SERVICE_LANE_TRIAGE: partial(
            service_job,
            table=TRIAGE_LANE_ROWS,
            clone_dirname=CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME,
            failures=failures,
        ),
        CONST_SERVICE_LANE_MODEL: partial(
            service_job,
            table=MODEL_LANE_ROWS,
            clone_dirname=CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
            failures=failures,
        ),
    }


__all__ = [
    "DEFAULT_DUE_TABLE",
    "MODEL_LANE_ROWS",
    "SCOPED_UPDATES",
    "STATUS_LANE_ROWS",
    "TRIAGE_LANE_ROWS",
    "FailureLedger",
    "JobOutcome",
    "JobRow",
    "ScopedUpdate",
    "WebhookDelivery",
    "build_stub_table",
    "ensure_checkout",
    "identity_refused",
    "model_clone",
    "parse_due_tuple",
    "run_due_jobs",
    "run_scoped_update",
    "service_job",
    "service_jobs",
    "service_state_dir",
]
