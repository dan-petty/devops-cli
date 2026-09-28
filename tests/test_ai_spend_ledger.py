"""Unit tests for SQLite lifetime spend ledger, schema initialization, and aggregation reports."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
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


def test_spend_ledger_stage_column_migration_in_place(tmp_path: Path) -> None:
    """Verify an existing database without a stage column is migrated in-place."""
    db_path = tmp_path / "spend_legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE ai_spend_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                server TEXT NOT NULL,
                backend_info TEXT,
                served_by TEXT,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0.0,
                cached INTEGER NOT NULL DEFAULT 0,
                request_type TEXT NOT NULL DEFAULT 'chat',
                duration_seconds REAL NOT NULL DEFAULT 0.0
            );
            """
        )
        conn.execute(
            """
            INSERT INTO ai_spend_records (
                timestamp, provider, server, model, prompt_tokens, completion_tokens,
                total_tokens, cost_usd, cached, request_type, duration_seconds
            ) VALUES ('2026-09-26T12:00:00Z', 'ollama', 'localhost:11434', 'llama3:8b', 10, 5, 15, 0.001, 0, 'chat', 1.0);
            """
        )

    ledger = SpendLedger(db_path=db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(ai_spend_records);").fetchall()
        }
        indices = {
            row[1] for row in conn.execute("PRAGMA index_list(ai_spend_records);").fetchall()
        }

    report = ledger.get_lifetime_report(group_by="all")
    stage_breakdown = {s.stage: s for s in report.stages}

    assert (
        "stage" in columns,
        "idx_spend_stage" in indices,
        report.total_requests,
        len(report.stages),
        "unattributed" in stage_breakdown,
        stage_breakdown["unattributed"].request_count,
    ) == (
        True,
        True,
        1,
        1,
        True,
        1,
    )


def test_spend_ledger_record_and_aggregate_by_stage(tmp_path: Path) -> None:
    """Verify recording with various stages and aggregating under by-stage breakdown."""
    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=500,
        completion_tokens=100,
        cost_usd=0.0002,
        stage="review.file_review",
    )
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=300,
        completion_tokens=50,
        cost_usd=0.0001,
        stage="review.verification",
    )
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=200,
        completion_tokens=40,
        cost_usd=0.00005,
        stage=None,
    )

    report = ledger.get_lifetime_report(group_by="all")
    stages = {s.stage: s for s in report.stages}

    assert (
        len(report.stages),
        stages["review.file_review"].request_count,
        stages["review.file_review"].total_tokens,
        stages["review.verification"].request_count,
        stages["review.verification"].total_tokens,
        stages["unattributed"].request_count,
        stages["unattributed"].total_tokens,
    ) == (
        3,
        1,
        600,
        1,
        350,
        1,
        240,
    )


def test_stage_scope_and_resolve_spend_stage() -> None:
    """Verify stage_scope context management and resolve_spend_stage fallback rules."""
    from devops_cli.ai.spend import current_stage, resolve_spend_stage, stage_scope

    assert (current_stage.get(), resolve_spend_stage()) == (None, None)

    with stage_scope("review.file_review"):
        in_scope = current_stage.get()
        resolved_in_scope = resolve_spend_stage()
        resolved_with_task = resolve_spend_stage(None, task_name="chat")
    after_scope = current_stage.get()

    fallback_chat = resolve_spend_stage(None, task_name="chat")
    fallback_unknown = resolve_spend_stage(None, task_name="nonexistent_task")
    unknown_explicit = resolve_spend_stage("unrecognized_stage")

    assert (
        in_scope,
        resolved_in_scope,
        resolved_with_task,
        after_scope,
        fallback_chat,
        fallback_unknown,
        unknown_explicit,
    ) == (
        "review.file_review",
        "review.file_review",
        "review.file_review",
        None,
        "chat",
        None,
        None,
    )


def test_ai_config_task_name_via_for_task() -> None:
    """Verify AIConfig.for_task populates task_name only for valid AITasksConfig fields."""
    from devops_cli.config.settings import AIConfig

    base_config = AIConfig()
    chat_config = base_config.for_task("chat")
    verification_config = base_config.for_task("verification")
    unknown_config = base_config.for_task("unregistered_stage_or_task")

    assert (
        base_config.task_name,
        chat_config.task_name,
        verification_config.task_name,
        unknown_config.task_name,
    ) == (
        None,
        "chat",
        "verification",
        None,
    )


def test_devops_ai_cost_cli_by_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI rendering of --by stage in table and json formats."""
    import json

    from typer.testing import CliRunner

    from devops_cli.commands.ai_cost import app

    runner = CliRunner()
    db_path = tmp_path / "cli_spend.db"
    ledger = SpendLedger(db_path=db_path)
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=400,
        completion_tokens=100,
        cost_usd=0.00015,
        stage="review.file_review",
    )
    monkeypatch.setattr("devops_cli.commands.ai_cost.get_spend_ledger", lambda: ledger)

    res_table = runner.invoke(app, ["report", "--by", "stage"])
    res_json = runner.invoke(app, ["report", "--by", "stage", "--format", "json"])

    data = json.loads(res_json.output)
    stages = data.get("stages", [])

    assert (
        res_table.exit_code,
        "AI Spend & Usage by Execution Stage" in res_table.output,
        "review.file_review" in res_table.output,
        res_json.exit_code,
        len(stages),
        stages[0]["stage"],
        stages[0]["request_count"],
    ) == (
        0,
        True,
        True,
        0,
        1,
        "review.file_review",
        1,
    )


def test_spend_ledger_counterfactual_and_hardware_payoff(tmp_path: Path) -> None:
    """Verify counterfactual pricing on read and hardware payoff tracking for local calls."""
    db_path = tmp_path / "payoff_spend.db"
    ledger = SpendLedger(db_path=db_path)

    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="llama3:8b",
        prompt_tokens=3000,
        completion_tokens=600,
        cost_usd=0.0,
        duration_seconds=1.5,
    )
    ledger.record_request(
        provider="vllm",
        server="example.com:8080",
        model="deepseek-chat",
        prompt_tokens=5000,
        completion_tokens=1000,
        cost_usd=0.010,
        duration_seconds=2.0,
    )

    report = ledger.get_lifetime_report(
        reference_model="gpt-4o",
        hardware_cost_usd=100.0,
    )
    payoff = report.hardware_payoff
    assert payoff is not None
    assert (
        report.reference_model,
        report.local_requests,
        report.local_tokens,
        report.local_prompt_tokens,
        report.local_completion_tokens,
        report.local_cost_equivalent_usd,
        report.counterfactual_spend_usd,
        round(report.counterfactual_savings_usd, 4),
        payoff.hardware_cost_usd,
        payoff.is_paid_off,
        round(payoff.remaining_usd, 4),
    ) == (
        "gpt-4o",
        1,
        3600,
        3000,
        600,
        0.0135,
        0.036,
        0.026,
        100.0,
        False,
        99.9865,
    )


def test_spend_ledger_iso_date_filtering(tmp_path: Path) -> None:
    """Verify ISO 8601 timestamp filtering eliminates lexical day leakage."""
    db_path = tmp_path / "filter_spend.db"
    ledger = SpendLedger(db_path=db_path)

    now = datetime.now(UTC)
    ts_recent = (now - timedelta(days=2)).isoformat()
    ts_old = (now - timedelta(days=12)).isoformat()

    ledger.record_request(
        provider="anthropic",
        server="example.com",
        model="claude-3-5-sonnet",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
        timestamp=ts_recent,
    )
    ledger.record_request(
        provider="anthropic",
        server="example.com",
        model="claude-3-5-sonnet",
        prompt_tokens=200,
        completion_tokens=100,
        cost_usd=0.002,
        timestamp=ts_old,
    )

    report_7d = ledger.get_lifetime_report(days=7)
    report_all = ledger.get_lifetime_report(days=None)

    assert (report_7d.total_requests, report_all.total_requests) == (1, 2)


def test_spend_ledger_init_db_duplicate_column_tolerance(tmp_path: Path) -> None:
    """Verify concurrent schema migrations tolerate duplicate column errors."""
    db_path = tmp_path / "race_spend.db"
    ledger = SpendLedger(db_path=db_path)

    # Calling _init_db again when columns exist is safe and idempotent
    ledger._init_db()

    with sqlite3.connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ai_spend_records);").fetchall()}

    assert ("served_by" in cols, "stage" in cols) == (True, True)


def test_spend_ledger_export_prometheus_with_report(tmp_path: Path) -> None:
    """Verify export_ai_spend_prometheus accepts precomputed report."""
    from devops_cli.ai.spend.prometheus import export_ai_spend_prometheus

    db_path = tmp_path / "prom_spend.db"
    ledger = SpendLedger(db_path=db_path)
    ledger.record_request(
        provider="openai",
        server="example.com",
        model="gpt-4o",
        prompt_tokens=500,
        completion_tokens=100,
        cost_usd=0.005,
    )
    report = ledger.get_lifetime_report(days=3, reference_model="gpt-4o")
    prom_output = export_ai_spend_prometheus(report=report)

    assert (
        "devops_cli_ai_counterfactual_spend_usd" in prom_output,
        "devops_cli_ai_tokens_total" in prom_output,
    ) == (True, True)
