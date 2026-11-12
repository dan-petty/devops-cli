"""Roadmap job evaluation, scheduling, checkout management, and execution.

The due table runs the status lane's rows, metrics, implement, stage_ready, release_comments,
github_status, cloudflare_status and pr_conflicts, before the model lane's, intake, retitle, stage,
refine and alternatives, so a burst of candidates never holds back the metrics (#1360), and a slow model never holds back the implement or stage_ready row
(#2757, #2865). The row stage_ready marks a green stage draft pull request ready. The row
release_comments comments the version, and the time it runs, on the issues of a release (#2917).
The row pr_conflicts comments once on a ready delivery pull request with merge conflicts (#4027).
`devops roadmap run` runs the whole table in one round. The Service runs each lane in its own worker and its own clone
(`service_jobs`), so a status-lane round never waits for a model-bound one (#1532); both lanes
read and write the repository's one `schedule.json`. The Service's ledger of failed rounds is
kept beside the repositories' schedules (`service_state_dir`), so a restart keeps it (#2474).
Each row is due by its interval, by a webhook hint in the batch, or by its due rule, which
judges the changes made since the row last succeeded: intake's is an issue reopened, or a fresh
candidate its last round left (`IntakeRecord`, kept beside `schedule.json`). A round's intake
decides at most `DEFAULT_ROADMAP_INTAKE_LIMIT` candidates. Refine is due every 17 minutes, on a first
run, and in a round where intake placed a critical fix or a P0 item (#1515). Stage, the row before
refine, is due every 37 minutes, on a first run, and after a round in which refine set an item Ready
(#2659): that round stamps `stage_due` in `schedule.json`. Stage runs before refine, so the first
round of a new pod stages before refine takes its items (#4796).
Retitle, the row before stage, is due every 61 minutes and on a first run. It examines at most
`DEFAULT_ROADMAP_RETITLE_LIMIT` items: it shortens a long title summary (#3535) and corrects a title
type that the branch types do not list (#4508), so stage reads the new titles.
The alternatives row is due every 719 minutes and on a first run, and checks at most
`roadmap.alternatives.first_pass_limit` items while an item has no check, else
`roadmap.alternatives.limit` items after (#2652). Every clone tracks origin's default branch.

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
from functools import cache, partial
from itertools import islice
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter
from pydantic import ValidationError as MalformedRecordError

from devops_cli.ai.client.factory import get_task_model
from devops_cli.config.constants import (
    CONST_GIT_CLI,
    CONST_ROADMAP_INTAKE_BATCH_KEYS,
    CONST_ROADMAP_INTAKE_RECORD_FILENAME,
    CONST_ROADMAP_REFINE_BATCH_KEYS,
    CONST_ROADMAP_REFINE_DUE_STAMP,
    CONST_ROADMAP_RETITLE_BATCH_KEYS,
    CONST_ROADMAP_RUN_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_STATE_FILENAME,
    CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME,
    CONST_ROADMAP_STAGE_BATCH_KEYS,
    CONST_ROADMAP_STAGE_DUE_STAMP,
    CONST_SERVICE_CAUSE_UNKNOWN,
    CONST_SERVICE_FAILURES_FILENAME,
    CONST_SERVICE_JOB_RESULT_ERROR,
    CONST_SERVICE_JOB_RESULT_STOPPED,
    CONST_SERVICE_JOB_RESULT_SUCCESS,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_LANE_TRIAGE,
    CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS,
    CONST_SERVICE_METRIC_JOB_SUSPENDED,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_SOURCE_POLL,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_INTAKE_LIMIT,
    DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_PR_CONFLICTS_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_RELEASE_COMMENTS_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_RETITLE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_RETITLE_LIMIT,
    DEFAULT_ROADMAP_STAGE_INTERVAL_MINUTES,
    DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import clock
from devops_cli.core.paths import (
    is_forbidden_system_path,
    safe_resolve_subpath,
    validate_no_path_traversal,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitOperationError,
    RoadmapRefineError,
    RoadmapRunError,
    SecurityError,
    ServiceStoppingError,
    ended_by_stop,
)
from devops_cli.exceptions.git import GitHubUnauthenticatedError
from devops_cli.github.request_scope import request_scope
from devops_cli.lang import MESSAGES

# `alternatives` imports pydantic_ai too: import it here for the same reason (#2535).
from devops_cli.roadmap.alternatives import (
    AlternativesWriter,
    plan_alternatives,
    raise_for_failed_checks,
    record_coverage,
)
from devops_cli.roadmap.failure import FailureClass, failure_class_of, retry_after
from devops_cli.roadmap.implement.implement_submit import run_implement_round
from devops_cli.roadmap.intake.intake import (
    IntakeApplied,
    IntakePlan,
    IntakeRecord,
    apply_intake,
    plan_intake,
    raise_for_failed_placements,
    start_candidate_counts,
)

# `refine` imports pydantic_ai. The Python 3.14 import lock deadlocks when two worker threads
# import it for the first time together, so import it at module level, in the Service's main
# thread, before any worker starts (#2535).
from devops_cli.roadmap.pr_conflicts import watch_conflicts
from devops_cli.roadmap.refine.refine import RefineWriter, plan_refine
from devops_cli.roadmap.release_comments import comment_releases
from devops_cli.roadmap.release_feed import GitHubReleaseFeed
from devops_cli.roadmap.release_roll import cluster_digests
from devops_cli.roadmap.retitle import apply_retitle, build_retitle_model, plan_retitle
from devops_cli.roadmap.round_log import log_failed_item
from devops_cli.roadmap.service_stop import service_stopping, stop_before

# `stage` imports the model client, which imports pydantic_ai too: import it here for the same
# reason (#2659).
from devops_cli.roadmap.stage.stage import (
    StageWriter,
    emit_stage_results,
    parse_filters,
    plan_stage,
    raise_for_failed,
    raise_for_failed_round,
)
from devops_cli.roadmap.stage.stage_ready import mark_stage_ready
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL
from devops_cli.roadmap.status_sync import sync_statuses
from devops_cli.roadmap.stores.listing_snapshot import (
    IncrementalListing,
    intake_listing,
    lane_listing,
)
from devops_cli.roadmap.stores.store import Change, ChangeKind, RoadmapStore
from devops_cli.roadmap.trust import is_person_comment
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.server.service import (
    LaneJob,
    StateRecord,
    TriggerBatch,
    keep_state_record,
    read_state_record,
)
from devops_cli.telemetry.instruments import ROADMAP_ROW_SECONDS, emit
from devops_cli.telemetry.metrics import GLOBAL_METRICS

if TYPE_CHECKING:
    from devops_cli.roadmap.intake.intake_model import IntakeModel

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
    whether it set an item Ready (refine), and the project files that the default branch of the
    repository lacks (stage, #4629). A later row of the round reads the outcome, so `missing` is
    the record that can start the onboarding of the repository (#4664). An outcome that set an
    item Ready stamps `stage_due` (#4796)."""

    placed_critical_or_p0: bool = False
    set_ready: bool = False
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class DueCheck:
    """What a row's due rule judges at a poll or a webhook (#1360): the changes made at or after
    the row's last success (none before its first), the time, that last success, the
    repository's data directory, which holds `schedule.json`, and the read of the number of the
    repository's newest issue, which a rule calls only when it needs the number (#4540)."""

    changes: tuple[Change, ...]
    now: datetime
    last_success: datetime | None
    repo_dir: Path
    newest_issue: Callable[[], int | None] = lambda: None


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


_Schedule = TypeAdapter(dict[str, datetime])


def _read_schedule(schedule_path: Path) -> dict[str, datetime]:
    """Read the last successful run time for each job from schedule.json. A missing file is a
    first run and reads as empty; one that exists and can't be read raises, naming it and the
    remedy, since an empty read would make every row due at once (#4042)."""
    if not schedule_path.is_file():
        return {}
    try:
        stamps = _Schedule.validate_json(schedule_path.read_text(encoding="utf-8"), strict=True)
    except (OSError, MalformedRecordError) as exc:
        reason = str(exc).splitlines()[0][:200]
        raise RoadmapRunError(
            MESSAGES.roadmap.run_schedule_unreadable.format(path=schedule_path, reason=reason),
            details={"path": str(schedule_path)[:256]},
        ) from exc
    return {job: at if at.tzinfo else at.replace(tzinfo=UTC) for job, at in stamps.items()}


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
    """Intake is due when an issue reopens, when its last round left a fresh candidate, or when
    the repository has an issue newer than the newest one that an intake round saw. The issue
    events report no opened issue, so the rule reads the newest issue, and only when nothing
    else makes intake due (#4540). A record with no newest issue makes no read. A record that
    can't be read makes intake due, so its run raises, naming the record."""
    if any(change.kind is ChangeKind.REOPENED for change in check.changes):
        return True
    try:
        record = read_intake_record(check.repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME)
    except RoadmapRunError:
        return True
    if record.pending:
        return True
    if record.newest is None:
        return False
    newest = check.newest_issue()
    return newest is not None and newest > record.newest


def _refine_cross_job(outcomes: Mapping[str, JobOutcome]) -> bool:
    """Refinement is due in a round where intake placed a critical fix or a P0 item."""
    intake_outcome = outcomes.get("intake")
    return intake_outcome is not None and intake_outcome.placed_critical_or_p0


def _outcome_of_failure(exc: Exception) -> JobOutcome:
    """What a failed job still did that the round follows: a refine run that failed for one
    item has set the others Ready, and the round stamps `stage_due` for them (#2659)."""
    if isinstance(exc, RoadmapRefineError):
        return JobOutcome(set_ready=exc.readied_count > 0)
    return JobOutcome()


def _apply_round(
    store: RoadmapStore,
    plan: IntakePlan,
    *,
    record: IntakeRecord,
    record_path: Path,
    repo: str,
    repo_dir: Path,
    now: datetime,
) -> JobOutcome:
    """Apply `plan`, stamp `refine_due` when intake placed a critical fix or a P0 item (#1540),
    keep the failed placements in the intake record (#4061), and then fail the round if a
    placement failed: the stamp and the record are written first, so a failure of another
    candidate does not lose them (#4042)."""
    start_candidate_counts(repo)
    applied = apply_intake(store, plan, repo=repo) if plan.has_writes else IntakeApplied()
    placed_p0 = applied.placed_critical_or_p0 > 0
    if placed_p0:
        _record_success(
            repo_dir / CONST_ROADMAP_RUN_STATE_FILENAME, CONST_ROADMAP_REFINE_DUE_STAMP, now
        )
    settled = record.settled(plan, applied, now)
    if settled != record:
        _write_intake_record(record_path, settled)
    raise_for_failed_placements(applied)
    return JobOutcome(placed_critical_or_p0=placed_p0)


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
    The record keeps the newest issue as the round starts, so an issue that opens later makes
    intake due at the next poll (#4540).
    The record of what it decided is written before any placement, so intake keeps the round's
    skips when a placement raises, and a candidate whose placement raised is
    decided again after the fresh ones. A candidate whose write fails is skipped, the round's
    others are placed, and the job then fails naming it (#1443)."""
    from devops_cli.roadmap.intake.intake_model import build_intake_model

    record_path = repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME
    record = read_intake_record(record_path)
    newest = store.newest_issue_number()
    plan = plan_intake(
        store,
        repo=repo,
        model=model or build_intake_model(),
        limit=limit,
        waiting=record.waiting,
        failed=record.failed,
        now=now,
    )
    after = record.after(plan, now, newest=newest)
    _write_intake_record(record_path, after)
    return _apply_round(
        store, plan, record=after, record_path=record_path, repo=repo, repo_dir=repo_dir, now=now
    )


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
    from devops_cli.roadmap.intake.intake_model import build_intake_model

    record_path = repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME
    record = read_intake_record(record_path)
    plan = plan_intake(
        store,
        repo=delivery.repo,
        model=model or build_intake_model(),
        issues=(delivery.number,),
        waiting=record.waiting,
        failed=record.failed,
        now=now,
    )
    merged = record.merged(plan, now)
    if merged != record:
        _write_intake_record(record_path, merged)
    return _apply_round(
        store,
        plan,
        record=merged,
        record_path=record_path,
        repo=delivery.repo,
        repo_dir=repo_dir,
        now=now,
    )


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
    """Run refine job and return JobOutcome; each item is written when it is done, so the stop
    of the Service loses at most the item in progress (#3631). The job fails, once the other
    items are written, when the model call or the write failed for any item. The stop ends the
    run, but the items that failed before it still fail the run (#2753)."""
    source = _job_clone("refine", clone_path)
    writer = RefineWriter(store, repo)
    try:
        plan = plan_refine(store, repo=repo, source=source, writer=writer)
        writer.write_waiting(plan)
    except ServiceStoppingError:
        writer.end()
        writer.raise_for_failures()
        raise
    writer.end()
    writer.raise_for_failures()
    return JobOutcome(set_ready=writer.readied_count > 0)


def _run_retitle_adapter(store: RoadmapStore, repo: str = "", **_: Any) -> JobOutcome:
    """Shorten the long title summary, or correct the unlisted title type (#4508), of at most
    `DEFAULT_ROADMAP_RETITLE_LIMIT` open items, as `devops roadmap retitle --confirm` does, with
    the model of that command (#3535). The row runs
    just before the stage row, so the stage job reads the new titles in the same round. It reads and
    writes the store only, so it needs no clone."""
    plan = plan_retitle(
        store, repo=repo, model=build_retitle_model(), limit=DEFAULT_ROADMAP_RETITLE_LIMIT
    )
    apply_retitle(store, plan)
    return JobOutcome()


def _run_stage_adapter(
    store: RoadmapStore,
    repo: str = "",
    clone_path: Path | None = None,
    **_: Any,
) -> JobOutcome:
    """Run the stage job as `devops roadmap stage --confirm` runs it, with the filter, the limit
    and the step budget of the settings: stage the Ready items they name in the job's clone and
    count each item by its result (#2659). An item that failed is recorded in its job record and
    waits for the wait of its failure class (`RETRY_AFTER`); the job fails, once the others are written, only
    when it tried items and handled none (#3493). A failure that no item explains, such as an
    outage, ends the run at once. Each item is written when it is planned, so a stop of the
    Service loses at most the item in progress (#4034). The outcome names the project files that
    the default branch lacks, such as `openspec/config.yaml`, for onboarding (#4629)."""
    source = _job_clone("stage", clone_path)
    writer = StageWriter(store, source)
    plan = plan_stage(
        store,
        repo=repo,
        source=source,
        filters=parse_filters(()),
        model=ToolboxModel(get_task_model("stage")),
        verifier=ToolboxModel(get_task_model("verification")),
        writer=writer,
    )
    applied = writer.applied()
    emit_stage_results(plan, applied, repo=repo)
    for failure in (*plan.failed, *applied.failed):
        log_failed_item(repo, failure.number, failure.step.value, failure.failure_class.value)
    synced = (
        sync_statuses(store, repo=repo, planned=plan.planned) if plan.planned is not None else None
    )
    raise_for_failed_round(plan, applied)
    if synced is not None:
        raise_for_failed(synced.failed, summary=MESSAGES.roadmap.status_sync_failed)
    return JobOutcome(missing=plan.missing)


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
    for held in result.needs_fix:
        logger.info(
            MESSAGES.roadmap.implement_round_needs_fix.format(
                number=held.item.number, pull=held.pull, label=PLAN_NEEDS_FIX_LABEL
            )
        )
    if result.created is not None and result.effort:
        logger.info(MESSAGES.roadmap.implement_round_effort.format(effort=result.effort))
        if result.fallback:
            logger.info(MESSAGES.roadmap.implement_round_fallback)
    raise_for_failed(result.status_failed, summary=MESSAGES.roadmap.status_sync_failed)
    return JobOutcome()


def _run_stage_ready_adapter(store: RoadmapStore, repo: str = "", **_: Any) -> JobOutcome:
    """Mark each green draft pull request that the stage job recorded ready for review, and fail,
    once the others are done, when a pull request failed (#2865). A round with no recorded draft
    sends no request of its own."""
    mark_stage_ready(store, repo=repo)
    return JobOutcome()


def _run_release_comments_adapter(
    store: RoadmapStore,
    *,
    repo: str,
    repo_dir: Path,
    now: datetime,
    **_: Any,
) -> JobOutcome:
    """Comment the version on each closed issue of a recent release, and the time its images run
    in the cluster (#2917). The row calls no model and needs no clone; its ledger
    `release_comments.json` lies beside `schedule.json`. It fails, once both comments are
    posted, when the cluster or the registry could not be read."""
    from devops_cli.config.constants import CONST_ROADMAP_RELEASE_LEDGER_FILENAME
    from devops_cli.http.egress import EgressLevel
    from devops_cli.http.entry import http_client
    from devops_cli.k8s.cluster_job_api import ClusterJobs

    with http_client(EgressLevel.PUBLIC) as client:
        comment_releases(
            store,
            GitHubReleaseFeed(repo),
            ledger_path=repo_dir / CONST_ROADMAP_RELEASE_LEDGER_FILENAME,
            now=now,
            roll=lambda: cluster_digests(ClusterJobs()),
            client=client,
        )
    return JobOutcome()


def _run_alternatives_adapter(store: RoadmapStore, repo: str = "", **_: Any) -> JobOutcome:
    """Check at most `roadmap.alternatives.first_pass_limit` open items while one has no check, else
    `roadmap.alternatives.limit` open items, for an open tool that covers them (#2652).
    A failed check is recorded in its item's job record and the others are written; the
    job fails, naming the items, only when it tried items and checked none (#2949). A repository
    the check is off for, such as a private one, costs a visibility read and nothing else. Each
    check is written when it is done, so a kill of the worker loses at most the check in
    progress, and a rate limit on a write ends the round with the checks that are written
    (#4034). The row sends the coverage gauges of the round after the checks, also when it
    writes nothing (#2950)."""
    plan = plan_alternatives(store, repo=repo, writer=AlternativesWriter(store))
    record_coverage(plan)
    if plan.off_reason:
        logger.info("The alternatives check of %s is off: %s", repo, plan.off_reason)
    raise_for_failed_checks(plan)
    return JobOutcome()


def _run_metrics_adapter(
    store: RoadmapStore,
    repo: str = "",
    clone_path: Path | None = None,
    **_: Any,
) -> JobOutcome:
    """Collect the project metrics, walking the version tags of the job's clone of `repo` and
    counting the Items of `store`, into OTLP (#1358). The Items also give the age of the oldest
    Item of each state, which only this row asks for (#2919). A failed collection and a
    missing clone fail the row (#4052); the status pages have rows of their own."""
    from devops_cli.github.metrics import (
        collect_project_metrics_report,
        emit_project_metrics_telemetry,
    )

    clone = _job_clone("metrics", clone_path)
    report = collect_project_metrics_report(
        root=clone, repo=repo or None, store=store, item_ages=True
    )
    emit_project_metrics_telemetry(report)
    return JobOutcome()


def _run_github_status_adapter(**_: Any) -> JobOutcome:
    """Read the GitHub status page and send its gauge into OTLP (#4052). The row needs no clone.
    A read that fails raises `ServiceStatusError`, so this row fails and no other row does."""
    from devops_cli.telemetry.service_status import (
        emit_service_status_telemetry,
        fetch_github_status,
    )

    emit_service_status_telemetry(fetch_github_status(), "github")
    return JobOutcome()


def _run_cloudflare_status_adapter(**_: Any) -> JobOutcome:
    """Read the Cloudflare status page and send its gauge into OTLP (#4052). The row needs no
    clone. A read that fails raises `ServiceStatusError`, so this row fails and no other row
    does."""
    from devops_cli.telemetry.service_status import (
        emit_service_status_telemetry,
        fetch_cloudflare_status,
    )

    emit_service_status_telemetry(fetch_cloudflare_status(), "cloudflare")
    return JobOutcome()


def _run_pr_conflicts_adapter(
    store: RoadmapStore, *, repo: str, repo_dir: Path, **_: Any
) -> JobOutcome:
    """Comment once on each ready delivery pull request that has merge conflicts with the default
    branch, and send the gauge of those pull requests (#4027). The row calls no model and needs no
    clone; its ledger `pr_conflicts.json` lies beside `schedule.json`. A clean pull request that
    is behind the default branch gets no action. A failed read of GitHub fails this row only."""
    from devops_cli.config.constants import CONST_ROADMAP_PR_CONFLICTS_LEDGER_FILENAME

    watch_conflicts(
        store, repo=repo, ledger_path=repo_dir / CONST_ROADMAP_PR_CONFLICTS_LEDGER_FILENAME
    )
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
        batch_keys=CONST_ROADMAP_STAGE_BATCH_KEYS,
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
    JobRow(
        name="release_comments",
        interval=timedelta(minutes=DEFAULT_ROADMAP_RELEASE_COMMENTS_INTERVAL_MINUTES),
        runner=_run_release_comments_adapter,
        first_run_due=True,
    ),
    JobRow(
        name="github_status",
        interval=timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES),
        runner=_run_github_status_adapter,
        first_run_due=True,
    ),
    JobRow(
        name="cloudflare_status",
        interval=timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES),
        runner=_run_cloudflare_status_adapter,
        first_run_due=True,
    ),
    JobRow(
        name="pr_conflicts",
        interval=timedelta(minutes=DEFAULT_ROADMAP_PR_CONFLICTS_INTERVAL_MINUTES),
        runner=_run_pr_conflicts_adapter,
        first_run_due=True,
    ),
)
"""The rows that call no model: the one that refreshes the metrics, the one that submits the
implement Job, which only talks to the Kubernetes API and GitHub, and the one that marks a green
stage pull request ready, which only talks to GitHub, and the one that comments a release on its
issues, which talks to GitHub, the registry and the Kubernetes API, the two that read the GitHub
and the Cloudflare status page, one row each, so a failed read fails its own row (#4052), and the
one that comments on a ready delivery pull request with merge conflicts, which only talks to GitHub
(#4027). The model runs in the Job, so a model-lane
round that is still running never delays the rows (#2757, #2865). `stage_ready` follows
`implement`, so a Staged item with a green draft gets its Job first, and the row leaves a pull
request that a Job works on alone. `release_comments`, the two status reads and `pr_conflicts`
come last: they wait for no other row, and a slow read delays no other row."""

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
"""The row that runs intake in its own triage lane (#1534)."""

MODEL_LANE_ROWS: tuple[JobRow, ...] = (
    JobRow(
        name="retitle",
        interval=timedelta(minutes=DEFAULT_ROADMAP_RETITLE_INTERVAL_MINUTES),
        batch_keys=CONST_ROADMAP_RETITLE_BATCH_KEYS,
        runner=_run_retitle_adapter,
        first_run_due=True,
    ),
    JobRow(
        name="stage",
        interval=timedelta(minutes=DEFAULT_ROADMAP_STAGE_INTERVAL_MINUTES),
        batch_keys=CONST_ROADMAP_STAGE_BATCH_KEYS,
        runner=_run_stage_adapter,
        needs_clone=True,
        first_run_due=True,
    ),
    JobRow(
        name="refine",
        interval=timedelta(minutes=DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES),
        batch_keys=CONST_ROADMAP_REFINE_BATCH_KEYS,
        runner=_run_refine_adapter,
        needs_clone=True,
        first_run_due=True,
        cross_job_predicate=_refine_cross_job,
    ),
    JobRow(
        name="alternatives",
        interval=timedelta(minutes=DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES),
        runner=_run_alternatives_adapter,
        first_run_due=True,
    ),
)
"""The rows that call the model, which answers one call at a time: intake, retitle, stage, refine
and the daily check for alternative tools (#2652). Stage runs before refine: a round of 7 refine
items takes 35 to 65 minutes and refine is due again when it ends, so with refine first the first
round of each new pod held the lane before stage had a turn (#4796)."""

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


def scoped_update_wakes_model_lane(delivery: WebhookDelivery, outcome: JobOutcome | None) -> bool:
    """Whether the model lane runs a round after the scoped update of `delivery` (#4412): after an
    edit, which changes the text that refine and retitle read, and after a placement of a critical
    fix or a P0 item, which stamps `refine_due`. The triage lane's scoped update wakes no other
    lane itself."""
    return delivery.action == "edited" or (outcome is not None and outcome.placed_critical_or_p0)


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
    each job's last round, so a scoped update never hides a change it did not handle. Its model
    and GitHub requests name its job as their row, as the job counter does (#4522)."""
    update = SCOPED_UPDATES.get((delivery.event, delivery.action))
    if update is None:
        return None
    schedule_path = _resolve_roadmap_repo_path(
        _resolve_data_dir(data_dir),
        delivery.repo,
        CONST_ROADMAP_RUN_STATE_FILENAME,
        error_cls=GitOperationError,
    )
    try:
        with request_scope(row=update.job):
            outcome = update.runner(
                store,
                delivery,
                repo_dir=schedule_path.parent,
                now=now or datetime.now(UTC),
                model=model,
            )
    except Exception as exc:
        _count_job(delivery.repo, update.lane, update.job, _failed_result(exc))
        raise
    _count_job(delivery.repo, update.lane, update.job, CONST_SERVICE_JOB_RESULT_SUCCESS)
    return outcome


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
    include_release_comments: bool | None = None,
    include_retitle: bool | None = None,
) -> tuple[JobRow, ...]:
    """The due table's rows, in its order, each running `runners`' stub for its job: metrics,
    implement, stage_ready, release_comments, github_status, cloudflare_status, pr_conflicts,
    intake, retitle, stage, refine and alternatives.
    Intake is always in; the others are added when asked for or given a stub."""
    r = runners or {}
    add_retitle = include_retitle if include_retitle is not None else ("retitle" in r)
    add_refine = include_refine if include_refine is not None else ("refine" in r)
    add_metrics = include_metrics if include_metrics is not None else ("metrics" in r)
    add_stage = include_stage if include_stage is not None else ("stage" in r)
    add_implement = include_implement if include_implement is not None else ("implement" in r)
    add_stage_ready = (
        include_stage_ready if include_stage_ready is not None else ("stage_ready" in r)
    )
    add_release_comments = (
        include_release_comments
        if include_release_comments is not None
        else ("release_comments" in r)
    )
    add_alternatives = (
        include_alternatives if include_alternatives is not None else ("alternatives" in r)
    )
    kept = {
        "metrics": add_metrics,
        "refine": add_refine,
        "retitle": add_retitle,
        "stage": add_stage,
        "implement": add_implement,
        "stage_ready": add_stage_ready,
        "release_comments": add_release_comments,
        "github_status": "github_status" in r,
        "cloudflare_status": "cloudflare_status" in r,
        "pr_conflicts": "pr_conflicts" in r,
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
    time, the repository's data directory and the read of its newest issue, which reads nothing
    in a round with no trigger."""

    schedule: Mapping[str, datetime]
    batch: Mapping[tuple[str, str, str], int]
    changes: Sequence[Change]
    now: datetime
    repo_dir: Path
    newest_issue: Callable[[], int | None] = lambda: None

    def is_due(self, row: JobRow) -> bool:
        """Whether `row` is due before any other row runs: by its interval, a hint in the
        batch, a stamp of another row, or its due rule over the changes since its own last
        success. Intake runs before refine, so its `refine_due` must be newer than refine's last
        success. Refine runs after stage, so a `stage_due` of the round in which stage last
        succeeded still makes stage due (#4796)."""
        last = self.schedule.get(row.name)
        if _is_interval_due(row, last, self.now) or _batch_matches(self.batch, row):
            return True
        if row.name == "refine":
            refine_due = self.schedule.get(CONST_ROADMAP_REFINE_DUE_STAMP)
            if refine_due is not None and (last is None or refine_due > last):
                return True
        if row.name == "stage":
            stage_due = self.schedule.get(CONST_ROADMAP_STAGE_DUE_STAMP)
            if stage_due is not None and (last is None or stage_due >= last):
                return True
        if row.due_rule is None:
            return False
        since = last or self.now
        mine = tuple(change for change in self.changes if change.at >= since)
        return row.due_rule(DueCheck(mine, self.now, last, self.repo_dir, self.newest_issue))


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


_FailedRounds = TypeAdapter(
    list[
        tuple[str, str, int, str, list[str], datetime | None]
        | tuple[str, str, int, str, list[str]]
        | tuple[str, str, int, str]
    ]
)
"""A ledger record: each repository and job with the rounds it failed in a row, the input of the
last, the class of each round's error and the time of the next probe round (#4065). A record
written before the retry time holds entries of five fields, and one written before the causes
(#3493) holds entries of four; both load with no retry time, so they keep the rule of the input
digest, and the causes of the second read as `unknown`."""
_KeptRounds = TypeAdapter(list[tuple[str, str, int, str, list[str], datetime | None]])
"""The record that the ledger writes: each entry holds its causes and its retry time."""


class FailureLedger:
    """How many rounds in a row each roadmap job failed, and the input it failed on (#2161).

    A job that fails `limit` rounds in a row does not run until its input is not the one it
    failed on, or until its retry time (#4065). Without a `limit`, the ledger reads the setting
    `service.max_failed_rounds` (#4802). New input is a webhook trigger, a change to an
    item the job reads, or a comment of a person (#2754). The retry time is the time of the last
    failed round plus `RETRY_AFTER` of the failure class of that round: after it, the job runs one
    probe round. A failed probe round sets a new retry time, and a success clears the job's
    record. A poll alone brings no new input, so a failing job costs one round for each wait and
    not one for each round. With a `record`, the ledger is kept in that file at each change and
    read back when the ledger is made, so a restart of the Service keeps it (#2474). The Service's
    /metrics shows each job that failed its limit of rounds in a row, with the class of its last
    failure (#2475).

    The ledger also holds the cause of each failed round: the value of its failure class, for the
    log line that suspends a job. The record keeps the causes, so a restart does not make them
    `unknown` (#3493). A record from before the causes or before the retry time loads, and its
    entry keeps the rule of the input digest alone.
    """

    def __init__(self, limit: int | None = None, record: Path | None = None) -> None:
        if limit is None:
            limit = load_settings().service.max_failed_rounds
        self._limit = limit
        self._record = record
        self._lock = threading.Lock()
        kept = [] if record is None else read_state_record(record, _FailedRounds, [])
        self._failed: dict[tuple[str, str], tuple[int, str, datetime | None]] = {}
        self._causes: dict[tuple[str, str], deque[str]] = {}
        for entry in kept:
            repo, job, rounds, failed_on = entry[:4]
            retry_at = entry[5] if len(entry) == 6 else None
            self._failed[(repo, job)] = (rounds, failed_on, retry_at)
            if len(entry) >= 5:
                self._causes[(repo, job)] = deque(entry[4][-limit:], maxlen=limit)
        self._labels: dict[tuple[str, str], str] = {}
        for repo, job in self._failed:
            self._report_locked(repo, job)

    @property
    def limit(self) -> int:
        """How many failed rounds in a row suspend a job."""
        return self._limit

    def suspended(self, repo: str, job: str, current: str, now: datetime) -> bool:
        """Whether `job` failed `limit` rounds in a row on this same input and `now` is before its
        retry time. An entry with no retry time is suspended until its input changes."""
        with self._lock:
            rounds, failed_on, retry_at = self._failed.get((repo, job), (0, None, None))
            if rounds < self._limit or failed_on != current:
                return False
            if retry_at is None:
                return True
            self._report_locked(repo, job, now)
            return now < retry_at

    def holds_failure(self, repo: str, job: str) -> bool:
        """Whether `job` failed a round that no success has cleared since."""
        with self._lock:
            return (repo, job) in self._failed

    def retry_at(self, repo: str, job: str) -> datetime | None:
        """The time of the next probe round of `job`, or None when it has none."""
        with self._lock:
            return self._failed.get((repo, job), (0, None, None))[2]

    def failed(self, repo: str, job: str, current: str, cause: str, now: datetime) -> int:
        """Count a failed round at `now` on `current` with its `cause`, the value of its failure
        class; the rounds in a row, which restart at 1 when the input is not the one of the last
        failure. From the limit on, the retry time is `now` plus the wait of the class."""
        with self._lock:
            rounds, failed_on, _ = self._failed.get((repo, job), (0, None, None))
            rounds = rounds + 1 if failed_on == current or rounds < self._limit else 1
            retry_at = now + retry_after(cause) if rounds >= self._limit else None
            self._failed[(repo, job)] = (rounds, current, retry_at)
            causes = self._causes.get((repo, job), deque(maxlen=self._limit))
            if rounds == 1:
                causes.clear()
            causes.append(cause)
            self._causes[(repo, job)] = causes
            self._keep_locked()
            self._report_locked(repo, job, now)
            return rounds

    def causes(self, repo: str, job: str) -> tuple[str, ...]:
        """The cause of each of the last rounds in a row that `job` failed, oldest first. A round
        that a process before the last restart counted has the cause `unknown`."""
        with self._lock:
            rounds, _, _ = self._failed.get((repo, job), (0, None, None))
            known = tuple(self._causes.get((repo, job), ()))
            return (CONST_SERVICE_CAUSE_UNKNOWN,) * (min(rounds, self._limit) - len(known)) + known

    def succeeded(self, repo: str, job: str) -> None:
        """Clear the record of `job`."""
        with self._lock:
            self._causes.pop((repo, job), None)
            if self._failed.pop((repo, job), None) is not None:
                self._keep_locked()
                self._report_locked(repo, job)

    def _class_label_locked(self, repo: str, job: str) -> str:
        """The failure class of the last round of `job` as the `class` label of its gauges: the
        last cause when it is a class, else `unknown`; the caller holds the lock."""
        known = self._causes.get((repo, job))
        last = known[-1] if known else CONST_SERVICE_CAUSE_UNKNOWN
        try:
            return FailureClass(last).value
        except ValueError:
            return CONST_SERVICE_CAUSE_UNKNOWN

    def _report_locked(self, repo: str, job: str, now: datetime | None = None) -> None:
        """Show on the Service's /metrics whether `job` failed its limit of rounds in a row, with
        the class of its last failure, and the seconds before its next probe round as of `now`
        (0 without `now`, or without a retry time). The series of the class that the job had
        before is set to 0, as the metrics hold no call that removes a series. The caller holds
        the lock, or the ledger is still being made."""
        key = (repo, job)
        entry = self._failed.get(key)
        before = self._labels.get(key)
        label = None if entry is None else self._class_label_locked(repo, job)
        if before is not None and before != label:
            self._set_gauges(repo, job, before, 0.0, 0.0)
        if entry is None or label is None:
            self._labels.pop(key, None)
            return
        rounds, _, retry_at = entry
        seconds = 0.0 if retry_at is None or now is None else (retry_at - now).total_seconds()
        self._labels[key] = label
        self._set_gauges(repo, job, label, 1.0 if rounds >= self._limit else 0.0, max(0.0, seconds))

    @staticmethod
    def _set_gauges(repo: str, job: str, label: str, suspended: float, seconds: float) -> None:
        labels = {"repo": repo, "row": job, "class": label}
        GLOBAL_METRICS.set_gauge(CONST_SERVICE_METRIC_JOB_SUSPENDED, suspended, labels=labels)
        GLOBAL_METRICS.set_gauge(
            CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS, seconds, labels=labels
        )

    def _keep_locked(self) -> None:
        """Write the ledger to its record, if it has one; the caller holds the lock."""
        if self._record is not None:
            kept = [
                (repo, job, rounds, failed_on, list(self._causes.get((repo, job), ())), retry_at)
                for (repo, job), (rounds, failed_on, retry_at) in self._failed.items()
            ]
            keep_state_record(
                self._record, StateRecord.LEDGER, _KeptRounds.dump_python(kept, mode="json")
            )


def service_state_dir(data_dir: Path | str | None = None) -> Path:
    """Where the Service keeps what a restart must not clear (#2474): the `roadmap` directory of
    the data directory, which holds each repository's `schedule.json`, on the Service's volume."""
    return _resolve_data_dir(data_dir) / "roadmap"


def _has_push(batch: Mapping[tuple[str, str, str], int]) -> bool:
    """Whether the batch holds a trigger other than a poll, such as a webhook delivery."""
    return any(key[0] != CONST_SERVICE_SOURCE_POLL for key in batch)


def _round_input(
    changes: Sequence[Change],
    batch: Mapping[tuple[str, str, str], int],
    at: datetime,
    reads_changes: bool = True,
    comment_at: datetime | None = None,
) -> str:
    """What the round's jobs read, as one digest a ledger record can keep: the changes since the
    oldest last success and, when the batch holds a trigger other than a poll, the time of the
    round, so such a trigger is new input to every job. A lane that reads no change has no input
    that a poll can change, so its input holds the hour of the round: a suspended row tries again
    in a later hour, once its fault is fixed (#2757). A row that failed a round also holds
    `comment_at`, when the newest comment of a person was made, so that person's answer is new
    input for it (#2754). A row with no such comment has the digest it had before."""
    seen = [(change.kind.value, change.number, change.at.isoformat()) for change in changes]
    hour = None if reads_changes else at.strftime("%Y-%m-%dT%H")
    parts: list[Any] = [seen, at.isoformat() if _has_push(batch) else None, hour]
    if comment_at is not None:
        parts.append(comment_at.isoformat())
    return hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()


def _row_inputs(
    rows: Sequence[JobRow],
    changes: Sequence[Change],
    batch: Mapping[tuple[str, str, str], int],
    at: datetime,
    comment_stamps: Mapping[str, datetime],
) -> dict[str, str]:
    """The input of each row in the round: the input of the round, and for a row in
    `comment_stamps` also the time of that comment of a person (#2754)."""
    reads_changes = _lane_reads_changes(rows)
    return {
        row.name: _round_input(changes, batch, at, reads_changes, comment_stamps.get(row.name))
        for row in rows
    }


_COMMENT_WINDOW = DEFAULT_GH_REST_PER_PAGE
"""How many of the newest comments of a repository a round reads for a comment of a person: one
page of the listing, so the read is one request (#2754)."""


def _person_comment_stamps(
    rows: Sequence[JobRow],
    initially_due: Mapping[str, bool],
    schedule: Mapping[str, datetime],
    failures: FailureLedger,
    batch: Mapping[tuple[str, str, str], int],
    repo: str,
    store: RoadmapStore,
) -> dict[str, datetime]:
    """For each row that may run in the round and failed a round before, when the newest comment
    of a person was made, unless that comment is older than the row's last success: the new input
    that a person's answer gives to a suspended row (#2754).

    One read serves all those rows: the comments of the repository, newest first, from the oldest
    last success among them (from the first comment when one never succeeded), up to the first
    comment of a person. The read stops at the newest `_COMMENT_WINDOW` comments. A person's
    comment that more comments than that have followed counts as no comment, so the row has the
    input it had before and runs again once. A comment older than a row's own last success is no
    input for it, so what a row holds never depends on the other rows that set the start of the
    read.

    The round reads nothing when a webhook started it, since the time of such a round is already
    new input for every row, and when no row that may run failed a round. A read that fails
    raises, as the read of the changes does."""
    if _has_push(batch):
        return {}
    failed = [
        row.name
        for row in rows
        if (initially_due[row.name] or row.cross_job_predicate is not None)
        and failures.holds_failure(repo, row.name)
    ]
    if not failed:
        return {}
    lasts = {name: schedule.get(name) for name in failed}
    known = [last for last in lasts.values() if last is not None]
    since = min(known) if len(known) == len(lasts) else None
    actor = _current_actor(store)
    newest = next(
        (
            c.created_at
            for c in islice(store.comments_since(since), _COMMENT_WINDOW)
            if is_person_comment(c, actor)
        ),
        None,
    )
    if newest is None:
        return {}
    return {name: newest for name, last in lasts.items() if last is None or newest >= last}


def _count_failure(
    failures: FailureLedger,
    repo: str,
    job: str,
    current: str,
    exc: BaseException,
    now: datetime,
) -> None:
    """Count a failed round of `job` at `now`, and log once when it reaches the limit. A round
    that the stop of the Service ends is not at fault, so it leaves the count as it was (#2753).
    The cause is the value of the failure class of `exc`. An error that is no `DevOpsCLIError`
    is `ci_infra`, as `retry_after` reads an unknown record (#4065)."""
    if ended_by_stop(exc):
        return
    klass = failure_class_of(exc) if isinstance(exc, DevOpsCLIError) else FailureClass.CI_INFRA
    rounds = failures.failed(repo, job, current, klass.value, now)
    retry_at = failures.retry_at(repo, job)
    if rounds == failures.limit and retry_at is not None:
        message = MESSAGES.serve.job_suspended.format(
            job=job,
            repo=repo,
            rounds=rounds,
            causes=", ".join(failures.causes(repo, job)),
            failure_class=klass.value,
            retry_at=retry_at.isoformat(),
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
    """The first line of an exception's message, masked and capped at 256 chars. The numbers of
    the failed items of an error that has them follow the cut, so a long reason of the first item
    hides no other item (#4535)."""
    lines = str(exc).strip().splitlines()
    first = mask_secrets(lines[0] if lines else type(exc).__name__)[:256]
    items: Sequence[int] = getattr(exc, "failed_items", ())
    if not items:
        return first
    return f"{first} (failed items: {', '.join(f'#{number}' for number in items)})"


def _failed_result(exc: BaseException) -> str:
    """The `result` of a job that ended with `exc`: a stop of the Service is no failure (#2753)."""
    return (
        CONST_SERVICE_JOB_RESULT_STOPPED if ended_by_stop(exc) else CONST_SERVICE_JOB_RESULT_ERROR
    )


def _count_job(repo: str, lane: str | None, row: str, result: str) -> None:
    """Count one job that ended under its repository, lane, row and result (#3495). A run with
    no lane, such as one of the command line, counts no job."""
    if lane is not None:
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_JOBS,
            labels={"repo": repo, "lane": lane, "row": row, "result": result},
        )


def _observe_row(repo: str, row: str, started: float | None, result: str) -> None:
    """Send the seconds that a row ran, since `started` on the monotonic clock, under its
    repository, row and result (#4058). The run of the command line sends it too. A row that
    failed before its runner started, such as in its clone, has no `started` and sends nothing."""
    if started is None:
        return
    emit(
        ROADMAP_ROW_SECONDS,
        clock.monotonic() - started,
        {"repo": repo, "row": row, "result": result},
    )


def _stamp_stage_due(schedule_path: Path, outcome: JobOutcome, at: datetime) -> None:
    """Stamp `stage_due` at `at`, the time of the round, when `outcome` set an item Ready, so the
    stage row, which runs before refine, is due in the next round (#2659, #4796)."""
    if outcome.set_ready:
        _record_success(schedule_path, CONST_ROADMAP_STAGE_DUE_STAMP, at)


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
    lane: str | None,
    comment_stamps: Mapping[str, datetime],
) -> tuple[str, ...]:
    """Execute all due jobs in order with failure tracking, the clone rows in `clone_dirname`.
    Each runner also gets the repository's data directory and the round's time. With the
    `failures` ledger, a job that failed its limit of rounds in a row on the same input does not
    run (#2161). The input of a row in `comment_stamps` also holds the time of that comment of a
    person (#2754). A refusal of the identity ends the round at once: no later job sends a
    request. Each row runs in the request scope of its name, so its GitHub requests count under
    it (#2475). Once the Service stops, no due row starts: the round ends with the stop, and the
    rows it did not start stay due for the next pod (#4485). A row whose outcome set an item Ready,
    also a failed one, stamps `stage_due` (#2659, #4796)."""
    succeeded_jobs: list[str] = []
    failed_jobs: list[str] = []
    outcomes: dict[str, JobOutcome] = {}
    clone_path: Path | None = None
    clone_error: Exception | None = None
    clone_jobs: list[str] = []
    error_entries: list[tuple[list[str], Exception]] = []
    stop: ServiceStoppingError | None = None
    inputs = _row_inputs(rows, changes, active_batch, current_time, comment_stamps)

    for row in rows:
        is_due = initially_due[row.name] or (
            row.cross_job_predicate is not None and row.cross_job_predicate(outcomes)
        )
        if not is_due or failures.suspended(repo, row.name, inputs[row.name], current_time):
            continue
        if service_stopping():
            stop = stop_before(f"row {row.name}")
            break

        if row.needs_clone and clone_error is not None:
            failed_jobs.append(row.name)
            clone_jobs.append(row.name)
            _count_job(repo, lane, row.name, _failed_result(clone_error))
            continue

        started: float | None = None
        try:
            if row.needs_clone and clone_path is None:
                clone_path = ensure_checkout(repo, base_data, remote_url, clone_dirname)

            started = clock.monotonic()
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
            _stamp_stage_due(schedule_path, outcomes[row.name], current_time)
            succeeded_jobs.append(row.name)
            _record_success(schedule_path, row.name, current_time)
            failures.succeeded(repo, row.name)
            _count_job(repo, lane, row.name, CONST_SERVICE_JOB_RESULT_SUCCESS)
            _observe_row(repo, row.name, started, CONST_SERVICE_JOB_RESULT_SUCCESS)
        except Exception as exc:
            failed_jobs.append(row.name)
            _count_job(repo, lane, row.name, _failed_result(exc))
            _observe_row(repo, row.name, started, _failed_result(exc))
            outcomes[row.name] = _outcome_of_failure(exc)
            _stamp_stage_due(schedule_path, outcomes[row.name], current_time)
            _count_failure(failures, repo, row.name, inputs[row.name], exc, current_time)
            if row.needs_clone and clone_path is None:
                clone_error = exc
                clone_jobs.append(row.name)
                error_entries.append((clone_jobs, exc))
            else:
                error_entries.append(([row.name], exc))
            if identity_refused(exc):
                break

    _raise_for_rows(failed_jobs, error_entries, stop)
    return tuple(succeeded_jobs)


def _raise_for_rows(
    failed_jobs: list[str],
    error_entries: Sequence[tuple[list[str], Exception]],
    stop: ServiceStoppingError | None,
) -> None:
    """Raise the error of a round whose rows failed, which names each row and groups their
    errors as its cause. Else raise the stop that ended the round before a row started."""
    if not failed_jobs:
        if stop is not None:
            raise stop
        return
    error_parts: list[str] = []
    exceptions: list[Exception] = []
    for job_names, entry_exc in error_entries:
        entry_exc.add_note(", ".join(job_names))
        error_parts.append(f"{', '.join(job_names)}: {_format_error_line(entry_exc)}")
        exceptions.append(entry_exc)

    msg = f"Roadmap jobs failed: {'; '.join(error_parts)}"
    cause = ExceptionGroup("Roadmap jobs failed", exceptions)
    raise RoadmapRunError(msg, failed_jobs=failed_jobs) from cause


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
    lane: str | None = None,
) -> tuple[str, ...]:
    """Evaluate and execute due roadmap jobs, the clone rows in `clone_dirname`.

    With no trigger in the batch, rows are judged on no changes, which reads nothing; a round
    whose rows are all not due reads no more than its changes and the newest issue (#4540).
    Each row is judged by `schedule.json` as the round found it, and each success is written as
    it happens. When a row that may run failed a round before, a round that only polls reads the
    newest comments of the repository once, for a comment of a person is new input for such a
    row (#2754).
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
    polled = replace(quiet, changes=changes, newest_issue=cache(store.newest_issue_number))
    initially_due = {row.name: polled.is_due(row) for row in rows}
    if not any(initially_due.values()):
        return ()

    if dry_run:
        return _simulate_dry_run(rows, initially_due)

    ledger = failures or FailureLedger()
    comment_stamps = _person_comment_stamps(
        rows, initially_due, schedule, ledger, active_batch, repo, store
    )
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
        ledger,
        lane,
        comment_stamps,
    )


def service_job(
    batch: TriggerBatch,
    *,
    table: Sequence[JobRow],
    clone_dirname: str,
    lane: str | None = None,
    failures: FailureLedger | None = None,
    listing: IncrementalListing | None = None,
) -> None:
    """Service mode adapter that runs one lane's due roadmap jobs, `table`, in its clone
    `clone_dirname` for a coalesced trigger batch, on the roadmap store of the batch's
    repository, counting its failed rounds in `failures`. The store reads every issue through
    `listing` when one is given, else the whole listing. The store reads no repository file: a
    repository needs no roadmap configuration (ADR 0016)."""
    from devops_cli.roadmap.stores import store as roadmap_store

    repo = batch.repo
    run_due_jobs(
        repo,
        roadmap_store.get_roadmap_store(repo, listing=listing),
        batch=batch,
        table=table,
        clone_dirname=clone_dirname,
        failures=failures,
        lane=lane,
    )


def service_jobs(state_dir: Path) -> Mapping[str, LaneJob]:
    """Each lane's job, which `devops serve --service` runs in one worker per lane of each
    repository (#1532). Every lane of every repository shares one ledger of failed rounds, kept
    in `state_dir`, so a restart keeps it (#2474). The triage lane, which runs intake, reads every
    issue through the listing snapshot in `state_dir`, as the scoped intake of a delivery does
    (#3670); its rounds and the scoped updates run one at a time on its worker, so one writer
    keeps the snapshot of each repository. The status lane reads every issue through a snapshot
    of its own, which only its worker writes (#4854)."""
    failures = FailureLedger(record=state_dir / CONST_SERVICE_FAILURES_FILENAME)
    return {
        CONST_SERVICE_LANE_STATUS: partial(
            service_job,
            table=STATUS_LANE_ROWS,
            clone_dirname=CONST_ROADMAP_RUN_CLONE_DIRNAME,
            lane=CONST_SERVICE_LANE_STATUS,
            failures=failures,
            listing=lane_listing(state_dir, CONST_SERVICE_LANE_STATUS),
        ),
        CONST_SERVICE_LANE_TRIAGE: partial(
            service_job,
            table=TRIAGE_LANE_ROWS,
            clone_dirname=CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME,
            lane=CONST_SERVICE_LANE_TRIAGE,
            failures=failures,
            listing=intake_listing(state_dir),
        ),
        CONST_SERVICE_LANE_MODEL: partial(
            service_job,
            table=MODEL_LANE_ROWS,
            clone_dirname=CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
            lane=CONST_SERVICE_LANE_MODEL,
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
    "scoped_update_wakes_model_lane",
    "service_job",
    "service_jobs",
    "service_state_dir",
]
