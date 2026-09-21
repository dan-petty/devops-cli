"""Unit tests for mapping changed source files onto their covering test modules."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import app as ci_app
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
