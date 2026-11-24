"""The cached state of a GitHub issue in the project brain (#6013).

The shared tier holds each issue that a Service row reads, under the key that `RepoRef.valkey_key`
builds, so rows share the issue and read GitHub only on a miss or after one hour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from devops_cli.config.constants import BrainStore
from devops_cli.config.defaults import (
    DEFAULT_BRAIN_ISSUE_MAX_AGE_SECONDS,
    DEFAULT_BRAIN_ISSUE_TTL_SECONDS,
)
from devops_cli.github.repo_ref import RepoRef
from devops_cli.models.webhooks import WebhookIssue
from devops_cli.roadmap.stores.store import GitHubState, IssueRecord, split_record

if TYPE_CHECKING:
    from devops_cli.valkey.tiered import TieredMapping


class CachedIssue(BaseModel):
    """The cached state of a GitHub issue in the project brain."""

    model_config = ConfigDict(frozen=True)

    record: IssueRecord
    etag: str | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_fresh(
        self,
        max_age: float = DEFAULT_BRAIN_ISSUE_MAX_AGE_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        """Whether the entry's check time is younger than `max_age`."""
        current = datetime.now(UTC) if now is None else now
        return (current - self.checked_at).total_seconds() < max_age


_CACHED_ISSUE_ADAPTER: TypeAdapter[CachedIssue] = TypeAdapter(CachedIssue)


def issue_cache(repo: str | RepoRef) -> TieredMapping[CachedIssue]:
    """A `TieredMapping[CachedIssue]` for `repo`, backed by the shared cache tier."""
    from devops_cli.valkey.tiered import TieredMapping

    ref = repo if isinstance(repo, RepoRef) else RepoRef(repo)
    return TieredMapping(
        ref.valkey_key("brain-issue"),
        _CACHED_ISSUE_ADAPTER,
        ttl=DEFAULT_BRAIN_ISSUE_TTL_SECONDS,
        store=BrainStore.ISSUE,
        entries=0,
    )


def cached_issue(repo: str | RepoRef, number: int) -> CachedIssue | None:
    """Read the cached issue from the brain, or None when missing or the tier fails."""
    try:
        return issue_cache(repo)[str(number)]
    except KeyError:
        return None


def remember_issue(repo: str | RepoRef, entry: CachedIssue) -> None:
    """Write `entry` into the brain cache under its issue number."""
    issue_cache(repo)[str(entry.record.number)] = entry


def issue_from_event(repo: str | RepoRef, issue: WebhookIssue) -> CachedIssue:
    """Build a `CachedIssue` from the `WebhookIssue` of an issue event."""
    ref = repo if isinstance(repo, RepoRef) else RepoRef(repo)
    clean_body, job_record = split_record(issue.body, issue=f"#{issue.number}")
    state = GitHubState.CLOSED if issue.state.lower() == "closed" else GitHubState.OPEN
    labels = tuple(lbl.name for lbl in issue.labels if lbl.name)
    record = IssueRecord(
        number=issue.number or 0,
        title=issue.title,
        url=f"https://github.com/{ref.display}/issues/{issue.number}",
        body=clean_body,
        state=state,
        state_reason=issue.state_reason,
        labels=labels,
        pull_request=issue.pull_request is not None,
        updated_at=issue.updated_at,
        job_record=job_record,
    )
    return CachedIssue(record=record, etag=None, checked_at=datetime.now(UTC))
