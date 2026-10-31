"""Unit tests for AI package initialization, dynamic exports, and lazy loading."""

from __future__ import annotations

import pytest

import devops_cli.ai as ai
import devops_cli.ai.analyze as analyze


def test_ai_package_has_no_facade_exports() -> None:
    """Verify devops_cli.ai has no lazy facade exports and holds only module docstring."""
    assert not hasattr(ai, "__all__")
    assert ai.__doc__ is not None


def test_ai_analyze_package_lazy_exports() -> None:
    """Verify all __all__ symbols in devops_cli.ai.analyze match the defining module symbols."""
    import devops_cli.ai.analyze.cache as cache
    import devops_cli.ai.analyze.outlines as outlines
    import devops_cli.ai.analyze.scanner as scanner

    expected = {
        "analyze_single_file": outlines.analyze_single_file,
        "detect_language": scanner.detect_language,
        "load_cached_analysis": cache.load_cached_analysis,
        "sanitize_reference": scanner.sanitize_reference,
        "save_analysis_metadata": cache.save_analysis_metadata,
        "scan_directory": scanner.scan_directory,
    }
    for symbol, defining_obj in expected.items():
        assert getattr(analyze, symbol) is defining_obj

    with pytest.raises(AttributeError, match="has no attribute 'nonexistent_analyze_symbol'"):
        _ = getattr(analyze, "nonexistent_analyze_symbol")
