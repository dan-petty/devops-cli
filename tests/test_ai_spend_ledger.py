"""Unit tests for SQLite lifetime spend ledger, schema initialization, and aggregation reports."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from devops_cli.ai.spend.ledger import SpendLedger, track_request_spend


def test_spend_ledger_schema_and_wal_initialization(tmp_path: Path) -> None:
    """Verify SpendLedger initializes SQLite schema with WAL journal mode and indexes."""
    db_path = tmp_path / "spend.db"
    SpendLedger(db_path=db_path)

    with sqlite3.connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        ]

    assert (journal_mode.lower(), "ai_spend_records" in tables) == ("wal", True)


def test_spend_ledger_record_and_aggregate_by_server(tmp_path: Path) -> None:
    """Verify recording spend requests and aggregating lifetime report by server."""
    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=1000,
        completion_tokens=200,
        cost_usd=0.00014,
        duration_seconds=1.2,
    )
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=2000,
        completion_tokens=400,
        cost_usd=0.00028,
        duration_seconds=2.4,
    )
    ledger.record_request(
        provider="vllm",
        server="example.com:8080",
        model="deepseek-chat",
        prompt_tokens=5000,
        completion_tokens=1000,
        cost_usd=0.010,
        duration_seconds=3.0,
    )

    report = ledger.get_lifetime_report(group_by="server")
    servers = {s.server: s for s in report.servers}

    assert (
        report.total_requests,
        report.total_tokens,
        round(report.total_spend_usd, 5),
        len(report.servers),
    ) == (
        3,
        9600,
        0.01042,
        2,
    )

    local_summary = servers["localhost:11434"]
    assert (
        local_summary.request_count,
        local_summary.total_tokens,
        local_summary.prompt_tokens,
        local_summary.completion_tokens,
        round(local_summary.approx_spend_usd, 5),
    ) == (
        2,
        3600,
        3000,
        600,
        0.00042,
    )


def test_spend_ledger_aggregate_by_model_and_provider(tmp_path: Path) -> None:
    """Verify aggregating lifetime report by model, provider, and all dimensions."""
    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    ledger.record_request(
        provider="openai",
        server="example.com",
        model="gpt-4o",
        prompt_tokens=1000,
        completion_tokens=500,
        cost_usd=0.0075,
        duration_seconds=0.8,
    )

    report_model = ledger.get_lifetime_report(group_by="model")
    report_provider = ledger.get_lifetime_report(group_by="provider")
    report_all = ledger.get_lifetime_report(group_by="all")

    assert (
        len(report_model.models),
        report_model.models[0].model,
        len(report_provider.providers),
        report_provider.providers[0].provider,
        len(report_all.servers),
        len(report_all.models),
        len(report_all.providers),
    ) == (
        1,
        "gpt-4o",
        1,
        "openai",
        1,
        1,
        1,
    )


def test_spend_ledger_reset(tmp_path: Path) -> None:
    """Verify ledger reset clears all recorded entries."""
    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    ledger.record_request(
        provider="test",
        server="localhost",
        model="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
        duration_seconds=0.5,
    )

    count_before = ledger.get_lifetime_report().total_requests
    ledger.reset()
    count_after = ledger.get_lifetime_report().total_requests

    assert (count_before, count_after) == (1, 0)


def test_track_request_spend_graceful_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify track_request_spend traps any database exceptions and never crashes the caller."""

    def fail_record(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError("Simulated database failure")

    monkeypatch.setattr(SpendLedger, "record_request", fail_record)

    # Should not raise exception
    record = track_request_spend(
        provider="ollama",
        model="llama3:8b",
        server="localhost:11434",
        prompt_tokens=100,
        completion_tokens=50,
        duration_seconds=1.0,
    )

    assert record is None
