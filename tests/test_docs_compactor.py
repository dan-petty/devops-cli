"""Comprehensive tests for automated documentation compaction engine."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.docs import app as docs_app
from devops_cli.docs.compactor import (
    DocCompactionRequest,
    DocCompactionResult,
    DocCompactor,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def compactor() -> DocCompactor:
    return DocCompactor()


SAMPLE_ROADMAP_MD = """# Strategic Roadmap — devops-cli

High-density product roadmap.

## Release Milestones (Chronological Order)

### Workstation Foundation, SecOps, Multi-Cloud IaC & Core Architecture (v0.0.1 – v0.1.9 - Completed)
- [x] **Runtime Core**: Python 3.14+ runtime with uv virtual environments.
- [x] **IaC Engine**: OpenTofu multi-cloud modules.

### Distributed Observability, Tracing & Telemetry (v0.2.0 - Completed)
- [x] **FastAPI Service Engine**: REST service for CLI invocation.
- [x] **OpenTelemetry SDK**: Distributed span tracing.

### Next-Gen Agentic Architecture (v0.2.1 - Completed)
- [x] **PydanticAI Framework**: Multi-agent review pipelines.
- [x] **Context Budgeting**: Client-side BPE tokenizer budgeting.

### Ephemeral Workload Sandboxing (v0.2.16 - Completed)
- [x] **Workload Sandbox**: Rootless Docker container sandbox.
- [x] **Health Probing**: Endpoint reachability evaluator.

### Multi-Cloud Mesh & Production Ecosystem (v0.3.0 - Future Vision)
- [ ] **Multi-Region Mesh**: Distributed cluster federation.

## Value vs. Effort Prioritization Matrix

| Priority Category | Feature / Focus | Primary Open Source Resource | Value | Effort | Target Release | Status |
|---|---|---|---|---|---|---|
| **Quick Wins** | Foundation, Finding Verification | Standard Library | High | Low | v0.1.x | ✅ Completed |
| | Context Budgeting | `tiktoken` | High | Low | v0.2.1 | ✅ Completed |
| | Dynamic Cost-Aware LLM Router | RouteLLM / Pydantic | High | Low | v0.2.2 | ✅ Completed |
| **Major Projects** | Universal Stage Pipelines | Pipeline SDK | High | High | v0.2.9 | ✅ Completed |
| | Ephemeral Sandboxing | Docker / K8s | High | High | v0.2.16 | ✅ Completed |
| | Multi-Region Mesh | Service Mesh | High | High | v0.3.0 | ⏳ Planned |
"""

SAMPLE_RELEASE_NOTES_MD = """# Release Notes — devops-cli v0.2.16

DevOps CLI release notes.

---

## 🚀 Highlights of v0.2.16

### 📦 Workload Sandboxing Engine
- Ephemeral container execution with resource bounds and security controls.
- Comprehensive health probing, endpoint schema checks, and trace waterfalls.
- Full isolation for multi-container integration runs.

---

## 🚀 Highlights of v0.2.14

### 🌳 Tree-Sitter Polyglot CST Parsing
- Concrete syntax tree parsing across Python, TypeScript, Go, Rust, Java.
- S-expression query resolution and language-agnostic AST graphs.

---

## 🚀 Highlights of v0.2.13

### 🤖 Sub-Agent Local Offloading Engine
- Offload token-intensive exploration to local open models.
- Harness slots for ModelSlot, SkillSlot, ToolSlot, SubAgentSlot.

---

## 🚀 Highlights of v0.2.12

### ⚡ Valkey Distributed Caching Tier
- Zero C-dependency RESP3 wire protocol client.
- Token-bucket sliding window rate limiting and vector embedding cache.

---

## 🚀 Highlights of v0.2.1

### 🤖 PydanticAI Framework
- Standardized agent pipelines with PydanticAI.
- Client-side token budgeting and AST diff chunking.

---

## 🚀 Highlights of v0.1 Series (v0.1.0 – v0.1.13 - Completed)

- **Vector Embedding Benchmarks**: Dense vector evaluation.
- **TLS Certificate Automation**: Native X.509 issuance.

---

## 🛠️ Environment & Requirements
- Python >=3.14
"""

SAMPLE_LOG_MD = """# Active Working Log — devops-cli

Chronological log of refactoring milestones.

### [2026-09-10] Phase 52.1: Workload Sandboxing Engine (Issue #106)
- **Workload Sandbox**: Rootless Docker container sandbox.
- **Testing**: 15 unit tests passing.

### [2026-09-08] Phase 49.8: Review Worker Pool (Issue #58)
- **Parallel Workers**: Implemented ReviewWorkerPool with taskgroup.
- **Testing**: 12 unit tests passing.

### [2026-08-10] Release v0.1.0 Foundation & Core Modernization
- **Initial Core**: Base CLI commands and dry-run models.
- **Testing**: Full suite green.
"""


def test_doc_compactor_models() -> None:
    req = DocCompactionRequest(
        series="v0.2",
        docs_dir=Path("docs"),
        archive_dir=Path("docs/agent/archive"),
        dry_run=True,
    )
    assert req.series == "v0.2"
    assert req.dry_run is True

    res = DocCompactionResult(
        series="v0.2",
        roadmap_compacted=True,
        roadmap_sections_count=3,
        release_notes_compacted=True,
        release_notes_sections_count=2,
        log_compacted=True,
        archive_file_path="docs/agent/archive/historical-phases-v0.2.x.md",
        modified_files=["docs/ROADMAP.md", "docs/RELEASE_NOTES.md", "docs/LOG.md"],
        bytes_saved=1200,
    )
    assert res.series == "v0.2"
    assert res.bytes_saved == 1200
    assert len(res.modified_files) == 3


def test_compact_roadmap_subsections(compactor: DocCompactor) -> None:
    compacted = compactor.compact_roadmap(SAMPLE_ROADMAP_MD, series="v0.2")

    # Should retain v0.1.x compacted block
    assert (
        "### Workstation Foundation, SecOps, Multi-Cloud IaC & Core Architecture (v0.0.1 – v0.1.9 - Completed)"
        in compacted
    )

    # Should replace individual v0.2.0, v0.2.1, v0.2.16 with single consolidated section
    assert (
        "### Distributed Observability, Tracing & Telemetry (v0.2.0 - Completed)" not in compacted
    )
    assert "### Next-Gen Agentic Architecture (v0.2.1 - Completed)" not in compacted
    assert "### Ephemeral Workload Sandboxing (v0.2.16 - Completed)" not in compacted

    # Consolidated summary header should exist
    assert "v0.2" in compacted
    assert "Completed)" in compacted

    # Should preserve future milestone v0.3.0
    assert "### Multi-Cloud Mesh & Production Ecosystem (v0.3.0 - Future Vision)" in compacted


def test_compact_roadmap_matrix_table(compactor: DocCompactor) -> None:
    compacted = compactor.compact_roadmap(SAMPLE_ROADMAP_MD, series="v0.2")

    # Granular v0.2.1 and v0.2.9 entries in table should be consolidated
    assert "v0.2.1 | ✅ Completed" not in compacted
    assert "v0.2.9 | ✅ Completed" not in compacted

    # Compact category rows should be present
    assert "| v0.2.x | ✅ Completed |" in compacted

    # v0.1.x and future v0.3.0 rows should still be present
    assert "| v0.1.x | ✅ Completed |" in compacted
    assert "| v0.3.0 | ⏳ Planned |" in compacted


def test_compact_release_notes(compactor: DocCompactor) -> None:
    compacted = compactor.compact_release_notes(SAMPLE_RELEASE_NOTES_MD, series="v0.2")

    # Individual highlights should be removed
    assert "## 🚀 Highlights of v0.2.16" not in compacted
    assert "## 🚀 Highlights of v0.2.1" not in compacted

    # Consolidated series section should exist
    assert "## 🚀 Highlights of v0.2 Series" in compacted

    # Existing v0.1 Series should remain
    assert "## 🚀 Highlights of v0.1 Series (v0.1.0 – v0.1.13 - Completed)" in compacted

    # Environment requirements should remain
    assert "## 🛠️ Environment & Requirements" in compacted


def test_compact_log(compactor: DocCompactor) -> None:
    compacted_log, archive_content = compactor.compact_log(SAMPLE_LOG_MD, series="v0.2")

    # Archive should contain archived phase items
    assert "Phase 52.1" in archive_content or "Phase 49.8" in archive_content
    assert "Historical Sprint Archive" in archive_content

    # Compacted log should contain archive index link
    assert "historical-phases-v0.2.x.md" in compacted_log


def test_compact_all_dry_run(tmp_path: Path, compactor: DocCompactor) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    archive_dir = docs_dir / "agent" / "archive"

    roadmap_file = docs_dir / "ROADMAP.md"
    notes_file = docs_dir / "RELEASE_NOTES.md"
    log_file = docs_dir / "LOG.md"

    roadmap_file.write_text(SAMPLE_ROADMAP_MD, encoding="utf-8")
    notes_file.write_text(SAMPLE_RELEASE_NOTES_MD, encoding="utf-8")
    log_file.write_text(SAMPLE_LOG_MD, encoding="utf-8")

    result = compactor.compact_all(
        docs_dir=docs_dir,
        archive_dir=archive_dir,
        series="v0.2",
        dry_run=True,
    )

    assert result.roadmap_compacted is True
    assert result.release_notes_compacted is True
    assert result.log_compacted is True
    assert result.bytes_saved >= 0

    # In dry run, files on disk should be unchanged!
    assert roadmap_file.read_text(encoding="utf-8") == SAMPLE_ROADMAP_MD
    assert notes_file.read_text(encoding="utf-8") == SAMPLE_RELEASE_NOTES_MD
    assert log_file.read_text(encoding="utf-8") == SAMPLE_LOG_MD
    assert not archive_dir.exists()


def test_compact_all_write(tmp_path: Path, compactor: DocCompactor) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    archive_dir = docs_dir / "agent" / "archive"

    roadmap_file = docs_dir / "ROADMAP.md"
    notes_file = docs_dir / "RELEASE_NOTES.md"
    log_file = docs_dir / "LOG.md"

    roadmap_file.write_text(SAMPLE_ROADMAP_MD, encoding="utf-8")
    notes_file.write_text(SAMPLE_RELEASE_NOTES_MD, encoding="utf-8")
    log_file.write_text(SAMPLE_LOG_MD, encoding="utf-8")

    result = compactor.compact_all(
        docs_dir=docs_dir,
        archive_dir=archive_dir,
        series="v0.2",
        dry_run=False,
    )

    assert result.roadmap_compacted is True
    assert result.release_notes_compacted is True
    assert result.log_compacted is True

    # Files should now be mutated
    assert roadmap_file.read_text(encoding="utf-8") != SAMPLE_ROADMAP_MD
    assert notes_file.read_text(encoding="utf-8") != SAMPLE_RELEASE_NOTES_MD
    assert log_file.read_text(encoding="utf-8") != SAMPLE_LOG_MD

    # Archive file should exist
    archive_file = archive_dir / "historical-phases-v0.2.x.md"
    assert archive_file.exists()
    assert len(archive_file.read_text(encoding="utf-8")) > 0


def test_cli_docs_compact_help(runner: CliRunner) -> None:
    result = runner.invoke(docs_app, ["compact", "--help"])
    assert result.exit_code == 0
    assert "compact" in result.output.lower()
    assert "--series" in result.output
    assert "--dry-run" in result.output
    assert "--check" in result.output


def test_cli_docs_compact_dry_run(tmp_path: Path, runner: CliRunner) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    archive_dir = docs_dir / "agent" / "archive"

    (docs_dir / "ROADMAP.md").write_text(SAMPLE_ROADMAP_MD, encoding="utf-8")
    (docs_dir / "RELEASE_NOTES.md").write_text(SAMPLE_RELEASE_NOTES_MD, encoding="utf-8")
    (docs_dir / "LOG.md").write_text(SAMPLE_LOG_MD, encoding="utf-8")

    result = runner.invoke(
        docs_app,
        [
            "compact",
            "--series",
            "v0.2",
            "--docs-dir",
            str(docs_dir),
            "--archive-dir",
            str(archive_dir),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "devops docs compact" in result.output
    assert (docs_dir / "ROADMAP.md").read_text(encoding="utf-8") == SAMPLE_ROADMAP_MD
    assert not archive_dir.exists()
    from devops_cli.dry_run.state import is_dry_run

    assert is_dry_run() is False


def test_cli_docs_compact_check_mode(tmp_path: Path, runner: CliRunner) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    archive_dir = docs_dir / "agent" / "archive"

    (docs_dir / "ROADMAP.md").write_text(SAMPLE_ROADMAP_MD, encoding="utf-8")
    (docs_dir / "RELEASE_NOTES.md").write_text(SAMPLE_RELEASE_NOTES_MD, encoding="utf-8")
    (docs_dir / "LOG.md").write_text(SAMPLE_LOG_MD, encoding="utf-8")

    # Needs compaction -> check should exit with 1
    result = runner.invoke(
        docs_app,
        [
            "compact",
            "--series",
            "v0.2",
            "--docs-dir",
            str(docs_dir),
            "--archive-dir",
            str(archive_dir),
            "--check",
        ],
    )
    assert result.exit_code == 1


def test_doc_compaction_error_bounds_details() -> None:
    """Verify DocCompactionError bounds series, target_file, and details to 256 chars."""
    from devops_cli.exceptions.docs import DocCompactionError

    huge_series = "v" + "0" * 300
    huge_path = "/path/to/" + "a" * 300
    huge_detail = "x" * 500

    err = DocCompactionError(
        "Compaction failed",
        series=huge_series,
        target_file=huge_path,
        details={"huge_field": huge_detail, "int_val": 42},
    )
    assert len(err.details["series"]) == 256
    assert len(err.details["target_file"]) == 256
    assert len(err.details["huge_field"]) == 256
    assert err.details["int_val"] == 42


def test_doc_compactor_invalid_series_syntax(compactor: DocCompactor) -> None:
    """Verify DocCompactionError is raised for invalid series syntax or traversal attempts."""
    from devops_cli.exceptions.docs import DocCompactionError

    for bad_series in ["../../outside", "v0.2/../../etc", "invalid!series", "v0.2;rm -rf /"]:
        with pytest.raises(DocCompactionError):
            compactor.compact_roadmap("# Roadmap", series=bad_series)


def test_compact_log_preserves_other_series(compactor: DocCompactor) -> None:
    """Ensure compact_log with series='v0.2' does NOT archive v0.1 entries."""
    compacted_log, archive_content = compactor.compact_log(SAMPLE_LOG_MD, series="v0.2")

    # Release v0.1.0 belongs to v0.1 and must remain in retained log
    assert "Release v0.1.0 Foundation & Core Modernization" in compacted_log
    assert "Release v0.1.0" not in archive_content


def test_doc_compactor_section_counters(tmp_path: Path, compactor: DocCompactor) -> None:
    """Verify DocCompactionResult populates roadmap and release notes section counters."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    archive_dir = docs_dir / "agent" / "archive"

    (docs_dir / "ROADMAP.md").write_text(SAMPLE_ROADMAP_MD, encoding="utf-8")
    (docs_dir / "RELEASE_NOTES.md").write_text(SAMPLE_RELEASE_NOTES_MD, encoding="utf-8")
    (docs_dir / "LOG.md").write_text(SAMPLE_LOG_MD, encoding="utf-8")

    res = compactor.compact_all(
        docs_dir=docs_dir,
        archive_dir=archive_dir,
        series="v0.2",
        dry_run=True,
    )
    assert res.roadmap_sections_count > 0
    assert res.release_notes_sections_count > 0
