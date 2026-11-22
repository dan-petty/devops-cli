"""The rows of `devops repos onboard` over one repository of a fake GitHub (#6773)."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.settings import load_settings
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.onboard.model import (
    DOC_COPIER,
    DOC_SECRETS,
    OnboardOptions,
    OnboardReport,
    RowState,
)
from devops_cli.github.onboard.run import onboard_repository, render_report
from devops_cli.github.repo_ref import RepoRef
from devops_cli.github.session import get_github_session
from tests.support.fakes.process import ProcessAnswer
from tests.support.github_repository import (
    CHECK_NAME,
    RELEASE_KEY,
    REPO,
    TEMPLATE_BRANCH,
    TEMPLATE_TAG,
    WEBHOOK_URL,
    OnboardHarness,
)

P = RowState.PRESENT


def _run(harness: OnboardHarness, *, confirm: bool = False, **options: Any) -> OnboardReport:
    """One run of the rows over REPO, as the command runs them."""
    chosen = OnboardOptions(repo=RepoRef(REPO), confirm=confirm, workdir=harness.workdir, **options)
    return onboard_repository(chosen, session=get_github_session(), settings=load_settings())


def _states(report: OnboardReport) -> dict[int, RowState]:
    return {row.number: row.state for row in report.rows}


def _row(report: OnboardReport, number: int) -> Any:
    return next(row for row in report.rows if row.number == number)


def _store_hook_secret(harness: OnboardHarness) -> None:
    """A Service hook on the repository whose secret the keyring map holds."""
    harness.state.hooks = [
        {
            "id": 9,
            "active": True,
            "events": ["*"],
            "config": {"url": WEBHOOK_URL, "content_type": "json"},
        }
    ]
    harness.keyring.values["service_webhook_secrets"] = json.dumps({REPO: "stored-secret"})


def _onboarded(harness: OnboardHarness, config: Any) -> None:
    """REPO as a confirmed run leaves it, with its template pull request merged."""
    harness.state.onboard(release_flow=True)
    _store_hook_secret(harness)
    config(service={"repos": [REPO]})


def test_a_second_confirmed_run_on_a_new_repository_writes_nothing(
    onboard_github: OnboardHarness, config: Any
) -> None:
    harness = onboard_github

    first = _run(harness, confirm=True)

    assert _states(first) == {
        0: P,
        1: P,
        2: RowState.APPLIED,
        3: RowState.APPLIED,
        4: RowState.NOT_AVAILABLE,
        5: RowState.APPLIED,
        6: RowState.APPLIED,
        7: P,
        8: RowState.APPLIED,
        9: RowState.APPLIED,
        10: RowState.APPLIED,
        11: RowState.APPLIED,
        12: RowState.APPLIED,
        13: RowState.APPLIED,
        14: RowState.SKIPPED,
        15: P,
    }, render_report(first)
    assert first.failing is False
    assert harness.state.graphql == [
        "markPullRequestReadyForReview",
        "mergeStateStatus",
        "enablePullRequestAutoMerge",
    ]
    assert harness.state.rulesets[0]["rules"][2]["parameters"]["required_status_checks"] == [
        {"context": CHECK_NAME}
    ]
    assert yaml.safe_load(config().read_text())["service"]["repos"] == [REPO]
    assert len(harness.calls("push-secrets")) == len(harness.calls("deploy-stack")) == 1

    harness.state.merge_template_pull()
    harness.api.sent.clear()
    calls = len(harness.processes.calls)

    second = _run(harness, confirm=True)

    assert harness.writes() == [], render_report(second)
    assert {row.state for row in second.rows} <= {P, RowState.NOT_AVAILABLE, RowState.SKIPPED}, (
        render_report(second)
    )
    assert second.failing is False
    later = [" ".join(call.argv) for call in harness.processes.calls[calls:]]
    assert not any("PUT" in argv or "k8s" in argv for argv in later), later


def test_a_plan_of_a_new_repository_sends_only_gets_and_names_each_change(
    onboard_github: OnboardHarness,
) -> None:
    report = _run(onboard_github)

    assert {request.method for request in onboard_github.api.sent} == {"GET"}
    assert onboard_github.calls("--vcs-ref")[0].argv[3] == TEMPLATE_TAG
    assert report.failing is True
    assert _row(report, 2).state is RowState.PENDING
    assert "allow_merge_commit: False" in _row(report, 2).changes
    assert _row(report, 9).changes[0].startswith("add ")
    assert onboard_github.calls("push-secrets") == []


def test_an_onboarded_repository_plans_no_change(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)

    report = _run(onboard_github)

    assert report.failing is False, render_report(report)
    assert {request.method for request in onboard_github.api.sent} == {"GET"}
    assert report.person_steps == ()
    assert render_report(report).endswith("Person steps: none.")


def test_the_release_key_reaches_no_output_log_or_argv(
    onboard_github: OnboardHarness, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    key_file = tmp_path / "release.pem"
    known = "KNOWN-TEST-VALUE-FROM-A-FILE"
    key_file.write_text(known, encoding="utf-8")
    caplog.set_level(logging.DEBUG)

    report = _run(onboard_github, confirm=True, release_key_file=key_file)

    upload = next(call for call in onboard_github.processes.calls if "PUT" in call.argv)
    assert upload.argv[4].endswith("/environments/release/secrets/RELEASE_APP_PRIVATE_KEY")
    assert "encrypted_value" in str(upload.stdin)
    seen = [
        render_report(report),
        caplog.text,
        *(" ".join(c.argv) for c in onboard_github.processes.calls),
    ]
    seen.append(str(upload.stdin))
    assert not any(known in text or RELEASE_KEY in text for text in seen)


@pytest.mark.parametrize("release_flow", [None, True], ids=["no flag", "--release-flow"])
def test_a_private_repository_on_the_free_plan_gets_no_release_flow(
    onboard_github: OnboardHarness, release_flow: bool | None
) -> None:
    onboard_github.state.private = True
    onboard_github.state.rulesets_forbidden = True
    onboard_github.state.payload.update(private=True, visibility="private")

    report = _run(onboard_github, confirm=True, release_flow=release_flow)

    assert onboard_github.calls("release_flow=false")
    assert [_row(report, n).state for n in (5, 6, 10)] == [RowState.SKIPPED] * 3
    assert not any(
        "environments" in write or "rulesets" in write for write in onboard_github.writes()
    )
    assert any("Free plan" in step.text for step in report.person_steps)


def test_an_app_that_is_not_installed_is_a_person_step(onboard_github: OnboardHarness) -> None:
    onboard_github.state.installed = False

    report = _run(onboard_github, confirm=True)

    assert _row(report, 7).state is RowState.PERSON
    assert any("example-service" in step.text for step in report.person_steps)
    assert not any(
        "installation" in str(request.url) and request.method == "PUT"
        for request in onboard_github.api.sent
    )


def test_a_flag_that_differs_from_the_answers_file_is_refused(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)

    with pytest.raises(DevOpsCLIError) as raised:
        _run(onboard_github, confirm=True, scopes=("worker",))

    assert (raised.value.error_code, raised.value.exit_code) == ("ONBOARD_ANSWER_DIFFERS", 2)
    assert "--scope" in raised.value.message
    assert onboard_github.writes() == []


def test_a_settings_file_that_the_schema_refuses_makes_the_baseline_rows_not_readable(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.state.schema["properties"].pop("immutable_releases")

    report = _run(onboard_github)

    for number in (2, 3, 5, 6, 9, 10, 11):
        assert _row(report, number).state is RowState.NOT_READABLE
        assert "templates/github-repository.schema.json" in str(_row(report, number).reason)


def test_no_copier_program_makes_the_baseline_rows_not_readable(
    onboard_github: OnboardHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, *a, **k: None if name == "copier" else real_which(name, *a, **k),
    )

    report = _run(onboard_github)

    assert _row(report, 2).state is RowState.NOT_READABLE
    assert "copier is not on PATH" in str(_row(report, 2).reason)
    assert [step.document for step in report.person_steps if "copier" in step.text] == [DOC_COPIER]


def test_a_token_without_workflow_stops_a_confirm_before_any_write(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.state.scopes = "repo"

    report = _run(onboard_github, confirm=True)

    assert _row(report, 0).state is RowState.FAILED
    assert "workflow" in str(_row(report, 0).reason)
    assert onboard_github.writes() == []


def test_a_token_without_workflow_stops_a_create_before_any_write(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.state.exists = False
    onboard_github.state.scopes = "repo"

    report = _run(onboard_github, confirm=True, create=True, visibility="public")

    assert _row(report, 0).state is RowState.FAILED
    assert "workflow" in str(_row(report, 0).reason)
    assert _row(report, 1).state is RowState.SKIPPED
    assert onboard_github.writes() == []


def test_a_missing_repository_without_create_skips_the_rest(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.state.exists = False

    report = _run(onboard_github)

    assert _row(report, 1).state is RowState.FAILED
    assert "--create" in _row(report, 1).changes[0]
    assert {_row(report, n).state for n in range(2, 16)} == {RowState.SKIPPED}


def test_create_makes_the_repository_of_the_login(onboard_github: OnboardHarness) -> None:
    onboard_github.state.exists = False

    report = _run(onboard_github, confirm=True, create=True, visibility="public")

    assert _row(report, 1).state is RowState.APPLIED
    assert onboard_github.writes()[0] == "POST /user/repos"


def test_a_dirty_checkout_refuses_the_service_row(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.processes.answer(
        lambda call: call.argv[:2] == ("git", "status"), ProcessAnswer(stdout=" M config.yaml\n")
    )

    report = _run(onboard_github, confirm=True)

    assert _row(report, 13).state is RowState.REFUSED
    assert _row(report, 13).reason == "the checkout has 1 changed files"
    assert load_settings().service.repos == []
    assert onboard_github.calls("deploy-stack") == []


def test_a_hook_that_sends_every_event_is_present(onboard_github: OnboardHarness) -> None:
    _store_hook_secret(onboard_github)

    report = _run(onboard_github, only=frozenset({12}))

    assert _states(report) == {12: P}


def test_a_new_hook_keeps_its_secret_in_the_keyring_only(onboard_github: OnboardHarness) -> None:
    report = _run(onboard_github, confirm=True, only=frozenset({12}))

    secret = json.loads(onboard_github.keyring.values["service_webhook_secrets"])[REPO]
    assert onboard_github.state.hooks[0]["config"]["secret"] == secret
    assert len(secret) == 64
    assert secret not in render_report(report)


def test_a_differing_label_is_kept(onboard_github: OnboardHarness) -> None:
    onboard_github.state.labels = [{"name": "scope/ci", "color": "000000", "description": "ci"}]

    report = _run(onboard_github, confirm=True, only=frozenset({8}))

    assert "label scope/ci" in report.kept
    assert not any(write.startswith("PATCH") for write in onboard_github.writes())
    assert "create scope/docs" in _row(report, 8).changes


def test_checks_that_do_not_end_leave_the_template_row_waiting(
    onboard_github: OnboardHarness, clock: Any
) -> None:
    onboard_github.state.check_runs = [
        {"name": CHECK_NAME, "status": "in_progress", "conclusion": None}
    ]

    report = _run(onboard_github, confirm=True)

    assert _row(report, 9).state is RowState.WAITING
    assert _row(report, 10).state is RowState.SKIPPED
    assert _row(report, 11).state is RowState.SKIPPED
    assert not any(
        "rulesets" in write or write == "POST /graphql" for write in onboard_github.writes()
    )


def test_a_pull_request_with_nothing_to_wait_for_merges(onboard_github: OnboardHarness) -> None:
    onboard_github.state.merge_state = "CLEAN"

    _run(onboard_github, confirm=True)

    assert onboard_github.state.graphql == [
        "markPullRequestReadyForReview",
        "mergeStateStatus",
        "mergePullRequest",
    ]
    assert onboard_github.state.refs["main"] == "merged"


def test_a_head_that_moves_after_its_checks_does_not_merge(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.state.merge_state = "CLEAN"
    onboard_github.state.push_during_checks = True

    report = _run(onboard_github, confirm=True)

    assert _row(report, 11).state is RowState.WAITING, render_report(report)
    assert "the next run" in str(_row(report, 11).reason)
    assert onboard_github.state.refs["main"] != "merged"
    assert onboard_github.state.pulls[0]["auto_merge"] is None


def test_a_drifted_commit_message_is_sent_with_its_title(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    onboard_github.state.payload["squash_merge_commit_message"] = "BLANK"

    report = _run(onboard_github, confirm=True, only=frozenset({2}))

    assert _row(report, 2).state is RowState.APPLIED, render_report(report)
    patch = next(request for request in onboard_github.api.sent if request.method == "PATCH")
    assert json.loads(patch.content) == {
        "squash_merge_commit_message": "PR_BODY",
        "squash_merge_commit_title": "PR_TITLE",
    }


def test_a_repository_file_with_other_text_is_kept(onboard_github: OnboardHarness) -> None:
    state = onboard_github.state
    state.commits["c0"] = {**state.commits["c0"], ".pre-commit-config.yaml": "repos: [own]\n"}

    report = _run(onboard_github, confirm=True, only=frozenset({9}))

    assert "file .pre-commit-config.yaml" in report.kept
    assert state.commits[state.refs[TEMPLATE_BRANCH]][".pre-commit-config.yaml"] == "repos: [own]\n"


def test_an_unreadable_store_informs_only(onboard_github: OnboardHarness, config: Any) -> None:
    _onboarded(onboard_github, config)
    onboard_github.qdrant.fail_operation("count_points")

    report = _run(onboard_github)

    assert _row(report, 15).state is RowState.NOT_READABLE
    assert report.failing is False


def test_a_missing_release_key_is_the_last_person_step(onboard_github: OnboardHarness) -> None:
    del onboard_github.keyring.values["github_release_app_private_key"]

    report = _run(onboard_github)

    last = render_report(report).splitlines()[-1]
    assert "devops config set github.release_app_private_key" in last
    assert DOC_SECRETS in last


def test_a_service_repository_gets_the_person_step_of_its_entry(
    onboard_github: OnboardHarness,
) -> None:
    report = _run(onboard_github, service=True, only=frozenset({14}))

    assert _states(report) == {14: RowState.PERSON}
    assert "k8s/services/app.yaml" in report.person_steps[0].text


def test_a_drifted_repository_gets_one_write_for_each_difference(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    state = onboard_github.state
    state.rulesets[0]["enforcement"] = "disabled"
    state.environments["release"].variables["RELEASE_APP_CLIENT_ID"] = "Iv23old"
    state.hooks[0]["active"] = False
    state.workflow_permissions["default_workflow_permissions"] = "write"

    report = _run(onboard_github, confirm=True, deploy=False)

    assert onboard_github.writes() == [
        "PUT /repos/example-org/app/actions/permissions/workflow",
        "PATCH /repos/example-org/app/environments/release/variables/RELEASE_APP_CLIENT_ID",
        "PUT /repos/example-org/app/rulesets/7",
        "PATCH /repos/example-org/app/hooks/9",
    ]
    assert state.rulesets[0]["enforcement"] == "active"
    assert _row(report, 13).state is RowState.APPLIED
    assert onboard_github.calls("deploy-stack") == []
    assert any("deploy-stack" in step.text for step in report.person_steps)


def test_a_stale_template_pull_request_gets_a_new_commit(onboard_github: OnboardHarness) -> None:
    _run(onboard_github, confirm=True, only=frozenset({9}))
    state = onboard_github.state
    first_head = state.refs[TEMPLATE_BRANCH]
    state.commits[first_head] = {
        path: text
        for path, text in state.commits[first_head].items()
        if path != ".github/labels.yml"
    }
    onboard_github.api.sent.clear()

    report = _run(onboard_github, confirm=True, only=frozenset({9}))

    assert _row(report, 9).changes == ("add .github/labels.yml",)
    assert f"PATCH /repos/{REPO}/git/refs/heads/{TEMPLATE_BRANCH}" in onboard_github.writes()
    assert f"POST /repos/{REPO}/pulls" not in onboard_github.writes()


def test_a_confirmed_run_starts_the_pass_of_an_index_that_is_not_current(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    onboard_github.qdrant.collections.clear()
    onboard_github.processes.answer(
        lambda call: "ls-remote" in call.argv, ProcessAnswer(returncode=1, stderr="no remote")
    )

    report = _run(onboard_github, confirm=True, only=frozenset({15}))

    started = onboard_github.calls("ls-remote")
    assert [call.argv[-2] for call in started] == [f"https://github.com/{REPO}.git"]
    assert (_row(report, 15).state, report.failing) == (RowState.FAILED, False)
