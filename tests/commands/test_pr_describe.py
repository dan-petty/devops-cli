"""`devops pr describe`: the title and the body of the pull request that delivers an issue (#3198).

No case reaches GitHub or runs `gh`: the issue and the labels file are in the in-memory roadmap,
and the checkout is a temporary directory.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.dry_run.state import set_dry_run
from devops_cli.roadmap.pull_form import body_problems, title_problems
from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"
ISSUE_TITLE = "feat(pr): build and check the title and body of a pull request"
SLUG = "pull-request-form-check"
WHY = "A title or a body that breaks the form of the project reads as broken after the merge."
LABELS = "".join(
    f'- name: "{name}"\n  color: "ededed"\n' for name in ("type/feature", "scope/pr", "scope/ai")
)
PROPOSAL = f"# Proposal\n\n## Why\n\n{WHY}\n\n## What Changes\n\n- A command.\n"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def issue(roadmap_store: InMemoryRoadmapStore) -> int:
    """Issue 1 of the in-memory repository, an item titled `ISSUE_TITLE`, and its labels file."""
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    return roadmap_store.seed_issue(
        ISSUE_TITLE, fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"}
    )


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout with the active change folder of issue 1."""
    (tmp_path / ".git").mkdir()
    folder = tmp_path / "openspec" / "changes" / f"1-{SLUG}"
    folder.mkdir(parents=True)
    (folder / "proposal.md").write_text(PROPOSAL, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _describe(runner: CliRunner, *args: str) -> Any:
    return runner.invoke(app, ["describe", "1", "--repo", REPO, *args])


def _archive(checkout: Path, *, name: str = f"2026-11-02-1-{SLUG}") -> None:
    changes = checkout / "openspec" / "changes"
    (changes / "archive").mkdir()
    (changes / f"1-{SLUG}").rename(changes / "archive" / name)


@pytest.mark.usefixtures("issue", "checkout")
def test_it_prints_the_title_then_the_body_built_from_the_change_folder(
    runner: CliRunner,
) -> None:
    result = _describe(runner, "--summary", "build the form of a pull request")
    today = date.today().isoformat()
    assert (result.exit_code, result.stdout) == (
        0,
        "feat(pr): build the form of a pull request\n\n"
        f"{WHY}\n\nCloses #1\n\n"
        f"Change: `openspec/changes/archive/{today}-1-{SLUG}/`\n",
    )


@pytest.mark.usefixtures("issue")
def test_an_archived_change_names_its_own_folder_and_gets_no_warning(
    runner: CliRunner, checkout: Path
) -> None:
    _archive(checkout)
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert (
        result.exit_code,
        f"Change: `openspec/changes/archive/2026-11-02-1-{SLUG}/`" in result.stdout,
        result.stderr,
    ) == (0, True, "")


@pytest.mark.usefixtures("issue", "checkout")
def test_a_change_that_is_not_archived_says_that_its_date_is_today(runner: CliRunner) -> None:
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert (result.exit_code, date.today().isoformat() in result.stderr) == (0, True)


@pytest.mark.usefixtures("issue", "checkout")
def test_what_it_prints_passes_the_check_of_create(runner: CliRunner) -> None:
    result = _describe(
        runner,
        "--summary",
        "build the form of a pull request",
        "--attribution",
        "Co-Authored-By: Claude <noreply@anthropic.com>",
    )
    title, _, body = result.stdout.rstrip("\n").partition("\n\n")
    declared = ("type/feature", "scope/pr")
    assert (result.exit_code, title_problems(title, declared), body_problems(body)) == (0, [], [])


@pytest.mark.usefixtures("issue", "checkout")
def test_the_attribution_lines_come_after_the_change_line(runner: CliRunner) -> None:
    result = _describe(
        runner,
        "--summary",
        "build the form of a pull request",
        "--attribution",
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "--attribution",
        "Claude-Session: https://claude.ai/code/session_example",
    )
    assert result.stdout.endswith(
        "/`\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n"
        "Claude-Session: https://claude.ai/code/session_example\n"
    )


@pytest.mark.usefixtures("issue", "checkout")
def test_the_why_option_replaces_the_why_of_the_proposal(runner: CliRunner) -> None:
    result = _describe(
        runner, "--summary", "build the form of a pull request", "--why", "A shorter reason, here."
    )
    assert (result.exit_code, "\n\nA shorter reason, here.\n\nCloses #1" in result.stdout) == (
        0,
        True,
    )


@pytest.mark.usefixtures("issue", "checkout")
def test_a_summary_over_60_characters_is_refused_and_nothing_is_printed(
    runner: CliRunner,
) -> None:
    result = _describe(runner, "--summary", "build the form of a pull request " * 3)
    assert (result.exit_code, result.stdout, "The limit is 60" in result.stderr) == (1, "", True)


@pytest.mark.usefixtures("issue", "checkout")
@pytest.mark.parametrize("summary", ["x", "placeholder"])
def test_a_placeholder_summary_is_refused(runner: CliRunner, summary: str) -> None:
    result = _describe(runner, "--summary", summary)
    assert (result.exit_code, result.stdout, "placeholder" in result.stderr) == (1, "", True)


@pytest.mark.usefixtures("checkout")
def test_a_scope_with_no_label_is_refused(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore
) -> None:
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    roadmap_store.seed_issue(
        "feat(zzz-unknown): a change",
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert (result.exit_code, "`scope/zzz-unknown`" in result.stderr) == (1, True)


@pytest.mark.usefixtures("issue", "checkout")
def test_a_why_over_the_limit_is_refused_and_not_cut(runner: CliRunner) -> None:
    result = _describe(
        runner, "--summary", "build the form of a pull request", "--why", "A long reason. " * 80
    )
    assert (result.exit_code, result.stdout, "Shorten the text above" in result.stderr) == (
        1,
        "",
        True,
    )


@pytest.mark.usefixtures("issue")
def test_a_proposal_with_no_why_is_refused(runner: CliRunner, checkout: Path) -> None:
    proposal = checkout / "openspec" / "changes" / f"1-{SLUG}" / "proposal.md"
    proposal.write_text("# Proposal\n\n## What Changes\n\n- A command.\n", encoding="utf-8")
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert (result.exit_code, "has no section `Why`" in result.stderr) == (1, True)


@pytest.mark.usefixtures("issue")
def test_a_why_with_a_closing_keyword_is_refused(runner: CliRunner, checkout: Path) -> None:
    proposal = checkout / "openspec" / "changes" / f"1-{SLUG}" / "proposal.md"
    proposal.write_text("# Proposal\n\n## Why\n\nThis closes #7 for good.\n", encoding="utf-8")
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert (result.exit_code, "closing keyword" in result.stderr) == (1, True)


@pytest.mark.usefixtures("issue", "checkout")
def test_an_issue_with_no_change_folder_is_refused(runner: CliRunner, checkout: Path) -> None:
    (checkout / "openspec" / "changes" / f"1-{SLUG}" / "proposal.md").unlink()
    (checkout / "openspec" / "changes" / f"1-{SLUG}").rmdir()
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert (result.exit_code, "No change folder for issue #1" in result.stderr) == (1, True)


@pytest.mark.usefixtures("checkout")
def test_a_number_that_is_no_item_is_refused(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore
) -> None:
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert (result.exit_code, "Issue #1 is no item of the roadmap" in result.stderr) == (1, True)


@pytest.mark.usefixtures("issue", "checkout")
def test_it_never_ends_a_text_with_an_ellipsis(runner: CliRunner) -> None:
    result = _describe(runner, "--summary", "build the form of a pull request")
    assert "..." not in result.stdout


def test_a_dry_run_lists_the_two_reads_and_opens_no_store(
    runner: CliRunner, roadmap_store_repos: list[str]
) -> None:
    set_dry_run(True)
    result = _describe(runner, "--summary", "build the form of a pull request")
    lines = result.stdout.splitlines()
    assert (result.exit_code, roadmap_store_repos) == (0, [])
    assert [
        any(f"repos/{REPO}/issues/1" in line for line in lines),
        any(f"repos/{REPO}/contents/.github/labels.yml" in line for line in lines),
    ] == [True, True]
