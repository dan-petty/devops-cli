"""Check a repository for the prerequisites of the roadmap jobs (#1359).

Onboarding checks six prerequisites:
1. Issues are turned on.
2. The App devops-cli-service is installed on the repository.
3. .github/labels.yml is on the default branch and is valid.
4. Every workflow label of the package and every label of that file exists on GitHub (#4652).
5. The repository is in service.repos.
6. The repository webhook posts the roadmap events to the Service.

It also reports three RAG rows of the repository: the points that Qdrant holds, the visibility
those points record, and the schedule that fills them (#3771). The exit code follows the six
prerequisites only.

With --confirm, missing labels are created with POST. No labels are edited or deleted. With
--confirm and a repository that service.repos holds, the command also starts the ingestion pass
of #1389 for that repository alone, and prints the point count of each collection (#3771). The
command writes no config file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import yaml
from pydantic import ValidationError

from devops_cli.ai.rag.indexer import rag_collection_names, resolve_qdrant_client
from devops_cli.ai.rag.ingest import visibility_from_payload
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.config.constants import (
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_WEBHOOK_EVENTS,
)
from devops_cli.config.settings import Settings, load_settings
from devops_cli.core.process import acts_as_github_app
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.github.client import RepositoryHook
from devops_cli.github.labels import LabelSpec, diff_labels
from devops_cli.github.session import GitHubSession, get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stores.store import RoadmapStore
from devops_cli.roadmap.title_labels import declared_label_specs
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS

_ROW_1_PREREQUISITE: Final[str] = "Issues are turned on"
_ROW_2_PREREQUISITE: Final[str] = "The App devops-cli-service is installed on the repository"
_ROW_3_PREREQUISITE: Final[str] = ".github/labels.yml is on the default branch and is valid"
_ROW_4_PREREQUISITE: Final[str] = (
    "Every workflow label and every label of .github/labels.yml exists on GitHub"
)
_ROW_5_PREREQUISITE: Final[str] = "The repository is in service.repos"
_ROW_6_PREREQUISITE: Final[str] = "The repository webhook posts the roadmap events to the Service"
_RAG_INDEXED_ROW: Final[str] = "indexed"
_RAG_VISIBILITY_ROW: Final[str] = "rag visibility"
_RAG_SCHEDULE_ROW: Final[str] = "rag schedule"
_RAG_ROWS_TITLE: Final[str] = "RAG rows:"


@dataclass(frozen=True)
class OnboardingRow:
    """One prerequisite row: its number, name, state, and optional reason or step."""

    number: int
    prerequisite: str
    state: str
    reason: str | None = None
    step: str | None = None


@dataclass(frozen=True)
class RagRow:
    """One RAG row: its name, state, and optional reason or step. It holds no number, because the
    exit code does not read it (#3771)."""

    name: str
    state: str
    reason: str | None = None
    step: str | None = None


@dataclass(frozen=True)
class OnboardingReport:
    """The report of checking onboarding prerequisites for a repository."""

    repo: str
    rows: tuple[OnboardingRow, ...]
    missing_labels: tuple[LabelSpec, ...] = ()
    differing_labels: tuple[LabelSpec, ...] = ()
    rag_rows: tuple[RagRow, ...] = ()

    @property
    def has_missing(self) -> bool:
        """Whether any prerequisite row is missing."""
        return any(row.state == "missing" for row in self.rows)

    @property
    def not_readable_count(self) -> int:
        """The count of prerequisite rows that are not readable."""
        return sum(1 for row in self.rows if row.state.startswith("not readable"))


@dataclass(frozen=True)
class OnboardingApplied:
    """The result of applying onboarding actions."""

    created_labels: tuple[LabelSpec, ...] = ()


@dataclass(frozen=True)
class _ProjectIndex:
    """The points of one project in both collections, and the visibility that they record."""

    code: int
    docs: int
    visibility: str | None


def _check_row_1(session: GitHubSession, repo: str) -> tuple[OnboardingRow, dict[str, Any] | None]:
    """Check whether issues are turned on, and give the repository payload that GitHub returns."""
    try:
        data = session.rest("GET", f"/repos/{repo}")
        if data.get("has_issues"):
            return OnboardingRow(1, _ROW_1_PREREQUISITE, "present"), data
        step = f"devops gh api -X PATCH repos/{repo} -f has_issues=true"
        return OnboardingRow(1, _ROW_1_PREREQUISITE, "missing", step=step), data
    except DevOpsCLIError as exc:
        return OnboardingRow(1, _ROW_1_PREREQUISITE, "not readable", reason=str(exc)), None


def _check_row_2(session: GitHubSession, repo: str) -> OnboardingRow:
    """Check whether the GitHub App is installed on the repository."""
    if not acts_as_github_app():
        try:
            login = session.login
        except DevOpsCLIError as exc:
            return OnboardingRow(2, _ROW_2_PREREQUISITE, "not readable", reason=str(exc))
        step = (
            "A person adds the repository at the installation page of the App. "
            "Run this command as the App, or look at the page."
        )
        return OnboardingRow(2, _ROW_2_PREREQUISITE, f"not readable as {login}", step=step)
    try:
        installed = any(
            item.get("full_name") == repo
            for item in session.paginate("/installation/repositories", iterable_key="repositories")
        )
        if installed:
            return OnboardingRow(2, _ROW_2_PREREQUISITE, "present")
        step = "A person adds the repository at the installation page of the App."
        return OnboardingRow(2, _ROW_2_PREREQUISITE, "missing", step=step)
    except DevOpsCLIError as exc:
        return OnboardingRow(2, _ROW_2_PREREQUISITE, "not readable", reason=str(exc))


def _check_row_3(
    store: RoadmapStore,
) -> tuple[OnboardingRow, list[LabelSpec] | None]:
    """Check whether .github/labels.yml is present and valid."""
    try:
        text = store.repository_file(CONST_ROADMAP_LABELS_PATH, ref=None)
    except GitHubFileNotFoundError:
        return (
            OnboardingRow(3, _ROW_3_PREREQUISITE, "missing", reason="labels.yml is missing"),
            None,
        )
    except DevOpsCLIError as exc:
        return (
            OnboardingRow(3, _ROW_3_PREREQUISITE, "not readable", reason=str(exc)),
            None,
        )

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError:
        return (
            OnboardingRow(3, _ROW_3_PREREQUISITE, "missing", reason="labels.yml is not YAML"),
            None,
        )

    if not isinstance(raw, list):
        return (
            OnboardingRow(
                3,
                _ROW_3_PREREQUISITE,
                "missing",
                reason="labels.yml is not a list of labels",
            ),
            None,
        )

    try:
        specs = declared_label_specs(text)
    except yaml.YAMLError, ValidationError:
        return (
            OnboardingRow(
                3,
                _ROW_3_PREREQUISITE,
                "missing",
                reason="labels.yml is not a list of labels",
            ),
            None,
        )

    return OnboardingRow(3, _ROW_3_PREREQUISITE, "present"), specs


def _check_row_4(
    store: RoadmapStore,
    specs: list[LabelSpec] | None,
) -> tuple[OnboardingRow, tuple[LabelSpec, ...], tuple[LabelSpec, ...]]:
    """Check whether every workflow label and every label of the file exists on GitHub. With no
    usable file (`specs` None), the row checks the workflow labels."""
    desired = specs if specs is not None else list(WORKFLOW_LABELS)
    try:
        existing = [label.model_dump() for label in store.repository_labels()]
        to_create, to_update, _ = diff_labels(desired, existing)
        missing = tuple(to_create)
        differing = tuple(to_update)
        if not missing:
            return (
                OnboardingRow(4, _ROW_4_PREREQUISITE, "present"),
                missing,
                differing,
            )
        step = "Run with --confirm to create missing labels."
        return (
            OnboardingRow(
                4,
                _ROW_4_PREREQUISITE,
                "missing",
                reason=f"{len(missing)} label(s) missing",
                step=step,
            ),
            missing,
            differing,
        )
    except DevOpsCLIError as exc:
        return (
            OnboardingRow(4, _ROW_4_PREREQUISITE, "not readable", reason=str(exc)),
            (),
            (),
        )


def _service_repos_step(repo: str) -> str:
    """The step that adds `repo` to the list that the scheduled pass reads. The command never
    writes `config.yaml`."""
    return f"Add to service.repos in config.yaml:\n  - {repo}\nThen run: devops k8s deploy-stack"


def _check_row_5(repo: str, settings: Settings) -> OnboardingRow:
    """Check whether the repository is in service.repos."""
    if repo in settings.service.repos:
        return OnboardingRow(5, _ROW_5_PREREQUISITE, "present")
    return OnboardingRow(5, _ROW_5_PREREQUISITE, "missing", step=_service_repos_step(repo))


def webhook_step(settings: Settings) -> str:
    """The step for a person that adds the repository webhook (#3772). It names no secret. The
    hook can send more events than the Service takes (#5035)."""
    events = ", ".join(sorted(CONST_ROADMAP_WEBHOOK_EVENTS))
    return (
        f"Add the webhook {settings.service.webhook_url} with content type application/json and "
        f"at least the events {events}, set it active, and store its secret with "
        "`devops config set service.webhook_secrets`."
    )


def _check_row_6(session: GitHubSession, repo: str, settings: Settings) -> OnboardingRow:
    """The repository webhook: present, missing, wrong, or not readable without administration
    read (#3772)."""
    step = webhook_step(settings)
    try:
        hooks = session.client.get_repository_hooks(repo)
    except GitHubOperationError as exc:
        return OnboardingRow(
            6,
            _ROW_6_PREREQUISITE,
            f"not readable as {session.login}",
            reason=str(exc),
            step=step,
        )
    if not hooks:
        return OnboardingRow(6, _ROW_6_PREREQUISITE, "missing", step=step)
    url = settings.service.webhook_url
    events = set(CONST_ROADMAP_WEBHOOK_EVENTS)
    matching = [hook for hook in hooks if hook.url == url]
    if any(
        hook.active and hook.content_type == "json" and events <= set(hook.events)
        for hook in matching
    ):
        return OnboardingRow(6, _ROW_6_PREREQUISITE, "present")
    wrong = _wrong_webhook_fields(
        matching[0] if matching else hooks[0], known_url=bool(matching), events=events
    )
    return OnboardingRow(
        6, _ROW_6_PREREQUISITE, "wrong", reason=f"Wrong: {', '.join(wrong)}.", step=step
    )


def _wrong_webhook_fields(hook: RepositoryHook, *, known_url: bool, events: set[str]) -> list[str]:
    """The fields of `hook` that do not match, with `url` when no hook holds the Service URL."""
    wrong = []
    if not known_url:
        wrong.append("url")
    if not hook.active:
        wrong.append("active")
    if hook.content_type != "json":
        wrong.append("content_type")
    if not events <= set(hook.events):
        wrong.append("events")
    return wrong


def _first_point(qdrant: QdrantClient, collection: str, repo: str) -> dict[str, Any] | None:
    """One point of `repo` in `collection`, or None when the collection holds none."""
    points = qdrant.scroll_points(
        collection, filter_payload={"project_name": repo}, limit=1, with_payload=True
    )
    return points[0] if points else None


def _recorded_visibility(point: dict[str, Any] | None) -> str | None:
    """The visibility that the payload of `point` records, or None when it records none."""
    if point is None:
        return None
    value = (point.get("payload") or {}).get("visibility")
    return str(value).lower() if value else None


def _count_project_points(qdrant: QdrantClient, settings: Settings, repo: str) -> tuple[int, int]:
    """The count of the points of `repo` in the code collection and in the docs collection."""
    code_collection, docs_collection = rag_collection_names(settings)
    return (
        qdrant.count_points(code_collection, filter_payload={"project_name": repo}),
        qdrant.count_points(docs_collection, filter_payload={"project_name": repo}),
    )


def _read_project_index(repo: str, settings: Settings) -> _ProjectIndex:
    """Count the points of `repo` in both collections, and read the visibility of one of them.

    Qdrant counts on the server, so one number crosses the network instead of every point, and the
    drift check counts this way too. A count raises a `DevOpsCLIError` when the store is
    unreachable.
    """
    qdrant = resolve_qdrant_client(settings=settings)
    code, docs = _count_project_points(qdrant, settings, repo)
    code_collection, docs_collection = rag_collection_names(settings)
    point = None
    if code or docs:
        point = _first_point(qdrant, code_collection if code else docs_collection, repo)
    return _ProjectIndex(code=code, docs=docs, visibility=_recorded_visibility(point))


def _indexed_row(index: _ProjectIndex) -> RagRow:
    """The indexed row: both collections, one of them, or neither."""
    counts = f"code {index.code}, docs {index.docs}"
    if index.code and index.docs:
        return RagRow(_RAG_INDEXED_ROW, "present", reason=counts)
    if index.code or index.docs:
        return RagRow(_RAG_INDEXED_ROW, "partial", reason=counts)
    return RagRow(_RAG_INDEXED_ROW, "missing")


def _visibility_row(index: _ProjectIndex, repo_payload: dict[str, Any] | None) -> RagRow:
    """The visibility row: the value that the points record, beside the value that GitHub returns.

    The repository read of row 1 serves this row, so it sends no request of its own.
    """
    if not index.code and not index.docs:
        return RagRow(_RAG_VISIBILITY_ROW, "not indexed")
    if repo_payload is None:
        return RagRow(_RAG_VISIBILITY_ROW, "not readable", reason="the repository read failed")
    recorded = index.visibility or "not recorded"
    published = visibility_from_payload(repo_payload)
    if index.visibility == published:
        return RagRow(_RAG_VISIBILITY_ROW, published)
    return RagRow(_RAG_VISIBILITY_ROW, "mismatch", reason=f"points {recorded}, github {published}")


def _check_rag_schedule(repo: str, settings: Settings) -> RagRow:
    """Check whether the list that the scheduled pass reads holds the repository."""
    if repo in settings.service.repos:
        return RagRow(_RAG_SCHEDULE_ROW, "present")
    return RagRow(_RAG_SCHEDULE_ROW, "missing", step=_service_repos_step(repo))


def check_rag_rows(
    repo: str,
    settings: Settings,
    repo_payload: dict[str, Any] | None,
) -> tuple[RagRow, ...]:
    """Check the points of `repo`, the visibility that they record, and its schedule (#3771).

    A store that cannot be read gives `not readable` in both rows that read it, with its reason,
    and the schedule row still prints.
    """
    try:
        index = _read_project_index(repo, settings)
    except DevOpsCLIError as exc:
        reason = str(exc)
        return (
            RagRow(_RAG_INDEXED_ROW, "not readable", reason=reason),
            RagRow(_RAG_VISIBILITY_ROW, "not readable", reason=reason),
            _check_rag_schedule(repo, settings),
        )
    return (
        _indexed_row(index),
        _visibility_row(index, repo_payload),
        _check_rag_schedule(repo, settings),
    )


def start_rag_pass(repo: str, settings: Settings) -> tuple[int, int]:
    """Run the ingestion pass of #1389 for `repo` alone, and give the point count of each collection.

    The pass is the only writer to Qdrant. It narrows to the one repository, so a confirmed
    onboarding of a repository that the schedule holds writes the points of that repository and no
    other, and a second run at the same head writes no point.
    """
    from devops_cli.ai.rag.ingest import run_ingest_pass

    run_ingest_pass(repo_filter=[repo], settings=settings)
    qdrant = resolve_qdrant_client(settings=settings)
    return _count_project_points(qdrant, settings, repo)


def check_onboarding(
    store: RoadmapStore,
    repo: str,
    *,
    session: GitHubSession | None = None,
    settings: Settings | None = None,
) -> OnboardingReport:
    """Check the six roadmap prerequisites for `repo`."""
    active_session = session or get_github_session()
    active_settings = settings or load_settings()

    row_1, repo_payload = _check_row_1(active_session, repo)
    row_2 = _check_row_2(active_session, repo)
    row_3, specs = _check_row_3(store)
    row_4, missing_labels, differing_labels = _check_row_4(store, specs)
    row_5 = _check_row_5(repo, active_settings)
    row_6 = _check_row_6(active_session, repo, active_settings)
    rag_rows = check_rag_rows(repo, active_settings, repo_payload)

    rows = (row_1, row_2, row_3, row_4, row_5, row_6)
    return OnboardingReport(
        repo=repo,
        rows=rows,
        missing_labels=missing_labels,
        differing_labels=differing_labels,
        rag_rows=rag_rows,
    )


def apply_onboarding(
    repo: str,
    report: OnboardingReport,
    *,
    session: GitHubSession | None = None,
) -> OnboardingApplied:
    """Create missing labels with POST requests. Differing labels are never edited."""
    active_session = session or get_github_session()
    created: list[LabelSpec] = []
    for spec in report.missing_labels:
        active_session.rest(
            "POST",
            f"/repos/{repo}/labels",
            body={
                "name": spec.name,
                "color": spec.color,
                "description": spec.description,
            },
        )
        created.append(spec)
    return OnboardingApplied(created_labels=tuple(created))


def _row_lines(
    name: str, state: str, reason: str | None, step: str | None, *, prefix: str = ""
) -> list[str]:
    """The lines of one row: its name and state, its reason, and its step when it is not present."""
    line = f"{prefix}{name}: {state}" if reason is None else f"{prefix}{name}: {state} ({reason})"
    lines = [line]
    if step and state != "present":
        lines.append(f"   Step: {step}")
    return lines


def render_onboarding(
    report: OnboardingReport,
    *,
    applied: OnboardingApplied | None = None,
) -> str:
    """Render the onboarding report in ASD-STE100."""
    texts = MESSAGES.roadmap
    lines: list[str] = [texts.onboard_title.format(repo=report.repo)]
    for row in report.rows:
        if row.number == 4 and applied is not None:
            lines.append(f"{row.number}. {row.prerequisite}: present")
            continue
        row_lines = _row_lines(
            row.prerequisite, row.state, row.reason, row.step, prefix=f"{row.number}. "
        )
        lines.extend(row_lines)

    if report.rag_rows:
        lines.append("")
        lines.append(_RAG_ROWS_TITLE)
        for rag_row in report.rag_rows:
            lines.extend(_row_lines(rag_row.name, rag_row.state, rag_row.reason, rag_row.step))

    if applied and applied.created_labels:
        lines.append("")
        lines.append(f"Created {len(applied.created_labels)} label(s).")
    elif applied is None and report.missing_labels:
        lines.append("")
        lines.append("Missing labels:")
        lines.extend(f"  - {spec.name}" for spec in report.missing_labels)

    if report.differing_labels:
        lines.append("")
        lines.append("Differing labels kept:")
        for spec in report.differing_labels:
            lines.append(f"  - {spec.name}: kept")

    lines.append("")
    lines.append(texts.onboard_not_readable_count.format(count=report.not_readable_count))
    return "\n".join(lines)


__all__ = [
    "OnboardingApplied",
    "OnboardingReport",
    "OnboardingRow",
    "RagRow",
    "apply_onboarding",
    "check_onboarding",
    "check_rag_rows",
    "render_onboarding",
    "start_rag_pass",
]
