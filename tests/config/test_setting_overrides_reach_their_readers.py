"""A setting that a config file or a variable sets reaches each module that read the setting's
default by name before, and so ignored it (#2447)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner


def _project_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """Load `text` as the project config file, with no data-directory variable over it."""
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(path))
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)


def test_a_chunker_splits_files_by_the_configured_chunk_size_and_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The workspace indexer and the code-retrieval benchmark build their chunker with no sizes, so
    it takes `ai.rag.chunk_size` and `ai.rag.chunk_overlap` from the settings."""
    from devops_cli.ai.rag.chunker import SemanticChunker

    _project_config(
        tmp_path, monkeypatch, "ai:\n  rag:\n    chunk_size: 900\n    chunk_overlap: 90\n"
    )

    chunker = SemanticChunker()

    assert (chunker.chunk_size, chunker.chunk_overlap) == (900, 90)


def test_rag_search_takes_its_top_k_and_min_score_from_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`devops ai rag search` without `--top-k` or `--min-score` uses `ai.rag.top_k` and
    `ai.rag.score_threshold`; the dry run shows the values a search would use."""
    from devops_cli.main import app as main_app

    monkeypatch.setenv("DEVOPS_CLI_AI_RAG_TOP_K", "9")
    monkeypatch.setenv("DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD", "0.6")

    result = CliRunner().invoke(main_app, ["--dry-run", "ai", "rag", "query", "deploy pods"])

    assert (
        result.exit_code,
        '"limit": 9' in result.output,
        '"score_threshold": 0.6' in result.output,
    ) == (0, True, True)


def test_a_retriever_with_no_defaults_takes_them_from_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `rag_search` tool gave the retriever no score threshold, so the threshold of every
    model search was the fixed default."""
    from devops_cli.ai.rag.retriever import SemanticRetriever

    monkeypatch.setenv("DEVOPS_CLI_AI_RAG_TOP_K", "7")
    monkeypatch.setenv("DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD", "0.55")

    retriever = SemanticRetriever(qdrant=cast(Any, object()), embedder=cast(Any, object()))

    assert (retriever.default_top_k, retriever.default_score_threshold) == (7, 0.55)


def test_group_analysis_records_the_sampling_of_the_analysis_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client of the review's `analysis` task sends `ai.tasks.analysis` sampling, so the report
    records it, and not the defaults of `ai.temperature` and `ai.top_p`."""
    from devops_cli.review.analysis import run_group_analysis

    _project_config(
        tmp_path,
        monkeypatch,
        "ai:\n  tasks:\n    analysis:\n      temperature: 0.7\n      top_p: 0.8\n",
    )

    report = run_group_analysis([], llm_client=None, kb_manuals={}, drift_manuals=[])

    assert (report.sampling.temperature, report.sampling.top_p) == (0.7, 0.8)


def test_an_audit_log_destination_in_the_configured_data_directory_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`DEVOPS_CLI_AUDIT_LOG_DEST` must lie in the data directory, which `data.dir` of the config
    file sets."""
    from devops_cli.core.audit import record_audit_event

    data_dir = (tmp_path / "configured-data").resolve()
    _project_config(tmp_path, monkeypatch, f"data:\n  dir: {data_dir}\n")
    destination = data_dir / "logs" / "audit.jsonl"
    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", str(destination))

    record_audit_event("devops example")

    assert destination.is_file()


def test_the_github_quota_ledger_lives_under_the_configured_cache_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each identity's quota ledger and response cache sit under `data.cache_dir`."""
    from devops_cli.github.rate_limiter import resolve_identity_cache_dir

    cache_dir = (tmp_path / "configured-cache").resolve()
    monkeypatch.setenv("DEVOPS_CLI_DATA_CACHE_DIR", str(cache_dir))

    assert resolve_identity_cache_dir("example-identity").parent == cache_dir


def test_the_service_state_lives_under_the_configured_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The roadmap Service keeps its schedules under `data.dir` of the config file."""
    from devops_cli.roadmap.run import service_state_dir

    data_dir = (tmp_path / "configured-data").resolve()
    _project_config(tmp_path, monkeypatch, f"data:\n  dir: {data_dir}\n")

    assert service_state_dir() == data_dir / "roadmap"


def test_the_osv_snapshot_digest_is_stamped_under_the_configured_cache_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no directory given, the snapshot digest of the OSV database is kept under
    `data.cache_dir`."""
    from devops_cli.security.osv_scanner import get_or_compute_snapshot_digest

    cache_dir = (tmp_path / "configured-cache").resolve()
    database = cache_dir / "osv_db" / "PyPI"
    database.mkdir(parents=True)
    (database / "all.zip").write_bytes(b"advisories")
    monkeypatch.setenv("DEVOPS_CLI_DATA_CACHE_DIR", str(cache_dir))
    monkeypatch.chdir(tmp_path)

    get_or_compute_snapshot_digest()

    assert (cache_dir / "osv_db" / ".snapshot_digest").is_file()
