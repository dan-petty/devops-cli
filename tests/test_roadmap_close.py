"""`devops roadmap close` (#743): closure summaries and the automatic release cut.

GitHub is the in-memory roadmap store; check runs come from a fake reader; git is a temporary
clone of a local bare remote, copied per test from one built per module; `gh` is a fake that
records each call. Nothing touches the network.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.release import app as release_app
from devops_cli.commands.roadmap import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.roadmap.close import (
    ClosePlan,
    Cut,
    Hold,
    ShippedClosure,
    apply_close,
    dry_run_close,
    plan_close,
    render_close,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import DEFAULT_DUE_TABLE
from devops_cli.roadmap.store import CloseReason, GitHubState, IssueRecord, MergedPullRequest

REPO = "example/roadmap"
RELEASE = "v0.2.26"
BRANCH = f"release/{RELEASE}"
CUT_BRANCH = f"release/{RELEASE}"
SHIPPED = "v0.2.25"
SHIPPED_BRANCH = f"release/{SHIPPED}"
runner = CliRunner()

CHECKS = CheckVerdictSummary(
    items=[
        PRCheckItem(name="gate", bucket=CheckBucket.PASS),
        PRCheckItem(name="docs", bucket=CheckBucket.SKIPPING),
    ]
)
TASK = """# Task: thing

## Description
Text.

## Acceptance Criteria
- [x] The thing works (`tests/test_thing.py`).
- [x] The other thing holds.

### Pending
- Pending a person: look.

## Decisions
None.
"""


def _checks(_: MergedPullRequest) -> CheckVerdictSummary:
    return CHECKS


@pytest.fixture
def roadmap(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    store = roadmap_store
    store.seed_file(".github/roadmap.toml", "board = 1\n")
    person = store.as_actor("alice")
    person.create_release("v0.2.25", state=GitHubState.CLOSED)
    person.create_release(RELEASE)
    person.create_release("v0.2.27")
    return store


def _issue(store: InMemoryRoadmapStore, title: str, release: str | None = RELEASE) -> int:
    return store.seed_issue(title, release=release, on_board=True)


def _deliver(
    store: InMemoryRoadmapStore,
    number: int,
    *,
    body: str | None = None,
    paths: tuple[str, ...] = ("src/thing.py",),
    task: str | None = None,
    base: str = BRANCH,
) -> MergedPullRequest:
    """Merge a pull request into `base`, the release branch, closing `number`, with its task
    file."""
    paths = (*paths, f"docs/agent/tasks/task-{number}-thing.md") if task else paths
    text = body if body is not None else f"Closes #{number}\n\nAdds the thing.\n\n## Tests\nAll."
    pr = store.merge_pull_request(f"feat: #{number}", base=base, body=text, changed_paths=paths)
    merged = next(p for p in store.merged_pull_requests(base) if p.number == pr)
    if task:
        store.seed_file(f"docs/agent/tasks/task-{number}-thing.md", task, ref=merged.merge_commit)
    return merged


def _plan(store: InMemoryRoadmapStore, checks: Any = _checks) -> ClosePlan:
    return plan_close(store, repo=REPO, checks=checks)


def _run(store: InMemoryRoadmapStore) -> tuple[ClosePlan, list[Cut]]:
    cuts: list[Cut] = []
    plan = _plan(store)
    apply_close(store, plan, cuts.append)
    return plan, cuts


# ── Closure ──


def test_a_merged_pull_request_closes_its_issue_with_a_two_part_comment(
    roadmap: InMemoryRoadmapStore,
) -> None:
    number = _issue(roadmap, "the thing")
    merged = _deliver(roadmap, number, task=TASK)
    _run(roadmap)
    issue = next(i for i in roadmap.issues() if i.number == number)
    (comment,) = roadmap.comments_on(number)
    assert (issue.state, issue.state_reason) == (GitHubState.CLOSED, CloseReason.COMPLETED)
    for expected in (
        "### What changed",
        f"{merged.url}, merged into `{BRANCH}` as {merged.merge_commit}.",
        "> Closes #1\n>\n> Adds the thing.",
        "2 file(s) changed.",
        "### How it was verified",
        f"Check runs at {merged.head_commit}:",
        "- gate: pass\n- docs: skipping",
        f"Acceptance Criteria of `docs/agent/tasks/task-{number}-thing.md`:",
        "- [x] The thing works (`tests/test_thing.py`).\n- [x] The other thing holds.",
        "### Pending\n- Pending a person: look.",
    ):
        assert expected in comment, expected
    assert "## Decisions" not in comment and "## Tests" not in comment


def test_a_pull_request_without_a_task_file_says_so(roadmap: InMemoryRoadmapStore) -> None:
    number = _issue(roadmap, "the thing")
    _deliver(roadmap, number)
    _run(roadmap)
    (comment,) = roadmap.comments_on(number)
    assert ("No task file." in comment, "Acceptance Criteria of" in comment) == (True, False)


@pytest.mark.parametrize(
    "body",
    [
        "Part 1 of #{n}",
        "```\nCloses #{n}\n```",
        "> Closes #{n}",
        "Use `Closes #{n}` to close it.",
        "Closes other/repo#{n}",
        "Closes #{pr}",
    ],
    ids=["part-of", "code-block", "quote", "inline-code", "other-repo", "pull-request"],
)
def test_these_bodies_close_nothing(roadmap: InMemoryRoadmapStore, body: str) -> None:
    number = _issue(roadmap, "the thing")
    other = roadmap.open_pull_request("open work", base=BRANCH, head="feat/other")
    _deliver(roadmap, number, body=body.format(n=number, pr=other))
    plan, _ = _run(roadmap)
    assert (plan.closings, roadmap.job_writes()) == ((), [])


def test_five_merged_pull_requests_close_five_issues_including_the_oldest(
    roadmap: InMemoryRoadmapStore,
) -> None:
    oldest = _issue(roadmap, "the oldest issue", release=None)
    numbers = [oldest, *(_issue(roadmap, f"item {n}") for n in range(4))]
    for number in numbers:
        _deliver(roadmap, number)
    plan, _ = _run(roadmap)
    closed = sorted(i.number for i in roadmap.issues() if i.state is GitHubState.CLOSED)
    assert ([c.number for c in plan.closings], closed, oldest) == (numbers, numbers, 1)


def test_a_closed_issue_gets_no_comment_and_a_second_run_writes_nothing(
    roadmap: InMemoryRoadmapStore,
) -> None:
    done = _issue(roadmap, "closed by hand")
    roadmap.as_actor("alice").close_by_hand(done, CloseReason.COMPLETED)
    number = _issue(roadmap, "the thing")
    _issue(roadmap, "still open")
    _deliver(roadmap, done)
    _deliver(roadmap, number)
    _run(roadmap)
    first = roadmap.job_writes()
    second, cuts = _run(roadmap)
    assert (
        roadmap.comments_on(done),
        [(w.operation, w.number) for w in first],
        second.closings,
        roadmap.job_writes() == first,
        cuts,
    ) == ([], [("comment", number), ("close_issue", number)], (), True, [])


def _fail_with(what: str) -> Callable[..., Any]:
    def fail(*_: object, **__: object) -> Any:
        raise GitHubOperationError(f"{what} failed (HTTP 502)")

    return fail


@pytest.mark.parametrize("read", ["merged_pull_requests", "issues", "checks"])
def test_a_failed_read_exits_non_zero_naming_it_and_the_issue_stays_open(
    roadmap: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch, read: str
) -> None:
    number = _issue(roadmap, "the thing")
    _deliver(roadmap, number)
    unread = CheckVerdictSummary(unread_reason="checks failed (HTTP 502)")
    if read != "checks":
        monkeypatch.setattr(roadmap, read, _fail_with(read))
    with patch(
        "devops_cli.github.check_verdict.fetch_pr_check_verdicts",
        return_value=unread if read == "checks" else CHECKS,
    ):
        result = runner.invoke(app, ["close", "--repo", REPO, "--confirm"])
    issue = next(i for i in InMemoryRoadmapStore.issues(roadmap) if i.number == number)
    assert (
        result.exit_code,
        "failed (HTTP 502)" in result.output,
        "No open issue to close" in result.output,
        issue.state,
        roadmap.job_writes(),
    ) == (1, True, False, GitHubState.OPEN, []), result.output


# ── When to cut ──


def _open_release_pr(store: InMemoryRoadmapStore, *, head: str = CUT_BRANCH) -> int:
    return store.open_pull_request(
        "feat(release): v0.2.26", base="main", head=head, labels=("release",), release=RELEASE
    )


def _no_open_item(store: InMemoryRoadmapStore) -> None:
    _deliver(store, _issue(store, "delivered"))


def _open_item(store: InMemoryRoadmapStore) -> None:
    _no_open_item(store)
    _issue(store, "still open")


def _pr_open(store: InMemoryRoadmapStore) -> None:
    _no_open_item(store)
    _open_release_pr(store)


def _pr_merged(store: InMemoryRoadmapStore) -> None:
    _no_open_item(store)
    store.close_pull_request(_open_release_pr(store), merged=True)


def _nothing_delivered(store: InMemoryRoadmapStore) -> None:
    store.close_by_hand(_issue(store, "dropped"), CloseReason.NOT_PLANNED)


def _old_pr_closed_and_other_head(store: InMemoryRoadmapStore) -> None:
    _no_open_item(store)
    store.close_pull_request(_open_release_pr(store))
    _open_release_pr(store, head="chore/other-branch")


@pytest.mark.parametrize(
    ("given", "hold", "listed"),
    [
        (_open_item, Hold.OPEN_ITEMS, " still open"),
        (_pr_open, Hold.PR_OPEN, "release pull request #"),
        (_pr_merged, Hold.PR_MERGED, "has merged"),
        (_nothing_delivered, Hold.NOTHING_DELIVERED, "delivers nothing"),
        (_old_pr_closed_and_other_head, None, f"Cut: push {CUT_BRANCH}"),
    ],
    ids=["open-item", "pr-open", "pr-merged", "nothing-delivered", "cut"],
)
def test_when_to_cut(
    roadmap: InMemoryRoadmapStore,
    given: Callable[[InMemoryRoadmapStore], None],
    hold: Hold | None,
    listed: str,
) -> None:
    given(roadmap)
    _issue(roadmap, "next release work", release="v0.2.27")
    plan, cuts = _run(roadmap)
    assert (plan.release, plan.hold, listed in render_close(plan), len(cuts)) == (
        RELEASE,
        hold,
        True,
        0 if hold else 1,
    ), render_close(plan)


def test_the_cut_names_the_branch_base_title_and_missing_fragments(
    roadmap: InMemoryRoadmapStore,
) -> None:
    with_fragment, without = _issue(roadmap, "a"), _issue(roadmap, "b")
    roadmap.as_actor("alice").close_by_hand(with_fragment, CloseReason.COMPLETED)
    roadmap.seed_file(f"changelog.d/{with_fragment}.md", "### Added\n- a\n", ref=BRANCH)
    _deliver(roadmap, without)
    plan, cuts = _run(roadmap)
    assert cuts == [
        Cut(
            version="0.2.26",
            branch=CUT_BRANCH,
            base="main",
            title="feat(release): v0.2.26",
            fragments=(f"changelog.d/{with_fragment}.md",),
            missing_fragments=(without,),
        )
    ]
    text = " ".join(render_close(plan).split())
    files = "pyproject.toml, src/devops_cli/__init__.py, uv.lock, CHANGELOG.md, docs/ROADMAP.md"
    assert (
        f"The cut commit changes {files}." in text,
        f"collects into CHANGELOG.md's [0.2.26] section and deletes: changelog.d/{with_fragment}.md"
        in text,
        f"with no changelog fragment: #{without}. Before the cut, add changelog.d/<issue>.md"
        in text,
    ) == (True, True, True), text


def test_no_open_release_holds_with_no_release(roadmap_store: InMemoryRoadmapStore) -> None:
    plan, cuts = _run(roadmap_store)
    assert (plan.hold, cuts) == (Hold.NO_RELEASE, [])


# ── A shipped release that still holds an open item (#1362) ──


def _issue_of(store: InMemoryRoadmapStore, number: int) -> IssueRecord:
    return next(issue for issue in store.issues() if issue.number == number)


def _close_release(store: InMemoryRoadmapStore, version: str) -> None:
    store.close_release(version)


def _close_by_edit(store: InMemoryRoadmapStore, version: str) -> None:
    store.edit_release(version, state=GitHubState.CLOSED)


@pytest.mark.parametrize(
    "close_milestone", [_close_release, _close_by_edit], ids=["close-release", "edit-release"]
)
def test_an_item_delivered_into_a_shipped_release_closes_before_the_current_releases(
    roadmap: InMemoryRoadmapStore, close_milestone: Callable[[InMemoryRoadmapStore, str], None]
) -> None:
    person = roadmap.as_actor("alice")
    person.edit_release(SHIPPED, state=GitHubState.OPEN)
    late = _issue(roadmap, "delivered after the cut", release=SHIPPED)
    merged = _deliver(roadmap, late, base=SHIPPED_BRANCH)
    close_milestone(person, SHIPPED)
    current = _issue(roadmap, "current work")
    _deliver(roadmap, current)
    plan, cuts = _run(roadmap)
    first = roadmap.job_writes()
    again, _ = _run(roadmap)
    (comment,) = roadmap.comments_on(late)
    assert (
        [closing.number for closing in plan.closings],
        [shipped.release for shipped in plan.shipped],
        f"{merged.url}, merged into `{SHIPPED_BRANCH}` as {merged.merge_commit}." in comment,
        (_issue_of(roadmap, late).state, _issue_of(roadmap, current).state),
        (plan.release, len(cuts)),
        (again.closings, again.shipped, roadmap.job_writes() == first),
    ) == (
        [late, current],
        [SHIPPED],
        True,
        (GitHubState.CLOSED, GitHubState.CLOSED),
        (RELEASE, 1),
        ((), (), True),
    )


def test_an_open_item_of_a_shipped_release_no_pull_request_delivers_stays_open_and_named(
    roadmap: InMemoryRoadmapStore,
) -> None:
    left = _issue(roadmap, "left open on purpose", release=SHIPPED)
    _deliver(roadmap, _issue(roadmap, "current work"))
    plan, cuts = _run(roadmap)
    text = render_close(plan)
    named = [
        text.find(line)
        for line in (f"## {SHIPPED}", f"- #{left} left open on purpose", f"Cut: push {CUT_BRANCH}")
    ]
    assert (
        plan.shipped,
        _issue_of(roadmap, left).state,
        (plan.hold, len(cuts)),
        -1 not in named and named == sorted(named),
    ) == (
        (ShippedClosure(release=SHIPPED, open_items=(_issue_of(roadmap, left),)),),
        GitHubState.OPEN,
        (None, 1),
        True,
    ), text


def test_a_shipped_pull_request_with_unreadable_checks_fails_the_run_and_holds_no_cut(
    roadmap: InMemoryRoadmapStore,
) -> None:
    late = _issue(roadmap, "delivered after the cut", release=SHIPPED)
    shipped = _deliver(roadmap, late, base=SHIPPED_BRANCH)
    _deliver(roadmap, _issue(roadmap, "current work"))
    unread = CheckVerdictSummary(unread_reason="checks failed (HTTP 502)")

    def verdicts(number: int, **_: object) -> CheckVerdictSummary:
        return unread if number == shipped.number else CHECKS

    with patch("devops_cli.github.check_verdict.fetch_pr_check_verdicts", side_effect=verdicts):
        result = runner.invoke(app, ["close", "--repo", REPO])
    assert (
        result.exit_code,
        f"Pull request #{shipped.number} closes #{late}, which stay open" in result.output,
        f"Cut: push {CUT_BRANCH}" in result.output,
        _issue_of(roadmap, late).state,
        roadmap.job_writes(),
    ) == (1, True, True, GitHubState.OPEN, []), result.output


def test_a_shipped_pull_request_closes_no_item_of_another_release(
    roadmap: InMemoryRoadmapStore,
) -> None:
    """A person reopened the item and moved it to a later release: the shipped release's pull
    request no longer closes it."""
    _issue(roadmap, "left open on purpose", release=SHIPPED)
    moved = _issue(roadmap, "reopened and moved", release="v0.2.27")
    _deliver(roadmap, moved, base=SHIPPED_BRANCH)
    plan, _ = _run(roadmap)
    assert (plan.closings, [s.release for s in plan.shipped], _issue_of(roadmap, moved).state) == (
        (),
        [SHIPPED],
        GitHubState.OPEN,
    )


def test_a_shipped_item_a_current_pull_request_closes_is_not_also_named_still_open(
    roadmap: InMemoryRoadmapStore,
) -> None:
    """The pull request that delivers it merged into the current release's branch: the item is
    a closing, and its shipped release no longer lists it as still open."""
    late = _issue(roadmap, "finished in the next release", release=SHIPPED)
    _deliver(roadmap, late)
    plan, _ = _run(roadmap)
    text = render_close(plan)
    assert (
        [closing.number for closing in plan.closings],
        plan.shipped,
        MESSAGES.roadmap.close_shipped_open.format(release=SHIPPED) in text,
        f"- #{late} finished in the next release" in text,
        _issue_of(roadmap, late).state,
    ) == ([late], (ShippedClosure(release=SHIPPED),), False, False, GitHubState.CLOSED), text


def test_a_shipped_item_a_person_reopened_stays_open_and_is_named(
    roadmap: InMemoryRoadmapStore,
) -> None:
    """A job never reverts a person's change (ADR 0002): the pull request that delivered the
    item does not close it again once a person reopens it in its shipped release."""
    person = roadmap.as_actor("alice")
    person.edit_release(SHIPPED, state=GitHubState.OPEN)
    item = _issue(roadmap, "not done after all", release=SHIPPED)
    _deliver(roadmap, item, base=SHIPPED_BRANCH)
    _run(roadmap)
    person.close_release(SHIPPED)
    person.reopen_issue(item)
    writes = roadmap.job_writes()
    plan, _ = _run(roadmap)
    text = render_close(plan)
    named = [
        text.find(line)
        for line in (
            MESSAGES.roadmap.close_shipped_reopened.format(release=SHIPPED),
            f"- #{item} not done after all",
        )
    ]
    assert (
        plan.closings,
        plan.shipped,
        _issue_of(roadmap, item).state,
        roadmap.job_writes() == writes,
        -1 not in named and named == sorted(named),
    ) == (
        (),
        (ShippedClosure(release=SHIPPED, reopened=(_issue_of(roadmap, item),)),),
        GitHubState.OPEN,
        True,
        True,
    ), text


def test_with_no_open_release_a_shipped_releases_delivered_item_still_closes(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    roadmap_store.as_actor("alice").create_release(SHIPPED, state=GitHubState.CLOSED)
    late = _issue(roadmap_store, "delivered after the cut", release=SHIPPED)
    _deliver(roadmap_store, late, base=SHIPPED_BRANCH)
    plan, cuts = _run(roadmap_store)
    text = render_close(plan)
    assert (
        [closing.number for closing in plan.closings],
        (plan.hold, cuts),
        _issue_of(roadmap_store, late).state,
        (f"## {SHIPPED}" in text, "the current release" in text, "No open issue" in text),
        text.rstrip().endswith("No cut: there is no open Release."),
    ) == ([late], (Hold.NO_RELEASE, []), GitHubState.CLOSED, (True, False, False), True), text


# ── Cut mechanics ──


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture(scope="module")
def release_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A bare remote with `main` and `release/v0.2.26`, and a clone on another branch."""
    base = tmp_path_factory.mktemp("cut")
    origin, clone = base / "origin.git", base / "clone"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    clone.mkdir()
    _git(clone, "init", "-q", "-b", "main")
    _git(clone, "config", "user.email", "ci@example.com")
    _git(clone, "config", "user.name", "CI")
    _git(clone, "config", "commit.gpgsign", "false")
    _git(clone, "remote", "add", "origin", str(origin))
    (clone / "src" / "devops_cli").mkdir(parents=True)
    (clone / "docs").mkdir()
    (clone / "changelog.d").mkdir()
    (clone / "pyproject.toml").write_text(
        '[project]\nname = "devops-cli"\nversion = "0.2.25"\n', encoding="utf-8"
    )
    (clone / "src" / "devops_cli" / "__init__.py").write_text('__version__ = "0.2.25"\n')
    (clone / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "devops-cli"\nversion = "0.2.25"\n', encoding="utf-8"
    )
    (clone / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n## [0.2.26]\n")
    (clone / "README.md").write_text("# devops-cli\n")
    (clone / "docs" / "ROADMAP.md").write_text("old\n")
    (clone / "changelog.d" / "1.md").write_text("### Added\n- one\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "init")
    _git(clone, "push", "-q", "origin", "main")
    _git(clone, "push", "-q", "origin", f"main:{BRANCH}")
    _git(clone, "checkout", "-q", "-b", "feat/elsewhere")
    return base


@pytest.fixture
def clone(release_template: Path, tmp_path: Path) -> tuple[Path, Path]:
    shutil.copytree(release_template, tmp_path, dirs_exist_ok=True)
    origin, clone = tmp_path / "origin.git", tmp_path / "clone"
    _git(clone, "remote", "set-url", "origin", str(origin))
    return origin, clone


@pytest.fixture
def fake_gh() -> Iterator[list[list[str]]]:
    calls: list[list[str]] = []

    def gh(cmd: list[str], *_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        out = "https://github.com/example/roadmap/pull/99\n" if "create" in cmd else "[]"
        return subprocess.CompletedProcess(cmd, 0, out, "")

    with (
        patch("devops_cli.commands.release.run_gh", side_effect=gh),
        patch("devops_cli.github.check_verdict.fetch_pr_check_verdicts", return_value=CHECKS),
    ):
        yield calls


def _close(clone: Path, *flags: str) -> Any:
    return runner.invoke(app, ["close", "--repo", REPO, "--root", str(clone), *flags])


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _undated(changelog: str, since: str) -> str:
    """`changelog` with the cut's date, `since` or a later today when the run crosses midnight
    UTC, as DATE."""
    for day in {since, _today()}:
        changelog = changelog.replace(f"] - {day}\n", "] - DATE\n")
    return changelog


def _release_check(work: Path) -> Any:
    """`devops release check` as release.yml runs it on the merge, docs taken as fresh.

    `check_docs` is patched, as in `tests/test_release.py`: release check has no docs skip, docs
    freshness is not this test's subject, and a real generation takes about 3 s.
    """
    with patch("devops_cli.commands.release.DocGenerator.check_docs", return_value=(True, [])):
        return runner.invoke(
            release_app, ["check", "--allow-dirty", "--skip-ci", "--root", str(work)]
        )


def test_the_cut_pushes_the_cut_branch_from_the_release_tip_and_opens_a_ready_pr(
    roadmap: InMemoryRoadmapStore, clone: tuple[Path, Path], fake_gh: list[list[str]]
) -> None:
    """The cut commit collects changelog.d/ into the version's section and deletes the
    fragments, so release.yml's `release check` passes on the merge (#1450)."""
    origin, work = clone
    tip, main = _git(origin, "rev-parse", BRANCH), _git(origin, "rev-parse", "main")
    since = _today()
    roadmap.seed_file("changelog.d/1.md", "### Added\n- one\n", ref=BRANCH)
    _deliver(roadmap, _issue(roadmap, "with fragment"))
    _deliver(roadmap, _issue(roadmap, "without fragment"))
    result = _close(work, "--confirm")
    cut = _git(origin, "rev-parse", CUT_BRANCH)
    changed = _git(origin, "diff", "--name-status", f"{cut}^", cut).splitlines()
    (create,) = [call for call in fake_gh if call[1:3] == ["pr", "create"]]
    assert result.exit_code == 0, result.output
    check = _release_check(work)
    assert (
        _git(origin, "rev-parse", f"{cut}^"),
        _git(origin, "rev-parse", BRANCH),
        _git(origin, "rev-parse", "main"),
        sorted(tuple(line.split("\t")[::-1]) for line in changed),
        _git(origin, "show", f"{cut}:docs/ROADMAP.md").startswith("<!--"),
        _undated(_git(origin, "show", f"{cut}:CHANGELOG.md"), since),
        [create[create.index(flag) + 1] for flag in ("--base", "--head", "--title", "--label")],
        create[create.index("--milestone") + 1],
        "--draft" in create,
        [c for c in fake_gh if {"merge", "review"} & set(c[1:3])],
        "with no changelog fragment" in result.output and "#2" in result.output,
        check.exit_code,
    ) == (
        tip,
        cut,
        main,
        [
            ("CHANGELOG.md", "M"),
            ("changelog.d/1.md", "D"),
            ("docs/ROADMAP.md", "M"),
            ("pyproject.toml", "M"),
            ("src/devops_cli/__init__.py", "M"),
            ("uv.lock", "M"),
        ],
        True,
        "# Changelog\n\n## [Unreleased]\n\n## [0.2.26] - DATE\n\n### Added\n- one",
        ["main", CUT_BRANCH, "feat(release): v0.2.26", "release"],
        RELEASE,
        False,
        [],
        True,
        0,
    ), check.output


def _push_to_the_release_branch(work: Path, change: Callable[[], object], message: str) -> str:
    """Merge a change into the release branch on origin, as an item PR does; its new tip."""
    _git(work, "checkout", "-q", "-B", "feat/more", f"origin/{BRANCH}")
    change()
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", message)
    _git(work, "push", "-q", "origin", f"HEAD:{BRANCH}")
    return _git(work, "rev-parse", "HEAD")


def test_a_cut_after_an_unmerged_release_pr_rebuilds_from_the_new_tip(
    roadmap: InMemoryRoadmapStore, clone: tuple[Path, Path], fake_gh: list[list[str]]
) -> None:
    """A fragment merged after a cut whose PR closed unmerged joins the version's section."""
    origin, work = clone
    since = _today()
    _deliver(roadmap, _issue(roadmap, "first"))
    assert _close(work, "--confirm").exit_code == 0
    roadmap.close_pull_request(_open_release_pr(roadmap))
    prev_tip = _push_to_the_release_branch(
        work, lambda: (work / "changelog.d" / "9.md").write_text("### Fixed\n- nine\n"), "fix: 9"
    )
    _deliver(roadmap, _issue(roadmap, "second"))
    result = _close(work, "--confirm")
    cut = _git(origin, "rev-parse", CUT_BRANCH)
    assert (
        result.exit_code,
        _git(origin, "rev-parse", f"{cut}^") == prev_tip,
        _git(origin, "ls-tree", "--name-only", cut, "changelog.d/"),
        _undated(_git(origin, "show", f"{cut}:CHANGELOG.md"), since),
    ) == (
        0,
        True,
        "",
        "# Changelog\n\n## [Unreleased]\n\n## [0.2.26] - DATE\n\n"
        "### Added\n- one\n\n### Fixed\n- nine",
    ), result.output


def _drop_the_fragment(work: Path) -> None:
    """Leave the release branch with no fragment and an empty `## [0.2.26]`."""
    _push_to_the_release_branch(
        work, lambda: _git(work, "rm", "-q", "changelog.d/1.md"), "chore: drop 1"
    )


def test_a_cut_with_no_fragment_and_no_entries_for_its_version_fails_before_it_pushes(
    roadmap: InMemoryRoadmapStore, clone: tuple[Path, Path], fake_gh: list[list[str]]
) -> None:
    """A release PR without its version's section would fail release.yml on the merge."""
    origin, work = clone
    _drop_the_fragment(work)
    refs = _git(origin, "for-each-ref")
    number = _issue(roadmap, "no entry")
    _deliver(roadmap, number)
    result = _close(work, "--confirm")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        [name in output for name in ("v0.2.26", "release/v0.2.26", "## [0.2.26]")],
        ERRORS.release.cut_changelog_missing_items.format(items=f"#{number}") in output,
        "Nothing was pushed" in output,
        _git(origin, "for-each-ref") == refs,
        [call for call in fake_gh if call[1:3] == ["pr", "create"]],
    ) == (1, [True, True, True], True, True, True, []), result.output


def test_the_services_close_job_names_the_items_with_no_fragment_when_the_cut_stops(
    roadmap: InMemoryRoadmapStore, clone: tuple[Path, Path], fake_gh: list[list[str]]
) -> None:
    """The Service renders no plan, so the error its log shows names the missing entries."""
    origin, work = clone
    _drop_the_fragment(work)
    refs = _git(origin, "for-each-ref")
    numbers = [_issue(roadmap, "no entry"), _issue(roadmap, "nor this")]
    for number in numbers:
        _deliver(roadmap, number)
    close_job = next(row.runner for row in DEFAULT_DUE_TABLE if row.name == "close")
    with pytest.raises(ValidationError) as stopped:
        close_job(store=roadmap, repo=REPO, clone_path=work)
    items = ", ".join(f"#{number}" for number in numbers)
    assert (
        ERRORS.release.cut_changelog_missing_items.format(items=items) in str(stopped.value),
        _git(origin, "for-each-ref") == refs,
        [call for call in fake_gh if call[1:3] == ["pr", "create"]],
    ) == (True, True, []), str(stopped.value)


def test_a_re_cut_whose_tip_holds_the_version_section_keeps_it(
    roadmap: InMemoryRoadmapStore, clone: tuple[Path, Path], fake_gh: list[list[str]]
) -> None:
    """The first cut collected every fragment, so a re-cut with none keeps that section."""
    origin, work = clone
    _deliver(roadmap, _issue(roadmap, "first"))
    assert _close(work, "--confirm").exit_code == 0
    roadmap.close_pull_request(_open_release_pr(roadmap))
    tip = _git(origin, "rev-parse", BRANCH)
    _deliver(roadmap, _issue(roadmap, "second, with no fragment"))
    result = _close(work, "--confirm")
    cut = _git(origin, "rev-parse", CUT_BRANCH)
    assert (
        result.exit_code,
        _git(origin, "rev-parse", f"{cut}:CHANGELOG.md")
        == _git(origin, "rev-parse", f"{tip}:CHANGELOG.md"),
    ) == (0, True), result.output


def test_a_run_without_confirm_previews_and_changes_nothing(
    roadmap: InMemoryRoadmapStore, clone: tuple[Path, Path], fake_gh: list[list[str]]
) -> None:
    origin, work = clone
    number = _issue(roadmap, "the thing")
    _deliver(roadmap, number)
    refs = _git(origin, "for-each-ref"), _git(work, "for-each-ref"), _git(work, "status", "-s")
    result = _close(work)
    assert (
        result.exit_code,
        f"Close #{number} as completed" in result.output,
        "### How it was verified" in result.output,
        f"Cut: push {CUT_BRANCH}" in result.output,
        "pass --confirm" in result.output,
        roadmap.job_writes(),
        (_git(origin, "for-each-ref"), _git(work, "for-each-ref"), _git(work, "status", "-s")),
        fake_gh,
    ) == (0, True, True, True, True, [], refs, []), result.output


# ── Dry run ──


def test_the_dry_run_lists_the_closes_and_the_cut_without_a_request() -> None:
    plan = dry_run_close(REPO, ref=None)
    lines = [request.line() for request in (*plan.requests, *plan.write_requests)]
    assert (plan.dry_run, plan.closings, plan.cut) == (True, (), None)
    for expected in (
        f"gh api 'repos/{REPO}/pulls?state=closed&base=release%2F%3Crelease%3E",
        "gh pr checks '<number>' --json name,state,bucket,workflow,link --repo example/roadmap",
        f"gh api -X PATCH 'repos/{REPO}/issues/<item>' -f state=closed -f state_reason=completed",
        "git push --force-with-lease -u origin 'release/<release>'",
        "--base '<branch>' --head 'release/<release>' --milestone '<release>' --label release",
    ):
        assert any(expected in line for line in lines), (expected, lines)
    assert not any("--draft" in line for line in lines)


def test_the_dry_run_lists_a_shipped_releases_reads_before_the_current_releases() -> None:
    texts = MESSAGES.roadmap
    cond, rep = texts.plan_conditions, texts.plan_repeat
    reads = dry_run_close(REPO, ref=None).requests
    issues, shipped, current = (
        next(i for i, r in enumerate(reads) if needle in r.line())
        for needle in ("issues?state=all", "%3Cshipped%20release%3E", "%3Crelease%3E&sort")
    )
    assert (
        issues < shipped < current,
        reads[issues].condition,
        (reads[shipped].condition, rep["shipped"] in reads[shipped].repeat),
        reads[current].condition,
    ) == (True, cond["read_issues"], (cond["shipped"], True), cond["current"])


def test_the_dry_run_command_makes_no_request_and_names_the_cut_files(
    roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.roadmap import store as store_module

    def refuse(*_: object, **__: object) -> Any:
        raise AssertionError("the dry run opened a store or ran a process")

    monkeypatch.setattr(store_module, "get_roadmap_store", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    result = runner.invoke(app, ["close", "--repo", REPO, "--dry-run", "--root", "/nonexistent"])
    output = " ".join(result.output.split())
    files = "pyproject.toml, src/devops_cli/__init__.py, uv.lock, CHANGELOG.md, docs/ROADMAP.md"
    assert (
        result.exit_code,
        "Dry run: no request was made" in output,
        f"A cut commits {files} on release/<release>" in output,
        "--draft" in output,
    ) == (0, True, True, False), result.output
