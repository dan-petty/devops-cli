"""Check a repository for the prerequisites of the roadmap jobs (#1359).

Onboarding checks six prerequisites:
1. Issues are turned on.
2. The App devops-cli-service is installed on the repository.
3. .github/labels.yml is on the default branch and is valid.
4. Every workflow label of the package and every label of that file exists on GitHub (#4652).
5. .github/workflows/clear-status.yml is on the default branch.
6. The repository is in service.repos.

With --confirm, missing labels are created with POST. No labels are edited or deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import yaml
from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.config.settings import Settings, load_settings
from devops_cli.core.process import acts_as_github_app
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.github.labels import LabelSpec, diff_labels
from devops_cli.github.session import GitHubSession, get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stores.store import RoadmapStore
from devops_cli.roadmap.title_labels import declared_label_specs
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS

_CLEAR_STATUS_PATH: Final[str] = ".github/workflows/clear-status.yml"
_ROW_1_PREREQUISITE: Final[str] = "Issues are turned on"
_ROW_2_PREREQUISITE: Final[str] = "The App devops-cli-service is installed on the repository"
_ROW_3_PREREQUISITE: Final[str] = ".github/labels.yml is on the default branch and is valid"
_ROW_4_PREREQUISITE: Final[str] = (
    "Every workflow label and every label of .github/labels.yml exists on GitHub"
)
_ROW_5_PREREQUISITE: Final[str] = ".github/workflows/clear-status.yml is on the default branch"
_ROW_6_PREREQUISITE: Final[str] = "The repository is in service.repos"


@dataclass(frozen=True)
class OnboardingRow:
    """One prerequisite row: its number, name, state, and optional reason or step."""

    number: int
    prerequisite: str
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

    @property
    def has_missing(self) -> bool:
        """Whether any row is missing."""
        return any(row.state == "missing" for row in self.rows)

    @property
    def not_readable_count(self) -> int:
        """The count of rows that are not readable."""
        return sum(1 for row in self.rows if row.state.startswith("not readable"))


@dataclass(frozen=True)
class OnboardingApplied:
    """The result of applying onboarding actions."""

    created_labels: tuple[LabelSpec, ...] = ()


def _check_row_1(session: GitHubSession, repo: str) -> OnboardingRow:
    """Check whether issues are turned on."""
    try:
        data = session.rest("GET", f"/repos/{repo}")
        if data.get("has_issues"):
            return OnboardingRow(1, _ROW_1_PREREQUISITE, "present")
        step = f"devops gh api -X PATCH repos/{repo} -f has_issues=true"
        return OnboardingRow(1, _ROW_1_PREREQUISITE, "missing", step=step)
    except DevOpsCLIError as exc:
        return OnboardingRow(1, _ROW_1_PREREQUISITE, "not readable", reason=str(exc))


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


def _check_row_5(store: RoadmapStore) -> OnboardingRow:
    """Check whether .github/workflows/clear-status.yml is present on the default branch."""
    try:
        store.repository_file(_CLEAR_STATUS_PATH, ref=None)
        return OnboardingRow(5, _ROW_5_PREREQUISITE, "present")
    except GitHubFileNotFoundError:
        step = "Add .github/workflows/clear-status.yml on the default branch."
        return OnboardingRow(5, _ROW_5_PREREQUISITE, "missing", step=step)
    except DevOpsCLIError as exc:
        return OnboardingRow(5, _ROW_5_PREREQUISITE, "not readable", reason=str(exc))


def _check_row_6(repo: str, settings: Settings) -> OnboardingRow:
    """Check whether the repository is in service.repos."""
    if repo in settings.service.repos:
        return OnboardingRow(6, _ROW_6_PREREQUISITE, "present")
    step = f"Add to service.repos in config.yaml:\n  - {repo}\nThen run: devops k8s deploy-stack"
    return OnboardingRow(6, _ROW_6_PREREQUISITE, "missing", step=step)


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

    row_1 = _check_row_1(active_session, repo)
    row_2 = _check_row_2(active_session, repo)
    row_3, specs = _check_row_3(store)
    row_4, missing_labels, differing_labels = _check_row_4(store, specs)
    row_5 = _check_row_5(store)
    row_6 = _check_row_6(repo, active_settings)

    rows = (row_1, row_2, row_3, row_4, row_5, row_6)
    return OnboardingReport(
        repo=repo,
        rows=rows,
        missing_labels=missing_labels,
        differing_labels=differing_labels,
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
        if row.reason:
            lines.append(f"{row.number}. {row.prerequisite}: {row.state} ({row.reason})")
        else:
            lines.append(f"{row.number}. {row.prerequisite}: {row.state}")
        if row.step and row.state != "present":
            lines.append(f"   Step: {row.step}")

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
    "apply_onboarding",
    "check_onboarding",
    "render_onboarding",
]
