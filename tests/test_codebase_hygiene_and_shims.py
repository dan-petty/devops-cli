"""Test suite for codebase hygiene, removal of shims, aliases, and forbidden patterns."""

from __future__ import annotations

import inspect
from pathlib import Path

from pydantic_ai.tools import RunContext as NativeRunContext

from devops_cli.ai.agents.context import RunContext
from devops_cli.ai.harness.compaction import WarnOnCacheBusts
from devops_cli.ai.harness.shell import Shell
from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.indexer import _is_indexable_file
from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    calculate_hallucination_similarity,
)
from devops_cli.ai.review_schema import Finding
from devops_cli.ai.tools import Tool
from devops_cli.commands.rag import app as rag_app
from devops_cli.commands.scan import app as scan_app
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.security.reference_extractor import is_file_reference


def test_tool_has_no_func_alias() -> None:
    """Tool class should use .function and not maintain a legacy .func alias property."""

    def sample_func(x: int) -> int:
        return x + 1

    t = Tool(sample_func, name="sample")
    assert t.function is sample_func
    assert not hasattr(t, "func"), "Legacy .func alias should be removed from Tool"


def test_run_context_is_subclass_not_monkeypatched() -> None:
    """RunContext must be a clean subclass of NativeRunContext without monkey-patching NativeRunContext."""
    assert issubclass(RunContext, NativeRunContext)
    # NativeRunContext should not have monkey-patch backup attributes or shim implementations
    assert not hasattr(NativeRunContext, "_orig_run_context_init")
    assert not hasattr(NativeRunContext, "_orig_run_context_model_copy")
    assert NativeRunContext.__init__.__name__ != "_run_context_init_shim"


def test_run_context_instance_functionality() -> None:
    """RunContext instances properly initialize attributes and support model_copy."""
    ctx = RunContext(
        deps={"key": "val"},
        session_id="sess-123",
        retry=2,
        loaded_capability_ids={"cap1"},
        tool_call_approved=True,
        tool_call_metadata={"source": "test"},
    )
    assert ctx.session_id == "sess-123"
    assert ctx.retry == 2
    assert "cap1" in ctx.loaded_capability_ids
    assert ctx.tool_call_approved is True
    assert ctx.tool_call_metadata == {"source": "test"}

    copied = ctx.model_copy(update={"retry": 3})
    assert copied.retry == 3
    assert copied.session_id == "sess-123"


def test_no_native_mcp_toolset_alias() -> None:
    """devops_cli.ai.mcp.toolset should not define legacy NativeMCPToolset alias."""
    import devops_cli.ai.mcp.toolset as ts_mod

    assert not hasattr(ts_mod, "NativeMCPToolset")
    assert hasattr(ts_mod, "MCPToolset")


def test_devops_cli_error_has_no_code_alias() -> None:
    """DevOpsCLIError should only expose .error_code and not maintain a .code alias."""
    err = DevOpsCLIError("Something failed", error_code="E_FAILED")
    assert err.error_code == "E_FAILED"
    assert not hasattr(err, "code"), "Legacy .code alias should be removed from DevOpsCLIError"


def test_scan_app_has_no_shim_alias_commands() -> None:
    """devops scan should not register gitleaks, semgrep, or checkov aliases; use canonical commands."""
    cmd_names = [cmd.name for cmd in scan_app.registered_commands if cmd.name]
    assert "secrets" in cmd_names
    assert "sast" in cmd_names
    assert "iac" in cmd_names
    assert "gitleaks" not in cmd_names, "scan gitleaks alias should be removed"
    assert "semgrep" not in cmd_names, "scan semgrep alias should be removed"
    assert "checkov" not in cmd_names, "scan checkov alias should be removed"


def test_scan_module_has_no_legacy_variable_aliases() -> None:
    """devops_cli.commands.scan should not export main, scan_main, or scan_app aliases."""
    import devops_cli.commands.scan as scan_mod

    assert not hasattr(scan_mod, "main")
    assert not hasattr(scan_mod, "scan_main")
    assert not hasattr(scan_mod, "scan_app")


def test_rag_app_has_no_reset_alias() -> None:
    """devops rag should use canonical clear command and not register reset alias."""
    cmd_names = [cmd.name for cmd in rag_app.registered_commands if cmd.name]
    assert "clear" in cmd_names
    assert "reset" not in cmd_names, "rag reset alias should be removed"


def test_shell_execution_has_no_run_shell_alias() -> None:
    """Shell.get_tools() should provide canonical run_command, not run_shell alias."""
    shell = Shell()
    tool_names = [t.name for t in shell.get_tools() if hasattr(t, "name")]
    assert "run_command" in tool_names
    assert "run_shell" not in tool_names, "Duplicate run_shell alias should be removed"


def test_compaction_cache_monitor_consolidated_parameters() -> None:
    """WarnOnCacheBusts.record_request should use consolidated 'now' parameter without 'current_time'."""
    monitor = WarnOnCacheBusts()
    sig = inspect.signature(monitor.record_request)
    assert "now" in sig.parameters
    assert "current_time" not in sig.parameters
    assert not hasattr(monitor, "record_usage"), "Legacy record_usage alias should be removed"


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


def test_reference_extractor_no_hardcoded_extensions(tmp_path: Path) -> None:
    """reference_extractor.py should not maintain _COMMON_FILE_EXTENSIONS or _PACKAGE_ARCHIVE_EXTENSIONS."""
    import devops_cli.security.reference_extractor as ref_mod

    assert not hasattr(ref_mod, "_COMMON_FILE_EXTENSIONS")
    assert not hasattr(ref_mod, "_PACKAGE_ARCHIVE_EXTENSIONS")

    # Dynamic file reference detection should still recognize files with common extensions
    assert is_file_reference("src/main.py") is True
    assert is_file_reference("README.md") is True
    assert is_file_reference("config.json") is True


def test_common_hallucinations_mathematical_similarity() -> None:
    """calculate_hallucination_similarity should calculate similarity score mathematically."""
    entry = CommonHallucinationEntry(
        id="HALLUCINATION-TEST",
        name="Test Hallucination",
        description="Test description for hallucination entry",
        category=HallucinationCategory.SYNTAX_GRAMMAR,
        pattern_keywords=["bracketless_except", "unparenthesized_except", "pep758"],
        signature_patterns=[r"except\s+[A-Za-z0-9_]+,\s*[A-Za-z0-9_]+:"],
        resolution="Valid Python syntax",
    )
    finding = Finding(
        category="syntax",
        severity="HIGH",
        location="src/test.py:10-12",
        title="Syntax error in unparenthesized_except bracketless_except clause",
        description="Found except ValueError, TypeError: which is invalid syntax.",
    )
    res = calculate_hallucination_similarity(finding, entry, file_path=Path("src/test.py"))
    assert res.similarity_score > 0.0
    assert res.matched_keywords
