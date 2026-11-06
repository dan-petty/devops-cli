"""`devops new command` and `devops new test` write the files of a command or a test in project
form, write over no file, and print the steps that stay manual (#3204)."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

GROUP_MODULE = '''"""The sample group."""

from __future__ import annotations

import typer

from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

app = new_typer(help=HELP.sample.app, no_args_is_help=True)


@app.command("existing", help=HELP.sample.existing)
def existing() -> None:
    """An older command."""
    raise typer.Exit(0)
'''

HELP_FILE = '''"""Help."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SampleCommandHelp:
    app: str = "The sample group."
    existing: str = "An older command."


@dataclass(frozen=True)
class HelpCatalog:
    sample: SampleCommandHelp = field(default_factory=SampleCommandHelp)
'''

MESSAGES_FILE = '''"""Messages."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SampleMessages:
    existing_done: str = "Done."


@dataclass(frozen=True)
class LanguageCatalog:
    sample: SampleMessages = field(default_factory=SampleMessages)
'''

GITHUB_MODULE = '''"""Reads issues."""

from devops_cli.github.session import get_github_session
'''


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository with a `sample` command group, its language entries, and two modules."""
    files = {
        "pyproject.toml": "",
        "src/devops_cli/commands/sample.py": GROUP_MODULE,
        "src/devops_cli/lang/en/help.py": HELP_FILE,
        "src/devops_cli/lang/en/messages.py": MESSAGES_FILE,
        "src/devops_cli/config/constants.py": '"""Constants."""\n',
        "src/devops_cli/github/issues.py": GITHUB_MODULE,
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_the_new_group_lists_the_command_and_test_subcommands(cli: Callable[..., Any]) -> None:
    """The help of `devops new` names both scaffold commands."""
    result = cli("new", "--help")

    assert (result.exit_code, "command" in result.output, "test" in result.output) == (
        0,
        True,
        True,
    )


def test_the_test_scaffold_writes_the_test_at_the_mirror_path(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """A module under `src/devops_cli/config/` gets its test under `tests/config/`."""
    result = cli("new", "test", "src/devops_cli/config/constants.py")

    written = repo / "tests/config/test_constants.py"
    assert (result.exit_code, written.is_file(), "pytest.fail" in written.read_text()) == (
        0,
        True,
        True,
    )


def test_the_test_scaffold_refuses_a_flat_test_path_and_names_the_mirror_path(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """`tests/test_constants.py` is no source module, so the command names the mirror path."""
    before = _tree(repo)

    result = cli("new", "test", "tests/test_constants.py")

    assert (result.exit_code, "tests/config/test_constants.py" in result.output) == (1, True)
    assert _tree(repo) == before


def test_the_test_scaffold_refuses_a_path_outside_the_source_package(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """A path outside `src/devops_cli` gets the mirror rule in the error."""
    result = cli("new", "test", "docs/TESTING.md")

    assert (result.exit_code, "mirror path" in result.output) == (1, True)


def test_the_test_scaffold_asks_for_the_fixture_of_the_edge_the_module_reaches(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """A module that imports the GitHub session gets a test that asks for `github_api`."""
    cli("new", "test", "src/devops_cli/github/issues.py")

    text = (repo / "tests/github/test_issues.py").read_text()
    assert 'usefixtures("github_api")' in text
    assert re.search(r"^def test_issues_\w+\(\) -> None:$", text, re.MULTILINE)


def test_the_scaffold_writes_over_no_file(repo: Path, cli: Callable[..., Any]) -> None:
    """The second run exits nonzero, names the test path and leaves the file as it was."""
    cli("new", "test", "src/devops_cli/config/constants.py")
    target = repo / "tests/config/test_constants.py"
    target.write_text("# edited\n", encoding="utf-8")

    result = cli("new", "test", "src/devops_cli/config/constants.py")

    assert (result.exit_code, "tests/config/test_constants.py" in result.output) == (1, True)
    assert target.read_text() == "# edited\n"


def test_a_dry_run_lists_the_paths_and_writes_nothing(repo: Path, cli: Callable[..., Any]) -> None:
    """`--dry-run` names the group module, both language files and the test, and changes nothing."""
    before = _tree(repo)

    result = cli("new", "command", "sample", "hello", "--dry-run")

    assert result.exit_code == 0
    for path in (
        "src/devops_cli/commands/sample.py",
        "src/devops_cli/lang/en/help.py",
        "src/devops_cli/lang/en/messages.py",
        "tests/commands/test_sample_hello.py",
    ):
        assert path in result.output
    assert _tree(repo) == before


def _class_strings(path: Path, class_name: str) -> dict[str, str]:
    """The string fields of a class in a source file, read from its syntax tree."""
    tree = ast.parse(path.read_text())
    (node,) = (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name)
    return {
        stmt.target.id: ast.literal_eval(stmt.value)
        for stmt in node.body
        if isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.target, ast.Name)
        and stmt.value is not None
    }


def test_the_command_scaffold_writes_the_function_and_the_language_entries(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """The group module holds the function, and each language class holds its new entry."""
    result = cli("new", "command", "sample", "hello")

    assert result.exit_code == 0
    group = (repo / "src/devops_cli/commands/sample.py").read_text()
    assert '@app.command("hello", help=HELP.sample.hello)' in group
    assert "def hello() -> None:" in group
    assert "from devops_cli.dry_run.decorator import dry_run_class" in group
    help_fields = _class_strings(repo / "src/devops_cli/lang/en/help.py", "SampleCommandHelp")
    message_fields = _class_strings(repo / "src/devops_cli/lang/en/messages.py", "SampleMessages")
    assert "hello" in help_fields
    assert "hello_done" in message_fields


def test_the_generated_help_has_at_most_three_sentences_and_names_its_page(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """The help of the new command is short and names `docs/commands/<group>.md`."""
    cli("new", "command", "sample", "hello")

    help_text = _class_strings(repo / "src/devops_cli/lang/en/help.py", "SampleCommandHelp")[
        "hello"
    ]
    sentences = re.split(r"(?<=[.!?])\s+", help_text.strip())
    assert (len(sentences) <= 3, "docs/commands/sample.md" in help_text) == (True, True)


def test_the_command_scaffold_writes_a_failing_test_with_match_in_the_mirror_folder(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """The test file of the command sits in `tests/commands/` and fails until it is written."""
    cli("new", "command", "sample", "hello")

    text = (repo / "tests/commands/test_sample_hello.py").read_text()
    assert "pytest.fail(" in text
    assert re.search(r"pytest\.raises\(\w+, match=", text)


def test_the_command_scaffold_prints_the_steps_that_stay_manual(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """The output names the command that regenerates the pages of the commands."""
    result = cli("new", "command", "sample", "hello")

    assert "devops docs generate --sync-readme" in result.output


def test_the_command_scaffold_refuses_a_group_that_has_no_module(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """An unknown group exits nonzero, names the module it looked for and writes no file."""
    before = _tree(repo)

    result = cli("new", "command", "missing", "hello")

    assert (result.exit_code, "src/devops_cli/commands/missing.py" in result.output) == (1, True)
    assert _tree(repo) == before


def test_the_command_scaffold_refuses_a_command_that_the_group_has(
    repo: Path, cli: Callable[..., Any]
) -> None:
    """A second run for the same command names the function it would add twice."""
    cli("new", "command", "sample", "hello")
    before = _tree(repo)

    result = cli("new", "command", "sample", "hello")

    assert (result.exit_code, "already defines the function hello" in result.output) == (1, True)
    assert _tree(repo) == before


@pytest.mark.parametrize("name", ["import", "Hello", "1hello"])
def test_the_command_scaffold_refuses_a_name_that_is_no_function_name(
    repo: Path, cli: Callable[..., Any], name: str
) -> None:
    """A Python keyword, an upper-case letter or a leading digit exits nonzero
    and writes no file, as the function of the command could not be named."""
    before = _tree(repo)

    result = cli("new", "command", "sample", name)

    assert (result.exit_code, "is not a name" in result.output, _tree(repo)) == (1, True, before)
