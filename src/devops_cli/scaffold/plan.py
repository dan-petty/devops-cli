"""Plan the files of a new command or a new test, then write them (#3204).

A plan holds the whole text of every file it creates or edits and the steps that stay manual. It
is computed from the files on disk and writes nothing, so `--dry-run` prints it and a conflict
is found before any file changes. The scaffold never writes over a file: it creates files that do
not exist, and it adds text to a module or a language file without touching the text there.
"""

from __future__ import annotations

import json
import keyword
from dataclasses import dataclass
from pathlib import Path

from devops_cli.core.templating import render_template
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.scaffold.edges import edge_fixtures
from devops_cli.scaffold.edits import (
    add_import,
    append_to_class,
    append_to_module,
    catalog_class,
    class_fields,
    function_names,
)

SOURCE_PACKAGE = Path("src/devops_cli")
TESTS_ROOT = Path("tests")
HELP_FILE = SOURCE_PACKAGE / "lang/en/help.py"
MESSAGES_FILE = SOURCE_PACKAGE / "lang/en/messages.py"
COMMANDS_DIR = SOURCE_PACKAGE / "commands"
HELP_CATALOG = "HelpCatalog"
MESSAGES_CATALOG = "LanguageCatalog"
DOCS_PAGE_DIR = "docs/commands"
# The imports a command function needs, as (module, name).
COMMAND_IMPORTS = (
    ("devops_cli.dry_run.decorator", "dry_run_class"),
    ("devops_cli.lang", "HELP"),
    ("devops_cli.lang", "MESSAGES"),
    ("devops_cli.output", "print_success"),
    ("devops_cli.telemetry", "trace_span"),
)


@dataclass(frozen=True)
class FileChange:
    """The text of one file after the scaffold: new when the file does not exist yet."""

    path: Path
    content: str
    created: bool


@dataclass(frozen=True)
class ScaffoldPlan:
    """The changes of one scaffold, in write order, and the steps that only a person can do."""

    changes: tuple[FileChange, ...]
    steps: tuple[str, ...]


def apply_plan(root: Path, plan: ScaffoldPlan) -> None:
    """Write each change of a plan under the root."""
    for change in plan.changes:
        target = root / change.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(change.content, encoding="utf-8")


def _refuse(problems: list[str]) -> None:
    """Raise one error that lists every problem, when there is any."""
    if problems:
        raise ValidationError("\n".join(problems), field="scaffold")


def _read(root: Path, path: Path) -> str:
    return (root / path).read_text(encoding="utf-8")


def mirror_test_path(module: Path) -> Path:
    """The path of the test of a source module: `tests/<package path>/test_<module>.py`."""
    relative = module.relative_to(SOURCE_PACKAGE)
    return TESTS_ROOT / relative.parent / f"test_{relative.stem}.py"


def _mirror_hint(root: Path, path: Path) -> str:
    """The mirror path of the one source module that a flat test path names, else an empty text."""
    stem = path.stem.removeprefix("test_")
    matches = sorted((root / SOURCE_PACKAGE).rglob(f"{stem}.py"))
    if len(matches) != 1:
        return ""
    return MESSAGES.new.mirror_hint.format(
        path=mirror_test_path(matches[0].relative_to(root)).as_posix()
    )


def _string_entry(name: str, *parts: str) -> str:
    """The source of a `str` field of a language class, in parentheses when it has several parts."""
    if len(parts) == 1:
        return f"{name}: str = {json.dumps(parts[0])}"
    body = "\n".join(f"    {json.dumps(part)}" for part in parts)
    return f"{name}: str = (\n{body}\n)"


def plan_test(root: Path, module: str) -> ScaffoldPlan:
    """Plan the test file of a module of the source package."""
    given = Path(module)
    absolute = given if given.is_absolute() else Path.cwd() / given
    try:
        relative = absolute.resolve().relative_to(root.resolve())
    except ValueError:
        relative = given
    if relative.parent.parts[:2] != SOURCE_PACKAGE.parts or relative.suffix != ".py":
        hint = _mirror_hint(root, relative) if relative.parts[:1] == TESTS_ROOT.parts else ""
        raise ValidationError(
            MESSAGES.new.not_source_module.format(path=relative.as_posix(), hint=hint).strip(),
            field="module",
        )
    problems = []
    if not (root / relative).is_file():
        problems.append(MESSAGES.new.module_missing.format(path=relative.as_posix()))
    if relative.stem == "__init__" or relative.parent == SOURCE_PACKAGE:
        problems.append(MESSAGES.new.module_has_no_mirror.format(path=relative.as_posix()))
    _refuse(problems)

    target = mirror_test_path(relative)
    _refuse(
        [MESSAGES.new.file_exists.format(path=target.as_posix())]
        if (root / target).exists()
        else []
    )
    dotted = ".".join((*relative.parent.parts[1:], relative.stem))
    content = render_template(
        "scaffold_module_test.py.j2",
        module=dotted,
        stem=relative.stem,
        fixtures=edge_fixtures(_read(root, relative)),
    )
    return ScaffoldPlan(
        changes=(FileChange(target, content, created=True),),
        steps=(MESSAGES.new.step_write_tests.format(path=target.as_posix()),),
    )


def plan_command(root: Path, group: str, name: str) -> ScaffoldPlan:
    """Plan the function, the language entries and the test of a command of an existing group."""
    field = name.replace("-", "_")
    if not (
        field.isidentifier()
        and not keyword.iskeyword(field)
        and name == name.lower()
        and group.isidentifier()
    ):
        raise ValidationError(MESSAGES.new.bad_name.format(group=group, name=name), field="name")
    module = COMMANDS_DIR / f"{group}.py"
    if not (root / module).is_file():
        raise ValidationError(
            MESSAGES.new.group_missing.format(group=group, path=module.as_posix()), field="group"
        )
    test_path = TESTS_ROOT / "commands" / f"test_{group}_{field}.py"

    group_source = _read(root, module)
    help_source = _read(root, HELP_FILE)
    messages_source = _read(root, MESSAGES_FILE)
    help_class = catalog_class(help_source, HELP_CATALOG, group)
    messages_class = catalog_class(messages_source, MESSAGES_CATALOG, group)
    if help_class is None or messages_class is None:
        missing = [
            MESSAGES.new.catalog_missing.format(path=path.as_posix(), catalog=catalog, group=group)
            for path, catalog, found in (
                (HELP_FILE, HELP_CATALOG, help_class),
                (MESSAGES_FILE, MESSAGES_CATALOG, messages_class),
            )
            if found is None
        ]
        raise ValidationError("\n".join(missing), field="group")
    problems = []
    if field in function_names(group_source):
        problems.append(MESSAGES.new.function_exists.format(path=module.as_posix(), function=field))
    if field in class_fields(help_source, help_class):
        problems.append(MESSAGES.new.entry_exists.format(path=HELP_FILE.as_posix(), entry=field))
    if f"{field}_done" in class_fields(messages_source, messages_class):
        problems.append(
            MESSAGES.new.entry_exists.format(path=MESSAGES_FILE.as_posix(), entry=f"{field}_done")
        )
    if (root / test_path).exists():
        problems.append(MESSAGES.new.file_exists.format(path=test_path.as_posix()))
    _refuse(problems)

    page = f"{DOCS_PAGE_DIR}/{group}.md"
    function = render_template("scaffold_command.py.j2", group=group, name=name, field=field)
    for import_module, import_name in COMMAND_IMPORTS:
        group_source = add_import(group_source, import_module, import_name)
    group_source = append_to_module(group_source, function)
    help_entry = _string_entry(
        field,
        f"{MESSAGES.new.help_summary.format(group=group, name=name)} ",
        MESSAGES.new.help_page.format(page=page),
    )
    message_entry = _string_entry(
        f"{field}_done", MESSAGES.new.message_text.format(group=group, name=name)
    )
    changes = (
        FileChange(module, group_source, created=False),
        FileChange(HELP_FILE, append_to_class(help_source, help_class, help_entry), False),
        FileChange(
            MESSAGES_FILE,
            append_to_class(messages_source, messages_class, message_entry),
            False,
        ),
        FileChange(
            test_path,
            render_template("scaffold_command_test.py.j2", group=group, name=name, field=field),
            created=True,
        ),
    )
    steps = (
        MESSAGES.new.step_write_help.format(
            help_path=HELP_FILE.as_posix(), messages_path=MESSAGES_FILE.as_posix()
        ),
        MESSAGES.new.step_write_tests.format(path=test_path.as_posix()),
        MESSAGES.new.step_regenerate_docs,
    )
    return ScaffoldPlan(changes=changes, steps=steps)
