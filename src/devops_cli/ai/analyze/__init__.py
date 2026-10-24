"""AI Codebase Analysis subpackage for outline extraction, project metadata, and caching."""

from __future__ import annotations

from devops_cli.ai.analyze.cache import (
    load_cached_analysis,
    save_analysis_metadata,
)
from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.analyze.scanner import (
    CODE_LANGUAGES,
    detect_language,
    detect_syntax,
    sanitize_reference,
    scan_directory,
    syntax_from_language,
)

__all__ = [
    "CODE_LANGUAGES",
    "analyze_single_file",
    "detect_language",
    "detect_syntax",
    "load_cached_analysis",
    "sanitize_reference",
    "save_analysis_metadata",
    "scan_directory",
    "syntax_from_language",
]
