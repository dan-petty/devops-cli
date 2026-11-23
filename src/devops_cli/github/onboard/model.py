"""The rows of an onboarding run, their states, the person steps and the options of a run."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from devops_cli.github.repo_ref import RepoRef


class RowState(StrEnum):
    """How a row ended. No state reads as clean by default: each row names its own."""

    PRESENT = "present"
    PENDING = "pending"
    APPLIED = "applied"
    WAITING = "waiting"
    SKIPPED = "skipped"
    NOT_AVAILABLE = "not available"
    PERSON = "person"
    REFUSED = "refused"
    NOT_READABLE = "not readable"
    FAILED = "failed"


# The states that leave the repository off its baseline: the command exits 1 on each of them.
_FAILING_STATES: Final[frozenset[RowState]] = frozenset(
    {RowState.PENDING, RowState.FAILED, RowState.NOT_READABLE}
)


@dataclass(frozen=True)
class PersonStep:
    """A step that GitHub, or a project rule, allows only a person to do, and the document that
    says so."""

    text: str
    document: str


# The documents of the person steps (design of #6773, "What stays with a person").
DOC_RULESETS: Final[str] = "https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset"
DOC_CREATE_REPOSITORY: Final[str] = (
    "https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user"
)
DOC_SECRETS: Final[str] = "https://docs.github.com/en/rest/actions/secrets"
DOC_GET_REPOSITORY: Final[str] = "https://docs.github.com/en/rest/repos/repos#get-a-repository"
DOC_GET_RULESET: Final[str] = "https://docs.github.com/en/rest/repos/rules#get-a-repository-ruleset"
DOC_VARIABLES: Final[str] = "https://docs.github.com/en/rest/actions/variables"
DOC_ENVIRONMENTS: Final[str] = (
    "https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/"
    "manage-environments"
)
DOC_INSTALL_APP: Final[str] = (
    "https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party"
)
DOC_SCOPES: Final[str] = (
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps"
)
DOC_WEBHOOKS: Final[str] = "https://docs.github.com/en/rest/repos/webhooks"
DOC_MERGE: Final[str] = (
    "https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/"
    "incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request"
)
DOC_SERVICES_ENTRY: Final[str] = (
    "https://github.com/dan-petty/infra/blob/main/docs/service-repos.md"
)
DOC_DEPLOY: Final[str] = "docs/CLUSTER.md"
DOC_COPIER: Final[str] = "https://copier.readthedocs.io/en/stable/#installation"


@dataclass(frozen=True)
class Row:
    """One step of the run: its number, its name, its state, what it changed or would change,
    why, and the person steps that stay. A row that `informs_only` never changes the exit code."""

    number: int
    name: str
    state: RowState
    changes: tuple[str, ...] = ()
    reason: str | None = None
    steps: tuple[PersonStep, ...] = ()
    informs_only: bool = False

    @property
    def failing(self) -> bool:
        """Whether the row leaves the repository off its baseline."""
        return not self.informs_only and self.state in _FAILING_STATES


@dataclass(frozen=True)
class OnboardOptions:
    """What a person asked for: the repository, the mode and the answers of the flags.

    `scopes`, `release_flow`, `release_type` and `template_ref` are answers: they apply only
    before `.copier-answers.yml` exists. `workdir` is the checkout that row 13 checks for a clean
    `origin/main` of devops-cli.
    """

    repo: RepoRef
    confirm: bool
    workdir: Path
    create: bool = False
    visibility: str | None = None
    scopes: tuple[str, ...] = ()
    release_flow: bool | None = None
    release_type: str | None = None
    template_ref: str | None = None
    release_key_file: Path | None = None
    rotate_release_key: bool = False
    deploy: bool = True
    service: bool = False
    only: frozenset[int] | None = None


@dataclass(frozen=True)
class OnboardReport:
    """The rows of one run, in number order, the template ref that the baseline came from, and the
    labels that differ and stay."""

    repo: str
    template_ref: str | None
    rows: tuple[Row, ...]
    kept: tuple[str, ...] = ()
    confirm: bool = False

    @property
    def failing(self) -> bool:
        """Whether a row leaves the repository off its baseline. In a plan, a template pull
        request that waits for its merge also counts: the repository is not onboarded yet."""
        return any(
            row.failing or (not self.confirm and row.state is RowState.WAITING) for row in self.rows
        )

    @property
    def person_steps(self) -> tuple[PersonStep, ...]:
        """Each person step of the rows, once, in row order."""
        seen: dict[str, PersonStep] = {}
        for row in self.rows:
            for step in row.steps:
                seen.setdefault(step.text, step)
        return tuple(seen.values())


_MISSING: Final[object] = object()


def differences(desired: Any, live: Any) -> Any:
    """The part of `desired` that `live` does not hold, or None when `live` holds all of it.

    A mapping compares key by key, so `live` can hold more keys than `desired`, such as the
    defaults that GitHub adds to an answer. A list matches when each element of `desired` matches
    a distinct element of `live` and both have the same length. A difference in a list gives the
    whole desired list.
    """
    if isinstance(desired, Mapping):
        if not isinstance(live, Mapping):
            return dict(desired)
        found = {}
        for key, value in desired.items():
            part = differences(value, live.get(key, _MISSING))
            if part is not None:
                found[key] = part
        return found or None
    if isinstance(desired, list):
        return None if _list_matches(desired, live) else list(desired)
    return None if desired == live else desired


def held_differences(
    desired: Mapping[str, Any], live: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """The differences of the top-level keys of `desired` that `live` holds, or None, and the keys
    that `live` does not hold.

    GitHub leaves a field out of its reply when the token may not read it, such as the merge
    settings of a repository and the bypass actors of a ruleset. Such a key is unknown, not a
    difference, so a row never gives it as a change (#6875). A missing key inside a nested value
    is still a difference.
    """
    held = {key: value for key, value in desired.items() if key in live}
    unread = tuple(key for key in desired if key not in live)
    return differences(held, live), unread


def _list_matches(desired: list[Any], live: Any) -> bool:
    """Whether each element of `desired` matches a distinct element of `live`."""
    if not isinstance(live, list) or len(live) != len(desired):
        return False
    free = list(live)
    for element in desired:
        match = next((item for item in free if differences(element, item) is None), _MISSING)
        if match is _MISSING:
            return False
        free.remove(match)
    return True


def change_lines(diff: Mapping[str, Any], prefix: str = "") -> list[str]:
    """One line for each leaf of `diff`: its dotted key and the value that the row sets."""
    lines: list[str] = []
    for key, value in diff.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            lines.extend(change_lines(value, f"{name}."))
        else:
            lines.append(f"{name}: {value}")
    return lines


@dataclass
class RowContext:
    """What the rows of one run share: the read of the repository, the plan limit (D2), the
    baseline, and what an earlier row found for a later one."""

    options: OnboardOptions
    repo_payload: dict[str, Any] | None = None
    plan_limited: bool = False
    rulesets: list[dict[str, Any]] | None = None
    reported_checks: tuple[str, ...] = ()
    template_pull: int | None = None
    template_head: str | None = None
    checks_passed: bool = False
    service_changed: bool = False
    stopped: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def repo(self) -> str:
        """The repository as `owner/name`."""
        return self.options.repo.display

    @property
    def default_branch(self) -> str:
        """The default branch that GitHub names, or `main` before the repository exists."""
        payload = self.repo_payload or {}
        return str(payload.get("default_branch") or "main")

    @property
    def private(self) -> bool:
        """Whether the repository is private."""
        payload = self.repo_payload or {}
        return bool(payload.get("private"))


__all__ = [
    "OnboardOptions",
    "OnboardReport",
    "PersonStep",
    "Row",
    "RowContext",
    "RowState",
    "change_lines",
    "differences",
    "held_differences",
]
