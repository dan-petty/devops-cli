"""Automated documentation compaction engine for devops-cli.

Summarizes historical release milestones, release notes highlights, and sprint logs
when transitioning across major or minor release boundaries (e.g. v0.2.x -> v0.3.x).
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.exceptions import DocCompactionError
from devops_cli.output import write_text_file

_SERIES_SUMMARY_TITLES: dict[str, str] = {
    "v0.1": "Workstation Foundation, SecOps, Multi-Cloud IaC & Core Architecture",
    "v0.2": "Distributed Observability, AI Agent Harness, Workload Sandboxing & Hardened SecOps",
}

_SERIES_ROADMAP_BULLETS: dict[str, list[str]] = {
    "v0.2": [
        "- [x] **Distributed Observability & Telemetry**: Prometheus client metrics, Jaeger distributed tracing waterfalls, Loki LogQL live log streaming, and OpenTelemetry traceparent propagation.",
        "- [x] **Next-Gen PydanticAI Agent Architecture**: PydanticAI native subsystems, multi-turn reasoning buffers, prompt mutation testing, and human-in-the-loop feedback dataset export.",
        "- [x] **Valkey Distributed Caching & Rate Limiting**: Pure-Python RESP3 wire protocol client, token-bucket rate limiter, and vector cache slashing LLM latency.",
        "- [x] **Code Intelligence, Tree-Sitter & Ingestion Engine**: Polyglot CST parser, library contract introspector, API drift auditor, and AST context packing.",
        "- [x] **Workload Sandboxing & Dynamic Runtime Security**: Rootless container sandbox, endpoint health probing, dynamic fuzzing, and base security scanner consolidation.",
    ],
}

_SERIES_RELEASE_NOTES_BULLETS: dict[str, list[str]] = {
    "v0.2": [
        "- **Distributed Observability & Telemetry Triad**: Prometheus client metrics, Jaeger distributed tracing waterfalls, Loki LogQL terminal log streaming, and OpenTelemetry traceparent propagation.",
        "- **PydanticAI Standardized Agent Framework**: 18 modernized agent subsystems, multi-turn reasoning buffers, prompt mutation testing, and human-in-the-loop feedback dataset export.",
        "- **Valkey Workstation Management & High-Performance Distributed Caching**: Pure-Python RESP3 wire protocol client, token-bucket rate limiter, and vector cache slashing LLM latency.",
        "- **Tree-Sitter Multilingual AST Graph & Polyglot Code Intelligence**: CST parsing across Python, TypeScript, Go, Rust, Java, and HCL with S-expression query resolution.",
        "- **Ephemeral Workload Sandboxing & Dynamic Probing**: Rootless container test harness, cgroup v2 metrics, protocol-agnostic health probing, and OpenAPI dynamic API fuzzing.",
        "- **BaseSecurityScanner Declarative Framework**: Standardized 11 static security scanners with pre-flight binary verification, bounded timeouts, and normalized finding models.",
    ],
}

_SERIES_MATRIX_SUMMARIES: dict[str, list[str]] = {
    "v0.2": [
        "| **Quick Wins** | Observability, Context Budgeting, Valkey Cache & Security Pre-Filters | Standard Library / PydanticAI / Valkey | High | Low | v0.2.x | ✅ Completed |",
        "| **Major Projects** | Universal Stage Pipelines, Ephemeral Sandboxing & Dynamic Probing | Docker / K8s / Tree-Sitter | High | High | v0.2.x | ✅ Completed |",
        "| **Fill-Ins** | Dynamic Schema Export, AST Memoization & Knowledge Base Linters | Click / Typer Introspection | Low | Low | v0.2.x | ✅ Completed |",
        "| **Foundation** | DevContainer Lifecycle, PSA Enforcement & Invariant Gates | Linux / Docker / OTel | Low | High | v0.2.x | ✅ Completed |",
    ],
}


class DocCompactionRequest(BaseModel):
    """Specification model for documentation compaction execution."""

    series: str = "v0.2"
    docs_dir: Path = Field(default_factory=lambda: Path("docs"))
    archive_dir: Path = Field(default_factory=lambda: Path("docs/agent/archive"))
    dry_run: bool = False
    check: bool = False
    compact_roadmap: bool = True
    compact_release_notes: bool = True
    compact_log: bool = True


class DocCompactionResult(BaseModel):
    """Summary of documentation compaction execution."""

    series: str
    roadmap_compacted: bool = False
    roadmap_sections_count: int = 0
    release_notes_compacted: bool = False
    release_notes_sections_count: int = 0
    log_compacted: bool = False
    archive_file_path: str | None = None
    modified_files: list[str] = Field(default_factory=list)
    bytes_saved: int = 0


_SERIES_REGEX = re.compile(r"^v?[0-9]+(?:\.[0-9]+)?(?:\.x)?$")
_SERIES_PHASE_RANGES: dict[str, tuple[float, float]] = {
    "v0.2": (41.0, 55.0),
}


def _normalize_series(series: str) -> str:
    """Normalize release series string, e.g. 'v0.2.x' -> 'v0.2'.

    Raises:
        DocCompactionError: If the release series syntax is invalid or contains traversal characters.
    """
    clean = series.strip().lower()
    if not _SERIES_REGEX.match(clean):
        raise DocCompactionError(
            f"Invalid release series syntax: {series!r}. Expected format like 'v0.2' or 'v0.2.x'.",
            series=series,
        )
    if clean.endswith(".x"):
        clean = clean[:-2]
    if not clean.startswith("v"):
        clean = f"v{clean}"
    return clean


def _resolve_safe_archive_file(archive_dir: Path, filename: str) -> Path:
    """Resolve archive file path and ensure strict containment within archive_dir."""
    resolved_dir = archive_dir.resolve()
    target = (resolved_dir / filename).resolve()
    if not target.is_relative_to(resolved_dir):
        raise DocCompactionError(
            f"Archive file path {target} escapes archive directory {resolved_dir}",
            target_file=str(target),
        )
    return target


def _version_matches_series(version_str: str, series: str) -> bool:
    """Check if a version string (e.g. 'v0.2.14') matches series prefix (e.g. 'v0.2')."""
    normalized_series = _normalize_series(series)
    ver = version_str.strip().lower()
    if not ver.startswith("v"):
        ver = f"v{ver}"
    return ver.startswith(f"{normalized_series}.") or ver == normalized_series


def _flush_log_block(
    block: list[str],
    is_historical: bool,
    archived_lines: list[str],
    retained_lines: list[str],
) -> None:
    """Flush accumulated lines into either archived or retained buffers."""
    if not block:
        return
    if is_historical:
        archived_lines.extend(block)
    else:
        retained_lines.extend(block)


def _is_historical_log_header(header_line: str, normalized_series: str) -> bool:
    """Determine if a log section header corresponds to target series milestones."""
    # 1. Extract explicit release version strings from header (e.g. 'Release v0.2.12', 'v0.1.0')
    found_versions = re.findall(
        r"(?:Release\s+|(?<=\s)v|^v)(\d+\.\d+(?:\.\d+)?)", header_line, re.IGNORECASE
    )
    if found_versions:
        matches_other = any(
            not _version_matches_series(v, normalized_series) for v in found_versions
        )
        matches_target = any(_version_matches_series(v, normalized_series) for v in found_versions)
        if matches_target and not matches_other:
            return True
        if matches_other:
            return False

    # 2. Check if header explicitly references the target series name (e.g. 'v0.2' or 'v0.2.x')
    series_pattern = rf"\b{re.escape(normalized_series)}(?:\.[0-9x]+)?\b"
    if re.search(series_pattern, header_line, re.IGNORECASE):
        return True

    # 3. Check for phase ranges specific to series if defined
    phase_match = re.search(r"\bPhase\s+(\d+(?:\.\d+)?)", header_line, re.IGNORECASE)
    if phase_match:
        try:
            phase_num = float(phase_match.group(1))
            phase_range = _SERIES_PHASE_RANGES.get(normalized_series)
            if phase_range and phase_range[0] <= phase_num <= phase_range[1]:
                return True
        except ValueError:
            pass

    return False


def _is_matrix_series_row(line: str, normalized_series: str) -> bool:
    """Check if a table row corresponds to the target release series."""
    if not line.startswith("|"):
        return False
    row_cells = [cell.strip() for cell in line.split("|")[1:-1]]
    return len(row_cells) >= 6 and _version_matches_series(row_cells[5], normalized_series)


class DocCompactor:
    """Automated documentation compaction engine."""

    def __init__(self, series_title_map: dict[str, str] | None = None) -> None:
        self.series_title_map = series_title_map or _SERIES_SUMMARY_TITLES

    def _extract_roadmap_versions(self, text: str, series: str) -> list[str]:
        """Extract all version numbers matching series in Section 2."""
        pattern = r"###\s+.*?\((v\d+\.\d+\.\d+).*?\)"
        matches = re.findall(pattern, text)
        return [v for v in matches if _version_matches_series(v, series)]

    def _build_roadmap_summary_block(self, series: str, versions: list[str]) -> str:
        """Construct consolidated roadmap summary subsection."""
        title = self.series_title_map.get(
            series, f"Extended Architecture & Automation ({series} Series)"
        )
        start_ver = versions[0] if versions else f"{series}.0"
        end_ver = versions[-1] if versions else f"{series}.x"
        header = f"### {title} ({start_ver} – {end_ver} - Completed)"
        bullets = _SERIES_ROADMAP_BULLETS.get(
            series,
            [
                f"- [x] **{title}**: Consolidated core features and operational automations for {series}."
            ],
        )
        return f"{header}\n" + "\n".join(bullets) + "\n"

    def _compact_roadmap_subsections(self, content: str, series: str) -> tuple[str, bool, int]:
        """Consolidate Section 2 milestone subsections for given series."""
        normalized_series = _normalize_series(series)
        versions = self._extract_roadmap_versions(content, normalized_series)
        if not versions:
            return content, False, 0

        sec2_match = re.search(r"## Release Milestones \(Chronological Order\)\n\n", content)
        sec3_match = re.search(r"\n## Value vs\. Effort Prioritization Matrix", content)
        if not sec2_match or not sec3_match:
            return content, False, 0

        sec2_start = sec2_match.end()
        sec3_start = sec3_match.start()
        sec2_content = content[sec2_start:sec3_start]

        subsection_re = re.compile(
            r"###\s+(.*?)\((v\d+\.\d+\.\d+)[^)]*\)\n(.*?)(?=\n###|\Z)", re.DOTALL
        )
        blocks = list(subsection_re.finditer(sec2_content))
        matching_blocks = [
            b for b in blocks if _version_matches_series(b.group(2), normalized_series)
        ]
        if not matching_blocks:
            return content, False, 0

        first_span_start = matching_blocks[0].start()
        last_span_end = matching_blocks[-1].end()

        summary_block = self._build_roadmap_summary_block(normalized_series, versions)
        new_sec2 = sec2_content[:first_span_start] + summary_block + sec2_content[last_span_end:]
        compacted = content[:sec2_start] + new_sec2 + content[sec3_start:]
        return compacted, True, len(matching_blocks)

    def _compact_roadmap_matrix(self, content: str, series: str) -> tuple[str, bool]:
        """Consolidate Section 3 Prioritization Matrix table rows for given series."""
        normalized_series = _normalize_series(series)
        marker = "## Value vs. Effort Prioritization Matrix"
        if marker not in content:
            return content, False

        header_part, matrix_part = content.split(marker, 1)
        lines = matrix_part.splitlines()

        cleaned_lines: list[str] = []
        replaced = False
        inside_table = False

        for line in lines:
            if line.startswith("|---|"):
                inside_table = True
                cleaned_lines.append(line)
                continue

            if inside_table and _is_matrix_series_row(line, normalized_series):
                if not replaced:
                    summary_rows = _SERIES_MATRIX_SUMMARIES.get(
                        normalized_series,
                        [
                            f"| **Foundation** | Consolidated {normalized_series}.x deliverables | Standard Library | High | Low | {normalized_series}.x | ✅ Completed |"
                        ],
                    )
                    cleaned_lines.extend(summary_rows)
                    replaced = True
                continue
            cleaned_lines.append(line)

        compacted = header_part + marker + "\n".join(cleaned_lines)
        return compacted, replaced

    def compact_roadmap(self, content: str, series: str = "v0.2") -> str:
        """Compact both milestone subsections and matrix rows in ROADMAP.md."""
        compacted, _ = self.compact_roadmap_with_count(content, series)
        return compacted

    def compact_roadmap_with_count(self, content: str, series: str = "v0.2") -> tuple[str, int]:
        """Compact milestone subsections and matrix rows and return (compacted_content, count)."""
        content, _, count = self._compact_roadmap_subsections(content, series)
        content, _ = self._compact_roadmap_matrix(content, series)
        return content, count

    def compact_release_notes(self, content: str, series: str = "v0.2") -> str:
        """Consolidate granular Highlights of vX.Y.Z sections into a single series block."""
        compacted, _ = self.compact_release_notes_with_count(content, series)
        return compacted

    def compact_release_notes_with_count(
        self, content: str, series: str = "v0.2"
    ) -> tuple[str, int]:
        """Consolidate granular Highlights sections and return (compacted_content, count)."""
        normalized_series = _normalize_series(series)
        pattern = re.compile(
            r"## 🚀 Highlights of (v\d+\.\d+\.\d+)\n\n(.*?)(?=\n## 🚀|\n## 🛠️|\Z)",
            re.DOTALL,
        )
        matches = list(pattern.finditer(content))
        matching_sections = [
            m for m in matches if _version_matches_series(m.group(1), normalized_series)
        ]

        if not matching_sections:
            return content, 0

        matched_versions = [m.group(1) for m in matching_sections]
        start_ver = matched_versions[-1] if matched_versions else f"{normalized_series}.0"
        end_ver = matched_versions[0] if matched_versions else f"{normalized_series}.x"

        first_span_start = matching_sections[0].start()
        last_span_end = matching_sections[-1].end()

        bullets = _SERIES_RELEASE_NOTES_BULLETS.get(
            normalized_series,
            [
                f"- **{normalized_series.upper()} Series Modernization**: Consolidated highlights for {normalized_series} release series."
            ],
        )

        series_block = (
            f"## 🚀 Highlights of {normalized_series} Series ({start_ver} – {end_ver} - Completed)\n\n"
            + "\n".join(bullets)
            + "\n\n---\n\n"
        )

        compacted = content[:first_span_start] + series_block + content[last_span_end:]
        return compacted, len(matching_sections)

    def compact_log(self, log_content: str, series: str = "v0.2") -> tuple[str, str]:
        """Separate historical log entries for series into archive content and compacted log."""
        normalized_series = _normalize_series(series)
        lines = log_content.splitlines()

        retained_lines: list[str] = []
        archived_lines: list[str] = [
            f"# Historical Sprint Archive — {normalized_series}.x Series",
            "",
            f"Archived development phases and refactoring logs for {normalized_series}.x.",
            "",
            "---",
            "",
        ]

        current_block: list[str] = []
        is_historical = False
        archive_link_added = False

        for line in lines:
            if line.startswith("### ["):
                _flush_log_block(current_block, is_historical, archived_lines, retained_lines)
                current_block = []
                is_historical = _is_historical_log_header(line, normalized_series)

            current_block.append(line)

        _flush_log_block(current_block, is_historical, archived_lines, retained_lines)

        archive_entry = (
            f"### Historical Sprint Archives\n"
            f"- [{normalized_series}.x Series Log](agent/archive/historical-phases-{normalized_series}.x.md): "
            f"Consolidated sprint logs for {normalized_series}.x development phases.\n\n---\n"
        )

        final_retained: list[str] = []
        for line in retained_lines:
            final_retained.append(line)
            if not archive_link_added and line.startswith(
                "Chronological log of refactoring milestones"
            ):
                final_retained.append("")
                final_retained.append(archive_entry)
                archive_link_added = True

        return "\n".join(final_retained) + "\n", "\n".join(archived_lines) + "\n"

    def compact_all(
        self,
        docs_dir: Path,
        archive_dir: Path,
        series: str = "v0.2",
        dry_run: bool = False,
        check: bool = False,
        compact_roadmap: bool = True,
        compact_release_notes: bool = True,
        compact_log: bool = True,
    ) -> DocCompactionResult:
        """Execute compaction across repository documentation files."""
        normalized_series = _normalize_series(series)
        result = DocCompactionResult(series=normalized_series)
        modified_files: list[str] = []
        total_orig_bytes = 0
        total_new_bytes = 0

        roadmap_path = docs_dir / "ROADMAP.md"
        if compact_roadmap and roadmap_path.exists():
            orig_text = roadmap_path.read_text(encoding="utf-8")
            total_orig_bytes += len(orig_text.encode("utf-8"))
            new_text, roadmap_count = self.compact_roadmap_with_count(orig_text, normalized_series)
            total_new_bytes += len(new_text.encode("utf-8"))
            result.roadmap_sections_count = roadmap_count
            if new_text != orig_text:
                result.roadmap_compacted = True
                modified_files.append(str(roadmap_path))
                if not dry_run and not check:
                    write_text_file(roadmap_path, new_text)

        notes_path = docs_dir / "RELEASE_NOTES.md"
        if compact_release_notes and notes_path.exists():
            orig_text = notes_path.read_text(encoding="utf-8")
            total_orig_bytes += len(orig_text.encode("utf-8"))
            new_text, notes_count = self.compact_release_notes_with_count(
                orig_text, normalized_series
            )
            total_new_bytes += len(new_text.encode("utf-8"))
            result.release_notes_sections_count = notes_count
            if new_text != orig_text:
                result.release_notes_compacted = True
                modified_files.append(str(notes_path))
                if not dry_run and not check:
                    write_text_file(notes_path, new_text)

        log_path = docs_dir / "LOG.md"
        if compact_log and log_path.exists():
            orig_text = log_path.read_text(encoding="utf-8")
            total_orig_bytes += len(orig_text.encode("utf-8"))
            compacted_log, archive_content = self.compact_log(orig_text, normalized_series)
            total_new_bytes += len(compacted_log.encode("utf-8"))
            if compacted_log != orig_text:
                result.log_compacted = True
                archive_file = _resolve_safe_archive_file(
                    archive_dir, f"historical-phases-{normalized_series}.x.md"
                )
                result.archive_file_path = str(archive_file)
                modified_files.append(str(log_path))
                if not dry_run and not check:
                    write_text_file(log_path, compacted_log)
                    write_text_file(archive_file, archive_content)

        result.modified_files = modified_files
        result.bytes_saved = max(0, total_orig_bytes - total_new_bytes)
        return result
