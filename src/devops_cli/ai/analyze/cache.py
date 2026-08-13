"""Metadata persistence, JSON caching, and Rich analysis summary rendering."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.ai.analyze.scanner import sanitize_reference
from devops_cli.config.constants import CONST_DATA_DIR
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import MESSAGES
from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta, ProjectAnalysisMeta

console = Console()


def save_analysis_metadata(
    target_type: Literal["branch", "pr", "path"],
    target_reference: str,
    title: str,
    files: list[FileAnalysisMeta],
    repo_root: Path,
    enhanced: bool = True,
) -> Path:
    """Save or update analysis metadata file under .data/analysis/."""
    sanitized_ref = sanitize_reference(target_reference, repo_root)
    top_root = find_top_level_repo_root(repo_root)
    analysis_dir = top_root / CONST_DATA_DIR / "analysis"
    if not is_dry_run():
        analysis_dir.mkdir(parents=True, exist_ok=True)
    out_file = analysis_dir / f"{target_type}-{sanitized_ref}-metadata.json"

    total_files = len(files)
    total_lines = sum(f.line_count for f in files)
    total_chars = sum(f.char_count for f in files)
    languages = sorted(list({f.language for f in files}))

    all_symbols: list[str] = []
    core_files = [
        f for f in files if not f.path.lower().startswith("test") and "test_" not in f.path.lower()
    ]
    other_files = [f for f in files if f not in core_files]

    for f in core_files + other_files:
        for s in f.key_symbols:
            if (
                s not in all_symbols
                and not s.startswith(("test_", "dummy_", "mock_", "tmp_"))
                and s not in ("BaseModel", "ConfigDict", "Exception", "Any", "SampleSchema")
            ):
                all_symbols.append(s)

    all_deps: list[str] = []
    for f in files:
        for d in f.dependencies:
            if d not in all_deps:
                all_deps.append(d)

    project_purpose = (
        f"Analysis session for {target_type} '{target_reference}' covering {total_files} file(s)."
    )

    conf_scores = [f.confidence_score for f in files if f.confidence_score is not None]
    proj_conf = round(sum(conf_scores) / len(conf_scores), 2) if conf_scores else None

    qual_scores = [f.quality_score for f in files if f.quality_score is not None]
    proj_qual = round(sum(qual_scores) / len(qual_scores), 2) if qual_scores else None

    proj_meta = ProjectAnalysisMeta(
        title=title,
        target_type=target_type,
        target_reference=target_reference,
        timestamp=datetime.now(UTC).isoformat(),
        total_files=total_files,
        total_lines=total_lines,
        total_chars=total_chars,
        languages=languages,
        primary_purpose=project_purpose,
        key_symbols=all_symbols[:50],
        dependencies=all_deps[:15],
        enhanced=enhanced,
        last_analyzed=datetime.now(UTC).isoformat() if enhanced else None,
        confidence_score=proj_conf,
        quality_score=proj_qual,
    )

    payload = AnalysisMetadata(project=proj_meta, files=files)

    if is_dry_run():
        rprint(MESSAGES.analyze.would_save_metadata.format(path=out_file))
        rprint("[yellow][dry-run][/yellow] AnalysisMetadata Pydantic model response:")
        console.print_json(payload.model_dump_json(indent=2))
    else:
        out_file.write_text(json.dumps(payload.model_dump(mode="json"), indent=2), encoding="utf-8")
        rprint(MESSAGES.analyze.saved_metadata.format(path=out_file))

    return out_file


def _render_analysis_summary(payload: AnalysisMetadata, out_path: Path) -> None:
    """Render a Rich summary table of the analysis metadata."""
    proj = payload.project
    console.print(MESSAGES.analyze.analysis_complete.format(title=proj.title))
    table = Table(show_header=False, box=None)
    table.add_row(MESSAGES.analyze.lbl_target, f"{proj.target_type} ({proj.target_reference})")
    table.add_row(MESSAGES.analyze.lbl_total_files, str(proj.total_files))
    table.add_row(MESSAGES.analyze.lbl_total_lines, f"{proj.total_lines:,}")
    table.add_row(MESSAGES.analyze.lbl_languages, ", ".join(proj.languages))
    if proj.enhanced:
        table.add_row(
            MESSAGES.analyze.lbl_enhanced,
            MESSAGES.analyze.enhanced_enabled,
        )
        conf_str = f"{proj.confidence_score:.2f}" if proj.confidence_score is not None else "N/A"
        table.add_row("Confidence Score:", conf_str)
        qual_str = f"{proj.quality_score:.2f}" if proj.quality_score is not None else "N/A"
        table.add_row("Quality Score:", qual_str)
    table.add_row(MESSAGES.analyze.lbl_saved_to, f"[link=file://{out_path}]{out_path}[/link]")
    console.print(table)


def load_cached_analysis(repo_root: Path = Path(".")) -> AnalysisMetadata | None:
    """Load latest cached AnalysisMetadata from top-level .data/analysis/ if present."""
    top_root = find_top_level_repo_root(repo_root)
    analysis_dir = top_root / CONST_DATA_DIR / "analysis"
    if not analysis_dir.is_dir():
        return None
    json_files = sorted(
        analysis_dir.glob("*-metadata.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not json_files:
        return None
    try:
        data = json_files[0].read_text(encoding="utf-8")
        return AnalysisMetadata.model_validate_json(data)
    except Exception:
        return None
