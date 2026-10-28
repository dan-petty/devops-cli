"""Review findings that an issue already carries (#2419).

An issue filed from a review finding carries the finding's fingerprint v2 (#1141) in a marker in
its body, an HTML comment that GitHub does not show. Before a hand-off to roadmap intake, the
review reads every issue that carries a marker, with one issue search, and leaves out each finding
that an issue settles: an open issue, or one closed as not planned or as a duplicate. A finding
whose issues were all closed as completed is handed off again, because the defect came back. The
match is on the same fingerprint, so no model decides it, and intake still never drops a
candidate (#2223).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlencode

from devops_cli.config.constants import (
    CONST_ISSUE_STATE_OPEN,
    CONST_REVIEW_FILED_FINDING_MARKER,
    CONST_REVIEW_FILED_FINDING_SETTLING_CLOSE_REASONS,
)
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.dry_run import PlannedRequest
from devops_cli.exceptions.validation import ValidationError
from devops_cli.github.client import GitHubClient, IssueSearchHit
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.request_plan import planned_session_read

_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_MARKER = re.compile(
    rf"<!-- {re.escape(CONST_REVIEW_FILED_FINDING_MARKER)}: "
    rf"fingerprint_v2=({_FINGERPRINT.pattern}) -->"
)


def finding_marker(fingerprint_v2: str) -> str:
    """The marker that the issue filed from a finding carries: an HTML comment with the finding's
    fingerprint v2. A value that is not 64 lowercase hex characters is refused, because a marker
    the parser cannot read would let the same finding be filed again."""
    if not _FINGERPRINT.fullmatch(fingerprint_v2):
        raise ValidationError(
            "A review finding marker needs a fingerprint v2 of 64 lowercase hex characters.",
            field="fingerprint_v2",
        )
    return f"<!-- {CONST_REVIEW_FILED_FINDING_MARKER}: fingerprint_v2={fingerprint_v2} -->"


def carried_fingerprints(body: str) -> frozenset[str]:
    """The fingerprint of every finding marker in an issue body."""
    return frozenset(_MARKER.findall(body))


def _settles(issue: IssueSearchHit) -> bool:
    """Whether the issue keeps the finding it carries out of a hand-off: it is open, or it was
    closed as not planned or as a duplicate."""
    if issue.state == CONST_ISSUE_STATE_OPEN:
        return True
    return issue.state_reason in CONST_REVIEW_FILED_FINDING_SETTLING_CLOSE_REASONS


@dataclass(frozen=True)
class FiledFindings:
    """The issues that carry each finding's fingerprint, and, for a dry run, the search that a
    real run sends instead of the issues it would find."""

    carriers: Mapping[str, tuple[IssueSearchHit, ...]] = field(default_factory=dict)
    requests: tuple[PlannedRequest, ...] = ()

    def settled(self, fingerprint_v2: str) -> bool:
        """Whether an issue settles the finding: one that carries its fingerprint is enough."""
        return any(_settles(issue) for issue in self.carriers.get(fingerprint_v2, ()))

    def unfiled[F](self, findings: Iterable[F], *, fingerprint: Callable[[F], str]) -> list[F]:
        """The findings, in their order, that no issue settles."""
        return [finding for finding in findings if not self.settled(fingerprint(finding))]


def _search_request(repo: str) -> PlannedRequest:
    """The first page of the search that the lookup sends, as a dry run lists it."""
    query = f'"{CONST_REVIEW_FILED_FINDING_MARKER}" in:body is:issue repo:{repo}'
    page = {"q": query, "per_page": DEFAULT_GH_REST_PER_PAGE, "page": 1}
    path = f"/search/issues?{urlencode(page)}"
    texts = MESSAGES.review
    return planned_session_read(
        path, texts.filed_findings_search_target, repeat=texts.filed_findings_search_repeat
    )


def read_filed_findings(
    repo: str, *, dry_run: bool, client: GitHubClient | None = None
) -> FiledFindings:
    """The issues of `repo`, open and closed, that carry a finding marker, by fingerprint.

    One issue search reads them, through the GitHub session (`client`, the session's own when
    None). A dry run makes no request and touches no GitHub identity: it returns no issue, so
    every finding stays, and the search that a real run sends.
    """
    if dry_run:
        return FiledFindings(requests=(_search_request(repo),))
    if client is None:
        client = get_github_session().client
    carriers: defaultdict[str, list[IssueSearchHit]] = defaultdict(list)
    for issue in client.search_issue_bodies(repo, CONST_REVIEW_FILED_FINDING_MARKER):
        for fingerprint_v2 in carried_fingerprints(issue.body or ""):
            carriers[fingerprint_v2].append(issue)
    return FiledFindings(carriers={fp: tuple(issues) for fp, issues in carriers.items()})


__all__ = [
    "FiledFindings",
    "carried_fingerprints",
    "finding_marker",
    "read_filed_findings",
]
