"""The scaffold edits a module at the positions of its syntax tree (#3204)."""

from __future__ import annotations

from devops_cli.scaffold.edits import add_import, append_to_class, append_to_module

MODULE = '''"""Doc."""

from __future__ import annotations

import typer

from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP
from devops_cli.output import print_error
'''


def test_a_name_joins_the_import_of_its_module_in_the_order_ruff_sorts_it() -> None:
    """`MESSAGES` joins `from devops_cli.lang import HELP` after `HELP`, constants first."""
    assert "from devops_cli.lang import HELP, MESSAGES\n" in add_import(
        MODULE, "devops_cli.lang", "MESSAGES"
    )


def test_a_name_that_is_imported_already_leaves_the_module_as_it_is() -> None:
    """The import is true already, so the text does not change."""
    assert add_import(MODULE, "devops_cli.lang", "HELP") == MODULE


def test_an_import_of_a_new_module_goes_before_the_first_module_that_sorts_after_it() -> None:
    """`devops_cli.dry_run.decorator` sorts between `core.cli` and `lang`."""
    result = add_import(MODULE, "devops_cli.dry_run.decorator", "dry_run_class")

    assert result.index("devops_cli.dry_run.decorator") < result.index("devops_cli.lang")
    assert result.index("devops_cli.core.cli") < result.index("devops_cli.dry_run.decorator")


def test_an_import_that_sorts_last_goes_after_the_last_import() -> None:
    """`devops_cli.telemetry` follows `devops_cli.output`."""
    assert add_import(MODULE, "devops_cli.telemetry", "trace_span").endswith(
        "from devops_cli.output import print_error\nfrom devops_cli.telemetry import trace_span\n"
    )


def test_text_added_to_a_class_follows_its_last_member_and_keeps_the_rest() -> None:
    """The new member lands inside the class, before the next top-level statement."""
    source = "class A:\n    x: str = (\n        'a'\n    )\n\n\nclass B:\n    y: int = 1\n"

    result = append_to_class(source, "A", 'z: str = "z"')

    assert result == (
        "class A:\n    x: str = (\n        'a'\n    )\n    z: str = \"z\"\n\n\nclass B:\n    y: int = 1\n"
    )


def test_text_added_to_a_module_follows_two_blank_lines() -> None:
    """The code before it keeps its text, and the file ends in one newline."""
    assert append_to_module("x = 1\n", "y = 2\n") == "x = 1\n\n\ny = 2\n"
