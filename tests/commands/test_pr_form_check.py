"""`devops pr create` checks the title and the body with the rules of `pull_form` (#3198).

A pull request that breaks the form is not opened: the command exits 1 before it sends the create
request, and prints every problem to stderr. A pull request in the form still opens as a draft.
No case reaches GitHub or runs `gh`: the labels file is in the in-memory roadmap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.core.process import PlannedProcessResult
from devops_cli.dry_run.state import set_dry_run
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore

REPO = "example/roadmap"
LABELS = "".join(
    f'- name: "{name}"\n  color: "ededed"\n' for name in ("type/feature", "scope/pr", "scope/ai")
)
TITLE = "feat(pr): check the form of a pull request"
BODY = (
    "A title or a body that breaks the form of the project reads as broken after the merge.\n\n"
    "Closes #3198\n\nChange: `openspec/changes/archive/2026-11-02-3198-pull-request-form/`"
)
PULL = "https://example.com/org/repo/pull/1\n"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def labels(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    return roadmap_store


@pytest.fixture(autouse=True)
def no_writes() -> Any:
    """The Status and the labels of an opened pull request are held by their own tests."""
    with (
        patch("devops_cli.commands.pr.set_delivered_status"),
        patch("devops_cli.commands.pr.pull_labels.add_pull_labels"),
    ):
        yield


def _create(runner: CliRunner, title: str, body: str, *args: str) -> tuple[Any, MagicMock]:
    gh = MagicMock(return_value=MagicMock(returncode=0, stdout=PULL, stderr=""))
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", gh),
    ):
        result = runner.invoke(
            app, ["create", "--title", title, "--body", body, "--repo", REPO, *args]
        )
    return result, gh


def test_a_title_and_a_body_in_the_form_open_a_draft(runner: CliRunner) -> None:
    result, gh = _create(runner, TITLE, BODY)
    args = gh.call_args.args[0]
    assert (result.exit_code, gh.call_count, "--draft" in args, result.stderr) == (0, 1, True, "")


def test_the_attribution_lines_after_the_change_line_are_accepted(runner: CliRunner) -> None:
    body = f"{BODY}\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    result, gh = _create(runner, TITLE, body)
    assert (result.exit_code, gh.call_count) == (0, 1)


@pytest.mark.parametrize(
    ("title", "body", "fragment"),
    [
        ("A plain title", BODY, "is not in the form"),
        (f"feat(pr): {'a' * 61}", BODY, "The limit is 60"),
        ("feat(pr): check the form of a pull re...", BODY, "ends with `...`"),
        ("feat(pr): x", BODY, "placeholder"),
        ("feat(pr)!: check the form", BODY, "Before 1.0.0"),
        ("feat(zzz-unknown): check the form", BODY, "`scope/zzz-unknown`"),
        (TITLE, "", "no line `Closes #<issue>`"),
        (TITLE, "x", "no line `Closes #<issue>`"),
        (TITLE, BODY.replace("Closes #3198\n\n", ""), "no line `Closes"),
        (TITLE, BODY.replace("Change:", "See:"), "no line `Change:`"),
        (TITLE, "placeholder\n\n" + BODY.split("\n\n", 1)[1], "placeholder"),
        (TITLE, BODY.split("\n\n", 1)[1], "has 0 characters"),
        (TITLE, "Co-Authored-By: Claude <x@example.com>\n\n" + BODY, "attribution lines"),
        (TITLE, BODY.replace("Closes #3198", "Closes #3199"), "issue 3199"),
        (TITLE, "<!-- Delete this comment. -->\n\n" + BODY, "template"),
        (TITLE, ("A long reason. " * 80) + "\n\n" + BODY.split("\n\n", 1)[1], "Shorten"),
    ],
)
def test_a_pull_request_that_breaks_the_form_opens_nothing(
    runner: CliRunner, title: str, body: str, fragment: str
) -> None:
    result, gh = _create(runner, title, body)
    assert (result.exit_code, gh.call_count, fragment in result.stderr) == (1, 0, True)


def test_every_problem_is_printed_at_once(runner: CliRunner) -> None:
    result, _ = _create(runner, f"feat(zzz)!: {'a' * 61}", "")
    assert [
        "Before 1.0.0" in result.stderr,
        "`scope/zzz`" in result.stderr,
        "The limit is 60" in result.stderr,
        "no line `Closes" in result.stderr,
        "no line `Change:`" in result.stderr,
    ] == [True] * 5


def test_a_labels_file_that_cannot_be_read_opens_nothing_and_names_the_file(
    runner: CliRunner,
) -> None:
    result, gh = _create(runner, TITLE, BODY, "--base", "feat/other")
    assert (result.exit_code, gh.call_count, ".github/labels.yml" in result.stderr) == (1, 0, True)


def test_the_labels_file_of_the_base_branch_decides_the_scope(
    runner: CliRunner, labels: InMemoryRoadmapStore
) -> None:
    labels.seed_file(".github/labels.yml", '- name: "type/feature"\n  color: "ededed"\n', ref="b")
    result, gh = _create(runner, TITLE, BODY, "--base", "b")
    assert (result.exit_code, gh.call_count, "`scope/pr`" in result.stderr) == (1, 0, True)


def test_a_scope_that_only_the_checkout_declares_is_accepted(
    runner: CliRunner, tmp_path: Path
) -> None:
    """A pull request that adds a scope also adds its label (CONTRIBUTING.md, section 4)."""
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "labels.yml").write_text(
        LABELS + '- name: "scope/newscope"\n  color: "ededed"\n', encoding="utf-8"
    )
    gh = MagicMock(return_value=MagicMock(returncode=0, stdout=PULL, stderr=""))
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", gh),
        patch("devops_cli.commands.pr._checkout", return_value=tmp_path),
        patch("devops_cli.commands.pr._target_repo", return_value=REPO),
    ):
        result = runner.invoke(
            app, ["create", "--title", "feat(newscope): add the scope", "--body", BODY]
        )
    assert (result.exit_code, gh.call_count) == (0, 1)


def test_the_fallback_is_not_reached_by_a_pull_request_that_is_refused(
    runner: CliRunner,
) -> None:
    with patch("devops_cli.commands.pr._fallback_create_pr") as fallback:
        result, gh = _create(runner, "A plain title", BODY)
    assert (result.exit_code, gh.call_count, fallback.call_count) == (1, 0, 0)


def test_a_dry_run_checks_the_form_without_a_request(
    runner: CliRunner, roadmap_store_repos: list[str]
) -> None:
    set_dry_run(True)
    planned = PlannedProcessResult(method="gh", argv=("gh", "pr", "create"))
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", return_value=planned) as gh,
    ):
        result = runner.invoke(
            app, ["create", "--title", "A plain title", "--body", BODY, "--repo", REPO]
        )
    assert (result.exit_code, gh.call_count, roadmap_store_repos) == (1, 0, [])
    assert "is not in the form" in result.stderr


def test_a_dry_run_of_a_pull_request_in_the_form_still_lists_its_requests(
    runner: CliRunner, roadmap_store_repos: list[str]
) -> None:
    set_dry_run(True)
    planned = PlannedProcessResult(method="gh", argv=("gh", "pr", "create"))
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", return_value=planned),
    ):
        result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY, "--repo", REPO])
    assert (result.exit_code, roadmap_store_repos, "labels.yml" in result.stdout) == (0, [], True)
