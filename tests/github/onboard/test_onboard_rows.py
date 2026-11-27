"""The rows of `devops repos onboard` over one repository of a fake GitHub (#6773)."""

from __future__ import annotations

import copy
import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import CONST_OPENSPEC_CONFIG_PATH
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.onboard import model
from devops_cli.github.onboard.drift import DriftState, drift_counts
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
    REPOSITORY_SETTINGS,
    RULESET,
    TEMPLATE_BRANCH,
    TEMPLATE_TAG,
    WEBHOOK_URL,
    OnboardHarness,
    baseline_settings,
    serve_template,
)

P = RowState.PRESENT
# The settings file of a repository, and the App ID of GitHub Actions in a required check.
_SETTINGS_FILE = "github/repository.yaml"
_ACTIONS = 15368


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


def _forget_hook_secret(harness: OnboardHarness) -> None:
    """The keyring map with no secret of REPO, as a workstation that holds no cluster values has
    it."""
    harness.keyring.values["service_webhook_secrets"] = json.dumps({})


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
        16: RowState.WAITING,
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
    assert _row(second, 16).state is P
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
    assert _row(report, 16).state is P


def test_a_plan_with_an_invalid_openspec_row_reports_drift(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    tree = onboard_github.state.commits[onboard_github.state.refs["main"]]
    tree[CONST_OPENSPEC_CONFIG_PATH] = "schema: another\n"

    report = _run(onboard_github)

    assert _row(report, 16).state is RowState.INVALID
    counts = drift_counts(report)
    assert counts.drift == 1
    assert counts.not_readable == 0
    assert counts.state is DriftState.DRIFT


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


def test_the_deploy_reads_the_tree_that_the_row_checked(
    onboard_github: OnboardHarness, infra_checkout: Path
) -> None:
    _run(onboard_github, confirm=True)

    deploys = [*onboard_github.calls("push-secrets"), *onboard_github.calls("deploy-stack")]
    assert [call.argv[-2:] for call in deploys] == [("--k8s-dir", str(infra_checkout))] * 2


def _in_infra(infra_checkout: Path, *prefix: str) -> Any:
    """A matcher of the git commands that run in the infra checkout."""
    return lambda call: call.cwd == infra_checkout.parent and call.argv[: len(prefix)] == prefix


def _in_workdir(harness: OnboardHarness, *prefix: str) -> Any:
    """A matcher of the git commands that run in the checkout of devops-cli."""
    return lambda call: call.cwd == harness.workdir and call.argv[: len(prefix)] == prefix


@pytest.mark.parametrize(
    ("command", "answer", "reason"),
    [
        (("git", "status"), ProcessAnswer(stdout=" M k8s/a.yaml\n"), "has 1 changed files"),
        (("git", "status"), ProcessAnswer(returncode=128), "git status failed"),
        (("git", "fetch"), ProcessAnswer(returncode=128), "git fetch origin main failed"),
        (("git", "rev-parse", "HEAD"), ProcessAnswer(stdout="f" * 40), "HEAD is not origin/main"),
    ],
    ids=["dirty", "broken", "unreachable", "stale"],
)
def test_a_dirty_or_stale_infra_checkout_refuses_the_service_row(
    onboard_github: OnboardHarness,
    infra_checkout: Path,
    command: tuple[str, ...],
    answer: ProcessAnswer,
    reason: str,
) -> None:
    onboard_github.processes.answer(_in_infra(infra_checkout, *command), answer)

    report = _run(onboard_github, confirm=True)

    row = _row(report, 13)
    assert (row.state, str(infra_checkout) in row.reason, reason in row.reason) == (
        RowState.REFUSED,
        True,
        True,
    ), row.reason
    assert load_settings().service.repos == []
    assert onboard_github.calls("push-secrets") == onboard_github.calls("deploy-stack") == []


@pytest.mark.parametrize(
    ("removed", "named"),
    [
        ("argocd/apps/agents.yaml", "argocd/apps"),
        ("cluster-secrets.toml", "cluster-secrets.toml"),
        ("../.git", "git checkout"),
        ("../.devops/project.toml", "infra.repos"),
    ],
    ids=["no-application", "no-secret-table", "no-checkout", "no-tree"],
)
def test_a_hollow_environment_tree_refuses_the_service_row(
    onboard_github: OnboardHarness, infra_checkout: Path, removed: str, named: str
) -> None:
    path = (infra_checkout / removed).resolve()
    shutil.rmtree(path) if path.is_dir() else path.unlink()

    report = _run(onboard_github, confirm=True)

    row = _row(report, 13)
    assert (row.state, named in row.reason) == (RowState.REFUSED, True), row.reason
    assert onboard_github.calls("push-secrets") == onboard_github.calls("deploy-stack") == []


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


def test_a_secret_write_needs_the_service_row(onboard_github: OnboardHarness, config: Any) -> None:
    _onboarded(onboard_github, config)
    _forget_hook_secret(onboard_github)

    report = _run(onboard_github, confirm=True, only=frozenset({12}))

    row = _row(report, 12)
    assert row.state is RowState.PENDING, render_report(report)
    assert any("secret" in change for change in row.changes)
    assert f"PATCH /repos/{REPO}/hooks/9" not in onboard_github.writes()
    assert json.loads(onboard_github.keyring.values["service_webhook_secrets"]) == {}


def test_a_no_deploy_run_writes_no_hook_secret(onboard_github: OnboardHarness, config: Any) -> None:
    _onboarded(onboard_github, config)
    _forget_hook_secret(onboard_github)

    report = _run(onboard_github, confirm=True, only=frozenset({12, 13}), deploy=False)

    assert _row(report, 12).state is RowState.PENDING
    assert f"PATCH /repos/{REPO}/hooks/9" not in onboard_github.writes()
    assert json.loads(onboard_github.keyring.values["service_webhook_secrets"]) == {}
    assert any("--no-deploy" in step.text for step in report.person_steps)


def test_a_refused_service_row_writes_no_hook_secret(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _forget_hook_secret(onboard_github)
    onboard_github.processes.answer(
        _in_workdir(onboard_github, "git", "status"), ProcessAnswer(stdout=" M src/a.py\n")
    )

    report = _run(onboard_github, confirm=True, only=frozenset({12, 13}))

    assert _row(report, 12).state is RowState.PENDING
    assert _row(report, 13).state is RowState.PRESENT
    assert f"PATCH /repos/{REPO}/hooks/9" not in onboard_github.writes()
    assert any("changed files" in step.text for step in report.person_steps)
    assert onboard_github.calls("deploy-stack") == []


def test_the_service_row_writes_the_secret(onboard_github: OnboardHarness, config: Any) -> None:
    _onboarded(onboard_github, config)
    _forget_hook_secret(onboard_github)

    report = _run(onboard_github, confirm=True, only=frozenset({12, 13}))

    secret = json.loads(onboard_github.keyring.values["service_webhook_secrets"])[REPO]
    assert len(secret) == 64
    assert onboard_github.state.hooks[0]["config"]["secret"] == secret
    assert [write for write in onboard_github.writes() if "hooks" in write] == [
        f"PATCH /repos/{REPO}/hooks/9"
    ]
    assert _row(report, 12).state is RowState.APPLIED


def test_the_deploy_plan_reads_the_checkout_once(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _forget_hook_secret(onboard_github)

    _run(onboard_github, confirm=True, only=frozenset({12, 13}))

    fetches = [
        call
        for call in onboard_github.processes.calls
        if call.argv[:2] == ("git", "fetch") and call.cwd == onboard_github.workdir
    ]
    assert len(fetches) == 1


def test_a_confirm_with_nothing_to_change_starts_no_git(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _forget_hook_secret(onboard_github)
    _run(onboard_github, confirm=True, only=frozenset({12, 13}))
    onboard_github.processes.calls.clear()

    report = _run(onboard_github, confirm=True)

    assert (_row(report, 12).state, _row(report, 13).state) == (P, P)
    assert [call.argv for call in onboard_github.processes.calls if call.argv[:1] == ("git",)] == []


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
    ]
    assert state.rulesets[0]["enforcement"] == "active"
    assert _row(report, 12).state is RowState.PENDING
    assert _row(report, 13).state is RowState.PRESENT
    assert onboard_github.calls("deploy-stack") == []
    assert not any("deploy-stack" in step.text for step in report.person_steps)


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


def test_a_bot_template_pull_request_requests_the_repository_owner(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.state.pull_author = "devops-cli-service[bot]"

    report = _run(onboard_github, confirm=True, only=frozenset({9}))

    assert _row(report, 9).state is RowState.APPLIED, render_report(report)
    assert f"POST /repos/{REPO}/pulls/1/requested_reviewers" in onboard_github.writes()
    assert [entry["login"] for entry in onboard_github.state.pulls[0]["requested_reviewers"]] == [
        "example-org"
    ]


def test_an_owner_template_pull_request_skips_requesting_the_owner(
    onboard_github: OnboardHarness,
) -> None:
    onboard_github.state.pull_author = "example-org"

    report = _run(onboard_github, confirm=True, only=frozenset({9}))

    assert _row(report, 9).state is RowState.APPLIED, render_report(report)
    assert f"POST /repos/{REPO}/pulls/1/requested_reviewers" not in onboard_github.writes()


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


# The merge settings of the baseline, which GitHub gives only to a token with Contents write
# (REST docs, Get a repository).
MERGE_KEYS = sorted(key for key in REPOSITORY_SETTINGS if key != "security_and_analysis")


def _without_merge_settings(harness: OnboardHarness) -> None:
    """The reply of `GET /repos/<repo>` as GitHub gives it to a token without Contents write."""
    for key in MERGE_KEYS:
        del harness.state.payload[key]


def test_a_reply_without_the_merge_settings_makes_row_2_not_readable(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _without_merge_settings(onboard_github)

    report = _run(onboard_github, only=frozenset({2}))

    row = _row(report, 2)
    assert (row.state, row.changes) == (RowState.NOT_READABLE, ()), render_report(report)
    assert len(MERGE_KEYS) == 8
    assert all(key in str(row.reason) for key in MERGE_KEYS), row.reason
    assert [step.document for step in row.steps] == [model.DOC_GET_REPOSITORY]
    assert "Contents write" in row.steps[0].text
    assert f"devops repos onboard {REPO} --plan --only 2" in row.steps[0].text
    assert onboard_github.writes() == []


def test_a_reply_without_the_merge_settings_still_writes_a_known_difference(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _without_merge_settings(onboard_github)
    onboard_github.state.payload["has_issues"] = False

    report = _run(onboard_github, only=frozenset({2}))

    row = _row(report, 2)
    assert (row.state, row.changes) == (RowState.PENDING, ("has_issues: True",)), render_report(
        report
    )
    assert all(key in str(row.reason) for key in MERGE_KEYS), row.reason


def test_a_reply_with_the_merge_settings_of_the_baseline_is_present(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)

    report = _run(onboard_github, only=frozenset({2}))

    assert _row(report, 2).state is P, render_report(report)
    assert _row(report, 2).steps == ()


def test_a_ruleset_reply_without_bypass_actors_makes_row_10_not_readable(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    # GitHub gives bypass_actors only to a token with write access to the ruleset (REST docs,
    # Get a repository ruleset).
    del onboard_github.state.rulesets[0]["bypass_actors"]

    report = _run(onboard_github, only=frozenset({10}))

    row = _row(report, 10)
    assert (row.state, row.changes) == (RowState.NOT_READABLE, ()), render_report(report)
    assert "bypass_actors" in str(row.reason)
    assert [step.document for step in row.steps] == [model.DOC_GET_RULESET]
    assert "write access to the ruleset" in row.steps[0].text
    assert onboard_github.writes() == []


def _declare_checks(harness: OnboardHarness, checks: list[str], **parameters: Any) -> None:
    """The `github/repository.yaml` of the default branch of REPO with a ruleset `main` that
    requires `checks` and sets `parameters`, as a repository declares its own checks in git."""
    settings = baseline_settings(release_flow=True)
    rule = settings["rulesets"][0]["rules"][2]
    rule["parameters"].update(
        parameters,
        required_status_checks=[{"context": name, "integration_id": _ACTIONS} for name in checks],
    )
    harness.state.commits[harness.state.refs["main"]][_SETTINGS_FILE] = yaml.safe_dump(settings)


def test_the_plan_names_the_required_checks_of_the_repository_file(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _declare_checks(onboard_github, ["K8s", "Lint"])

    report = _run(onboard_github, only=frozenset({10}))

    row = _row(report, 10)
    assert (row.state, row.changes) == (
        RowState.PENDING,
        (f"ruleset main: required checks K8s, Lint, {CHECK_NAME}",),
    ), render_report(report)
    assert onboard_github.writes() == []


def test_a_confirmed_run_requires_the_checks_of_the_repository_file(
    onboard_github: OnboardHarness, config: Any
) -> None:
    # The live ruleset requires CHECK_NAME, which the file does not name: the check stays.
    _onboarded(onboard_github, config)
    _declare_checks(onboard_github, ["K8s", "Lint"], strict_required_status_checks_policy=True)

    _run(onboard_github, confirm=True, only=frozenset({10}))

    assert onboard_github.writes() == ["PUT /repos/example-org/app/rulesets/7"]
    assert onboard_github.state.rulesets[0]["rules"][2] == {
        "type": "required_status_checks",
        "parameters": {
            "do_not_enforce_on_create": True,
            "required_status_checks": [
                {"context": "K8s", "integration_id": _ACTIONS},
                {"context": "Lint", "integration_id": _ACTIONS},
                {"context": CHECK_NAME, "integration_id": _ACTIONS},
            ],
            "strict_required_status_checks_policy": True,
        },
    }
    onboard_github.api.sent.clear()

    second = _run(onboard_github, confirm=True, only=frozenset({10}))

    assert (_row(second, 10).state, onboard_github.writes()) == (P, [])


def test_a_baseline_ruleset_with_no_checks_rule_gets_the_rule_of_the_repository_file(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _declare_checks(onboard_github, ["K8s"])
    ruleset = copy.deepcopy(RULESET)
    ruleset["rules"] = ruleset["rules"][:2]
    serve_template(onboard_github.processes, extra={"rulesets": [ruleset]})

    report = _run(onboard_github, only=frozenset({10}))

    row = _row(report, 10)
    assert (row.state, row.changes) == (
        RowState.PENDING,
        (f"ruleset main: required checks K8s, {CHECK_NAME}",),
    ), render_report(report)
    assert onboard_github.writes() == []


def _required_checks(harness: OnboardHarness) -> list[str]:
    """The check names that the live ruleset `main` of REPO requires."""
    rule = next(
        rule
        for rule in harness.state.rulesets[0]["rules"]
        if rule["type"] == "required_status_checks"
    )
    return [entry["context"] for entry in rule["parameters"]["required_status_checks"]]


def test_a_skipped_check_run_is_no_required_check(onboard_github: OnboardHarness) -> None:
    # A reusable-workflow job that skips reports its own name: the ruleset must not require it.
    onboard_github.state.check_runs = [
        {"name": "K8s", "status": "completed", "conclusion": "skipped"},
        {"name": "Lint", "status": "completed", "conclusion": "success"},
    ]

    _run(onboard_github, confirm=True, only=frozenset({9, 10}))

    checks = _required_checks(onboard_github)
    assert "K8s" not in checks
    assert "Lint" in checks


def test_an_unexpanded_matrix_name_is_no_required_check(onboard_github: OnboardHarness) -> None:
    # A skipped matrix job reports its name with the expression unexpanded, and no pull request
    # reports such a name.
    onboard_github.state.check_runs = [
        {
            "name": "Push by digest (${{ matrix.platform }})",
            "status": "completed",
            "conclusion": "success",
        },
        {"name": "Lint", "status": "completed", "conclusion": "success"},
    ]

    _run(onboard_github, confirm=True, only=frozenset({9, 10}))

    assert _required_checks(onboard_github) == ["Lint"]


@pytest.mark.parametrize("leg", ["skipped", "success"], ids=["skipped leg", "passing leg"])
def test_a_matrix_leg_gives_way_to_its_job_name(onboard_github: OnboardHarness, leg: str) -> None:
    onboard_github.state.check_runs = [
        {"name": "Tests & Coverage", "status": "completed", "conclusion": "success"},
        {"name": "Tests & Coverage (shard 1 of 5)", "status": "completed", "conclusion": leg},
    ]

    _run(onboard_github, confirm=True, only=frozenset({9, 10}))

    checks = _required_checks(onboard_github)
    assert "Tests & Coverage" in checks
    assert "Tests & Coverage (shard 1 of 5)" not in checks


def _template_pull(harness: OnboardHarness, *, state: str, merged: bool = False) -> None:
    """A template pull request of REPO in `state` whose head is the default branch head, as a
    pull request that still waits or that a confirmed run merged leaves it."""
    repository = harness.state
    repository.refs[TEMPLATE_BRANCH] = repository.refs["main"]
    repository.pulls.append(
        {
            "number": 1,
            "node_id": "PR_1",
            "state": state,
            "draft": False,
            "merged": merged,
            "auto_merge": None,
            "title": "ci: add the files of the repository template",
            "user": {"login": REPO.partition("/")[0]},
            "requested_reviewers": [],
            "head": {"ref": TEMPLATE_BRANCH, "sha": repository.refs["main"]},
        }
    )


def _require_live_checks(harness: OnboardHarness, checks: list[str]) -> None:
    """Add `checks` to the required checks of the live ruleset `main` of REPO."""
    rule = next(
        rule
        for rule in harness.state.rulesets[0]["rules"]
        if rule["type"] == "required_status_checks"
    )
    rule["parameters"]["required_status_checks"] += [
        {"context": name, "integration_id": _ACTIONS} for name in checks
    ]


def test_a_live_required_check_that_only_skipped_is_dropped(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _template_pull(onboard_github, state="open")
    _require_live_checks(onboard_github, ["K8s"])
    onboard_github.state.check_runs = [
        {"name": "K8s", "status": "completed", "conclusion": "skipped"},
        {"name": CHECK_NAME, "status": "completed", "conclusion": "success"},
    ]

    report = _run(onboard_github, confirm=True, only=frozenset({9, 10}))

    row = _row(report, 10)
    assert row.changes == (f"ruleset main: required checks {CHECK_NAME}; dropped K8s",), (
        render_report(report)
    )
    assert _required_checks(onboard_github) == [CHECK_NAME]


def test_a_live_matrix_leg_gives_way_to_its_job_name(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _template_pull(onboard_github, state="open")
    _require_live_checks(onboard_github, ["Tests & Coverage (shard 1 of 5)"])
    onboard_github.state.check_runs = [
        {"name": "Tests & Coverage", "status": "completed", "conclusion": "success"},
        {"name": CHECK_NAME, "status": "completed", "conclusion": "success"},
    ]

    report = _run(onboard_github, confirm=True, only=frozenset({9, 10}))

    row = _row(report, 10)
    assert row.changes == (
        f"ruleset main: required checks {CHECK_NAME}, Tests & Coverage; "
        "dropped Tests & Coverage (shard 1 of 5)",
    ), render_report(report)
    assert _required_checks(onboard_github) == [CHECK_NAME, "Tests & Coverage"]


def test_a_plan_reports_a_required_check_that_only_skipped(
    onboard_github: OnboardHarness, config: Any
) -> None:
    _onboarded(onboard_github, config)
    _template_pull(onboard_github, state="open")
    _require_live_checks(onboard_github, ["K8s"])
    onboard_github.state.check_runs = [
        {"name": "K8s", "status": "completed", "conclusion": "skipped"},
        {"name": CHECK_NAME, "status": "completed", "conclusion": "success"},
    ]

    report = _run(onboard_github, only=frozenset({9, 10}))

    row = _row(report, 10)
    assert (row.state, row.changes) == (
        RowState.PENDING,
        (f"ruleset main: required checks {CHECK_NAME}; dropped K8s",),
    ), render_report(report)
    assert onboard_github.writes() == []


@pytest.mark.parametrize(
    ("merged", "run", "live"),
    [
        (True, ("Semantic PR title", "success"), []),
        (True, ("K8s", "skipped"), ["K8s"]),
        (False, ("Semantic PR title", "success"), []),
    ],
    ids=["merged-old-check-name", "merged-skipped-live-check", "closed-old-check-name"],
)
def test_a_template_pull_request_that_is_not_open_gives_row_10_no_check(
    onboard_github: OnboardHarness,
    config: Any,
    merged: bool,
    run: tuple[str, str],
    live: list[str],
) -> None:
    # The head of a merged pull request ran the workflows of that time: dan-petty/devtools#99
    # reported `Semantic PR title`, which no workflow reports after the template came back (#7476).
    _onboarded(onboard_github, config)
    _template_pull(onboard_github, state="closed", merged=merged)
    _require_live_checks(onboard_github, live)
    name, conclusion = run
    onboard_github.state.check_runs = [
        {"name": CHECK_NAME, "status": "completed", "conclusion": "success"},
        {"name": name, "status": "completed", "conclusion": conclusion},
    ]

    report = _run(onboard_github, confirm=True, only=frozenset({9, 10}))

    states = _states(report)
    assert (states[9], states[10], onboard_github.writes()) == (P, P, []), render_report(report)
    assert _required_checks(onboard_github) == [CHECK_NAME, *live]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "rulesets: [\n",
            f"Cannot read the config file: {_SETTINGS_FILE} of {REPO} on main is not valid YAML "
            "(ParserError) at line 2, column 1.",
        ),
        (
            "unknown: true\n",
            f"{_SETTINGS_FILE} of {REPO} on main does not match "
            "templates/github-repository.schema.json: Additional properties are not allowed "
            "('unknown' was unexpected)",
        ),
    ],
    ids=["no-yaml", "schema-refuses"],
)
def test_a_repository_file_that_cannot_be_read_makes_row_10_not_readable(
    onboard_github: OnboardHarness, config: Any, text: str, reason: str
) -> None:
    _onboarded(onboard_github, config)
    onboard_github.state.commits[onboard_github.state.refs["main"]][_SETTINGS_FILE] = text

    report = _run(onboard_github, confirm=True, only=frozenset({10}))

    row = _row(report, 10)
    assert (row.state, row.reason) == (RowState.NOT_READABLE, reason), render_report(report)
    assert onboard_github.writes() == []
