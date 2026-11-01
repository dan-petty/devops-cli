"""The golden set of the stage job: its cases load, cover the plans of 2026-11-01, and match the
models (#3028)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.stage_change import StageProposal
from devops_cli.roadmap.stage_eval_cases import (
    CASES_DIRECTORY,
    DefectType,
    GateName,
    StageCase,
    Verdict,
    load_cases,
    select_cases,
)
from tests.support.paths import REPO_ROOT

# The 37 pull requests of the evaluation of 2026-11-01: 35 merged and 2 open then.
EVALUATED_PULLS = frozenset(
    {2975, 2976, 2977, 2978, 2979, 2980, 2981, 2982, 2983, 2984, 2985, 2986, 2987, 2988, 2989}
    | {2990, 2991, 2992, 2993, 2994, 2995, 2996, 2997, 2998, 2999, 3001, 3002}
    | {2719, 2761, 2766, 2857, 2858, 2859, 2870, 2958, 2971, 2972}
)
SHA_LENGTH = 40


@pytest.fixture(scope="module")
def cases() -> list[StageCase]:
    return load_cases(REPO_ROOT / CASES_DIRECTORY)


def test_the_set_holds_the_37_plans_and_three_good_ones(cases: list[StageCase]) -> None:
    reviewed = {case.pull for case in cases if case.verdict is not Verdict.GOOD}
    good = [case for case in cases if case.verdict is Verdict.GOOD]

    assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 40, 3)
    assert len(EVALUATED_PULLS) == 37


def test_a_good_case_is_the_twin_of_a_reviewed_case_and_has_no_defect(
    cases: list[StageCase],
) -> None:
    names = {case.name for case in cases}

    good = [case for case in cases if case.verdict is Verdict.GOOD]

    assert all(case.defects == () and case.twin_of in names for case in good)


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
