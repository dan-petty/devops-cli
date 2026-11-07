"""The release pull request that the scheduled merge may merge (#3921, RELEASE_CYCLE.md).

`.github/workflows/release-merge.yml` runs `python -m devops_cli.release.merge_candidate` every
6 hours. The module reads the open release pull request, judges it, and prints `number=<n>` and
`sha=<head commit>` on standard output when it may merge. It prints nothing there when it may not,
and it says why on standard error. It merges nothing and writes nothing to GitHub: a later step of
the workflow merges the commit it printed, with the release App token.

The pull request may merge only when all of these hold: it is open and not a draft; the release
App opened it from the branch of release-please; it has the label `autorelease: pending` and not
the label `hold-release`; its title is `chore(main): release <version>`; it changes only the files
that release-please writes; every check that the rules of `main` require passed on its head, and no
other check failed there; no required check failed on the head of `main`; GitHub reports it as
mergeable. It looks at the first pull request, by number, that passes, so a run picks at most one.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

from packaging.version import InvalidVersion, Version
from pydantic import AliasPath, BaseModel, ConfigDict, Field, field_validator

from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, read_check_runs
from devops_cli.github.client import PullRequestFile
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.output.console import write_stderr, write_stdout

BASE_BRANCH: Final[str] = "main"
RELEASE_LABEL: Final[str] = "autorelease: pending"
HOLD_LABEL: Final[str] = "hold-release"
RELEASE_BRANCH_PREFIX: Final[str] = f"release-please--branches--{BASE_BRANCH}"
TITLE_PREFIX: Final[str] = f"chore({BASE_BRANCH}): release "
# The files release-please writes: the manifest, the changelog, the version of the package and the
# version in the lock file. A test compares them with `release-please-config.json`.
RELEASE_FILES: Final[frozenset[str]] = frozenset(
    {".release-please-manifest.json", "CHANGELOG.md", "pyproject.toml", "uv.lock"}
)
# GitHub merges a pull request in these states; `unstable` means that a check which no rule requires
# is not green, and the guards judge the checks themselves.
MERGEABLE_STATES: Final[frozenset[str]] = frozenset({"clean", "unstable", "has_hooks"})
_NOT_GREEN: Final[frozenset[CheckBucket]] = frozenset({CheckBucket.FAIL, CheckBucket.CANCEL})


class ReleasePull(BaseModel):
    """The fields of a pull request that the guards read."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    number: int
    title: str
    state: str
    draft: bool = False
    author: str = Field(validation_alias=AliasPath("user", "login"))
    head_ref: str = Field(validation_alias=AliasPath("head", "ref"))
    head_sha: str = Field(validation_alias=AliasPath("head", "sha"))
    head_repository: str | None = Field(
        default=None, validation_alias=AliasPath("head", "repo", "full_name")
    )
    base_ref: str = Field(validation_alias=AliasPath("base", "ref"))
    labels: tuple[str, ...] = ()
    mergeable: bool | None = None
    mergeable_state: str = ""

    @field_validator("labels", mode="before")
    @classmethod
    def _label_names(cls, value: Any) -> tuple[str, ...]:
        if not value:
            return ()
        return tuple(item["name"] if isinstance(item, dict) else str(item) for item in value)


@dataclass(frozen=True)
class ReleaseFacts:
    """What GitHub says about one release pull request, as the guards read it."""

    pull: ReleasePull
    repository: str
    app_login: str
    files: tuple[PullRequestFile, ...]
    required_checks: tuple[str, ...]
    pull_checks: CheckVerdictSummary
    base_checks: CheckVerdictSummary


def _title_names_a_version(title: str) -> bool:
    if not title.startswith(TITLE_PREFIX):
        return False
    try:
        Version(title.removeprefix(TITLE_PREFIX))
    except InvalidVersion:
        return False
    return True


def _pull_refusals(facts: ReleaseFacts) -> list[str]:
    """The refusals that the pull request alone gives: state, author, branch, labels, title,
    mergeability."""
    texts = MESSAGES.release
    pull = facts.pull
    number = pull.number
    refusals: list[str] = []
    if pull.state != "open":
        refusals.append(texts.refusal_not_open.format(number=number))
    if pull.draft:
        refusals.append(texts.refusal_draft.format(number=number))
    if pull.author.casefold() != facts.app_login.casefold():
        refusals.append(
            texts.refusal_author.format(number=number, author=pull.author, app=facts.app_login)
        )
    if (
        not pull.head_ref.startswith(RELEASE_BRANCH_PREFIX)
        or pull.base_ref != BASE_BRANCH
        or pull.head_repository != facts.repository
    ):
        refusals.append(
            texts.refusal_branch.format(number=number, base=BASE_BRANCH, head=pull.head_ref)
        )
    if RELEASE_LABEL not in pull.labels:
        refusals.append(texts.refusal_label.format(number=number, label=RELEASE_LABEL))
    if HOLD_LABEL in pull.labels:
        refusals.append(texts.refusal_hold.format(number=number, label=HOLD_LABEL))
    if not _title_names_a_version(pull.title):
        refusals.append(texts.refusal_title.format(number=number))
    if pull.mergeable is not True or pull.mergeable_state not in MERGEABLE_STATES:
        refusals.append(
            texts.refusal_mergeable.format(number=number, state=pull.mergeable_state or "unknown")
        )
    return refusals


def _file_refusals(facts: ReleaseFacts) -> list[str]:
    """One refusal for each file that release-please does not write, or that the pull request adds,
    removes or renames."""
    number = facts.pull.number
    refusals: list[str] = []
    for changed in facts.files:
        paths = [
            changed.filename,
            *([changed.previous_filename] if changed.previous_filename else []),
        ]
        for path in paths:
            if path not in RELEASE_FILES or changed.status != "modified":
                refusals.append(MESSAGES.release.refusal_file.format(number=number, path=path))
    return refusals


def _check_refusals(facts: ReleaseFacts) -> list[str]:
    """The refusals of the checks: every required check passed on the head of the pull request, no
    other check failed there, and no required check failed on the head of `main`."""
    texts = MESSAGES.release
    number = facts.pull.number
    refusals: list[str] = []
    for summary, subject in (
        (facts.pull_checks, texts.subject_pull.format(number=number)),
        (facts.base_checks, texts.subject_base.format(base=BASE_BRANCH)),
    ):
        if summary.unread_reason:
            refusals.append(
                texts.refusal_checks_unread.format(subject=subject, reason=summary.unread_reason)
            )
    if not facts.required_checks:
        refusals.append(texts.refusal_no_required.format(base=BASE_BRANCH))
    if refusals:
        return refusals
    required = set(facts.required_checks)
    for name in sorted(required):
        items = [item for item in facts.pull_checks.items if item.name == name]
        if not items:
            refusals.append(texts.refusal_required_missing.format(name=name, number=number))
        refusals.extend(
            texts.refusal_required_state.format(
                name=name, state=item.state or item.bucket, number=number
            )
            for item in items
            if item.bucket != CheckBucket.PASS
        )
    refusals.extend(
        texts.refusal_other_failed.format(name=item.name, number=number)
        for item in facts.pull_checks.items
        if item.name not in required and item.bucket in _NOT_GREEN
    )
    refusals.extend(
        texts.refusal_base_red.format(name=item.name, base=BASE_BRANCH)
        for item in facts.base_checks.items
        if item.name in required and item.bucket in _NOT_GREEN
    )
    return refusals


def refusals(facts: ReleaseFacts) -> list[str]:
    """Every reason the pull request may not merge now; an empty list means that it may."""
    return [*_pull_refusals(facts), *_file_refusals(facts), *_check_refusals(facts)]


class RestSession(Protocol):
    """The reads of the GitHub session that the pick makes."""

    def rest(
        self, method: str, path: str, *, accept: str | None = None, body: Any = None
    ) -> Any: ...

    def paginate(self, path: str, *, iterable_key: str | None = None) -> Iterator[Any]: ...


@dataclass(frozen=True)
class Candidate:
    """The release pull request that may merge, and the commit that was judged."""

    number: int
    head_sha: str


def _required_checks(session: RestSession, repository: str) -> tuple[str, ...]:
    """The names of the checks that the rules of `main` require."""
    names: set[str] = set()
    for rule in session.paginate(
        f"/repos/{repository}/rules/branches/{BASE_BRANCH}?per_page={DEFAULT_GH_REST_PER_PAGE}"
    ):
        if isinstance(rule, dict) and rule.get("type") == "required_status_checks":
            for check in rule.get("parameters", {}).get("required_status_checks", []):
                names.add(str(check["context"]))
    return tuple(sorted(names))


def _release_numbers(session: RestSession, repository: str) -> list[int]:
    """The numbers of the open pull requests into `main` that carry the release label, lowest first."""
    listing = session.paginate(
        f"/repos/{repository}/pulls?state=open&base={BASE_BRANCH}&per_page={DEFAULT_GH_REST_PER_PAGE}"
    )
    return sorted(
        int(item["number"])
        for item in listing
        if isinstance(item, dict)
        and RELEASE_LABEL in {label["name"] for label in item.get("labels", [])}
    )


def _changed_files(
    session: RestSession, repository: str, number: int
) -> tuple[PullRequestFile, ...]:
    """Every file the pull request changes, read page by linked page."""
    listing = session.paginate(
        f"/repos/{repository}/pulls/{number}/files?per_page={DEFAULT_GH_REST_PER_PAGE}"
    )
    return tuple(PullRequestFile.model_validate(item) for item in listing)


def pick(
    session: RestSession, repository: str, app_login: str, say: Callable[[str], None] = write_stderr
) -> Candidate | None:
    """The first release pull request, by number, that may merge; None when none may.

    `say` receives one line for each pull request that may not merge, and for each fact it lacks.
    """
    texts = MESSAGES.release
    owner, name = repository.split("/", 1)
    numbers = _release_numbers(session, repository)
    if not numbers:
        say(texts.no_release_pull.format(label=RELEASE_LABEL) + "\n")
        return None
    required = _required_checks(session, repository)
    base_sha = str(
        session.rest("GET", f"/repos/{repository}/branches/{BASE_BRANCH}")["commit"]["sha"]
    )
    base_checks = read_check_runs(owner, name, base_sha, session=session)
    for number in numbers:
        pull = ReleasePull.model_validate(
            session.rest("GET", f"/repos/{repository}/pulls/{number}")
        )
        facts = ReleaseFacts(
            pull=pull,
            repository=repository,
            app_login=app_login,
            files=_changed_files(session, repository, number),
            required_checks=required,
            pull_checks=read_check_runs(owner, name, pull.head_sha, session=session),
            base_checks=base_checks,
        )
        found = refusals(facts)
        if not found:
            return Candidate(number=number, head_sha=pull.head_sha)
        for reason in found:
            say(texts.refused.format(number=number, reason=reason) + "\n")
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Print the pull request that may merge as `number=` and `sha=` lines for `$GITHUB_OUTPUT`.

    Exit status 0 when the read finished, whether or not a pull request may merge, and 1 when
    GitHub could not be read, so a failed read never looks like a refusal.
    """
    parser = argparse.ArgumentParser(prog="python -m devops_cli.release.merge_candidate")
    parser.add_argument("--repo", required=True, help=MESSAGES.release.usage_repo)
    parser.add_argument("--app-login", required=True, help=MESSAGES.release.usage_app)
    args = parser.parse_args(argv)
    try:
        candidate = pick(get_github_session(), args.repo, args.app_login)
    except GitHubOperationError as error:
        write_stderr(MESSAGES.release.unread.format(reason=error) + "\n")
        return 1
    if candidate is None:
        write_stderr(MESSAGES.release.none_picked + "\n")
        return 0
    write_stderr(
        MESSAGES.release.picked.format(number=candidate.number, sha=candidate.head_sha) + "\n"
    )
    write_stdout(f"number={candidate.number}\nsha={candidate.head_sha}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
