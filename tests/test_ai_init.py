"""Unit tests for AI package initialization, dynamic exports, and lazy loading."""

from __future__ import annotations

import pytest

import devops_cli.ai as ai
import devops_cli.ai.analyze as analyze


def test_ai_package_lazy_exports() -> None:
    """Verify all __all__ symbols in devops_cli.ai can be dynamically imported."""
    for symbol in ai.__all__:
        attr = getattr(ai, symbol)
        assert attr is not None, f"Failed to export {symbol}"

    with pytest.raises(AttributeError, match="has no attribute 'nonexistent_symbol'"):
        _ = getattr(ai, "nonexistent_symbol")


def test_ai_analyze_package_lazy_exports() -> None:
    """Verify all __all__ symbols in devops_cli.ai.analyze can be dynamically imported."""
    for symbol in analyze.__all__:
        attr = getattr(analyze, symbol)
        assert attr is not None, f"Failed to export {symbol} from analyze"

    with pytest.raises(AttributeError, match="has no attribute 'nonexistent_analyze_symbol'"):
        _ = getattr(analyze, "nonexistent_analyze_symbol")
