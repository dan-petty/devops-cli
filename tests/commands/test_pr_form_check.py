"""`devops pr create` checks the title and the body with the rules of `pull_form` (#3198).

A pull request that breaks the form is not opened: the command exits 1 before it sends the create
request, and prints every problem to stderr. A pull request in the form still opens as a draft.
No case reaches GitHub or runs `gh`: the labels file is in the in-memory roadmap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.core.process import get_process_runner
from devops_cli.dry_run.state import set_dry_run
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.gh_process import answer_origin, gh_argv, mentions

REPO = "example/roadmap"
LABELS = "".join(
    f'- name: "{name}"\n  color: "ededed"\n'
    for name in ("type/feature", "scope/pr", "scope/ai", "type/docs", "scope/openspec")
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


NO_CLOSING_ISSUES = json.dumps(
    {
        "data": {
            "repository": {
                "pullRequest": {"closingIssuesReferences": {"totalCount": 0, "nodes": []}}
            }
        }
    }
)


@pytest.fixture(autouse=True)
def labels(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The labels file of the repository, and the pull request that `PULL` names."""
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    roadmap_store.seed_issue("feat(pr): a pull request", pull_request=True)
    return roadmap_store


@pytest.fixture(autouse=True)
def gh(gh_edge: ProcessFake) -> ProcessFake:
    """gh, which opens the pull request and finds that it closes no issue. The Status and the
    labels of an opened pull request are held by their own tests."""
    gh_edge.answer(["gh", "pr", "create"], ProcessAnswer(stdout=PULL))
    gh_edge.answer(mentions("closingIssuesReferences"), ProcessAnswer(stdout=NO_CLOSING_ISSUES))
    return gh_edge


def _create(runner: CliRunner, title: str, body: str, *args: str) -> tuple[Any, list[list[str]]]:
    """Run `devops pr create` and return the result and the `gh` commands it sent that are no read
    of the closing issues."""
    result = runner.invoke(app, ["create", "--title", title, "--body", body, "--repo", REPO, *args])
    sent = [
        argv
        for argv in gh_argv(get_process_runner())  # type: ignore[arg-type]
        if not any("closingIssuesReferences" in a for a in argv)
    ]
    return result, sent


def test_a_title_and_a_body_in_the_form_open_a_draft(runner: CliRunner) -> None:
    result, gh = _create(runner, TITLE, BODY)
    args = gh[0]
    assert (result.exit_code, len(gh), "--draft" in args, result.stderr) == (0, 1, True, "")


def test_the_attribution_lines_after_the_change_line_are_accepted(runner: CliRunner) -> None:
    body = f"{BODY}\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    result, gh = _create(runner, TITLE, body)
    assert (result.exit_code, len(gh)) == (0, 1)


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
    assert (result.exit_code, len(gh), fragment in result.stderr) == (1, 0, True)


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
    assert (result.exit_code, len(gh), ".github/labels.yml" in result.stderr) == (1, 0, True)


def test_the_labels_file_of_the_base_branch_decides_the_scope(
    runner: CliRunner, labels: InMemoryRoadmapStore
) -> None:
    labels.seed_file(".github/labels.yml", '- name: "type/feature"\n  color: "ededed"\n', ref="b")
    result, gh = _create(runner, TITLE, BODY, "--base", "b")
    assert (result.exit_code, len(gh), "`scope/pr`" in result.stderr) == (1, 0, True)


def test_a_scope_that_only_the_checkout_declares_is_accepted(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gh: ProcessFake
) -> None:
    """A pull request that adds a scope also adds its label (CONTRIBUTING.md, section 4)."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "labels.yml").write_text(
        LABELS + '- name: "scope/newscope"\n  color: "ededed"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    answer_origin(gh, REPO)
    result = runner.invoke(
        app, ["create", "--title", "feat(newscope): add the scope", "--body", BODY]
    )
    assert (result.exit_code, len(gh_argv(gh))) == (0, 2)


def test_the_fallback_is_not_reached_by_a_pull_request_that_is_refused(
    runner: CliRunner, gh: ProcessFake
) -> None:
    result, sent = _create(runner, "A plain title", BODY)
    assert (result.exit_code, len(sent), gh.calls) == (1, 0, [])


def test_a_dry_run_checks_the_form_without_a_request(
    runner: CliRunner, gh: ProcessFake, roadmap_store_repos: list[str]
) -> None:
    set_dry_run(True)
    result = runner.invoke(
        app, ["create", "--title", "A plain title", "--body", BODY, "--repo", REPO]
    )
    assert (result.exit_code, gh.calls, roadmap_store_repos) == (1, [], [])
    assert "is not in the form" in result.stderr


def test_a_title_with_a_byte_that_is_no_utf8_gets_the_form_report_and_no_traceback(
    runner: CliRunner,
) -> None:
    """argv holds a byte that is no UTF-8 as a lone surrogate, which counts as one unit (#3249)."""
    result, gh = _create(runner, "fix(pr): " + "\udcff" * 61, BODY)

    assert (result.exit_code, len(gh)) == (1, 0)
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "The summary has 61 characters" in result.stderr


def test_a_dry_run_of_a_pull_request_in_the_form_still_lists_its_requests(
    runner: CliRunner, gh: ProcessFake, roadmap_store_repos: list[str]
) -> None:
    set_dry_run(True)
    result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY, "--repo", REPO])
    assert (result.exit_code, gh.calls, roadmap_store_repos, "labels.yml" in result.stdout) == (
        0,
        [],
        [],
        True,
    )


PLAN_TITLE = "docs(openspec): plan #3236 revise scope to role tools"
PLAN_BODY = (
    "Plans #3236\n\n"
    "The plan audits the job-role tools and names the follow-up for the rest of the tools.\n\n"
    "Change: `openspec/changes/3236-read-only-tools-take-paths-that/`"
)


def test_a_plan_with_a_plans_line_opens_a_draft(runner: CliRunner) -> None:
    """A plan closes no issue, so its body has `Plans #<issue>` and no `Closes` line (#3314)."""
    result, gh = _create(runner, PLAN_TITLE, PLAN_BODY)
    assert (result.exit_code, len(gh)) == (0, 1)


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        (PLAN_BODY.replace("Plans #3236", "Closes #3236"), "single line `Plans #3236`"),
        (PLAN_BODY.replace("Plans #3236", "Plans #3236\nCloses #3236"), "closes no issue"),
        (PLAN_BODY.replace("Plans #3236", "Plans #9"), "single line `Plans #3236`"),
        (PLAN_BODY.replace("3236-read", "9-read"), "names issue 9"),
    ],
)
def test_a_plan_body_that_breaks_the_plan_form_opens_nothing(
    runner: CliRunner, body: str, fragment: str
) -> None:
    result, gh = _create(runner, PLAN_TITLE, body)
    assert (result.exit_code, len(gh), fragment in result.stderr) == (1, 0, True)


def test_a_delivery_title_still_needs_a_closes_line(runner: CliRunner) -> None:
    result, gh = _create(runner, TITLE, PLAN_BODY)
    assert (result.exit_code, len(gh), "no line `Closes" in result.stderr) == (1, 0, True)
