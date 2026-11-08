"""The labels that the Conventional Commit title of a pull request gives (#2748).

`devops pr create` adds them with the rule of intake (#2715). No case reaches GitHub or runs `gh`:
the labels file and the pull request are in the in-memory roadmap.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.core.process import get_process_runner
from devops_cli.dry_run.state import set_dry_run
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.stores.store import ChangeKind
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.gh_process import answer_gh, gh_argv, mentions

REPO = "example/roadmap"
LABELS_PATH = ".github/labels.yml"

DECLARED = ("type/bug", "type/docs", "type/feature", "scope/ai", "scope/security")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("fix(ai): a title", ("type/bug", "scope/ai", None)),
        ("feat(security)!: a title", ("type/feature", "scope/security", None)),
        ("docs: a title", ("type/docs", None, None)),
        ("A plain title", (None, None, None)),
        ("fix(zzz-unknown): a title", ("type/bug", None, "scope/zzz-unknown")),
        ("chore(ai): a title", (None, "scope/ai", None)),
    ],
)
def test_the_title_gives_the_declared_labels(
    title: str, expected: tuple[str | None, str | None, str | None]
) -> None:
    from devops_cli.roadmap.title_labels import TitleLabels, title_labels

    assert title_labels(title, DECLARED) == TitleLabels(*expected)


def test_the_labels_of_a_title_are_its_type_then_its_scope() -> None:
    from devops_cli.roadmap.title_labels import title_labels

    assert title_labels("fix(ai): a title", DECLARED).labels == ("type/bug", "scope/ai")


def test_the_declared_names_come_from_the_labels_file() -> None:
    from devops_cli.roadmap.title_labels import declared_label_names

    text = '- name: "type/bug"\n  color: "d73a4a"\n- name: "scope/ai"\n  color: "0e8a16"\n'
    assert declared_label_names(text) == ("type/bug", "scope/ai")


# ── devops pr create ───────────────────────────────────────────────────────────

LABELS_FILE = "".join(f'- name: "{name}"\n  color: "ededed"\n' for name in DECLARED)
PULL = "https://example.com/org/repo/pull/1\n"
# A body in the form (#3198): `devops pr create` refuses every other.
BODY = (
    "The command gives the labels of the title to the pull request it opens.\n\n"
    "Closes #2748\n\nChange: `openspec/changes/archive/2026-11-02-2748-title-labels/`"
)


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
def status(gh_edge: ProcessFake) -> ProcessFake:
    """gh, which answers `pr create` with a pull request URL and the read of the issues a pull
    request closes with none: the write of the Status (#2717) is held by
    tests/commands/test_pr_status.py. The fixture returns the fake, for the cases that count the
    reads."""
    gh_edge.answer(["gh", "pr", "create"], ProcessAnswer(stdout=PULL))
    gh_edge.answer(mentions("closingIssuesReferences"), ProcessAnswer(stdout=NO_CLOSING_ISSUES))
    return gh_edge


def _status_reads(gh: ProcessFake) -> list[str]:
    """The pull requests whose closing issues were read to set a Status, in order."""
    return [
        arg.removeprefix("number=")
        for argv in gh_argv(gh)
        for arg in argv
        if arg.startswith("number=") and any("closingIssuesReferences" in a for a in argv)
    ]


@pytest.fixture
def pull(roadmap_store: InMemoryRoadmapStore) -> int:
    """Pull request 1 of the in-memory repository, which declares `DECLARED` on its default
    branch."""
    roadmap_store.seed_file(LABELS_PATH, LABELS_FILE)
    return roadmap_store.seed_issue("fix(ai): a title", pull_request=True)


def _labeled(roadmap: InMemoryRoadmapStore) -> set[tuple[int, str | None]]:
    since = datetime(1970, 1, 1, tzinfo=UTC)
    return {
        (change.number, change.label)
        for change in roadmap.changes_since(since)
        if change.kind is ChangeKind.LABELED
    }


def _create(runner: CliRunner, title: str, *args: str) -> tuple[Any, list[list[str]]]:
    """Run `devops pr create` and return the result and the `gh` commands it sent that are no read
    of the closing issues."""
    result = runner.invoke(app, ["create", "--title", title, "--body", BODY, "--repo", REPO, *args])
    gh = get_process_runner()
    sent = [
        ["gh", *argv]
        for argv in gh_argv(gh)  # type: ignore[arg-type]
        if not any("closingIssuesReferences" in a for a in argv)
    ]
    return result, sent


@pytest.mark.usefixtures("status")
@pytest.mark.parametrize(
    ("title", "labels"),
    [
        ("fix(ai): a title", {"type/bug", "scope/ai"}),
        ("docs: a title", {"type/docs"}),
    ],
)
def test_create_gives_the_pull_request_the_labels_of_its_title(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int, title: str, labels: set[str]
) -> None:
    result, gh = _create(runner, title)
    assert (
        result.exit_code,
        _labeled(roadmap_store),
        "warning" in result.output.lower(),
        len(gh),
    ) == (0, {(pull, label) for label in labels}, False, 1)


@pytest.mark.usefixtures("status")
def test_create_reads_the_labels_file_on_the_base_branch(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int
) -> None:
    on_base = '- name: "scope/ai"\n  color: "ededed"\n'
    roadmap_store.seed_file(LABELS_PATH, on_base, ref="feat/base")
    result, _ = _create(runner, "docs(ai): a title", "--base", "feat/base")
    assert (result.exit_code, _labeled(roadmap_store)) == (0, {(pull, "scope/ai")})


@pytest.mark.usefixtures("status")
def test_a_scope_with_no_declared_label_opens_nothing_and_names_the_label(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int
) -> None:
    result, gh = _create(runner, "fix(zzz-unknown): a title")
    assert (
        result.exit_code,
        len(gh),
        _labeled(roadmap_store),
        "scope/zzz-unknown" in result.stderr,
        LABELS_PATH in result.stderr,
        "scope/zzz-unknown" in result.stdout,
    ) == (1, 0, set(), True, True, False)


@pytest.mark.usefixtures("status")
def test_a_refused_label_exits_1_names_it_and_leaves_the_pull_request(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int
) -> None:
    roadmap_store.fail_write(write="label_issue", error=GitHubOperationError("HTTP 422"))
    result, gh = _create(runner, "fix(ai): a title")
    commands = [argv[:3] for argv in gh]
    assert (
        result.exit_code,
        "pull/1" in result.output or "#1" in result.output,
        "type/bug" in result.output,
        "HTTP 422" in result.output,
        f"repos/{REPO}/issues/{pull}/labels" in result.output,
        _labeled(roadmap_store),
        commands,
    ) == (1, True, True, True, True, {(pull, "scope/ai")}, [["gh", "pr", "create"]])


@pytest.mark.usefixtures("pull")
@pytest.mark.parametrize(
    "text", [None, "not: a list of label specs"], ids=["missing", "unreadable"]
)
def test_a_labels_file_that_is_missing_or_unreadable_opens_nothing_and_names_the_file(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, status: ProcessFake, text: str | None
) -> None:
    if text is not None:
        roadmap_store.seed_file(LABELS_PATH, text, ref="feat/other")
    result, gh = _create(runner, "fix(ai): a title", "--base", "feat/other")
    assert (
        result.exit_code,
        len(gh),
        LABELS_PATH in result.stderr,
        _labeled(roadmap_store),
        len(_status_reads(status)),
    ) == (1, 0, True, set(), 0)


def test_the_status_is_set_when_a_label_is_refused(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int, status: ProcessFake
) -> None:
    roadmap_store.fail_write(write="label_issue", error=GitHubOperationError("HTTP 502"))
    result, _ = _create(runner, "fix(ai): a title")
    assert (result.exit_code, _status_reads(status)) == (1, [str(pull)])


def test_create_exits_1_and_names_pull_request_when_label_issue_unauthenticated(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int, status: ProcessFake
) -> None:
    from devops_cli.exceptions.git import GitHubUnauthenticatedError

    roadmap_store.fail_write(write="label_issue", error=GitHubUnauthenticatedError("bad token"))
    result, _ = _create(runner, "fix(ai): a title")
    assert result.exit_code == 1
    assert f"#{pull}" in result.stderr


@pytest.mark.usefixtures("status")
def test_the_rest_fallback_gives_the_labels_too(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int, status: ProcessFake
) -> None:
    created = {"number": pull, "html_url": "https://example.com/org/repo/pull/1"}
    status.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="fix/x\n"))
    answer_gh(status, "pr", "create", returncode=1, stderr="GraphQL: the query failed")
    status.answer(mentions("pulls?head="), ProcessAnswer(stdout="[]"))
    status.answer(
        mentions(f"repos/{REPO}/pulls", "title="), ProcessAnswer(stdout=json.dumps(created))
    )
    status.answer(["gh", "api", f"repos/{REPO}"], ProcessAnswer(stdout='{"default_branch": "m"}'))
    result = runner.invoke(
        app, ["create", "--title", "fix(ai): a title", "--body", BODY, "--repo", REPO]
    )
    assert (result.exit_code, _labeled(roadmap_store)) == (
        0,
        {(pull, "type/bug"), (pull, "scope/ai")},
    )


@pytest.mark.usefixtures("status")
@pytest.mark.parametrize("title", ["fix(ai): a title", "feat(security): a title"])
def test_the_audit_finds_no_mismatch_after_create(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int, title: str
) -> None:
    from devops_cli.github.labels import audit_repository_labels

    result, _ = _create(runner, title)
    held = [{"name": label} for number, label in sorted(_labeled(roadmap_store)) if number == pull]
    findings = audit_repository_labels([{"number": pull, "title": title, "labels": held}])
    assert (result.exit_code, findings) == (0, [])


def test_a_dry_run_reads_no_label_file_and_adds_no_label(
    runner: CliRunner,
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    status: ProcessFake,
) -> None:
    set_dry_run(True)
    result = runner.invoke(
        app, ["create", "--title", "fix(ai): a title", "--body", BODY, "--repo", REPO]
    )
    assert (result.exit_code, roadmap_store_repos, _labeled(roadmap_store), status.calls) == (
        0,
        [],
        set(),
        [],
    )


def test_a_dry_run_lists_the_label_requests_of_the_title(
    runner: CliRunner, roadmap_store_repos: list[str]
) -> None:
    set_dry_run(True)
    result = runner.invoke(
        app,
        [
            "create",
            "--title",
            "fix(ai): a title",
            "--body",
            BODY,
            "--repo",
            REPO,
            "--base",
            "feat/base",
        ],
    )
    lines = result.stdout.splitlines()
    assert (result.exit_code, roadmap_store_repos) == (0, [])
    assert [
        any(f"repos/{REPO}/contents/.github/labels.yml?ref=feat%2Fbase" in line for line in lines),
        any(
            f"repos/{REPO}/issues/<number>/labels" in line and "type/bug" in line for line in lines
        ),
        any(
            f"repos/{REPO}/issues/<number>/labels" in line and "scope/ai" in line for line in lines
        ),
        any("placeholder" in line for line in lines),
    ] == [True, True, True, True]


def test_labels_file_declares_scope_git() -> None:
    """The repository's .github/labels.yml declares scope/git (#2800)."""
    import yaml

    from tests.support.paths import REPO_ROOT

    text = (REPO_ROOT / ".github" / "labels.yml").read_text(encoding="utf-8")
    labels = yaml.safe_load(text)
    git_labels = [
        label for label in labels if isinstance(label, dict) and label.get("name") == "scope/git"
    ]
    assert len(git_labels) == 1
    assert git_labels[0]["color"] == "24292E"
    assert git_labels[0]["description"] != ""


@pytest.mark.usefixtures("status")
def test_a_title_with_git_scope_gets_the_scope_git_label(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, status: ProcessFake
) -> None:
    """A PR whose title scope is git receives scope/git when declared (#2800)."""
    from tests.support.paths import REPO_ROOT

    text = (REPO_ROOT / ".github" / "labels.yml").read_text(encoding="utf-8")
    roadmap_store.seed_file(LABELS_PATH, text)
    pull = roadmap_store.seed_issue("test(git): example", pull_request=True)
    result, _ = _create(runner, "test(git): example")
    assert (
        result.exit_code,
        "does not declare scope/git" in result.output,
        _labeled(roadmap_store),
    ) == (0, False, {(pull, "type/test"), (pull, "scope/git")})
