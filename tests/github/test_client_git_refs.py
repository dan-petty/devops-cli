"""Tests for GitHubClient.create_ref (POST /repos/{owner}/{repo}/git/refs) (#5499)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import API, github_json

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

REPO = "owner/widget"
REF = "refs/heads/feat/5499-test-branch"
SHA = "0123456789abcdef0123456789abcdef01234567"


def test_create_ref_posts_payload_and_returns_object(github_api: GitHubApiFake) -> None:
    expected_response = {
        "ref": REF,
        "node_id": "MDM6UmVmMTI=",
        "url": f"https://api.github.com/repos/{REPO}/git/{REF}",
        "object": {
            "sha": SHA,
            "type": "commit",
            "url": f"https://api.github.com/repos/{REPO}/git/commits/{SHA}",
        },
    }
    github_api.route("POST", f"/repos/{REPO}/git/refs", github_json(expected_response, status=201))

    client = get_github_session().client
    result = client.create_ref(REPO, ref=REF, sha=SHA)

    assert result == expected_response
    assert github_api.requested == [f"POST {API}/repos/{REPO}/git/refs"]
    assert json.loads(github_api.sent[0].content) == {"ref": REF, "sha": SHA}


def test_create_ref_raises_when_answer_is_not_dict(github_api: GitHubApiFake) -> None:
    github_api.route("POST", f"/repos/{REPO}/git/refs", github_json("not a dict", status=200))

    client = get_github_session().client
    with pytest.raises(GitHubUnreadError, match="is not an object"):
        client.create_ref(REPO, ref=REF, sha=SHA)
