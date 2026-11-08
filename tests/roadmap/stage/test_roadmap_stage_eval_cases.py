"""The golden set of the stage job: its cases load, cover the plans of 2026-11-01, and match the
models (#3028)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    NO_COMMIT,
    DefectType,
    GateName,
    StageCase,
    Verdict,
    cases_with_commit,
    load_cases,
    select_cases,
)
from tests.support.paths import REPO_ROOT

# The 37 pull requests of the evaluation of 2026-11-01: 35 merged and 2 open then. Pull request
# 3167 is a plan of the stage job that was closed with `x` in every text (#3200). Pull request
# 3174 is the plan with one group titled `placeholder` (#3264). The case of #3411 is the plan of
# that change before its own check exists: a What Changes item names a path that no group lists.
# The case of #3331 is the plan of that change before the replay rule exists: a group changes a
# check of the stage job and no group task runs the eval replay.
# Pull request 3435 is the plan of #3410. Its good case is the plan as merged, and its reviewed case
# is the same plan without the group that adds the field of the case, so that the group that adds
# the case of a move of the stage modules changes only test files and delivers nothing (#3448).
# Pull request 3278 is the plan of PR #3278 (for #2441) with own-change, scenario code, and reference defects (#3321).
# The case of #3328 is the plan before the prompt-key gate exists: a group adds a field to
# StageProposal and no group changes roadmap_stage_change.md.
EVALUATED_PULLS = frozenset(
    {2975, 2976, 2977, 2978, 2979, 2980, 2981, 2982, 2983, 2984, 2985, 2986, 2987, 2988, 2989}
    | {2990, 2991, 2992, 2993, 2994, 2995, 2996, 2997, 2998, 2999, 3001, 3002}
    | {2719, 2761, 2766, 2857, 2858, 2859, 2870, 2958, 2971, 2972}
    | {3167, 3173, 3174, 3278, 3328, 3331, 3378, 3411, 3435, 3247}
)
SHA_LENGTH = 40
FULL_HASH = re.compile(r"[0-9a-f]{40}")


@pytest.fixture(scope="module")
def cases() -> list[StageCase]:
    return load_cases(REPO_ROOT / CASES_DIRECTORY)


def test_the_set_holds_the_47_plans_and_five_good_ones(cases: list[StageCase]) -> None:
    reviewed = {case.pull for case in cases if case.verdict is not Verdict.GOOD}
    good = [case for case in cases if case.verdict is Verdict.GOOD]

    assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 52, 5)
    assert len(EVALUATED_PULLS) == 47


def test_a_good_case_is_the_twin_of_a_reviewed_case_and_has_no_defect(
    cases: list[StageCase],
) -> None:
    names = {case.name for case in cases}

    good = [case for case in cases if case.verdict is Verdict.GOOD]

    assert all(
        case.defects == () and (case.twin_of is None or case.twin_of in names) for case in good
    )


def test_a_reviewed_case_has_a_defect_with_evidence_and_the_commits_are_shas(
    cases: list[StageCase],
) -> None:
    for case in cases:
        assert len(case.merge_commit) == len(case.base_commit) == SHA_LENGTH
        assert case.verdict is Verdict.GOOD or case.defects
        assert all(defect.evidence.strip() and defect.problem.strip() for defect in case.defects)


def test_every_type_of_defect_is_used_by_the_set(cases: list[StageCase]) -> None:
    used = {defect.type for case in cases for defect in case.defects}

    assert used == set(DefectType)


def test_a_plan_fails_the_schema_of_the_reply_only_when_a_defect_names_the_kind_gate(
    cases: list[StageCase],
) -> None:
    refused = set()
    for case in cases:
        try:
            StageProposal.model_validate(case.plan)
        except ValidationError:
            refused.add(case.name)

    named = {c.name for c in cases if any(d.gate is GateName.KIND for d in c.defects)}

    assert refused == named


def test_the_change_folder_of_a_case_is_in_its_tree(cases: list[StageCase]) -> None:
    case = cases[0]

    tree = case.tree()

    assert tree.has(f"openspec/changes/{case.change}/tasks.md")
    assert tree.has(case.facts.tracked[0]) is True


def test_a_case_with_an_unknown_defect_type_fails_and_names_the_case(
    cases: list[StageCase], tmp_path: Path
) -> None:
    source = REPO_ROOT / CASES_DIRECTORY / cases[0].name
    shutil.copytree(source, tmp_path / "broken")
    meta = json.loads((tmp_path / "broken" / "case.json").read_text(encoding="utf-8"))
    meta["defects"][0]["type"] = "not_a_type"
    (tmp_path / "broken" / "case.json").write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="broken"):
        load_cases(tmp_path)


def test_a_folder_with_no_case_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="no case"):
        load_cases(tmp_path)


def test_cases_are_picked_by_name_or_by_issue_and_cut_by_the_limit(cases: list[StageCase]) -> None:
    first, second = cases[0], cases[1]

    by_name = select_cases(cases, (first.name,), None)
    by_issue = select_cases(cases, (str(second.issue),), None)
    cut = select_cases(cases, (), 2)

    assert ([c.name for c in by_name], [c.name for c in by_issue]) == (
        [first.name],
        [c.name for c in cases if c.issue == second.issue],
    )
    assert [c.name for c in cut] == [first.name, second.name]


def test_a_name_that_picks_no_case_fails(cases: list[StageCase]) -> None:
    with pytest.raises(ConfigurationError, match="no-such-case"):
        select_cases(cases, ("no-such-case",), None)


def test_a_case_reads_its_search_evidence_and_an_old_case_holds_none(
    cases: list[StageCase],
) -> None:
    case = next(c for c in cases if c.pull == 3378)
    old = next(c for c in cases if c.pull != 3378)

    assert set(case.facts.search_evidence) == {
        "devops_cli.roadmap.stage_missing",
        "devops_cli.roadmap.stage",
        "devops_cli.roadmap.stage_",
    }
    assert case.facts.search_evidence["devops_cli.roadmap.stage_"]
    assert old.facts.search_evidence == {}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=False
    )


def test_each_base_commit_of_the_set_is_a_full_hash_of_a_real_commit_or_the_case_reads_none(
    cases: list[StageCase],
) -> None:
    if _git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        pytest.skip("A shallow clone lacks the old commits that the cases name.")

    not_commits = []
    for case in cases:
        if case.base_commit == NO_COMMIT:
            assert any("reads no commit" in note for note in case.notes), case.name
        elif not (
            FULL_HASH.fullmatch(case.base_commit)
            and _git("cat-file", "-e", f"{case.base_commit}^{{commit}}").returncode == 0
        ):
            not_commits.append((case.name, case.base_commit))

    assert not_commits == []


def test_each_merge_commit_of_the_set_is_a_full_hash_or_the_case_reads_none(
    cases: list[StageCase],
) -> None:
    for case in cases:
        assert case.merge_commit == NO_COMMIT or FULL_HASH.fullmatch(case.merge_commit), case.name
        assert (case.merge_commit == NO_COMMIT) == (case.base_commit == NO_COMMIT), case.name


def test_a_case_holds_a_commit_unless_its_base_commit_is_the_null_id(
    cases: list[StageCase],
) -> None:
    held = cases[0]
    unmerged = held.model_copy(update={"base_commit": NO_COMMIT})

    assert (held.has_commit, unmerged.has_commit) == (True, False)
    assert NO_COMMIT == "0" * SHA_LENGTH


def test_the_cases_with_a_commit_keep_the_order_and_the_others_are_named(
    cases: list[StageCase],
) -> None:
    first, second, third = cases[:3]
    unmerged = second.model_copy(update={"base_commit": NO_COMMIT})

    run, left_out = cases_with_commit([first, unmerged, third])

    assert (run, left_out) == ([first, third], (unmerged.name,))


def test_a_selection_of_cases_that_all_hold_a_commit_leaves_none_out(
    cases: list[StageCase],
) -> None:
    run, left_out = cases_with_commit(cases[:2])

    assert (run, left_out) == (cases[:2], ())


def test_a_selection_with_no_case_that_holds_a_commit_fails_and_names_the_cases(
    cases: list[StageCase],
) -> None:
    unmerged = [case.model_copy(update={"base_commit": NO_COMMIT}) for case in cases[:2]]

    with pytest.raises(ConfigurationError, match="no commit") as raised:
        cases_with_commit(unmerged)

    assert all(case.name in str(raised.value) for case in unmerged)
