"""The registry and ratchet declarations of the test suite (#3254)."""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import CodeType

from devops_cli.roadmap.stage.stage_registry import (
    counts_in,
    missing_test_paths,
    registry_table,
)


def test_a_declaration_enters_the_table_with_its_path_and_line(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        'REGISTRY_COUNTS = (("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),)\n',
        encoding="utf-8",
    )

    table = registry_table(tmp_path)

    assert len(table) == 1
    entry = table[0]
    assert entry.kind == "prefix"
    assert entry.token == "CONST_ROADMAP_"
    assert entry.path == "tests/roadmap/test_roadmap_limit_classes.py"
    assert entry.line == 1
    assert entry.declaring_path == "tests/test_example.py"


def test_a_spec_naming_a_missing_test_module_returns_its_name(tmp_path: Path) -> None:
    spec_text = "The scenario runs with `tests/test_missing_example.py`."
    assert missing_test_paths(tmp_path, [spec_text]) == ["tests/test_missing_example.py"]


def test_a_docstring_naming_an_existing_test_module_returns_nothing(tmp_path: Path) -> None:
    test_path = "tests/roadmap/test_roadmap_limit_classes.py"
    target = tmp_path / test_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("REGISTRY_COUNTS = ()\n", encoding="utf-8")

    docstring = f'"""Test limits in `{test_path}`."""'
    assert missing_test_paths(tmp_path, [docstring]) == []


def test_counts_in_handles_missing_file_or_syntax_error(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent.py"
    assert counts_in(missing) == ()

    syntax_bad = tmp_path / "bad.py"
    syntax_bad.write_text("def broken_syntax(:\n", encoding="utf-8")
    assert counts_in(syntax_bad) == ()


def test_counts_in_handles_non_tuple_and_short_entries(tmp_path: Path) -> None:
    non_tuple = tmp_path / "non_tuple.py"
    non_tuple.write_text("REGISTRY_COUNTS = 'not-a-tuple'\n", encoding="utf-8")
    assert counts_in(non_tuple) == ()

    short_entry = tmp_path / "short.py"
    short_entry.write_text(
        "REGISTRY_COUNTS = (('only_one',), ('two', 'items'))\n", encoding="utf-8"
    )
    assert counts_in(short_entry) == ()


# PEP 669 gives six tool ids, 0 to 5.
_MONITORING_TOOL_IDS = range(6)


@contextmanager
def _parsed_texts() -> Iterator[list[object]]:
    """The first argument of each call of `ast.parse` in the block. `sys.monitoring` (PEP 669)
    reports each call, so the test replaces no function."""
    monitoring = sys.monitoring
    tool = next(tool for tool in _MONITORING_TOOL_IDS if monitoring.get_tool(tool) is None)
    texts: list[object] = []

    def on_call(_code: CodeType, _offset: int, called: object, first: object) -> None:
        if called is ast.parse:
            texts.append(first)

    monitoring.use_tool_id(tool, "registry-parse-calls")
    monitoring.register_callback(tool, monitoring.events.CALL, on_call)
    monitoring.set_events(tool, monitoring.events.CALL)
    try:
        yield texts
    finally:
        monitoring.set_events(tool, monitoring.events.NO_EVENTS)
        monitoring.register_callback(tool, monitoring.events.CALL, None)
        monitoring.free_tool_id(tool)


def test_a_module_that_does_not_name_the_counts_is_not_parsed(tmp_path: Path) -> None:
    module = tmp_path / "test_plain.py"
    module.write_text("def test_plain() -> None:\n    assert True\n", encoding="utf-8")

    with _parsed_texts() as parsed:
        assert counts_in(module) == ()

    assert parsed == []


def test_a_module_that_names_the_counts_only_in_a_comment_gives_no_entry(tmp_path: Path) -> None:
    module = tmp_path / "test_comment.py"
    text = "# REGISTRY_COUNTS = (('prefix', 'CONST_', 'tests/test_x.py'),)\nVALUE = 1\n"
    module.write_text(text, encoding="utf-8")

    with _parsed_texts() as parsed:
        assert counts_in(module) == ()

    assert parsed == [text]


def test_registry_table_nonexistent_dir(tmp_path: Path) -> None:
    assert registry_table(tmp_path / "does_not_exist") == ()


def test_registry_table_skips_non_file_py_paths(tmp_path: Path) -> None:
    dir_with_py_suffix = tmp_path / "tests" / "folder.py"
    dir_with_py_suffix.mkdir(parents=True, exist_ok=True)
    assert registry_table(tmp_path) == ()


def test_missing_test_paths_with_collection() -> None:
    known = {"tests/test_existing.py"}
    texts = ["Refers to tests/test_existing.py and tests/test_other.py"]
    assert missing_test_paths(known, texts) == ["tests/test_other.py"]
