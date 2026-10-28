"""Review findings that an issue already carries: the marker and the lookup (#2419)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import pytest

from devops_cli.exceptions.validation import ValidationError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.review.filed_findings import (
    carried_fingerprints,
    finding_marker,
    read_filed_findings,
)
from tests.support.fakes.github import API, github_json, quota_headers

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

_REPO = "octo/repo"
_A, _B, _C, _D, _E = (letter * 64 for letter in "abcde")


@dataclass(frozen=True)
class _Finding:
    """A finding as a session saves it: a title and the fingerprint v2 of the admitted finding."""

    title: str
    fingerprint: str


def _fingerprint(finding: _Finding) -> str:
    return finding.fingerprint


def _search_path() -> str:
    """The one search the lookup sends: the marker's phrase in the bodies of the repo's issues."""
    query = f'"devops-review-finding" in:body is:issue repo:{_REPO}'
    return f"/search/issues?{urlencode({'q': query, 'per_page': 100, 'page': 1})}"


def _issue(
    number: int, fingerprints: list[str], *, state: str = "open", reason: str | None = None
) -> dict[str, Any]:
    """A search item: an issue whose body carries the markers of `fingerprints`."""
    body = "\n".join(["## Problem", "A finding.", *(finding_marker(fp) for fp in fingerprints)])
    return {"number": number, "state": state, "state_reason": reason, "body": body}


def _route_search(api: GitHubApiFake, *issues: dict[str, Any]) -> None:
    """Answer the lookup's search with `issues`, with a search quota that needs no refresh."""
    get_github_rate_limiter().update_quota(
        "search", remaining=30, limit=30, reset_epoch=time.time() + 60.0
    )
    payload = {"total_count": len(issues), "incomplete_results": False, "items": list(issues)}
    quota = quota_headers(29, resource="search", limit=30)
    api.route("GET", _search_path(), github_json(payload, headers=quota))


def test_a_marker_round_trips_its_fingerprints() -> None:
    """A body gives the fingerprint of each marker in it, and no marker gives none."""
    body = "\n".join(
        [
            "Text.",
            finding_marker(_A),
            "More text.",
            finding_marker(_B),
            "<!-- devops-review-finding: fingerprint_v2=short -->",
        ]
    )

    assert (finding_marker(_A), carried_fingerprints(body), carried_fingerprints("None.")) == (
        f"<!-- devops-review-finding: fingerprint_v2={_A} -->",
        frozenset({_A, _B}),
        frozenset(),
    )


@pytest.mark.parametrize("value", ["", "A" * 64, "a" * 63, "g" * 64, f"{_A} -->"])
def test_a_marker_refuses_a_value_that_is_no_fingerprint(value: str) -> None:
    """A marker the parser cannot read would let the same finding be filed again."""
    with pytest.raises(ValidationError):
        finding_marker(value)


def test_the_review_leaves_out_the_findings_an_issue_settles(github_api: GitHubApiFake) -> None:
    """Open, not planned and duplicate issues settle a finding; a completed one does not."""
    _route_search(
        github_api,
        _issue(1, [_A]),
        _issue(2, [_B], state="closed", reason="not_planned"),
        _issue(3, [_C], state="closed", reason="completed"),
        _issue(4, [_D], state="closed", reason="duplicate"),
    )
    findings = [
        _Finding(title, fp) for title, fp in zip("ABCDE", (_A, _B, _C, _D, _E), strict=True)
    ]

    filed = read_filed_findings(_REPO, dry_run=False)
    kept = filed.unfiled(findings, fingerprint=_fingerprint)

    assert ([f.title for f in kept], filed.requests, github_api.requested) == (
        ["C", "E"],
        (),
        [f"GET {API}{_search_path()}"],
    )


def test_one_settling_issue_keeps_a_finding_out(github_api: GitHubApiFake) -> None:
    """A finding that a completed issue and an open issue both carry stays out."""
    _route_search(
        github_api, _issue(5, [_A], state="closed", reason="completed"), _issue(6, [_A, _B])
    )

    filed = read_filed_findings(_REPO, dry_run=False)

    assert filed.unfiled([_Finding("A", _A), _Finding("B", _B)], fingerprint=_fingerprint) == []


def test_a_dry_run_of_the_lookup_makes_no_request(github_api: GitHubApiFake) -> None:
    """The dry run names the search a real run sends, sends nothing, and leaves out no finding."""
    filed = read_filed_findings(_REPO, dry_run=True)

    assert (
        [request.argv for request in filed.requests],
        [f.title for f in filed.unfiled([_Finding("A", _A)], fingerprint=_fingerprint)],
        github_api.requested,
    ) == ([("GET", f"{API}{_search_path()}")], ["A"], [])
