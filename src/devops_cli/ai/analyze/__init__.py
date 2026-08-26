"""AI Codebase Analysis subpackage for outline extraction, project metadata, and caching."""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name in {"load_cached_analysis", "save_analysis_metadata"}:
        from devops_cli.ai.analyze.cache import (
            load_cached_analysis,
            save_analysis_metadata,
        )

        mapping = {
            "load_cached_analysis": load_cached_analysis,
            "save_analysis_metadata": save_analysis_metadata,
        }
        return mapping[name]
    if name == "analyze_single_file":
        from devops_cli.ai.analyze.outlines import analyze_single_file

        return analyze_single_file
    if name in {"detect_language", "sanitize_reference", "scan_directory"}:
        from devops_cli.ai.analyze.scanner import (
            detect_language,
            sanitize_reference,
            scan_directory,
        )

        mapping = {
            "detect_language": detect_language,
            "sanitize_reference": sanitize_reference,
            "scan_directory": scan_directory,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "analyze_single_file",
    "detect_language",
    "load_cached_analysis",
    "sanitize_reference",
    "save_analysis_metadata",
    "scan_directory",
]
