"""Hygiene invariants: no hardcoded file-extension sets, and every private function in security/ has a caller."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.indexer import _is_indexable_file
from tests.support.paths import REPO_ROOT


def test_chunker_no_hardcoded_extension_sets(tmp_path: Path) -> None:
    """chunker.py should not define hardcoded literal sets of file extensions."""
    import devops_cli.ai.rag.chunker as chunker_mod

    assert not hasattr(chunker_mod, "_DOC_EXTENSIONS")
    assert not hasattr(chunker_mod, "_IAC_EXTENSIONS")
    assert not hasattr(chunker_mod, "_CONFIG_EXTENSIONS")
    assert not hasattr(chunker_mod, "_JS_TS_EXTENSIONS")
    assert not hasattr(chunker_mod, "_C_LIKE_EXTENSIONS")

    chunker = SemanticChunker()
    doc_file = tmp_path / "guide.md"
    doc_file.write_text("# Title\n\nSome docs here.", encoding="utf-8")
    chunks = chunker.chunk_file(doc_file, relative_to=tmp_path)
    assert len(chunks) >= 1
    assert chunks[0].category == "docs"


def test_indexer_no_hardcoded_indexable_extensions(tmp_path: Path) -> None:
    """indexer.py should not define 63-element _INDEXABLE_EXTENSIONS set; use dynamic text detection."""
    import devops_cli.ai.rag.indexer as indexer_mod

    assert not hasattr(indexer_mod, "_INDEXABLE_EXTENSIONS")

    # Verify text file detection works on any valid text/code file
    py_file = tmp_path / "app.py"
    py_file.write_text("print('hello')", encoding="utf-8")
    assert _is_indexable_file(py_file, tmp_path) is True

    # Unknown extension with plain text content should still be indexed
    custom_doc = tmp_path / "doc.customtext"
    custom_doc.write_text("Plain text documentation", encoding="utf-8")
    assert _is_indexable_file(custom_doc, tmp_path) is True

    # Binary file with null bytes should NOT be indexed
    bin_file = tmp_path / "app.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\x04\xff")
    assert _is_indexable_file(bin_file, tmp_path) is False


def test_reference_extractor_no_hardcoded_extensions() -> None:
    """reference_extractor.py should not maintain _COMMON_FILE_EXTENSIONS or _PACKAGE_ARCHIVE_EXTENSIONS."""
    import devops_cli.security.reference_extractor as ref_mod

    assert not hasattr(ref_mod, "_COMMON_FILE_EXTENSIONS")
    assert not hasattr(ref_mod, "_PACKAGE_ARCHIVE_EXTENSIONS")


def test_security_module_private_functions_all_have_callers() -> None:
    """Every module-level `_private` function in `security/*.py` is used somewhere in src/ or tests/.

    A private helper nobody calls is a dead copy of a live path, free to drift from it and to
    mislead whoever reads it. A `def` in column 0 is a module-level definition by Python's
    indentation grammar, which a regex reads at a fraction of the cost of parsing every module.
    Most helpers are used in their own module, so only a name that appears there once, at its
    `def`, is looked for across both trees.
    """
    module_level_private_def = re.compile(r"^(?:async\s+)?def\s+(_[^\W_]\w*)", re.MULTILINE)
    unused_at_home = [
        (module.name, name)
        for module in sorted((REPO_ROOT / "src/devops_cli/security").glob("*.py"))
        for source in [module.read_text(encoding="utf-8")]
        for identifiers in [Counter(re.findall(r"\b_\w+", source))]
        for name in module_level_private_def.findall(source)
        if identifiers[name] < 2
    ]
    sources = [
        path.read_text(encoding="utf-8")
        for tree in ("src", "tests")
        for path in (REPO_ROOT / tree).rglob("*.py")
    ]
    uncalled = [
        f"{module}:{name}"
        for module, name in unused_at_home
        if sum(len(re.findall(rf"\b{name}\b", text)) for text in sources if name in text) < 2
    ]
    assert uncalled == []
