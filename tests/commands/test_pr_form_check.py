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
    for name in ("type/feature", "scope/pr", "scope/ai", "type/docs", "scope/spec")
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


CLOSING_ISSUE = json.dumps(
    {
        "data": {
            "repository": {
                "pullRequest": {
                    "closingIssuesReferences": {
                        "totalCount": 1,
                        "nodes": [
                            {
                                "number": 3198,
                                "state": "OPEN",
                                "repository": {"nameWithOwner": REPO},
                                "labels": {"nodes": []},
                            }
                        ],
                    }
                }
            }
        }
    }
)


@pytest.fixture(autouse=True)
def labels(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The labels file of the repository, which plans with OpenSpec, and the pull request that
    `PULL` names. `tests/commands/test_pr_other_repository.py` holds a repository without
    OpenSpec (#3767)."""
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    roadmap_store.seed_file("openspec/config.yaml", "schema: spec-driven\n")
    roadmap_store.seed_issue("feat(pr): a pull request", pull_request=True)
    return roadmap_store


@pytest.fixture(autouse=True)
def gh(gh_edge: ProcessFake) -> ProcessFake:
    """gh, which opens the pull request and finds that it closes no issue. The Status and the
    labels of an opened pull request are held by their own tests."""
    gh_edge.answer(["gh", "pr", "create"], ProcessAnswer(stdout=PULL))
    gh_edge.answer(mentions("closingIssuesReferences"), ProcessAnswer(stdout=CLOSING_ISSUE))
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


PLAN_TITLE = "docs(spec): plan #3236 revise scope to role tools"
PLAN_BODY = (
    "The plan audits the job-role tools and names the follow-up for the rest of the tools.\n\n"
    "Plans #3236\n\n"
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


def test_pr_create_reads_body_file_and_short_flag(
    runner: CliRunner, gh: ProcessFake, tmp_path: Path
) -> None:
    """`pr create --body-file` and `-F` read UTF-8 file text and pass it via `--body`."""
    set_dry_run(True)
    body_path = tmp_path / "body.md"
    body_path.write_text(BODY, encoding="utf-8")

    res_long = runner.invoke(
        app, ["create", "--title", TITLE, "--body-file", str(body_path), "--repo", REPO]
    )
    res_short = runner.invoke(
        app, ["create", "--title", TITLE, "-F", str(body_path), "--repo", REPO]
    )

    assert res_long.exit_code == 0
    assert res_short.exit_code == 0
    assert gh.calls == []
    assert "--body" in res_long.stdout
    assert "A title or a body" in res_long.stdout


def test_pr_create_reads_body_file_from_stdin(runner: CliRunner, gh: ProcessFake) -> None:
    """`pr create --body-file -` reads the PR body from standard input."""
    set_dry_run(True)
    res = runner.invoke(
        app,
        ["create", "--title", TITLE, "--body-file", "-", "--repo", REPO],
        input=BODY,
    )

    assert res.exit_code == 0
    assert gh.calls == []
    assert "Closes #3198" in res.stdout


def test_pr_create_rejects_body_and_body_file_together(
    runner: CliRunner, gh: ProcessFake, tmp_path: Path
) -> None:
    """`pr create` exits 2 and names both options when `--body` and `--body-file` are given."""
    body_path = tmp_path / "body.md"
    body_path.write_text(BODY, encoding="utf-8")

    res = runner.invoke(
        app,
        ["create", "--title", TITLE, "--body", "text", "--body-file", str(body_path), "--dry-run"],
    )

    assert res.exit_code == 2
    assert "--body" in res.output
    assert "--body-file" in res.output
    assert gh.calls == []


def test_pr_create_missing_body_file_exits_2(
    runner: CliRunner, gh: ProcessFake, tmp_path: Path
) -> None:
    """`pr create --body-file missing` exits 2 and names `--body-file`."""
    missing = tmp_path / "missing.md"
    res = runner.invoke(app, ["create", "--title", TITLE, "--body-file", str(missing), "--dry-run"])

    assert res.exit_code == 2
    assert "--body-file" in res.output
    assert gh.calls == []


def test_pr_create_applies_length_and_template_checks_to_body_file(
    runner: CliRunner, gh: ProcessFake, tmp_path: Path
) -> None:
    """`pr create` refuses oversized and template-placeholder bodies read from `--body-file`."""
    oversized = tmp_path / "long.md"
    oversized.write_text(
        "a" * 1001
        + "\n\nCloses #3198\n\nChange: `openspec/changes/archive/2026-11-02-3198-pull-request-form/`",
        encoding="utf-8",
    )
    res_long = runner.invoke(
        app, ["create", "--title", TITLE, "--body-file", str(oversized), "--repo", REPO]
    )
    assert res_long.exit_code == 1
    assert "1,000" in res_long.stderr or "1000" in res_long.stderr

    placeholder = tmp_path / "placeholder.md"
    placeholder.write_text(
        "Summary of the pull request.\n\n<!-- placeholder comment -->\n\nCloses #3198\n\nChange: `openspec/changes/archive/2026-11-02-3198-pull-request-form/`",
        encoding="utf-8",
    )
    res_tpl = runner.invoke(
        app, ["create", "--title", TITLE, "--body-file", str(placeholder), "--repo", REPO]
    )
    assert res_tpl.exit_code == 1
    assert gh.calls == []


def test_a_scope_declared_only_on_head_is_accepted(
    runner: CliRunner, labels: InMemoryRoadmapStore
) -> None:
    """With `--repo` and `--head`, a scope declared only on the head ref opens the draft (#6469)."""
    labels.seed_file(
        ".github/labels.yml",
        LABELS + '- name: "scope/tools"\n  color: "ededed"\n',
        ref="feat/tools",
    )
    result, gh = _create(runner, "feat(tools): add tool", BODY, "--head", "feat/tools")
    assert (result.exit_code, len(gh), result.stderr) == (0, 1, "")


def test_a_scope_declared_on_head_without_base_labels_file_is_accepted(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore
) -> None:
    """When `--base` has no `.github/labels.yml` yet, `--head`'s file still validates (#6469)."""
    roadmap_store.seed_file(
        ".github/labels.yml",
        LABELS + '- name: "scope/tools"\n  color: "ededed"\n',
        ref="feat/onboard",
    )
    roadmap_store.seed_file("openspec/config.yaml", "schema: spec-driven\n", ref="b")
    result, gh = _create(
        runner, "feat(tools): onboard", BODY, "--base", "b", "--head", "feat/onboard"
    )
    assert (result.exit_code, len(gh), result.stderr) == (0, 1, "")


def test_a_scope_declared_only_on_base_is_accepted_with_head(
    runner: CliRunner, labels: InMemoryRoadmapStore
) -> None:
    """With `--repo` and `--head`, a scope declared only on the base ref still passes (#6469)."""
    labels.seed_file(
        ".github/labels.yml", '- name: "type/feature"\n  color: "ededed"\n', ref="feat/x"
    )
    result, gh = _create(runner, TITLE, BODY, "--head", "feat/x")
    assert (result.exit_code, len(gh), result.stderr) == (0, 1, "")


@pytest.mark.parametrize(
    ("base_args", "expected_base"),
    [
        (["--base", "main"], "`main`"),
        ([], "the default branch"),
    ],
)
def test_refusal_with_repo_and_head_names_both_refs(
    runner: CliRunner,
    labels: InMemoryRoadmapStore,
    base_args: list[str],
    expected_base: str,
) -> None:
    """When neither base nor head declares the scope, the refusal names both refs (#6469)."""
    labels.seed_file(".github/labels.yml", LABELS, ref="main")
    labels.seed_file(".github/labels.yml", LABELS, ref="feat/tools")
    result, gh = _create(runner, "feat(tools): add tool", BODY, *base_args, "--head", "feat/tools")
    assert (result.exit_code, len(gh)) == (1, 0)
    assert ".github/labels.yml" in result.stderr
    assert expected_base in result.stderr
    assert "`feat/tools`" in result.stderr
    assert "`scope/tools`" in result.stderr
    assert "declare the label in the same pull request" in result.stderr


def test_refusal_with_repo_and_no_head_names_base_ref_only(
    runner: CliRunner, labels: InMemoryRoadmapStore
) -> None:
    """With `--repo` and no `--head`, the refusal names the base ref only (#6469)."""
    labels.seed_file(".github/labels.yml", LABELS, ref="main")
    result, gh = _create(runner, "feat(tools): add tool", BODY, "--base", "main")
    assert (result.exit_code, len(gh)) == (1, 0)
    assert ".github/labels.yml on `main` does not declare `scope/tools`" in result.stderr
    assert "declare the label in the same pull request" in result.stderr


def test_refusal_in_checkout_mode_keeps_checkout_message(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gh: ProcessFake
) -> None:
    """With no `--repo`, checkout mode keeps the unqualified `.github/labels.yml` message (#6469)."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "labels.yml").write_text(LABELS, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    answer_origin(gh, REPO)
    result = runner.invoke(app, ["create", "--title", "feat(tools): add tool", "--body", BODY])
    assert result.exit_code == 1
    assert (
        "The scope `tools` has no label: .github/labels.yml does not declare `scope/tools`. "
        "Use a scope with a label, or declare the label in the same pull request."
    ) in result.stderr


def test_head_malformed_labels_yml_stops_with_file_error(
    runner: CliRunner, labels: InMemoryRoadmapStore
) -> None:
    """Malformed `.github/labels.yml` on `--head` stops creation rather than being ignored (#6469)."""
    labels.seed_file(".github/labels.yml", "not: a list\n", ref="feat/broken")
    result, gh = _create(runner, TITLE, BODY, "--head", "feat/broken")
    assert (result.exit_code, len(gh), ".github/labels.yml" in result.stderr) == (1, 0, True)
