"""Unit tests for the typed webhook payloads: the pull request and check suite numbers of a delivery."""

from __future__ import annotations

from devops_cli.models.webhooks import GitHubWebhookPayload


def test_a_pull_request_and_a_check_suite_payload_validate() -> None:
    """Verify that a pull request payload and a check suite payload both expose their number."""
    pull_request = GitHubWebhookPayload.model_validate(
        {
            "action": "synchronize",
            "repository": {"full_name": "example/example"},
            "pull_request": {"number": 42},
        },
    )
    check_suite = GitHubWebhookPayload.model_validate(
        {
            "action": "completed",
            "repository": {"full_name": "example/example"},
            "check_suite": {"pull_requests": [{"number": 42}]},
        },
    )

    assert pull_request.pull_request is not None
    assert pull_request.pull_request.number == 42
    assert pull_request.delivery_numbers == (42,)
    assert pull_request.issue is None

    assert check_suite.check_suite is not None
    assert check_suite.delivery_numbers == (42,)
    assert check_suite.issue is None


def test_a_delivery_numbers_the_issue_its_pull_requests_and_nothing() -> None:
    """Verify that the numbers of a delivery follow the object that it names."""
    issue = GitHubWebhookPayload.model_validate(
        {
            "action": "opened",
            "repository": {"full_name": "example/example"},
            "issue": {"number": 7},
        },
    )
    suite = GitHubWebhookPayload.model_validate(
        {
            "action": "completed",
            "repository": {"full_name": "example/example"},
            "check_suite": {"pull_requests": [{"number": 42}, {"number": 43}]},
        },
    )
    ping = GitHubWebhookPayload.model_validate({"repository": {"full_name": "example/example"}})

    assert issue.delivery_numbers == (7,)
    assert suite.delivery_numbers == (42, 43)
    assert ping.delivery_numbers == ()
