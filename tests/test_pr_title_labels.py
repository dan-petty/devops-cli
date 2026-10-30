"""The labels that the Conventional Commit title of a pull request gives (#2748).

`devops pr create` adds them with the rule of intake (#2715). No case reaches GitHub or runs `gh`:
the labels file and the pull request are in the in-memory roadmap.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.core.process import PlannedProcessResult
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ChangeKind
from devops_cli.roadmap.title_labels import TitleLabels, declared_label_names, title_labels

REPO = "example/roadmap"
LABELS_PATH = ".github/labels.yml"

DECLARED = ("type/bug", "type/docs", "type/feature", "scope/ai", "scope/security")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("fix(ai): a title", TitleLabels("type/bug", "scope/ai")),
        ("feat(security)!: a title", TitleLabels("type/feature", "scope/security")),
        ("docs: a title", TitleLabels("type/docs", None)),
        ("A plain title", TitleLabels(None, None)),
        ("fix(zzz-unknown): a title", TitleLabels("type/bug", None, "scope/zzz-unknown")),
        ("chore(ai): a title", TitleLabels(None, "scope/ai")),
    ],
)
def test_the_title_gives_the_declared_labels(title: str, expected: TitleLabels) -> None:
    assert title_labels(title, DECLARED) == expected


def test_the_labels_of_a_title_are_its_type_then_its_scope() -> None:
    assert title_labels("fix(ai): a title", DECLARED).labels == ("type/bug", "scope/ai")


def test_the_declared_names_come_from_the_labels_file() -> None:
    text = '- name: "type/bug"\n  color: "d73a4a"\n- name: "scope/ai"\n  color: "0e8a16"\n'
    assert declared_label_names(text) == ("type/bug", "scope/ai")


# ── devops pr create ───────────────────────────────────────────────────────────

LABELS_FILE = "".join(f'- name: "{name}"\n  color: "ededed"\n' for name in DECLARED)
PULL = "https://example.com/org/repo/pull/1\n"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def status() -> Iterator[MagicMock]:
    """The write of the Status (#2717), which tests/test_pr_status.py holds."""
    with patch("devops_cli.commands.pr.set_delivered_status") as record:
        yield record


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


def _create(runner: CliRunner, title: str, *args: str) -> tuple[Any, MagicMock]:
    gh = MagicMock(return_value=MagicMock(returncode=0, stdout=PULL, stderr=""))
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", gh),
    ):
        return runner.invoke(app, ["create", "--title", title, "--repo", REPO, *args]), gh


@pytest.mark.usefixtures("status")
@pytest.mark.parametrize(
    ("title", "labels"),
    [
        ("fix(ai): a title", {"type/bug", "scope/ai"}),
        ("docs: a title", {"type/docs"}),
        ("A plain title", set()),
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
        gh.call_count,
    ) == (0, {(pull, label) for label in labels}, False, 1)


@pytest.mark.usefixtures("status")
def test_create_reads_the_labels_file_on_the_base_branch(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int
) -> None:
    roadmap_store.seed_file(LABELS_PATH, '- name: "type/bug"\n  color: "ededed"\n', ref="feat/base")
    result, _ = _create(runner, "fix(ai): a title", "--base", "feat/base")
    assert (result.exit_code, _labeled(roadmap_store)) == (0, {(pull, "type/bug")})


@pytest.mark.usefixtures("status")
def test_a_scope_with_no_declared_label_gets_a_warning_and_no_label(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int
) -> None:
    result, _ = _create(runner, "fix(zzz-unknown): a title")
    assert (
        result.exit_code,
        _labeled(roadmap_store),
        "scope/zzz-unknown" in result.output,
        LABELS_PATH in result.output,
    ) == (0, {(pull, "type/bug")}, True, True)


@pytest.mark.usefixtures("status")
def test_a_refused_label_exits_1_names_it_and_leaves_the_pull_request(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int
) -> None:
    add = roadmap_store.label_issue

    def refuse_the_type(number: int, label: str) -> None:
        if label == "type/bug":
            raise GitHubOperationError("HTTP 422")
        add(number, label)

    with patch.object(roadmap_store, "label_issue", side_effect=refuse_the_type):
        result, gh = _create(runner, "fix(ai): a title")
    commands = [call.args[0][:3] for call in gh.call_args_list]
    assert (
        result.exit_code,
        "pull/1" in result.output or "#1" in result.output,
        "type/bug" in result.output,
        "HTTP 422" in result.output,
        _labeled(roadmap_store),
        commands,
    ) == (1, True, True, True, {(pull, "scope/ai")}, [["gh", "pr", "create"]])


@pytest.mark.usefixtures("pull")
@pytest.mark.parametrize(
    "text", [None, "not: a list of label specs"], ids=["missing", "unreadable"]
)
def test_a_labels_file_that_is_missing_or_unreadable_exits_1_and_names_the_file(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, status: MagicMock, text: str | None
) -> None:
    if text is not None:
        roadmap_store.seed_file(LABELS_PATH, text, ref="feat/other")
    result, _ = _create(runner, "fix(ai): a title", "--base", "feat/other")
    assert (
        result.exit_code,
        "#1" in result.output,
        LABELS_PATH in result.output,
        _labeled(roadmap_store),
        status.call_count,
    ) == (1, True, True, set(), 1)


def test_the_status_is_set_when_a_label_is_refused(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int, status: MagicMock
) -> None:
    with patch.object(roadmap_store, "label_issue", side_effect=GitHubOperationError("HTTP 502")):
        result, _ = _create(runner, "fix(ai): a title")
    assert (result.exit_code, status.call_args.args) == (1, (REPO, pull, "In Progress"))


@pytest.mark.usefixtures("status")
def test_the_rest_fallback_gives_the_labels_too(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, pull: int
) -> None:
    created = {"number": pull, "html_url": "https://example.com/org/repo/pull/1"}
    replies = {
        "pr create": MagicMock(returncode=1, stdout="", stderr="GraphQL: rate limit"),
        "pulls?head=": MagicMock(returncode=0, stdout="[]", stderr=""),
        "repos/example/roadmap/pulls -f": MagicMock(returncode=0, stdout=json.dumps(created)),
        "repos/example/roadmap": MagicMock(
            returncode=0, stdout=json.dumps({"default_branch": "m"})
        ),
    }

    def gh(args: list[str], **_: object) -> MagicMock:
        sent = " ".join(args)
        return replies[max((key for key in replies if key in sent), key=len)]

    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr._detect_current_branch", return_value="fix/x"),
        patch("devops_cli.commands.pr.run_gh", side_effect=gh),
    ):
        result = runner.invoke(app, ["create", "--title", "fix(ai): a title", "--repo", REPO])
    assert (result.exit_code, _labeled(roadmap_store)) == (
        0,
        {(pull, "type/bug"), (pull, "scope/ai")},
    )


def test_a_dry_run_reads_no_label_file_and_adds_no_label(
    runner: CliRunner,
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    status: MagicMock,
) -> None:
    planned = PlannedProcessResult(method="gh", argv=("gh", "pr", "create"))
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", return_value=planned),
    ):
        result = runner.invoke(app, ["create", "--title", "fix(ai): a title", "--repo", REPO])
    assert (result.exit_code, roadmap_store_repos, _labeled(roadmap_store), status.call_count) == (
        0,
        [],
        set(),
        0,
    )
