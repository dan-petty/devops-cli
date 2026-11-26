"""The cached state of a GitHub issue in the project brain (#6013, #7292).

The shared tier holds each issue that a Service row reads in a public repository, under the key
`valkey:roadmap:v1:issue:<owner>/<name>:<number>` with the casefolded name of `RepoRef.key`, so
rows share the issue and read GitHub only on a miss or after one hour. The key is under
`CONST_VALKEY_ROADMAP_PREFIX`, which the `sweep` ACL user of `valkey-devops` writes and the `brain`
user reads (#4704). The mapping keeps no copy in the process: a webhook delivery changes an entry
from another process.

The shared tier holds the issues of a private repository only for the process that sends
`SWEEP_USER` (ADR 0023 section 8). A read and a write of an entry take the visibility of the
repository from the one check of the module `visibility`, in this order:

1. `private`, the answer that the caller holds, such as the `repository.private` of a signed
   webhook delivery.
2. The answer that the process holds from an earlier check.
3. `is_private`, the read of GitHub of the caller. The cache sends it only after Valkey answered
   one `GET` of the key prefix, which holds no value and names no repository. So a process with
   no Valkey sends no visibility read.

A caller that gives no `private` and no `is_private`, in a process that holds no answer, gets an
unknown answer. For a private or an unknown answer, the cache sends no command of the entry: a
read gives None, so its caller reads GitHub, and a write does not occur. `for_user` makes a
private answer public for the process that sends `SWEEP_USER`, as the snapshot store has it. Each
read and each write counts one result on `devops_cli_brain_reads_total` or
`devops_cli_brain_writes_total` with the store `issue`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from devops_cli.config.constants import (
    CONST_VALKEY_ROADMAP_PREFIX,
    BrainRead,
    BrainStore,
    BrainWrite,
)
from devops_cli.config.defaults import (
    DEFAULT_BRAIN_ISSUE_MAX_AGE_SECONDS,
    DEFAULT_BRAIN_ISSUE_TTL_SECONDS,
)
from devops_cli.github.repo_ref import RepoRef
from devops_cli.models.webhooks import WebhookIssue
from devops_cli.roadmap.stores.store import (
    GitHubState,
    IssueRecord,
    decode_job_record,
    split_record,
)

# The modules `visibility`, `valkey.cache` and `valkey.tiered` are imported in the functions that
# use them: the GitHub store imports this module, and the help of a command loads no cachetools.
if TYPE_CHECKING:
    from devops_cli.valkey.tiered import TieredMapping

# The key prefix of each cached issue. No key has this name, so a `GET` of it holds no value.
_ISSUE_PREFIX: Final = f"{CONST_VALKEY_ROADMAP_PREFIX}:issue"


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


def _issue_cache(repo: str | RepoRef) -> TieredMapping[CachedIssue]:
    """A `TieredMapping[CachedIssue]` for `repo`, backed by the shared cache tier. Its prefix
    holds the casefolded name of the repository, as the key of the shared snapshot does, and the
    `:` after the name ends the repository part: the keys of `o/n` are no keys of `o/nn`. The
    mapping has no visibility check, so only `cached_issue` and `remember_issue` use it."""
    from devops_cli.valkey.tiered import TieredMapping

    ref = repo if isinstance(repo, RepoRef) else RepoRef(repo)
    return TieredMapping(
        f"{_ISSUE_PREFIX}:{ref.key}",
        _CACHED_ISSUE_ADAPTER,
        ttl=DEFAULT_BRAIN_ISSUE_TTL_SECONDS,
        store=BrainStore.ISSUE,
        entries=0,
    )


def issue_key(repo: str | RepoRef, number: int) -> str:
    """The Valkey key of the cached issue `number` of `repo`,
    `valkey:roadmap:v1:issue:<owner>/<name>:<number>`, with the casefolded name of `RepoRef.key`,
    so each spelling of a name gives one key."""
    return _issue_cache(repo).shared_key(str(number))


def _tier_answers() -> bool:
    """Whether the shared tier answers now: one `GET` of the key prefix of the cached issues,
    which holds no value and names no repository. A process with no tier, an open breaker and a
    failed command give False."""
    from devops_cli.valkey.cache import shared_cache_tier

    tier = shared_cache_tier()
    return tier is not None and tier.get_with_ttl(_ISSUE_PREFIX) is not None


def _refusal(
    repo: str | RepoRef, private: bool | None, is_private: Callable[[], bool] | None
) -> tuple[BrainRead, BrainWrite] | None:
    """None when the shared tier takes the entries of `repo` from this process: the visibility is
    public as the tier takes it for the ACL user of the process (`for_user`). Else the results
    that a read and a write of an entry count, and the cache sends no command of the entry. The
    answer is `private` of the caller, else the answer that the process holds, else the answer of
    `is_private`, which the cache reads only after Valkey answered (`fallback` and `skipped` when
    it does not); with none of them the answer is unknown."""
    from devops_cli.roadmap.stores.visibility import (
        Visibility,
        configured_valkey_user,
        for_user,
        held_visibility,
        visibility_of,
    )

    name = repo.display if isinstance(repo, RepoRef) else repo
    answer: Visibility | None
    if private is not None:
        answer = Visibility.PRIVATE if private else Visibility.PUBLIC
    else:
        answer = held_visibility(name)
    if answer is None:
        if is_private is None:
            answer = Visibility.UNKNOWN
        elif _tier_answers():
            answer = visibility_of(name, is_private)
        else:
            return BrainRead.FALLBACK, BrainWrite.SKIPPED
    shared = for_user(answer, configured_valkey_user())
    if shared is Visibility.PUBLIC:
        return None
    if shared is Visibility.PRIVATE:
        return BrainRead.PRIVATE, BrainWrite.PRIVATE
    return BrainRead.UNKNOWN, BrainWrite.UNKNOWN


def cached_issue(
    repo: str | RepoRef,
    number: int,
    *,
    private: bool | None = None,
    is_private: Callable[[], bool] | None = None,
) -> CachedIssue | None:
    """Read the cached issue from the brain, or None when it is missing, when the tier fails, or
    when the shared tier does not take the repository from this process (a private or an unknown
    answer of the visibility, which sends no command of the entry). `private` is the answer that
    the caller holds, and `is_private` is its read of GitHub (see the module docstring)."""
    refused = _refusal(repo, private, is_private)
    if refused is not None:
        from devops_cli.valkey.tiered import count_read

        count_read(BrainStore.ISSUE, refused[0])
        return None
    try:
        return _issue_cache(repo)[str(number)]
    except KeyError:
        return None


def remember_issue(
    repo: str | RepoRef,
    entry: CachedIssue,
    *,
    private: bool | None = None,
    is_private: Callable[[], bool] | None = None,
) -> None:
    """Write `entry` into the brain cache under its issue number. A private or an unknown answer
    of the visibility writes nothing, and so does a tier that does not answer before the
    visibility read of the cache. `private` is the answer that the caller holds, and `is_private`
    is its read of GitHub (see the module docstring)."""
    refused = _refusal(repo, private, is_private)
    if refused is not None:
        from devops_cli.valkey.tiered import count_write

        count_write(BrainStore.ISSUE, refused[1])
        return
    _issue_cache(repo)[str(entry.record.number)] = entry


def issue_from_event(repo: str | RepoRef, issue: WebhookIssue) -> CachedIssue:
    """Build a `CachedIssue` from the `WebhookIssue` of an issue event."""
    ref = repo if isinstance(repo, RepoRef) else RepoRef(repo)
    clean_body, held = split_record(issue.body, issue=f"#{issue.number}")
    job_record = decode_job_record(held, issue=f"#{issue.number}")
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
