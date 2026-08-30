"""AI Codebase Analysis subpackage for outline extraction, project metadata, and caching."""

from __future__ import annotations

from devops_cli.ai.analyze.cache import (
    load_cached_analysis,
    save_analysis_metadata,
)
from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.analyze.scanner import (
    detect_language,
    sanitize_reference,
    scan_directory,
)

__all__ = [
    "analyze_single_file",
    "detect_language",
    "load_cached_analysis",
    "sanitize_reference",
    "save_analysis_metadata",
    "scan_directory",
]
