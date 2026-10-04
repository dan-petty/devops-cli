"""Unit tests for mapping changed source files onto their covering test modules."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ci.cache import resolve_coverage_index_path
from devops_cli.commands.ci import app as ci_app
from devops_cli.core.coverage_index import CoverageIndex, save_index
from devops_cli.core.test_selection import (
    module_path_for_source,
    select_tests_for_sources,
)

runner = CliRunner()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Build a miniature project with a source tree and a matching test tree."""
    src = tmp_path / "src" / "devops_cli"
    (src / "security").mkdir(parents=True)
    (src / "security" / "secrets.py").write_text("VALUE = 1\n", encoding="utf-8")
    (src / "security" / "__init__.py").write_text("", encoding="utf-8")
    (src / "orphan.py").write_text("UNCOVERED = True\n", encoding="utf-8")

    tests = tmp_path / "tests"
    tests.mkdir()
    # Covers by import, but its name matches no convention.
    (tests / "test_credential_flow.py").write_text(
        "from devops_cli.security.secrets import VALUE\n", encoding="utf-8"
    )
    # Covers by naming convention, without importing the module.
    (tests / "test_secrets.py").write_text("def test_noop() -> None: ...\n", encoding="utf-8")
    # Unrelated.
    (tests / "test_unrelated.py").write_text(
        "from devops_cli.other import thing\n", encoding="utf-8"
    )
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# 1. Module path derivation
# ─────────────────────────────────────────────────────────────────────────────


def test_module_path_derived_from_source_layout(project: Path) -> None:
    """A source file maps to its importable dotted module path."""
    path = project / "src" / "devops_cli" / "security" / "secrets.py"
    assert module_path_for_source(path, project) == "devops_cli.security.secrets"


def test_package_init_maps_to_the_package(project: Path) -> None:
    """An `__init__.py` addresses its package, not a module named `__init__`."""
    path = project / "src" / "devops_cli" / "security" / "__init__.py"
    assert module_path_for_source(path, project) == "devops_cli.security"


def test_non_source_paths_have_no_module_path(project: Path) -> None:
    """Files outside the source tree, or that are not Python, map to nothing."""
    (project / "README.md").write_text("# docs\n", encoding="utf-8")
    assert module_path_for_source(project / "README.md", project) is None
    assert module_path_for_source(project / "tests" / "test_secrets.py", project) is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Selection
# ─────────────────────────────────────────────────────────────────────────────


def test_selection_unions_convention_and_import_matches(project: Path) -> None:
    """Both naming convention and actual imports contribute covering tests.

    Convention alone misses a test whose name does not follow the module, and imports
    alone miss a conventionally named test that exercises behaviour indirectly.
    """
    selection = select_tests_for_sources(["src/devops_cli/security/secrets.py"], project)

    assert selection.pytest_targets() == [
        "tests/test_credential_flow.py",
        "tests/test_secrets.py",
    ]
    assert selection.unmapped_sources == []


def test_unrelated_tests_are_not_selected(project: Path) -> None:
    """A test covering a different module is left out of the narrowed run."""
    selection = select_tests_for_sources(["src/devops_cli/security/secrets.py"], project)
    assert "tests/test_unrelated.py" not in selection.pytest_targets()


def test_source_without_covering_tests_is_reported(project: Path) -> None:
    """An uncovered source is surfaced rather than silently yielding an empty run."""
    selection = select_tests_for_sources(["src/devops_cli/orphan.py"], project)

    assert (selection.pytest_targets(), selection.unmapped_sources) == (
        [],
        ["src/devops_cli/orphan.py"],
    )
    assert selection.has_selection is False


def test_test_files_pass_straight_through(project: Path) -> None:
    """A test file supplied directly is run as given."""
    selection = select_tests_for_sources(["tests/test_unrelated.py"], project)
    assert selection.pytest_targets() == ["tests/test_unrelated.py"]


def test_non_python_files_are_ignored_without_being_flagged(project: Path) -> None:
    """Docs and manifests are neither run nor reported as uncovered code."""
    (project / "README.md").write_text("# docs\n", encoding="utf-8")
    selection = select_tests_for_sources(["README.md"], project)

    assert (selection.pytest_targets(), selection.unmapped_sources) == ([], [])


def test_multiple_sources_deduplicate_shared_tests(project: Path) -> None:
    """Two sources covered by one test module produce a single pytest target."""
    selection = select_tests_for_sources(
        ["src/devops_cli/security/secrets.py", "tests/test_secrets.py"], project
    )
    assert selection.pytest_targets().count("tests/test_secrets.py") == 1


def test_absolute_paths_are_accepted(project: Path) -> None:
    """Pre-commit may pass absolute paths; they resolve the same as relative ones."""
    absolute = project / "src" / "devops_cli" / "security" / "secrets.py"
    assert select_tests_for_sources([absolute], project).pytest_targets() == [
        "tests/test_credential_flow.py",
        "tests/test_secrets.py",
    ]


def test_missing_tests_tree_yields_no_targets(tmp_path: Path) -> None:
    """A project without a tests directory selects nothing rather than raising."""
    (tmp_path / "src" / "devops_cli").mkdir(parents=True)
    (tmp_path / "src" / "devops_cli" / "mod.py").write_text("X = 1\n", encoding="utf-8")

    selection = select_tests_for_sources(["src/devops_cli/mod.py"], tmp_path)
    assert (selection.pytest_targets(), selection.unmapped_sources) == (
        [],
        ["src/devops_cli/mod.py"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. CLI behaviour
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_runs_only_the_covering_tests(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    """Passing a source file narrows the pytest invocation to its covering tests."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "src/devops_cli/security/secrets.py"])

    assert result.exit_code == 0
    assert "tests/test_credential_flow.py" in called[0]
    assert "tests/test_unrelated.py" not in called[0]


def test_cli_without_paths_runs_the_whole_suite(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """Omitting paths preserves the original full-suite behaviour."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test"])

    assert result.exit_code == 0
    assert not any(arg.startswith("tests/") for arg in called[0])


def test_cli_falls_back_to_full_suite_for_uncovered_sources(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """An uncovered source escalates to the full suite rather than verifying nothing."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "src/devops_cli/orphan.py"])

    assert result.exit_code == 0
    assert not any(arg.startswith("tests/") for arg in called[0])
    assert "Falling back to the full suite" in result.output


def test_cli_refuses_a_silent_green_with_no_fallback(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """With --no-fallback an uncovered source fails instead of reporting success.

    Reporting a pass without executing a single test is the one outcome a pre-commit
    hook must never produce.
    """
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "src/devops_cli/orphan.py", "--no-fallback"])

    assert result.exit_code == 1
    assert called == []
    assert "Refusing to report success" in result.output


def test_cli_exits_cleanly_for_documentation_only_changes(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A docs-only commit runs nothing and succeeds, without a spurious failure."""
    called: list[list[str]] = []
    (project / "README.md").write_text("# docs\n", encoding="utf-8")
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "README.md"])

    assert (result.exit_code, called) == (0, [])


# ─────────────────────────────────────────────────────────────────────────────
# 4. Coverage index test selection and fallback lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_selects_tests_from_coverage_index_and_names_selector(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """With an index mapping src/a.py to test_a.py and test_far.py, test runs both and names index."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_far.py").write_text("def test_far(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py", "tests/test_far.py"]},
        source_hashes={"src/a.py": "h_a", "tests/test_a.py": "h_ta", "tests/test_far.py": "h_tf"},
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "tests/test_a.py": "h_ta",
            "tests/test_far.py": "h_tf",
        },
    )

    result = runner.invoke(ci_app, ["test", "src/a.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, targets, "coverage index" in result.output) == (
        0,
        ["tests/test_a.py", "tests/test_far.py"],
        True,
    )


def test_cli_test_selects_tests_for_modified_files_since_build(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """When a file is modified since index build, its covering tests are also selected."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "src" / "b.py").write_text("B = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_b.py").write_text("def test_b(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"], "src/b.py": ["tests/test_b.py"]},
        source_hashes={
            "src/a.py": "h_a",
            "src/b.py": "h_b_old",
            "tests/test_a.py": "h_ta",
            "tests/test_b.py": "h_tb",
        },
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "src/b.py": "h_b_new",
            "tests/test_a.py": "h_ta",
            "tests/test_b.py": "h_tb",
        },
    )

    result = runner.invoke(ci_app, ["test", "src/a.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, targets) == (
        0,
        ["tests/test_a.py", "tests/test_b.py"],
    )


def test_cli_test_added_test_file_selects_itself_without_fallback(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A newly added test file selects itself and causes no fallback."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_new.py").write_text("def test_new(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={"src/a.py": "h_a", "tests/test_a.py": "h_ta"},
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "tests/test_a.py": "h_ta",
            "tests/test_new.py": "h_new",
        },
    )

    result_direct = runner.invoke(ci_app, ["test", "tests/test_new.py", "--no-fallback"])
    targets_direct = [arg for arg in called[0] if arg.startswith("tests/")]

    result_drift = runner.invoke(ci_app, ["test", "src/a.py", "--no-fallback"])
    targets_drift = [arg for arg in called[1] if arg.startswith("tests/")]

    assert (
        result_direct.exit_code,
        targets_direct,
        result_drift.exit_code,
        targets_drift,
    ) == (
        0,
        ["tests/test_new.py"],
        0,
        ["tests/test_a.py", "tests/test_new.py"],
    )


def test_cli_test_deleted_test_file_is_dropped(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A deleted test file in the index is not passed to pytest."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py", "tests/test_far.py"]},
        source_hashes={"src/a.py": "h_a", "tests/test_a.py": "h_ta"},
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {"src/a.py": "h_a", "tests/test_a.py": "h_ta"},
    )

    result = runner.invoke(ci_app, ["test", "src/a.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, targets) == (0, ["tests/test_a.py"])


def test_cli_test_trigger_file_conftest_forces_full_run(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """tests/conftest.py forces full suite run with or without index, and fails on --no-fallback."""
    (project / "tests" / "conftest.py").write_text("# fixture\n", encoding="utf-8")
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={"src/a.py": "h_a", "tests/conftest.py": "h_c"},
        built_at=100.0,
    )

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {"src/a.py": "h_a", "tests/conftest.py": "h_c"},
    )

    res_no_idx = runner.invoke(ci_app, ["test", "tests/conftest.py"])
    targets_no_idx = [arg for arg in called[0] if arg.startswith("tests/")]

    save_index(index, index_path)
    res_with_idx = runner.invoke(ci_app, ["test", "tests/conftest.py"])
    targets_with_idx = [arg for arg in called[1] if arg.startswith("tests/")]

    res_no_fb = runner.invoke(ci_app, ["test", "tests/conftest.py", "--no-fallback"])

    assert (
        res_no_idx.exit_code,
        targets_no_idx,
        "tests/conftest.py" in res_no_idx.output,
        res_with_idx.exit_code,
        targets_with_idx,
        "tests/conftest.py" in res_with_idx.output,
        res_no_fb.exit_code,
        "tests/conftest.py" in res_no_fb.output,
    ) == (0, [], True, 0, [], True, 1, True)


def test_cli_test_trigger_file_modified_since_build_forces_full_run(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A trigger file modified since build forces a full run and names the trigger file."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={"src/a.py": "h_a", "pyproject.toml": "h_old"},
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {"src/a.py": "h_a", "pyproject.toml": "h_new"},
    )

    result = runner.invoke(ci_app, ["test", "src/a.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, targets, "pyproject.toml" in result.output) == (0, [], True)


def test_cli_test_helper_without_index_runs_importing_tests(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """With no index, tests/helper.py runs tests importing it and never passes helper itself."""
    (project / "tests" / "helper.py").write_text("HELPER = 1\n", encoding="utf-8")
    (project / "tests" / "test_importing.py").write_text(
        "from tests.helper import HELPER\n", encoding="utf-8"
    )
    (project / "tests" / "test_other.py").write_text("def test_x(): pass\n", encoding="utf-8")

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "tests/helper.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (
        result.exit_code,
        targets,
        "tests/helper.py" not in targets,
    ) == (0, ["tests/test_importing.py"], True)


def test_cli_test_text_fallback_with_no_index_and_version_1_index(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """Text-based selector is attributed when index is missing or version 1."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    res_no_idx = runner.invoke(ci_app, ["test", "src/devops_cli/security/secrets.py"])

    index_path = resolve_coverage_index_path(project)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text('{"format_version": 1, "covering_tests": {}}', encoding="utf-8")
    res_v1_idx = runner.invoke(ci_app, ["test", "src/devops_cli/security/secrets.py"])

    assert (
        res_no_idx.exit_code,
        "text-based selector" in res_no_idx.output,
        res_v1_idx.exit_code,
        "text-based selector" in res_v1_idx.output,
    ) == (0, True, 0, True)


def test_cli_test_unindexed_source_falls_back_per_source(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """An index with src/a.py but not src/c.py runs index tests for a.py and text tests for c.py."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "src" / "c.py").write_text("C = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_c.py").write_text("import c\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={
            "src/a.py": "h_a",
            "src/c.py": "h_c",
            "tests/test_a.py": "h_ta",
            "tests/test_c.py": "h_tc",
        },
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "src/c.py": "h_c",
            "tests/test_a.py": "h_ta",
            "tests/test_c.py": "h_tc",
        },
    )

    result = runner.invoke(ci_app, ["test", "src/a.py", "src/c.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (
        result.exit_code,
        targets,
        "src/a.py → tests/test_a.py (coverage index)" in result.output,
        "src/c.py → tests/test_c.py (text-based selector)" in result.output,
    ) == (
        0,
        ["tests/test_a.py", "tests/test_c.py"],
        True,
        True,
    )
