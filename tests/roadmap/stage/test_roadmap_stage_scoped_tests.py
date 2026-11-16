"""Stage surfaces scoped tests in plan reads (#3993)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.roadmap.implement.implement_scoped_ci import ScopedTests
from devops_cli.roadmap.stage.stage_change import StageGroup
from devops_cli.roadmap.stage.stage_scoped_tests import (
    apply_scoped_tests,
    apply_scoped_tests_to_groups,
)
from tests.support.builders import make_stage_proposal


def _make_group(
    *,
    reads: list[str] | None = None,
    changes: list[str] | None = None,
    creates: list[str] | None = None,
) -> StageGroup:
    changes_list = changes or ["src/devops_cli/sample.py"]
    creates_list = creates or []
    creates_lines = {p: 10 for p in creates_list}
    return StageGroup(
        title="Test group",
        kind="behavior",
        reads=reads or [],
        changes=changes_list,
        creates=creates_list,
        creates_lines=creates_lines,
        test="Run test",
        implementation="Implement feature",
        verify="uv run pytest",
    )


def test_source_change_selects_test_in_reads(tmp_path: Path) -> None:
    source_file = tmp_path / "src/devops_cli/shout.py"
    test_file = tmp_path / "tests/test_shout.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text("from devops_cli.shout import VALUE\n", encoding="utf-8")

    group = _make_group(
        reads=["docs/SAMPLE.md"],
        changes=["src/devops_cli/shout.py"],
    )

    new_groups, warnings = apply_scoped_tests_to_groups(tmp_path, [group])

    assert len(new_groups) == 1
    assert "tests/test_shout.py" in new_groups[0].reads
    assert "docs/SAMPLE.md" in new_groups[0].reads
    assert warnings == ()


def test_scoped_test_already_in_reads_preserved_once(tmp_path: Path) -> None:
    source_file = tmp_path / "src/devops_cli/shout.py"
    test_file = tmp_path / "tests/test_shout.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text("from devops_cli.shout import VALUE\n", encoding="utf-8")

    group = _make_group(
        reads=["docs/SAMPLE.md", "tests/test_shout.py"],
        changes=["src/devops_cli/shout.py"],
    )

    new_groups, warnings = apply_scoped_tests_to_groups(tmp_path, [group])

    assert len(new_groups) == 1
    assert new_groups[0].reads.count("tests/test_shout.py") == 1
    assert new_groups[0].reads == ["docs/SAMPLE.md", "tests/test_shout.py"]
    assert warnings == ()


def test_no_scoped_tests_leaves_reads_unchanged(tmp_path: Path) -> None:
    source_file = tmp_path / "src/devops_cli/uncovered.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("VALUE = 1\n", encoding="utf-8")

    group = _make_group(
        reads=["docs/README.md"],
        changes=["src/devops_cli/uncovered.py"],
    )

    new_groups, warnings = apply_scoped_tests_to_groups(tmp_path, [group])

    assert len(new_groups) == 1
    assert new_groups[0].reads == ["docs/README.md"]
    assert warnings == ()


def test_missing_scoped_test_path_omitted_and_warns(tmp_path: Path) -> None:
    group = _make_group(
        reads=["docs/README.md"],
        changes=["src/devops_cli/shout.py"],
    )
    missing_path = "tests/test_missing_file.py"

    new_groups, warnings = apply_scoped_tests_to_groups(
        tmp_path,
        [group],
        planner=lambda s, c: ScopedTests(paths=(missing_path,)),
    )

    assert len(new_groups) == 1
    assert missing_path not in new_groups[0].reads
    assert new_groups[0].reads == ["docs/README.md"]
    assert len(warnings) == 1
    assert missing_path in warnings[0]


def test_apply_scoped_tests_on_proposal(tmp_path: Path) -> None:
    source_file = tmp_path / "src/devops_cli/shout.py"
    test_file = tmp_path / "tests/test_shout.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text("from devops_cli.shout import VALUE\n", encoding="utf-8")

    group = _make_group(
        reads=["docs/README.md"],
        changes=["src/devops_cli/shout.py"],
    )
    proposal = make_stage_proposal(groups=[group])

    updated_proposal, warnings = apply_scoped_tests(tmp_path, proposal)

    assert "tests/test_shout.py" in updated_proposal.groups[0].reads
    assert "docs/README.md" in updated_proposal.groups[0].reads
    assert warnings == ()
