"""`devops roadmap stage`: a group that moves a name prefix covers every module of it (#3372).

The check reads the move from an old path in `changes` and a new path under `<folder>/<prefix>/`
in `creates`. It requires every top-level Python module of the prefix in the tree to appear in the
`changes` of some group, and it refuses a `! git grep` verify literal that names one module.
"""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_change import StageGroup, check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

_TEST = "tests/roadmap/test_roadmap_stage_move_prefix.py"
TREE = StagedTree(
    [
        "src/devops_cli/roadmap/stage_ready.py",
        "src/devops_cli/roadmap/stage_verify.py",
        "src/devops_cli/roadmap/status.py",
        _TEST,
    ]
)
_READY = "src/devops_cli/roadmap/stage_ready.py"
_VERIFY = "src/devops_cli/roadmap/stage_verify.py"
_READY_NEW = "src/devops_cli/roadmap/stage/ready.py"
_VERIFY_NEW = "src/devops_cli/roadmap/stage/verify.py"


def _group(
    changes: list[str],
    creates: list[str],
    *,
    verify: str = f"uv run devops ci test {_TEST}",
) -> StageGroup:
    """A `behavior` group that moves `changes` and creates `creates`, with a valid task and
    check."""
    return StageGroup.model_validate(
        {
            "title": "Move the modules of the prefix",
            "kind": "behavior",
            "reads": [],
            "changes": changes,
            "creates": creates,
            "creates_lines": {path: 20 for path in creates},
            "test": "Write a test for the moved modules",
            "implementation": "Move every module of the prefix into its subpackage",
            "verify": verify,
        }
    )


def _move(verify: str = f"uv run devops ci test {_TEST}") -> StageGroup:
    return _group([_READY, _READY_NEW], [_READY_NEW], verify=verify)


def _check(groups: list[StageGroup], tree: StagedTree = TREE) -> list[str]:
    return check_proposal(make_stage_proposal(groups=groups), [], tree, registry=())


# ── The prefix coverage rule ──────────────────────────────────────────────────


def test_a_move_group_that_omits_a_module_of_its_prefix_is_refused() -> None:
    problems = _check([_move()])

    assert any(f"`{_VERIFY}`" in problem for problem in problems)


def test_a_later_group_that_moves_the_missing_module_is_accepted() -> None:
    first = _move()
    later = _group([_VERIFY, _VERIFY_NEW], [_VERIFY_NEW])

    problems = _check([first, later])

    assert not any(_READY in problem or _VERIFY in problem for problem in problems)


def test_a_module_of_another_prefix_is_not_required() -> None:
    problems = _check([_move()])

    assert not any("`src/devops_cli/roadmap/status.py`" in problem for problem in problems)


def test_a_test_module_of_the_folder_is_not_required() -> None:
    tree = StagedTree([_READY, "tests/roadmap/test_roadmap_stage_ready.py", _TEST])

    problems = _check([_move()], tree)

    assert not any("test_roadmap_stage_ready.py" in problem for problem in problems)


# ── The verify command of a move group ───────────────────────────────────────


def test_a_verify_that_names_one_module_of_the_prefix_is_refused() -> None:
    problems = _check([_move("! git grep -n -F devops_cli.roadmap.stage_ready src/ tests/")])

    assert any("names one module of the moved prefix" in problem for problem in problems)


def test_a_verify_that_names_the_bare_prefix_is_refused() -> None:
    problems = _check([_move("! git grep -n -F devops_cli.roadmap.stage src/ tests/")])

    assert any("names one module of the moved prefix" in problem for problem in problems)


def test_a_verify_that_names_the_dotted_prefix_is_accepted() -> None:
    problems = _check([_move("! git grep -n -F devops_cli.roadmap.stage_ src/ tests/")])

    assert not any("names one module of the moved prefix" in problem for problem in problems)
