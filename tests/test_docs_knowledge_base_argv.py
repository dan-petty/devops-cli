"""Tests for collecting knowledge base Markdown command lines and resolving them statically."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.docs import app as docs_app
from devops_cli.core.command_resolver import (
    ArgvPlaceholder,
    CommandReferenceDefect,
    CommandReferenceFinding,
    module_click_command,
    resolve_devops_argv,
)
from devops_cli.docs.generator import DocGenerator
from devops_cli.docs.markdown_argv_collector import (
    collect_handwritten_docs_argv_references,
    collect_knowledge_base_argv_references,
    collect_markdown_argv_references,
)
from devops_cli.docs.source_argv_collector import (
    DevopsArgvReference,
    describe_unresolved_references,
)
from devops_cli.main import _COMMAND_SPECS

FIXTURE_MARKDOWN = """\
# Knowledge Base Sample

Run the review pipeline on a branch:

```bash
devops ai review branch --persona devsecops # start devsecops review
devops review verify <session> --index <n> --status MITIGATED
```

For quick queries, use `devops ai rag query "sample query"` inline.
"""

DEFECTIVE_REFERENCE = DevopsArgvReference(
    path="docs/sample.md",
    line=4,
    owner="<markdown>",
    tokens=("nonexistent-cmd", "--invalid-flag"),
)


def test_collect_markdown_argv_references_fixture() -> None:
    """Verify collector parses fenced lines, inline spans, placeholders, and trailing comments."""
    references = collect_markdown_argv_references(FIXTURE_MARKDOWN, "fixture.md")

    expected = [
        (
            "fixture.md",
            6,
            ("ai", "review", "branch", "--persona", "devsecops"),
        ),
        (
            "fixture.md",
            7,
            (
                "review",
                "verify",
                ArgvPlaceholder(expression="<session>"),
                "--index",
                ArgvPlaceholder(expression="<n>"),
                "--status",
                "MITIGATED",
            ),
        ),
        (
            "fixture.md",
            10,
            ("ai", "rag", "query", "sample query"),
        ),
    ]

    actual = [(ref.path, ref.line, ref.tokens) for ref in references]
    assert actual == expected


def test_docs_check_reports_an_unresolved_knowledge_base_argv(tmp_path: Path) -> None:
    """Verify `devops docs check` fails and reports an unresolved knowledge base command line."""
    with (
        patch.object(DocGenerator, "generate_all_docs", return_value={}),
        patch(
            "devops_cli.docs.source_argv_collector.collect_source_argv_references",
            return_value=[],
        ),
        patch(
            "devops_cli.docs.markdown_argv_collector.collect_knowledge_base_argv_references",
            return_value=[DEFECTIVE_REFERENCE],
        ),
    ):
        ok, errors = DocGenerator().check_docs(tmp_path, check_readme_table=False)
        result = CliRunner().invoke(
            docs_app, ["check", "--no-check-readme", "--output-dir", str(tmp_path)]
        )

    expected_errors = describe_unresolved_references([DEFECTIVE_REFERENCE])
    assert (ok, errors, result.exit_code, "docs/sample.md:4" in result.output) == (
        False,
        expected_errors,
        1,
        True,
    )


def test_every_knowledge_base_argv_resolves() -> None:
    """Verify every devops command line in the bundled knowledge base resolves statically."""
    for module_path, _ in _COMMAND_SPECS.values():
        module_click_command(module_path)

    with patch("subprocess.Popen", side_effect=AssertionError("no subprocess")) as popen:
        references = collect_knowledge_base_argv_references()
        unresolved = describe_unresolved_references(references)

    cli_ref_count = sum(1 for ref in references if ref.path.endswith("cli_command_reference.md"))

    assert (
        unresolved,
        cli_ref_count >= 60,
        popen.called,
    ) == ([], True, False)


def test_every_handwritten_doc_argv_resolves() -> None:
    """Verify every devops command line in the hand-written docs resolves statically."""
    for module_path, _ in _COMMAND_SPECS.values():
        module_click_command(module_path)

    with patch("subprocess.Popen", side_effect=AssertionError("no subprocess")) as popen:
        references = collect_handwritten_docs_argv_references()
        unresolved = describe_unresolved_references(references)

    paths_seen = {ref.path for ref in references}
    expected_paths = {
        "README.md",
        "ARCHITECTURE.md",
        "RELEASE_CYCLE.md",
        "docs/SDLC.md",
        "docs/ROUTINE_TASKS.md",
        "docs/DEVCONTAINER_USAGE.md",
        "k8s/README.md",
    }
    assert (
        unresolved,
        expected_paths.issubset(paths_seen),
        popen.called,
    ) == ([], True, False)


def test_docs_check_reports_an_unresolved_handwritten_doc_argv(tmp_path: Path) -> None:
    """Verify `devops docs check` fails and reports an unresolved handwritten doc command line."""
    with (
        patch.object(DocGenerator, "generate_all_docs", return_value={}),
        patch(
            "devops_cli.docs.source_argv_collector.collect_source_argv_references",
            return_value=[],
        ),
        patch(
            "devops_cli.docs.markdown_argv_collector.collect_knowledge_base_argv_references",
            return_value=[],
        ),
        patch(
            "devops_cli.docs.markdown_argv_collector.collect_handwritten_docs_argv_references",
            return_value=[DEFECTIVE_REFERENCE],
        ),
    ):
        ok, errors = DocGenerator().check_docs(tmp_path, check_readme_table=False)
        result = CliRunner().invoke(
            docs_app, ["check", "--no-check-readme", "--output-dir", str(tmp_path)]
        )

    expected_errors = describe_unresolved_references([DEFECTIVE_REFERENCE])
    assert (ok, errors, result.exit_code, "docs/sample.md:4" in result.output) == (
        False,
        expected_errors,
        1,
        True,
    )


def test_handwritten_docs_defective_reference_fails_resolution() -> None:
    """Verify defective commands like 'devops pr merge' fail resolution when checked."""
    for module_path, _ in _COMMAND_SPECS.values():
        module_click_command(module_path)

    defective_md = """\
# Defective Documentation
```bash
devops pr merge 123 --squash
devops scan kubelinter -p k8s/
```
"""
    refs = collect_markdown_argv_references(defective_md, "test_defective.md")
    unresolved = describe_unresolved_references(refs)
    assert len(unresolved) == 2


def test_an_option_in_optional_group_brackets_is_validated() -> None:
    """Verify an option written inside a synopsis optional group is checked, not skipped."""
    markdown = """\
```bash
devops release pr [-v <ver>]
devops release pr [--no-such-flag]
```
"""
    references = collect_markdown_argv_references(markdown, "x.md")

    assert (
        references[0].tokens,
        [resolve_devops_argv(reference.tokens) for reference in references],
    ) == (
        ("release", "pr", "-v", ArgvPlaceholder(expression="<ver>]")),
        [
            None,
            CommandReferenceFinding(
                defect=CommandReferenceDefect.UNKNOWN_OPTION,
                command_path="devops release pr",
                token="--no-such-flag",
            ),
        ],
    )
