"""The command `devops repos onboard`: its modes, its output and its exit code (#6773)."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.support.fakes.github import API, github_json
from tests.support.fakes.otlp import FakeCollector
from tests.support.github_repository import (
    REPO,
    WEBHOOK_URL,
    OnboardHarness,
    RepositoryState,
)

OTHER = "example-org/other"
# The token exchange of the Service App of the harness (installation 42).
MINT = "/app/installations/42/access_tokens"


def _onboarded(harness: OnboardHarness, state: RepositoryState) -> None:
    """`state` as a confirmed run leaves it, with its hook secret in the keyring map."""
    state.onboard(release_flow=True)
    state.hooks = [
        {
            "id": 9,
            "active": True,
            "events": ["*"],
            "config": {"url": WEBHOOK_URL, "content_type": "json"},
        }
    ]
    stored = json.loads(harness.keyring.values.get("service_webhook_secrets", "{}"))
    harness.keyring.values["service_webhook_secrets"] = json.dumps({**stored, state.repo: "s"})


def test_a_dry_run_sends_no_request_and_lists_the_routes(
    cli: Callable[..., Any], onboard_github: OnboardHarness
) -> None:
    result = cli("repos", "onboard", REPO, "--dry-run")

    assert result.exit_code == 0, result.output
    assert onboard_github.api.sent == []
    assert onboard_github.processes.calls == []
    assert f"POST /repos/{REPO}/labels" in result.stdout
    assert "owner: person config" in result.stdout


def test_two_modes_are_refused(cli: Callable[..., Any], onboard_github: OnboardHarness) -> None:
    result = cli("repos", "onboard", REPO, "--plan", "--confirm")

    assert result.exit_code == 2
    assert "--plan, --dry-run and --confirm" in result.output
    assert onboard_github.api.sent == []


def test_all_refuses_confirm(cli: Callable[..., Any], onboard_github: OnboardHarness) -> None:
    result = cli("repos", "onboard", "--all", "--confirm")

    assert result.exit_code == 2
    assert "--all checks the drift only" in result.output
    assert onboard_github.api.sent == []


def test_an_onboarded_repository_exits_0_with_no_person_step(
    cli: Callable[..., Any], onboard_github: OnboardHarness, config: Callable[..., Any]
) -> None:
    _onboarded(onboard_github, onboard_github.state)
    config(service={"repos": [REPO]})

    result = cli("repos", "onboard", REPO)

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0] == f"# Onboarding of {REPO} at v0.3.0"
    assert result.stdout.rstrip().endswith("Person steps: none.")


def test_only_one_row(cli: Callable[..., Any], onboard_github: OnboardHarness) -> None:
    result = cli("repos", "onboard", REPO, "--only", "8")

    rows = [line for line in result.stdout.splitlines() if line[:1].isdigit()]
    assert rows == ["8. Labels: pending"]
    assert result.exit_code == 1


def test_the_drift_check_reads_every_service_repository(
    cli: Callable[..., Any], onboard_github: OnboardHarness, config: Callable[..., Any]
) -> None:
    other = RepositoryState(OTHER)
    onboard_github.api.serve(other.answer)
    _onboarded(onboard_github, onboard_github.state)
    _onboarded(onboard_github, other)
    other.payload["allow_merge_commit"] = True
    config(service={"repos": [REPO, OTHER]})

    result = cli("repos", "onboard", "--all", "--plan")

    assert result.exit_code == 1, result.output
    assert f"# Onboarding of {REPO} at v0.3.0" in result.stdout
    assert f"# Onboarding of {OTHER} at v0.3.0" in result.stdout
    assert "   - allow_merge_commit: False" in result.stdout
    assert {request.method for request in onboard_github.api.sent} == {"GET"}


# The gauge of the drift check (#6783), read by its name, so the tests import no name of the change.
DRIFT_GAUGE = "devops_cli_repos_drift_rows"


def _drift_points(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    """The last value of each series of the drift gauge, by repository and state."""
    return {(labels["repo"], labels["state"]): value for labels, value in otlp.points(DRIFT_GAUGE)}


def _state_lines(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.startswith("Drift check of ")]


def test_a_pending_change_gives_the_drift_report(
    cli: Callable[..., Any],
    onboard_github: OnboardHarness,
    config: Callable[..., Any],
    otlp: FakeCollector,
) -> None:
    _onboarded(onboard_github, onboard_github.state)
    onboard_github.state.payload["allow_merge_commit"] = True
    config(service={"repos": [REPO]})

    result = cli("repos", "onboard", "--all", "--plan")

    points = _drift_points(otlp)
    assert result.exit_code == 1, result.output
    assert points[(REPO, "drift")] > 0
    assert points[(REPO, "not_readable")] == 0
    assert [line.split(" (")[0] for line in _state_lines(result.stdout)] == [
        f"Drift check of {REPO}: drift"
    ]


def test_no_change_gives_no_drift_report(
    cli: Callable[..., Any],
    onboard_github: OnboardHarness,
    config: Callable[..., Any],
    otlp: FakeCollector,
) -> None:
    _onboarded(onboard_github, onboard_github.state)
    config(service={"repos": [REPO]})

    result = cli("repos", "onboard", "--all", "--plan")

    assert result.exit_code == 0, result.output
    assert _drift_points(otlp) == {(REPO, "drift"): 0, (REPO, "not_readable"): 0}
    assert [line.split(" (")[0] for line in _state_lines(result.stdout)] == [
        f"Drift check of {REPO}: clean"
    ]


def test_a_row_that_is_not_readable_gives_its_own_state(
    cli: Callable[..., Any],
    onboard_github: OnboardHarness,
    config: Callable[..., Any],
    otlp: FakeCollector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Until the runner image holds `copier`, the rows that read the baseline are `not readable`:
    the check reports that as its own state, neither drift nor clean."""
    _onboarded(onboard_github, onboard_github.state)
    config(service={"repos": [REPO]})
    real_which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, *a, **k: None if name == "copier" else real_which(name, *a, **k),
    )

    result = cli("repos", "onboard", "--all", "--plan")

    points = _drift_points(otlp)
    assert result.exit_code == 1, result.output
    assert points[(REPO, "drift")] == 0
    assert points[(REPO, "not_readable")] > 0
    assert [line.split(" (")[0] for line in _state_lines(result.stdout)] == [
        f"Drift check of {REPO}: not readable"
    ]


def test_one_repository_sets_no_drift_gauge(
    cli: Callable[..., Any],
    onboard_github: OnboardHarness,
    config: Callable[..., Any],
    otlp: FakeCollector,
) -> None:
    _onboarded(onboard_github, onboard_github.state)
    config(service={"repos": [REPO]})

    result = cli("repos", "onboard", REPO, "--plan")

    assert result.exit_code == 0, result.output
    assert (otlp.points(DRIFT_GAUGE), _state_lines(result.stdout)) == ([], [])


def _act_as_the_app(
    harness: OnboardHarness, app_key: str, monkeypatch: pytest.MonkeyPatch, *, drift: bool
) -> None:
    """Make the process act as the App of the harness, as the nightly Job does, and answer its
    token request. With `drift`, the process sets the variable of the drift check."""
    from devops_cli.config.constants import CONST_GITHUB_APP_PRIVATE_KEY_ENV
    from devops_cli.github.rate_limiter import get_github_rate_limiter
    from devops_cli.github.session import reset_github_session

    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, app_key)
    if drift:
        monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK", "true")
    reset_github_session()
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    harness.api.route(
        "POST",
        f"{API}{MINT}",
        github_json({"token": "ghs_drift", "expires_at": expires_at}, status=201),
    )


def test_the_drift_check_as_the_app_reads_no_user(
    cli: Callable[..., Any],
    onboard_github: OnboardHarness,
    config: Callable[..., Any],
    onboard_app_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The nightly Job acts as the App, and GitHub refuses `GET /user` to an installation token:
    row 0 reads no scopes and the run goes on (#6783)."""
    _onboarded(onboard_github, onboard_github.state)
    config(service={"repos": [REPO]})
    _act_as_the_app(onboard_github, onboard_app_key, monkeypatch, drift=False)

    result = cli("repos", "onboard", "--all", "--plan")

    requests = {f"{request.method} {request.url.path}" for request in onboard_github.api.sent}
    assert result.exit_code == 0, result.output
    assert "GET /user" not in requests
    assert {request.split(" ")[0] for request in requests - {f"POST {MINT}"}} == {"GET"}
    assert "0. Preflight: present (the token reports no OAuth scopes)" in result.stdout


def test_the_drift_check_with_a_write_token_sends_only_gets(
    cli: Callable[..., Any],
    onboard_github: OnboardHarness,
    config: Callable[..., Any],
    onboard_app_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The token of the drift check can write the contents and the settings of a repository
    (#6888), and a plan still sends GET requests only, also over a repository off its baseline."""
    state = onboard_github.state
    _onboarded(onboard_github, state)
    state.payload["allow_merge_commit"] = True
    state.rulesets[0]["enforcement"] = "disabled"
    state.workflow_permissions["default_workflow_permissions"] = "write"
    config(service={"repos": [REPO]})
    _act_as_the_app(onboard_github, onboard_app_key, monkeypatch, drift=True)

    result = cli("repos", "onboard", "--all", "--plan")

    mint = [request for request in onboard_github.api.sent if request.url.path == MINT]
    others = [request for request in onboard_github.api.sent if request.url.path != MINT]
    assert result.exit_code == 1, result.output
    assert "   - allow_merge_commit: False" in result.stdout
    permissions = json.loads(mint[0].content)["permissions"]
    assert (permissions["contents"], permissions["administration"]) == ("write", "write")
    assert others
    assert {request.method for request in others} == {"GET"}
