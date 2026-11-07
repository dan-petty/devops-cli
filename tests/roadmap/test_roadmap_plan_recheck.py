"""`devops roadmap plan-recheck`: one result for each change folder on the default branch (#3492)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest

from devops_cli.openspec.tool import isolated_openspec
from devops_cli.roadmap.plan_recheck import (
    PlanRecheck,
    PlanResult,
    recheck_plans,
    refusals_by_gate,
    render_recheck,
)
from devops_cli.roadmap.stage_change import StageProposal, render_change
from devops_cli.roadmap.store import GitHubState, ItemField
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, validate_args

if TYPE_CHECKING:
    from collections.abc import Iterator

    from devops_cli.openspec.tool import OpenSpecTool
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

CREATED = datetime(2026, 11, 4, tzinfo=UTC).date()
FIELDS = {ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"}
MISSING = "src/devops_cli/missing.py"
TASKS = "openspec/changes/{issue}-keep-the-last-comment/tasks.md"


REJECTION = "The change breaks a rule of OpenSpec."


def _change(issue: int) -> str:
    return f"{issue}-keep-the-last-comment"


@pytest.fixture
def tool(openspec_fake: OpenSpecFake) -> Iterator[OpenSpecTool]:
    """The pinned OpenSpec, which accepts the change folder of each of the issues 1 to 3."""
    for issue in range(1, 4):
        openspec_fake.script(validate_args(_change(issue)), 0, VALID_REPORT)
    with isolated_openspec() as pinned:
        yield pinned


def _proposal(test_file: str = "tests/test_sample.py") -> StageProposal:
    """The stock plan, with its new test module at `test_file`."""
    stock = make_stage_proposal()
    group = stock.groups[0]
    update = {
        "changes": ["src/devops_cli/sample.py", test_file],
        "creates": [test_file],
        "creates_lines": {test_file: 40},
        "test": group.test.replace("tests/test_sample.py", test_file) if group.test else None,
        "verify": group.verify.replace("tests/test_sample.py", test_file) if group.verify else None,
    }
    return make_stage_proposal(groups=[group.model_copy(update=update)])


def _plan(issue: int, proposal: StageProposal | None = None) -> dict[str, str]:
    change = f"{issue}-keep-the-last-comment"
    return render_change(change, proposal or _proposal(), {"comment-thread"}, created=CREATED)


def _recheck(
    repo: StageRepo, store: InMemoryRoadmapStore, tool: OpenSpecTool
) -> dict[str, tuple[PlanResult, int]]:
    recheck = recheck_plans(repo.clone, store, tool=tool)
    return {r.folder: (r.result, r.issue) for r in recheck.records}


def _store(*, closed: tuple[int, ...] = (), count: int = 3) -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore()
    for number in range(1, count + 1):
        state = GitHubState.CLOSED if number in closed else GitHubState.OPEN
        store.seed_issue(f"An item {number}", state=state, fields=FIELDS)
    return store


def test_each_numbered_folder_gets_one_result(stage_repo: StageRepo, tool: OpenSpecTool) -> None:
    ok = _plan(1)
    no_design = _plan(2, _proposal("tests/test_other.py"))
    del no_design["openspec/changes/2-keep-the-last-comment/design.md"]
    broken = _plan(3, _proposal("tests/test_third.py"))
    broken["openspec/changes/3-keep-the-last-comment/tasks.md"] = "# Tasks\n\nNothing here.\n"
    stage_repo.track({**ok, **no_design, **broken})

    results = _recheck(stage_repo, _store(), tool)

    assert results == {
        "1-keep-the-last-comment": (PlanResult.OK, 1),
        "2-keep-the-last-comment": (PlanResult.REWRITE, 2),
        "3-keep-the-last-comment": (PlanResult.NEW_PLAN, 3),
    }


def test_a_folder_of_a_closed_issue_is_cleanup_and_no_count_holds_it(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track({**_plan(1), **_plan(2, _proposal("tests/test_other.py"))})
    store = _store(closed=(2,), count=2)

    recheck = recheck_plans(stage_repo.clone, store, tool=tool)

    assert {r.issue: r.result for r in recheck.records} == {
        1: PlanResult.OK,
        2: PlanResult.CLEANUP,
    }
    assert len(recheck.live) == 1
    assert recheck.summary()["live"] == 1
    assert "1 folders count. 1 folders of closed issues are left out" in render_recheck(recheck)


def test_a_plan_whose_new_file_is_on_the_default_branch_is_delivered(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track({**_plan(1), "tests/test_sample.py": "def test_it() -> None: ...\n"})

    results = _recheck(stage_repo, _store(count=1), tool)

    assert results == {"1-keep-the-last-comment": (PlanResult.DELIVERED, 1)}


def _without_verification(files: dict[str, str], issue: int = 1) -> dict[str, str]:
    """`files` with every `Verification:` line of the `tasks.md` of the folder removed."""
    path = TASKS.format(issue=issue)
    kept = [line for line in files[path].splitlines(keepends=True) if "Verification:" not in line]
    return {**files, path: "".join(kept)}


def test_a_plan_that_the_rewrite_fixes_is_a_rewrite_and_counts_as_unreadable_and_unverified(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track(_without_verification(_plan(1)))

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert record.result is PlanResult.REWRITE
    assert (recheck.unverified, recheck.unreadable) == (1, 1)
    command = "uv run devops ci test tests/test_sample.py"
    assert record.notes == (
        f"Group 1: add the line `Verification:` with `{command}` under its first task.",
    )
    assert record.refusals == ()


def test_a_rewrite_record_holds_the_files_that_the_rewrite_changes(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    files = _without_verification(_plan(1))
    del files["openspec/changes/1-keep-the-last-comment/design.md"]
    stage_repo.track(files)

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert record.result is PlanResult.REWRITE
    assert record.rewrite is not None
    assert [change.path for change in record.rewrite.changes] == [
        "openspec/changes/1-keep-the-last-comment/design.md",
        "openspec/changes/1-keep-the-last-comment/tasks.md",
    ]
    assert record.as_dict()["files"] == [change.path for change in record.rewrite.changes]
    assert "design.md" in render_recheck(recheck)


def test_a_plan_whose_rewritten_text_still_fails_a_gate_is_a_new_plan_with_that_refusal(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track(_without_verification(_reading_a_missing_file(1)))

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert record.result is PlanResult.NEW_PLAN
    assert record.rewrite is None
    assert [refusal.gate for refusal in record.refusals] == ["paths"]
    assert "`src/devops_cli/missing.py`" in record.refusals[0].message


def test_a_group_that_changes_no_test_and_no_document_stays_a_new_plan_with_the_reader_error(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    files = _without_verification(_plan(1))
    path = TASKS.format(issue=1)
    files[path] = files[path].replace(
        "tests/test_sample.py` (new)", "src/devops_cli/other.py` (new)"
    )
    stage_repo.track(files)

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert record.result is PlanResult.NEW_PLAN
    assert [refusal.gate for refusal in record.refusals] == ["read"]
    assert (recheck.unreadable, recheck.unverified) == (1, 1)


def test_a_criterion_of_group_zero_is_a_new_plan_with_the_reader_error(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    criteria = [{"criterion": "The command prints one line for each problem", "group": 1}]
    files = _plan(1, make_stage_proposal(groups=_proposal().groups, criteria=criteria))
    path = TASKS.format(issue=1)
    files[path] = files[path].replace("Group 1:", "Group 0:")
    stage_repo.track(files)

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert record.result is PlanResult.NEW_PLAN
    assert [refusal.gate for refusal in record.refusals] == ["read"]
    assert recheck.unreadable == 1


def test_a_plan_that_passes_and_that_the_rewrite_does_not_change_is_ok(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track(_plan(1))

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert (record.result, record.notes, record.rewrite) == (PlanResult.OK, (), None)
    assert (recheck.unverified, recheck.unreadable) == (0, 0)


def test_the_first_problem_of_an_unreadable_plan_is_its_reason(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    files = _plan(1)
    files["openspec/changes/1-keep-the-last-comment/tasks.md"] = "# Tasks\n\nNothing here.\n"
    stage_repo.track(files)

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert (record.result, record.readable) == (PlanResult.NEW_PLAN, False)
    (refusal,) = record.refusals
    assert (refusal.gate, record.notes) == ("read", ())
    assert "1-keep-the-last-comment" in refusal.message
    assert recheck.unreadable == 1


def _reading_a_missing_file(issue: int) -> dict[str, str]:
    """A plan whose group reads a file that no commit holds, so the gate `paths` refuses it."""
    stock = _proposal(f"tests/test_n{issue}.py")
    group = stock.groups[0].model_copy(update={"reads": [MISSING]})
    return _plan(issue, make_stage_proposal(groups=[group]))


def _unreadable(issue: int) -> dict[str, str]:
    """A plan whose `tasks.md` holds no group, so the plan reader refuses it."""
    files = _plan(issue, _proposal(f"tests/test_n{issue}.py"))
    files[TASKS.format(issue=issue)] = "# Tasks\n\nNothing here.\n"
    return files


def _branch(
    repo: StageRepo,
    name: str,
    *,
    write: Mapping[str, str] | None = None,
    remove: Sequence[str] = (),
) -> None:
    """Make the local branch `name` from `main` with `write` committed and the folders `remove`
    deleted, and switch back to `main`. The branch is not pushed."""
    repo.git("switch", "-q", "-c", name)
    for path, text in (write or {}).items():
        (repo.clone / path).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / path).write_text(text, encoding="utf-8")
    for folder in remove:
        repo.git("rm", "-q", "-r", folder)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", f"work on {name}")
    repo.git("switch", "-q", "main")


def _branch_json(recheck: PlanRecheck) -> dict[str, object]:
    """The part of the JSON report that holds the comparison with the branch."""
    return cast("dict[str, object]", recheck.as_dict()["branch"])


def _compare(
    repo: StageRepo, store: InMemoryRoadmapStore, branch: str, tool: OpenSpecTool
) -> PlanRecheck:
    return recheck_plans(repo.clone, store, tool=tool, branch=branch)


def test_a_refusal_names_the_gate_that_found_it(stage_repo: StageRepo, tool: OpenSpecTool) -> None:
    stage_repo.track({**_reading_a_missing_file(1), **_unreadable(2)})

    recheck = recheck_plans(stage_repo.clone, _store(count=2), tool=tool)

    by_folder = {r.folder: r for r in recheck.records}
    assert {r.gate for r in by_folder["1-keep-the-last-comment"].refusals} == {"paths"}
    assert [r.gate for r in by_folder["2-keep-the-last-comment"].refusals] == ["read"]
    report = render_recheck(recheck)
    assert "  [paths] Group 1 names `src/devops_cli/missing.py`" in report
    assert (
        "  [read] The plan reader cannot read `openspec/changes/2-keep-the-last-comment`" in report
    )
    assert "Refusals by gate: paths 1, read 1." in report


def test_a_finding_of_openspec_is_a_refusal_of_the_gate_openspec(
    stage_repo: StageRepo, tool: OpenSpecTool, openspec_fake: OpenSpecFake
) -> None:
    stage_repo.track(_plan(1))
    openspec_fake.script(validate_args(_change(1)), 1, "", REJECTION)

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    (record,) = recheck.records
    assert record.result is PlanResult.NEW_PLAN
    assert [r.gate for r in record.refusals] == ["openspec"]
    assert record.refusals[0].message == f"`openspec validate` finds: {REJECTION}"


def test_a_run_with_no_branch_compares_nothing(stage_repo: StageRepo, tool: OpenSpecTool) -> None:
    stage_repo.track(_plan(1))

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=tool)

    assert recheck.branch is None
    assert recheck.new_refusals == ()
    assert "Branch" not in render_recheck(recheck)
    assert "branch" not in recheck.as_dict()


def test_a_branch_run_reads_each_folder_of_both_sides_with_the_plan_reader_and_no_model(
    stage_repo: StageRepo, tool: OpenSpecTool, model_fake: ModelFake
) -> None:
    stage_repo.track({**_plan(1), **_plan(2, _proposal("tests/test_other.py"))})
    _branch(stage_repo, "topic", remove=["openspec/changes/2-keep-the-last-comment"])

    recheck = _compare(stage_repo, _store(count=2), "topic", tool)

    assert recheck.branch is not None
    assert [r.folder for r in recheck.branch.records] == ["1-keep-the-last-comment"]
    assert [r.folder for r in recheck.records] == [
        "1-keep-the-last-comment",
        "2-keep-the-last-comment",
    ]
    # `read_change` reads a folder, and a folder it refuses has the gate `read`: all 3 were read.
    records = (*recheck.records, *recheck.branch.records)
    assert len(records) == 3
    assert all(record.readable for record in records)
    assert {record.result for record in records} == {PlanResult.OK}
    assert model_fake.calls == []


def test_each_gate_lists_the_refusals_of_the_branch_and_of_the_default_branch(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track({**_reading_a_missing_file(1), **_plan(2, _proposal("tests/test_other.py"))})
    _branch(
        stage_repo,
        "topic",
        write=_reading_a_missing_file(2),
        remove=["openspec/changes/1-keep-the-last-comment"],
    )

    recheck = _compare(stage_repo, _store(count=2), "topic", tool)

    assert recheck.branch is not None
    on_default = refusals_by_gate(recheck.records)["paths"]
    on_branch = refusals_by_gate(recheck.branch.records)["paths"]
    assert [r.folder for r in on_default] == ["1-keep-the-last-comment"]
    assert [r.folder for r in on_branch] == ["2-keep-the-last-comment"]
    report = render_recheck(recheck)
    assert "Branch `topic` against `main`: 1 folders on the branch, 2 on `main`." in report
    assert "Gate paths: 1 on `main`, 1 on `topic`." in report
    assert "  main: 1-keep-the-last-comment: Group 1 names `src/devops_cli/missing.py`" in report
    assert "  topic: 2-keep-the-last-comment: Group 1 names `src/devops_cli/missing.py`" in report


def test_a_refusal_that_the_branch_adds_is_a_case_to_review(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track(_plan(1))
    _branch(stage_repo, "topic", write=_reading_a_missing_file(2))

    recheck = _compare(stage_repo, _store(count=2), "topic", tool)

    (added,) = recheck.new_refusals
    assert (added.folder, added.gate) == ("2-keep-the-last-comment", "paths")
    assert "`src/devops_cli/missing.py`" in added.message
    report = render_recheck(recheck)
    assert "New refusals on `topic`: 1." in report
    assert f"  case to review: 2-keep-the-last-comment [paths] {added.message}" in report
    assert _branch_json(recheck)["new_refusals"] == [{**added.as_dict(), "label": "case to review"}]


def test_a_refusal_that_both_sides_hold_is_not_new(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track(_reading_a_missing_file(1))
    _branch(stage_repo, "topic", write=_plan(2, _proposal("tests/test_other.py")))

    recheck = _compare(stage_repo, _store(count=2), "topic", tool)

    assert recheck.new_refusals == ()
    report = render_recheck(recheck)
    assert "New refusals on `topic`: 0." in report
    assert "Gate paths: 1 on `main`, 1 on `topic`." in report
    assert report.count("  both: 1-keep-the-last-comment: Group 1 names") == 1


def test_a_folder_that_the_reader_refuses_is_not_read_and_the_run_goes_on(
    stage_repo: StageRepo, tool: OpenSpecTool
) -> None:
    stage_repo.track(_plan(1))
    write = {**_unreadable(2), **_plan(3, _proposal("tests/test_third.py"))}
    _branch(stage_repo, "topic", write=write)

    recheck = _compare(stage_repo, _store(count=3), "topic", tool)

    assert recheck.branch is not None
    results = {r.folder: r.result for r in recheck.branch.records}
    assert results == {
        "1-keep-the-last-comment": PlanResult.OK,
        "2-keep-the-last-comment": PlanResult.NEW_PLAN,
        "3-keep-the-last-comment": PlanResult.OK,
    }
    assert recheck.branch.unread == ("2-keep-the-last-comment",)
    on_branch = render_recheck(recheck).split("Branch `topic` against `main`", 1)[1].splitlines()
    assert "Not read on `topic`: 2-keep-the-last-comment." in on_branch
    assert {"ok 1-keep-the-last-comment", "ok 3-keep-the-last-comment"} <= set(on_branch)
    assert "new-plan 2-keep-the-last-comment" in on_branch
    assert "Results: ok 2, rewrite 0, new-plan 1, delivered 0, cleanup 0." in on_branch
    assert _branch_json(recheck)["not_read"] == ["2-keep-the-last-comment"]
