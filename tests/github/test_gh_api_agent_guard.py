"""Protected route classification and agent write guard tests for `devops gh api` (#5316)."""

from __future__ import annotations

import pytest

from devops_cli.exceptions import DevOpsCLIError, GitHubApiAccessRefusedError
from devops_cli.github.api_guard import (
    classify_protected_route,
    normalize_gh_api_path,
    require_gh_api_access,
    require_gh_api_argv_access,
)


@pytest.mark.parametrize(
    ("method", "endpoint", "expected_class"),
    [
        ("PATCH", "repos/o/r", "repository settings"),
        ("DELETE", "repos/o/r", "repository settings"),
        ("PUT", "repos/o/r/branches/main/protection", "repository settings"),
        (
            "PUT",
            "repos/o/r/branches/release/v1/protection/required_status_checks",
            "repository settings",
        ),
        ("PATCH", "repos/o/r/actions/permissions/workflow", "repository settings"),
        ("POST", "repos/o/r/keys", "repository settings"),
        ("POST", "repos/o/r/hooks", "repository settings"),
        ("PUT", "repos/o/r/topics", "repository settings"),
        ("POST", "repos/o/r/rulesets", "rulesets"),
        ("PUT", "repos/o/r/rulesets/1", "rulesets"),
        ("PATCH", "orgs/o/rulesets/2", "rulesets"),
        ("DELETE", "repos/o/r/rulesets/1", "rulesets"),
        ("PUT", "repos/o/r/actions/secrets/MY_KEY", "secrets"),
        ("DELETE", "repos/o/r/environments/prod/secrets/MY_KEY", "secrets"),
        ("PUT", "orgs/o/actions/secrets/ORG_KEY", "secrets"),
        ("PUT", "repos/o/r/dependabot/secrets/DEP_KEY", "secrets"),
        ("PATCH", "orgs/o", "organization settings"),
        ("POST", "orgs/o/repos", "organization settings"),
        ("PUT", "orgs/o/actions/permissions", "organization settings"),
        ("POST", "orgs/o/teams", "organization settings"),
        ("DELETE", "orgs/o/members/alice", "organization settings"),
        ("POST", "repos/o/r/transfer", "repository transfer"),
    ],
)
def test_protected_route_table_classifies_every_protected_class(
    method: str, endpoint: str, expected_class: str
) -> None:
    """Every protected route class matches its mutating HTTP methods."""
    match = classify_protected_route(method, endpoint)

    assert match is not None
    assert match.route_class == expected_class


@pytest.mark.parametrize(
    ("method", "endpoint", "expected_normalized", "expected_class"),
    [
        ("PUT", "/repos/o/r/rulesets/1?force=true", "repos/o/r/rulesets/1", "rulesets"),
        (
            "POST",
            "https://api.github.com/repos/o/r/transfer?confirm=1#top",
            "repos/o/r/transfer",
            "repository transfer",
        ),
        ("PATCH", "///repos/o/r/?visibility=private", "repos/o/r", "repository settings"),
    ],
)
def test_route_normalization_strips_slash_and_query_string(
    method: str, endpoint: str, expected_normalized: str, expected_class: str
) -> None:
    """Leading slashes, scheme/host prefixes, query strings, and fragments normalize cleanly."""
    assert normalize_gh_api_path(endpoint) == expected_normalized
    match = classify_protected_route(method, endpoint)

    assert match is not None
    assert (match.route_class, match.endpoint) == (expected_class, expected_normalized)


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("POST", "/repos/o/r/issues"),
        ("POST", "/repos/o/r/pulls"),
        ("POST", "/repos/o/r/labels"),
        ("POST", "/repos/o/r/actions/workflows/1/dispatches"),
        ("POST", "repos/o/r/issues/12/comments"),
        ("PATCH", "repos/o/r/pulls/12"),
        ("GET", "/repos/o/r/rulesets/1?force=true"),
        ("GET", "repos/o/r/actions/secrets"),
        ("GET", "orgs/o"),
        ("GET", "repos/o/r/transfer"),
    ],
)
def test_open_routes_and_reads_remain_allowed_for_agent_callers(
    agent_caller: None, method: str, endpoint: str
) -> None:
    """Issue, PR, label, dispatch writes, and GET reads remain open for agent callers."""
    assert classify_protected_route(method, endpoint) is None
    require_gh_api_access(method, endpoint)


def test_agent_protected_write_is_refused_with_route_and_owner_step(agent_caller: None) -> None:
    """An agent caller writing to a protected route raises a refusal naming route and owner step."""
    with pytest.raises(GitHubApiAccessRefusedError) as caught:
        require_gh_api_access("POST", "/repos/o/r/transfer?dry=0")

    exc = caught.value
    assert isinstance(exc, DevOpsCLIError)
    msg = exc.message.lower()
    assert "repos/o/r/transfer" in exc.message
    assert "repository transfer" in msg
    assert "owner" in msg or "person" in msg
    assert exc.details["pattern"] == "repos/{owner}/{repo}/transfer"


def test_agent_implicit_post_via_fields_is_refused(agent_caller: None) -> None:
    """`-f` / `-F` / `--input` imply POST in `gh api` and are refused on protected routes."""
    with pytest.raises(GitHubApiAccessRefusedError) as caught:
        require_gh_api_argv_access(["repos/o/r/transfer", "-f", "new_owner=other-org"])

    assert (caught.value.error_code, "repos/o/r/transfer" in caught.value.message) == (
        "GITHUB_API_ACCESS_REFUSED",
        True,
    )


def test_empty_endpoint_and_fallback_argv_parsing(agent_caller: None) -> None:
    """Empty endpoints do not match, and unparseable argv flags still resolve method safely."""
    assert normalize_gh_api_path("/") == ""
    assert classify_protected_route("POST", "/") is None

    # `parse_gh_api_args` returns None on `--jq -.a`; fallback resolves read vs write safely.
    assert (
        require_gh_api_argv_access(
            ["repos/o/r/transfer", "--jq", "-.a"], endpoint_override="repos/o/r/transfer"
        )
        is None
    )
    with pytest.raises(GitHubApiAccessRefusedError) as overridden:
        require_gh_api_argv_access(
            ["repos/o/r/transfer", "--jq", "-.a"],
            method_override="post",
            endpoint_override="repos/o/r/transfer",
        )
    assert overridden.value.details["method"] == "POST"

    with pytest.raises(GitHubApiAccessRefusedError) as field_fallback:
        require_gh_api_argv_access(
            ["repos/o/r/transfer", "--jq", "-.a", "-f", "new_owner=other-org"],
            endpoint_override="repos/o/r/transfer",
        )
    assert field_fallback.value.details["method"] == "POST"


def test_person_protected_write_is_allowed(person_caller: None) -> None:
    """A person caller is allowed on protected write routes."""
    assert require_gh_api_access("POST", "repos/o/r/transfer") is None
    assert require_gh_api_argv_access(["repos/o/r/rulesets/1", "-X", "PUT"]) is None
