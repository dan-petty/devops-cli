"""The facts of the repository that the GitHub roadmap store reads: visibility, latest release,
license and the evidence of a finding (#1335).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.roadmap.stores.github_store import (
    is_private_args,
    issue_edit,
    issue_edit_args,
)
from devops_cli.roadmap.stores.store import (
    Evidence,
    EvidenceKind,
    RepositoryFacts,
)
from tests.support.roadmap_github_store import REPO, recorded_store


@pytest.mark.parametrize(
    ("kind", "value", "reply", "endpoint", "holds"),
    [
        (
            "advisory",
            "GHSA-abcd-efgh-ijkl",
            {"ghsa_id": "x"},
            "advisories/GHSA-abcd-efgh-ijkl",
            True,
        ),
        ("advisory", "GHSA-abcd-efgh-ijkl", (1, "gh: Not Found (HTTP 404)"), "advisories/", False),
        ("failed_run", "123", {"conclusion": "failure"}, f"repos/{REPO}/actions/runs/123", True),
        ("failed_run", "123", {"conclusion": "success"}, f"repos/{REPO}/actions/runs/123", False),
        ("regression_commit", "abc1234", {"sha": "abc1234"}, f"repos/{REPO}/commits/abc1234", True),
        ("regression_commit", "abc1234", (1, "HTTP 422: No commit found"), "commits/", False),
    ],
)
def test_evidence_holds_reads_the_advisory_run_or_commit(
    kind: str, value: str, reply: Any, endpoint: str, holds: bool
) -> None:
    store, runner = recorded_store({"api ": reply})
    found = store.evidence_holds(Evidence(kind=EvidenceKind(kind), value=value))
    assert (found, endpoint in runner.calls[0][0][-1]) == (holds, True)


def test_evidence_with_a_path_in_its_value_never_leaves_its_endpoint() -> None:
    store, runner = recorded_store({"api ": {"sha": "x"}})
    store.evidence_holds(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="../pulls/1"))
    assert runner.calls[0][0][-1] == f"repos/{REPO}/commits/..%2Fpulls%2F1"


def test_the_visibility_read_and_the_issue_write_send_their_arguments() -> None:
    owner, name = REPO.split("/", 1)
    assert (
        issue_edit_args(REPO, 42),
        json.loads(issue_edit(labels=["status/new"], body="Text")),
        json.loads(issue_edit(body="Text")),
        is_private_args(REPO),
    ) == (
        ["api", "-X", "PATCH", f"repos/{REPO}/issues/42", "--input", "-"],
        {"labels": ["status/new"], "body": "Text"},
        {"body": "Text"},
        [
            "api",
            "graphql",
            "-f",
            "query=query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { isPrivate } }",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
        ],
    )


def test_repository_is_private_github_store() -> None:
    store, _ = recorded_store({"isPrivate": {"data": {"repository": {"isPrivate": True}}}})
    assert store.repository_is_private() is True


def test_repository_facts_read_the_repository_and_its_latest_release() -> None:
    """One REST read of the repository and one of its latest release, with the license, the last
    push and the star count (#2650)."""
    repository = {
        "full_name": "example/tool",
        "html_url": "https://github.com/example/tool",
        "license": {"spdx_id": "MIT"},
        "archived": False,
        "pushed_at": "2026-10-29T15:04:03Z",
        "stargazers_count": 7,
    }
    release = {"tag_name": "v2.0.0", "published_at": "2026-10-28T00:55:47Z"}
    store, runner = recorded_store({"/releases/latest": release, "repos/example/tool": repository})
    assert (store.repository_facts("example/tool"), [args for args, _ in runner.calls]) == (
        RepositoryFacts(
            full_name="example/tool",
            url="https://github.com/example/tool",
            license="MIT",
            pushed_at=datetime(2026, 10, 29, 15, 4, 3, tzinfo=UTC),
            stars=7,
            latest_release="v2.0.0",
            released_at=datetime(2026, 10, 28, 0, 55, 47, tzinfo=UTC),
        ),
        [["api", "repos/example/tool"], ["api", "repos/example/tool/releases/latest"]],
    )


def test_repository_facts_of_a_repository_with_no_release_or_license() -> None:
    repository = {
        "full_name": "example/tool",
        "html_url": "https://github.com/example/tool",
        "license": None,
        "archived": True,
        "pushed_at": None,
        "stargazers_count": 0,
    }
    gone = (1, "gh: Not Found (HTTP 404)")
    store, _ = recorded_store({"/releases/latest": gone, "repos/example/tool": repository})
    facts = store.repository_facts("example/tool")
    assert facts is not None
    assert (
        facts.license,
        facts.archived,
        facts.pushed_at,
        facts.latest_release,
    ) == (None, True, None, None)


def test_repository_facts_of_a_missing_repository_are_none_and_a_failed_read_raises() -> None:
    missing, _ = recorded_store({"repos/example/none": (1, "gh: Not Found (HTTP 404)")})
    broken, _ = recorded_store({"repos/example/tool": (1, "gh: Server Error (HTTP 502)")})
    assert missing.repository_facts("example/none") is None
    with pytest.raises(GitHubOperationError, match=r"Could not read the repository example/tool"):
        broken.repository_facts("example/tool")


@pytest.mark.parametrize("name", ["scanner", "a/b/c", "../user", "example/..", "a b/c"])
def test_repository_facts_refuses_a_name_that_is_no_repository_name_before_any_request(
    name: str,
) -> None:
    store, runner = recorded_store({})
    with pytest.raises(GitHubOperationError, match="is not a repository name"):
        store.repository_facts(name)
    assert runner.calls == []


def test_dependency_purls_read_the_sbom_of_the_dependency_graph_once() -> None:
    """One REST read of the SPDX SBOM that the dependency graph exports gives the package URL of
    each package; a package with no package URL gives none (#4661)."""
    sbom = {
        "sbom": {
            "packages": [
                {
                    "name": "mcp",
                    "externalRefs": [
                        {
                            "referenceCategory": "PACKAGE-MANAGER",
                            "referenceType": "purl",
                            "referenceLocator": "pkg:pypi/mcp@2.3.0",
                        }
                    ],
                },
                {"name": "com.github.example/roadmap", "externalRefs": []},
                {
                    "name": "@devcontainers/cli",
                    "externalRefs": [
                        {
                            "referenceCategory": "SECURITY",
                            "referenceType": "cpe23Type",
                            "referenceLocator": "cpe:2.3:a:devcontainers:cli",
                        },
                        {
                            "referenceCategory": "PACKAGE-MANAGER",
                            "referenceType": "purl",
                            "referenceLocator": "pkg:npm/%40devcontainers/cli@0.89.0",
                        },
                    ],
                },
            ]
        }
    }
    store, runner = recorded_store({"dependency-graph/sbom": sbom})
    assert (store.dependency_purls(), [args for args, _ in runner.calls]) == (
        ["pkg:pypi/mcp@2.3.0", "pkg:npm/%40devcontainers/cli@0.89.0"],
        [["api", f"repos/{REPO}/dependency-graph/sbom"]],
    )


def test_dependency_purls_of_a_repository_with_no_dependency_graph_are_none() -> None:
    """GitHub answers 404 when the dependency graph of the repository is off; another failed read
    raises (#4661)."""
    off, _ = recorded_store({"dependency-graph/sbom": (1, "gh: Not Found (HTTP 404)")})
    broken, _ = recorded_store({"dependency-graph/sbom": (1, "gh: Server Error (HTTP 502)")})
    assert off.dependency_purls() == []
    with pytest.raises(GitHubOperationError, match="Could not read the SBOM"):
        broken.dependency_purls()
