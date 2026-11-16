"""`devops roadmap stage`: a task group changes at most 5 files, unless it moves a prefix (#3995).

A task group lists at most `MAX_GROUP_CHANGES` (5) files in `changes`, unless the group is an
exempt prefix move whose `changes` holds only the old modules of one prefix move and the modules
that the group creates. A group that exceeds the limit is refused by the `group-files` gate.
"""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_change import (
    MAX_GROUP_CHANGES,
    ProposalGate,
    StageGroup,
    check_gates,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

_TEST = "tests/roadmap/test_sample.py"
_SRC_1 = "src/devops_cli/mod1.py"
_SRC_2 = "src/devops_cli/mod2.py"
_SRC_3 = "src/devops_cli/mod3.py"
_SRC_4 = "src/devops_cli/mod4.py"
_SRC_5 = "src/devops_cli/mod5.py"
_SRC_6 = "src/devops_cli/mod6.py"

_PREFIX_OLD_1 = "src/devops_cli/box_a.py"
_PREFIX_OLD_2 = "src/devops_cli/box_b.py"
_PREFIX_OLD_3 = "src/devops_cli/box_c.py"
_PREFIX_OLD_4 = "src/devops_cli/box_d.py"
_PREFIX_OLD_5 = "src/devops_cli/box_e.py"

_PREFIX_NEW_1 = "src/devops_cli/box/a.py"
_PREFIX_NEW_2 = "src/devops_cli/box/b.py"
_PREFIX_NEW_3 = "src/devops_cli/box/c.py"
_PREFIX_NEW_4 = "src/devops_cli/box/d.py"
_PREFIX_NEW_5 = "src/devops_cli/box/e.py"

_DOC = "docs/ROADMAP_WORKFLOW.md"

TREE = StagedTree(
    [
        _TEST,
        _SRC_1,
        _SRC_2,
        _SRC_3,
        _SRC_4,
        _SRC_5,
        _SRC_6,
        _PREFIX_OLD_1,
        _PREFIX_OLD_2,
        _PREFIX_OLD_3,
        _PREFIX_OLD_4,
        _PREFIX_OLD_5,
        _DOC,
    ]
)


def _make_group(
    changes: list[str],
    *,
    creates: list[str] | None = None,
    title: str = "Work on the task",
    kind: str = "behavior",
    test: str | None = f"Write tests in `{_TEST}`",
    implementation: str = "Implement the requested change",
    verify: str | None = f"uv run devops ci test {_TEST}",
) -> StageGroup:
    creates_list = creates or []
    return StageGroup.model_validate(
        {
            "title": title,
            "kind": kind,
            "reads": [],
            "changes": changes,
            "creates": creates_list,
            "creates_lines": {p: 10 for p in creates_list},
            "test": test,
            "implementation": implementation,
            "verify": verify,
        }
    )


def test_constant_max_group_changes() -> None:
    assert MAX_GROUP_CHANGES == 5


def test_proposal_gate_enum_member() -> None:
    assert ProposalGate.GROUP_FILES == "group-files"


def test_a_group_over_the_limit_is_refused() -> None:
    first = _make_group([_SRC_1], title="First group")
    second = _make_group(
        [_SRC_1, _SRC_2, _SRC_3, _SRC_4, _SRC_5, _SRC_6],
        title="Wire the check",
    )
    proposal = make_stage_proposal(groups=[first, second])

    found = check_gates(proposal, [], TREE, registry=())

    (problem,) = found[ProposalGate.GROUP_FILES]
    assert "2" in problem
    assert "Wire the check" in problem
    assert "6" in problem
    assert "5" in problem


def test_a_group_at_the_limit_is_accepted() -> None:
    group = _make_group([_SRC_1, _SRC_2, _SRC_3, _SRC_4, _SRC_5])
    proposal = make_stage_proposal(groups=[group])

    found = check_gates(proposal, [], TREE, registry=())

    assert found[ProposalGate.GROUP_FILES] == []


def test_a_prefix_move_over_the_limit_is_accepted() -> None:
    old_paths = [_PREFIX_OLD_1, _PREFIX_OLD_2, _PREFIX_OLD_3, _PREFIX_OLD_4, _PREFIX_OLD_5]
    new_paths = [_PREFIX_NEW_1, _PREFIX_NEW_2, _PREFIX_NEW_3, _PREFIX_NEW_4, _PREFIX_NEW_5]
    group = _make_group(old_paths + new_paths, creates=new_paths)
    proposal = make_stage_proposal(groups=[group])

    found = check_gates(proposal, [], TREE, registry=())

    assert found[ProposalGate.GROUP_FILES] == []


def test_a_prefix_move_with_an_extra_document_is_refused() -> None:
    old_paths = [_PREFIX_OLD_1, _PREFIX_OLD_2, _PREFIX_OLD_3, _PREFIX_OLD_4, _PREFIX_OLD_5]
    new_paths = [_PREFIX_NEW_1, _PREFIX_NEW_2, _PREFIX_NEW_3, _PREFIX_NEW_4, _PREFIX_NEW_5]
    group = _make_group(old_paths + new_paths + [_DOC], creates=new_paths)
    proposal = make_stage_proposal(groups=[group])

    found = check_gates(proposal, [], TREE, registry=())

    (problem,) = found[ProposalGate.GROUP_FILES]
    assert "11" in problem
