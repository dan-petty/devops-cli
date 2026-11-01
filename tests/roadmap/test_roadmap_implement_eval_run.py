"""A run of `devops roadmap eval implement` (#3030): one fixture in a scratch clone, through the
real step with a scripted model, and the report of its properties.

Git runs for real on temporary repositories. The other programs of the exit checks and of the
command properties are answered at the process edge by `process_fake`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS
from devops_cli.exceptions.roadmap import ImplementEvalError
from devops_cli.roadmap.implement_eval import LoadedCase, load_case
from devops_cli.roadmap.implement_eval_run import (
    FixtureItems,
    RunReport,
    check_recorded,
    make_clone,
    render_dry_run,
    render_report,
    run_case,
    write_report,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import (
    WINDOW,
    command_text,
    git,
    is_clean_at,
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_eval import PLAN, case_data, eval_repo, write_fixture

pytestmark = pytest.mark.usefixtures("keyring_store")

SIX = [
    "tests_kept",
    "diff_scope",
    "no_scratch",
    "tasks_ticked",
    "tests_pass",
    "verify_passes",
]


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    return eval_repo(tmp_path / "repo")


def _loaded(tmp_path: Path, base: str, **overrides: Any) -> LoadedCase:
    return load_case(write_fixture(tmp_path / "fixture", case=case_data(base=base, **overrides)))


def _statuses(report: Any) -> dict[str, str]:
    return {record.name: record.status for record in report.properties}


def test_a_step_that_does_the_group_passes_the_six_properties_and_leaves_nothing(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, base = repo
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    report = run_case(_loaded(tmp_path, base), repo=checkout, model=script.model(), window=WINDOW)

    clones = {call.cwd for call in programs.calls if call.argv[0] == "uv"}
    assert (report.fixture, report.status, report.reason, report.requests, report.tool_calls) == (
        "sample",
        "done",
        "",
        2,
        3,
    )
    assert _statuses(report) == dict.fromkeys(SIX, "pass")
    assert report.input_tokens > 0
    assert report.seconds >= 0
    assert is_clean_at(checkout, base)
    assert [clone.exists() for clone in clones] == [False]
    assert {call.argv[0] for call in programs.calls} == {"git", "uv"}


def test_a_step_that_stops_with_a_scratch_file_fails_the_scope_and_skips_the_commands(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, base = repo
    programs.answer(
        lambda call: "ruff check" in command_text(call),
        ProcessAnswer(returncode=1, stdout="E501 line too long\n"),
    )
    scratch = write_call("scratch.py", "print('x')\n")
    script = ModelScript(tool_calls(scratch, *the_whole_group()), say("Done."))

    report = run_case(_loaded(tmp_path, base), repo=checkout, model=script.model(), window=WINDOW)

    assert report.status == "stopped"
    assert "ruff check" in report.reason
    assert _statuses(report) == {
        "tests_kept": "pass",
        "diff_scope": "fail",
        "no_scratch": "fail",
        "tasks_ticked": "pass",
        "tests_pass": "skipped",
        "verify_passes": "skipped",
    }
    assert report.first_failed == "diff_scope"
    assert is_clean_at(checkout, base)


def test_a_step_that_the_window_refuses_is_reported_refused_with_every_property_skipped(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, base = repo
    script = ModelScript(say("Never asked."))

    report = run_case(_loaded(tmp_path, base), repo=checkout, model=script.model(), window=100)

    assert (report.status, report.requests, script.seen) == ("refused", 0, [])
    assert _statuses(report) == dict.fromkeys(SIX, "skipped")
    assert "tokens" in report.reason


def test_the_clone_has_the_plan_of_the_fixture_committed_and_no_remote(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, base = repo
    loaded = _loaded(tmp_path, base)
    other = dict(loaded.plan) | {"proposal.md": "# Proposal\n\nA different why.\n"}
    changed = LoadedCase(case=loaded.case, body=loaded.body, plan=other, diffs=loaded.diffs)
    work = tmp_path / "work"
    work.mkdir()

    clone = make_clone(changed, checkout, work)

    proposal = clone / "openspec" / "changes" / "1-sample-change" / "proposal.md"
    assert (
        git(clone, "remote"),
        git(clone, "status", "--porcelain"),
        git(clone, "rev-parse", "HEAD~1"),
        git(clone, "log", "-1", "--format=%s"),
        proposal.read_text(encoding="utf-8"),
    ) == (
        "",
        "",
        base,
        "docs(openspec): the plan of the fixture (#1)",
        "# Proposal\n\nA different why.\n",
    )


def test_the_clone_shares_the_objects_of_the_repository_it_clones(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, base = repo
    work = tmp_path / "work"
    work.mkdir()

    clone = make_clone(_loaded(tmp_path, base), checkout, work)

    alternates = clone / ".git" / "objects" / "info" / "alternates"
    assert alternates.read_text(encoding="utf-8").strip() == str(checkout / ".git" / "objects")


def test_a_base_that_the_repository_lacks_is_refused_with_the_commit(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, _ = repo
    missing = "f" * 40

    with pytest.raises(ImplementEvalError) as raised:
        run_case(
            _loaded(tmp_path, missing),
            repo=checkout,
            model=ModelScript(say("x")).model(),
            window=WINDOW,
        )

    assert str(raised.value) == (
        f"Fixture sample: this repository lacks the commit {missing}. "
        "Fetch the full history, then run again."
    )


def test_the_item_of_a_fixture_is_the_only_item_it_holds(tmp_path: Path) -> None:
    loaded = load_case(write_fixture(tmp_path))

    items = FixtureItems(loaded)

    item = items.item(1)
    assert item is not None
    assert (item.title, item.body, items.item(2)) == (
        "Make the sample shout",
        loaded.body,
        None,
    )


def test_a_check_of_recorded_results_needs_no_clone_and_matches_the_record(
    tmp_path: Path, programs: ProcessFake
) -> None:
    loaded = load_case(write_fixture(tmp_path))

    reports = check_recorded(loaded)

    assert [(r.result, r.status, r.expected, r.matches) for r in reports] == [
        ("good", "recorded", (), True),
        ("scratch", "recorded", ("diff_scope", "no_scratch"), True),
    ]
    assert programs.calls == []


def test_a_result_that_fails_other_properties_than_recorded_does_not_match(
    tmp_path: Path,
) -> None:
    results = [{"name": "good", "source": "a test", "diff": "good.diff", "fails": ["diff_scope"]}]
    loaded = load_case(write_fixture(tmp_path, case=case_data(results=results)))

    (report,) = check_recorded(loaded)

    assert (report.matches, report.expected, report.first_failed) == (False, ("diff_scope",), None)


def test_a_check_with_commands_applies_the_diff_in_a_clone_and_runs_the_commands(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, base = repo
    programs.answer(
        lambda call: command_text(call) == "uv run devops docs check", ProcessAnswer(returncode=1)
    )

    good, scratch = check_recorded(_loaded(tmp_path, base), repo=checkout, commands=True)

    assert _statuses(good) == SIX_WITH_DOCS_FAILING
    assert (good.matches, scratch.matches) == (True, True)
    assert is_clean_at(checkout, base)


SIX_WITH_DOCS_FAILING = {
    "tests_kept": "pass",
    "diff_scope": "pass",
    "no_scratch": "pass",
    "tasks_ticked": "pass",
    "tests_pass": "pass",
    "verify_passes": "fail",
}


def test_a_diff_that_does_not_apply_leaves_the_command_properties_skipped(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake
) -> None:
    checkout, base = repo
    broken = "diff --git a/src/sample.py b/src/sample.py\n--- a/src/sample.py\n+++ b/src/sample.py\n@@ -1,1 +1,1 @@\n-nothing like it\n+x\n"
    fixture = write_fixture(
        tmp_path / "fixture",
        case=case_data(
            base=base,
            results=[{"name": "broken", "source": "a test", "diff": "broken.diff", "fails": []}],
        ),
        diffs={"broken.diff": broken},
    )

    (report,) = check_recorded(load_case(fixture), repo=checkout, commands=True)

    by_name = {record.name: record for record in report.properties}
    assert by_name["tests_pass"].status == "skipped"
    assert by_name["tests_pass"].detail.startswith("The recorded diff does not apply to the base: ")


def test_the_report_renders_each_result_with_its_cost_and_its_first_failed_property(
    tmp_path: Path, repo: tuple[Path, str], programs: ProcessFake, snapshot: Any
) -> None:
    checkout, base = repo
    loaded = _loaded(tmp_path, base)
    done = run_case(
        loaded,
        repo=checkout,
        model=ModelScript(
            tool_calls(write_call("scratch.py", "x = 1\n"), *the_whole_group()), say("Done.")
        ).model(),
        window=WINDOW,
    )
    fixed = done.model_copy(update={"seconds": 1.5, "input_tokens": 10, "output_tokens": 5})
    report = RunReport(model="example-model", results=(fixed, *check_recorded(loaded)))

    assert render_report(report) == snapshot


def test_the_report_is_written_as_json_in_a_file_named_for_the_moment(tmp_path: Path) -> None:
    report = RunReport(results=tuple(check_recorded(load_case(write_fixture(tmp_path / "f")))))

    path = write_report(report, tmp_path / "reports", datetime(2026, 11, 1, 12, 30, 5, tzinfo=UTC))

    assert path == tmp_path / "reports" / "implement-20261101-123005.json"
    written = json.loads(path.read_text(encoding="utf-8"))
    assert (written["model"], [r["result"] for r in written["results"]]) == (
        "",
        ["good", "scratch"],
    )


def test_a_dry_run_lists_the_steps_and_their_model_requests(tmp_path: Path) -> None:
    loaded = load_case(write_fixture(tmp_path))

    text = render_dry_run([loaded], model="example-model")

    assert text.splitlines() == [
        "Dry run: no request was made, nothing was cloned and no model ran. The steps are:",
        "- sample: issue #1, group 1, base 0123456789ab",
        "",
        "The model requests of a run:",
        f"1. model request example-model for group 1 of item #1 (fixture sample)  [repeated up to {CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS} times]",
    ]


def test_the_sample_plan_is_the_plan_that_the_repository_holds(
    tmp_path: Path, repo: tuple[Path, str]
) -> None:
    checkout, _ = repo
    folder = checkout / "openspec" / "changes" / "1-sample-change"

    assert {name: (folder / name).read_text(encoding="utf-8") for name in PLAN} == PLAN
