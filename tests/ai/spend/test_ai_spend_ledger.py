"""Unit tests for SQLite lifetime spend ledger, schema initialization, and aggregation reports."""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.spend.ledger import SpendLedger, observe_llm_calls, track_request_spend


def test_spend_ledger_schema_and_wal_initialization(tmp_path: Path) -> None:
    """Verify SpendLedger initializes SQLite schema with WAL journal mode and indexes."""
    db_path = tmp_path / "spend.db"
    SpendLedger(db_path=db_path)

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
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
        provider="openai",
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


def test_track_request_spend_graceful_error_handling(
    monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
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
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
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
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
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
        stage="compose",
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
        stages["compose"].request_count,
        stages["compose"].total_tokens,
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
    analysis_config = base_config.for_task("analysis")
    unknown_config = base_config.for_task("unregistered_stage_or_task")

    assert (
        base_config.task_name,
        chat_config.task_name,
        analysis_config.task_name,
        unknown_config.task_name,
    ) == (
        None,
        "chat",
        "analysis",
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
        provider="openai",
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


# The ledger schema before the finish_reason column existed.
_SCHEMA_BEFORE_FINISH_REASON = """
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
    duration_seconds REAL NOT NULL DEFAULT 0.0,
    stage TEXT
);
"""


def _columns(db_path: Path) -> set[str]:
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(ai_spend_records);")}


def _finish_reasons(db_path: Path) -> list[tuple[str, str | None]]:
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(
            "SELECT model, finish_reason FROM ai_spend_records ORDER BY id"
        ).fetchall()


def test_a_ledger_records_each_replys_finish_reason(tmp_path: Path) -> None:
    """Verify a new ledger has the column, and a recorded reason reaches the row and observers."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    seen: list[dict[str, object]] = []

    with observe_llm_calls(seen.append):
        record = track_request_spend(
            provider="ollama",
            model="llama3:8b",
            server="localhost:11434",
            prompt_tokens=10,
            completion_tokens=5,
            finish_reason="length",
            ledger=ledger,
        )

    assert (
        "finish_reason" in _columns(ledger.db_path),
        record.finish_reason if record else None,
        [call["finish_reason"] for call in seen],
        _finish_reasons(ledger.db_path),
    ) == (True, "length", ["length"], [("llama3:8b", "length")])


def test_an_existing_ledger_gains_the_finish_reason_column(tmp_path: Path) -> None:
    """Verify a ledger written before finish_reason existed keeps its rows and records it."""
    db_path = tmp_path / "spend.db"
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(_SCHEMA_BEFORE_FINISH_REASON)
        conn.execute(
            "INSERT INTO ai_spend_records (timestamp, provider, server, model) "
            "VALUES ('2026-09-01T00:00:00+00:00', 'ollama', 'local', 'qwen')"
        )

    SpendLedger(db_path=db_path).record_request(
        provider="ollama",
        server="local",
        model="llama3:8b",
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.0,
        finish_reason="stop",
    )

    assert _finish_reasons(db_path) == [("qwen", None), ("llama3:8b", "stop")]


def test_spend_ledger_init_db_duplicate_column_tolerance(tmp_path: Path) -> None:
    """Verify concurrent schema migrations tolerate duplicate column errors."""
    db_path = tmp_path / "race_spend.db"
    ledger = SpendLedger(db_path=db_path)

    # Calling _init_db again when columns exist is safe and idempotent
    ledger._init_db()

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ai_spend_records);").fetchall()}

    assert ("served_by" in cols, "stage" in cols, "finish_reason" in cols) == (True, True, True)


def _pricing_sources(db_path: Path) -> list[tuple[str, str | None, float]]:
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(
            "SELECT model, pricing_source, cost_usd FROM ai_spend_records ORDER BY id"
        ).fetchall()


def test_each_request_records_where_its_price_came_from(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A hosted model that genai-prices does not know was stored at $0 and nothing recorded that
    it went unpriced. Each row now stores its pricing source: genai-prices and its provider,
    `local`, or `unknown` with one warning for each model; a cached reply ran no model and has
    none (#1672)."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    caplog.set_level(logging.WARNING)
    for model, server, provider, cached in (
        ("gpt-4o", "example.com", "openai", False),
        ("gpt-9-preview", "example.com", "openai", False),
        ("gpt-9-preview", "example.com", "openai", False),
        ("qwen3:8b", "localhost:11434", "ollama", False),
        ("gpt-4o", "cache", "openai", True),
    ):
        track_request_spend(
            provider=provider,
            model=model,
            server=server,
            prompt_tokens=1_000_000,
            completion_tokens=0,
            cached=cached,
            ledger=ledger,
        )

    assert (
        _pricing_sources(ledger.db_path),
        sum("gpt-9-preview" in record.getMessage() for record in caplog.records),
    ) == (
        [
            ("gpt-4o", "genai_prices:openai", 2.5),
            ("gpt-9-preview", "unknown", 0.0),
            ("gpt-9-preview", "unknown", 0.0),
            ("qwen3:8b", "local", 0.0),
            ("gpt-4o", None, 0.0),
        ],
        1,
    )


def test_an_existing_ledger_gains_the_pricing_source_column(tmp_path: Path) -> None:
    """Verify a ledger written before pricing_source existed keeps its rows and records it."""
    db_path = tmp_path / "spend.db"
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(_SCHEMA_BEFORE_FINISH_REASON)
        conn.execute(
            "INSERT INTO ai_spend_records (timestamp, provider, server, model) "
            "VALUES ('2026-09-01T00:00:00+00:00', 'ollama', 'local', 'qwen')"
        )

    SpendLedger(db_path=db_path).record_request(
        provider="ollama",
        server="local",
        model="llama3:8b",
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.0,
        pricing_source="local",
    )

    assert _pricing_sources(db_path) == [("qwen", None, 0.0), ("llama3:8b", "local", 0.0)]


def test_an_existing_ledger_gains_the_served_model_column(tmp_path: Path) -> None:
    """Verify a ledger written before served_model existed keeps its rows and records the
    deployment model that a gateway reply names (#2031)."""
    db_path = tmp_path / "spend.db"
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(_SCHEMA_BEFORE_FINISH_REASON)
        conn.execute(
            "INSERT INTO ai_spend_records (timestamp, provider, server, model) "
            "VALUES ('2026-09-01T00:00:00+00:00', 'ollama', 'local', 'qwen')"
        )

    SpendLedger(db_path=db_path).record_request(
        provider="gateway",
        server="example.com:4000",
        model="devops-chat",
        served_model="openai/gpt-4o",
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.0,
    )

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT model, served_model FROM ai_spend_records ORDER BY id")
        assert rows.fetchall() == [("qwen", None), ("devops-chat", "openai/gpt-4o")]


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
        "devops_cli_ai_ledger_counterfactual_spend_usd" in prom_output,
        "devops_cli_ai_ledger_tokens" in prom_output,
    ) == (True, True)


def test_add_column_duplicate_tolerance_and_stale_column_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify _add_column tolerates existing columns and _init_db succeeds when column check is stale (#661)."""
    from devops_cli.ai.spend.ledger import _add_column

    db_path = tmp_path / "stale_check.db"
    ledger = SpendLedger(db_path=db_path)

    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        _add_column(conn, "ALTER TABLE ai_spend_records ADD COLUMN served_by TEXT;")

    # Simulate stale column check in _init_db returning empty cursor
    real_get_conn = ledger._get_connection

    class StaleConnProxy:
        def __init__(self, conn: sqlite3.Connection) -> None:
            self._conn = conn

        def execute(self, sql: str, *args: Any) -> Any:
            if "table_info" in sql:
                cursor = self._conn.cursor()
                cursor.execute("SELECT 1 WHERE 0")
                return cursor
            return self._conn.execute(sql, *args)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._conn, name)

        def __enter__(self) -> StaleConnProxy:
            self._conn.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self._conn.__exit__(*args)

    monkeypatch.setattr(ledger, "_get_connection", lambda: StaleConnProxy(real_get_conn()))
    ledger._init_db()

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ai_spend_records);").fetchall()}
    assert ("served_by" in cols, "stage" in cols, "finish_reason" in cols) == (True, True, True)


def test_spend_ledger_days_filter_excludes_earlier_record_on_cutoff_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify --days filter excludes a record from earlier on the cutoff calendar day than the cutoff timestamp (#661)."""
    import devops_cli.ai.spend.ledger as ledger_mod

    db_path = tmp_path / "cutoff_test.db"
    ledger = SpendLedger(db_path=db_path)

    pinned_now = datetime(2026, 10, 11, 15, 0, 0, tzinfo=UTC)

    class PinnedDatetime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return pinned_now

    monkeypatch.setattr(ledger_mod, "datetime", PinnedDatetime)

    # Cutoff for days=1 is 2026-10-10T15:00:00+00:00
    # Earlier on the cutoff calendar day (2026-10-10 10:00): should be EXCLUDED
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="earlier-on-cutoff-day",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
        timestamp="2026-10-10T10:00:00+00:00",
    )
    # Later on the cutoff calendar day (2026-10-10 16:00): should be INCLUDED
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="later-on-cutoff-day",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
        timestamp="2026-10-10T16:00:00+00:00",
    )
    # Today (2026-10-11 12:00): should be INCLUDED
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="today-record",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
        timestamp="2026-10-11T12:00:00+00:00",
    )

    report = ledger.get_lifetime_report(days=1, group_by="model")
    models = {m.model for m in report.models}
    assert (
        report.total_requests,
        "earlier-on-cutoff-day" in models,
        "later-on-cutoff-day" in models,
        "today-record" in models,
    ) == (2, False, True, True)


def test_spend_ledger_cli_prometheus_filtering_and_reference_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify devops ai cost report and bare devops ai cost with prometheus format filter by days and hardware cost (#661)."""
    import re

    from typer.testing import CliRunner

    from devops_cli.commands.ai_cost import app as cost_app

    cli_runner = CliRunner()
    db_path = tmp_path / "prom_cli_spend.db"
    ledger = SpendLedger(db_path=db_path)

    now = datetime.now(UTC)
    three_days_ago = now - timedelta(days=3)

    ledger.record_request(
        provider="openai",
        server="example.com",
        model="model-today",
        prompt_tokens=10_000,
        completion_tokens=2_000,
        cost_usd=0.05,
        timestamp=now.isoformat(),
    )
    ledger.record_request(
        provider="openai",
        server="example.com",
        model="model-old",
        prompt_tokens=5_000,
        completion_tokens=1_000,
        cost_usd=0.02,
        timestamp=three_days_ago.isoformat(),
    )

    monkeypatch.setattr("devops_cli.commands.ai_cost.get_spend_ledger", lambda: ledger)

    # 1. Report command with --reference-model gpt-4o
    res_4o = cli_runner.invoke(
        cost_app,
        [
            "report",
            "--format",
            "prometheus",
            "--days",
            "1",
            "--hardware-cost",
            "1000",
            "--reference-model",
            "gpt-4o",
        ],
    )
    assert (
        res_4o.exit_code,
        'devops_cli_ai_ledger_requests{model="model-today"' in res_4o.stdout,
        'model="model-old"' not in res_4o.stdout,
        "devops_cli_ai_ledger_hardware_cost_usd 1000.0" in res_4o.stdout,
    ) == (0, True, True, True)

    match_4o = re.search(
        r"devops_cli_ai_ledger_counterfactual_spend_usd\s+([0-9.]+)", res_4o.stdout
    )
    assert match_4o is not None
    cf_spend_4o = float(match_4o.group(1))

    # 2. Report command with --reference-model gpt-4o-mini -> counterfactual spend changes
    res_mini = cli_runner.invoke(
        cost_app,
        [
            "report",
            "--format",
            "prometheus",
            "--days",
            "1",
            "--hardware-cost",
            "1000",
            "--reference-model",
            "gpt-4o-mini",
        ],
    )
    match_mini = re.search(
        r"devops_cli_ai_ledger_counterfactual_spend_usd\s+([0-9.]+)", res_mini.stdout
    )
    assert match_mini is not None
    cf_spend_mini = float(match_mini.group(1))
    assert (res_mini.exit_code, cf_spend_4o != cf_spend_mini) == (0, True)

    # 3. Bare devops ai cost --format prometheus behaves same way
    res_bare = cli_runner.invoke(
        cost_app,
        [
            "--format",
            "prometheus",
            "--days",
            "1",
            "--hardware-cost",
            "1000",
            "--reference-model",
            "gpt-4o",
        ],
    )
    assert (
        res_bare.exit_code,
        'devops_cli_ai_ledger_requests{model="model-today"' in res_bare.stdout,
        'model="model-old"' not in res_bare.stdout,
        "devops_cli_ai_ledger_hardware_cost_usd 1000.0" in res_bare.stdout,
    ) == (0, True, True, True)


def test_a_new_ledger_opens_from_several_threads_at_once(tmp_path: Path) -> None:
    """Switching a database to WAL needs an exclusive lock that SQLite refuses at once, whatever
    the connection's timeout, so five threads that open the same new ledger together failed with
    "database is locked" in a few trials of every hundred (#1820). Forty new ledgers make the
    failure at the base near certain."""
    failures: list[str] = []

    def open_ledger(db_path: Path, start: threading.Barrier) -> None:
        start.wait()
        try:
            SpendLedger(db_path)
        except sqlite3.OperationalError as exc:
            failures.append(str(exc))

    for trial in range(40):
        start = threading.Barrier(5)
        threads = [
            threading.Thread(target=open_ledger, args=(tmp_path / f"spend-{trial}.db", start))
            for _ in range(5)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert failures == []


def test_local_savings_price_embedding_tokens_at_the_embedding_reference(tmp_path: Path) -> None:
    """Embedding tokens price at text-embedding-3-small's $0.02/M input, chat tokens at gpt-4o's
    $2.50/M input, in the report's total and in each server, model and stage (#1623)."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    for model, request_type in (("qwen3:8b", "chat"), ("bge-m3:latest", "embedding")):
        ledger.record_request(
            provider="ollama",
            server="localhost:11434",
            model=model,
            prompt_tokens=1_000_000,
            completion_tokens=0,
            cost_usd=0.0,
            request_type=request_type,
            stage="embedding" if request_type == "embedding" else "chat",
        )

    report = ledger.get_lifetime_report(reference_model="gpt-4o")

    assert (
        report.reference_embedding_model,
        report.local_cost_equivalent_usd,
        report.counterfactual_spend_usd,
        [(s.server, s.cost_equivalent_usd) for s in report.servers],
        sorted((m.model, m.cost_equivalent_usd) for m in report.models),
        sorted((s.stage, s.cost_equivalent_usd) for s in report.stages),
    ) == (
        "text-embedding-3-small",
        2.52,
        2.52,
        [("localhost:11434", 2.52)],
        [("bge-m3:latest", 0.02), ("qwen3:8b", 2.5)],
        [("chat", 2.5), ("embedding", 0.02)],
    )


def test_the_embedding_reference_is_a_setting(tmp_path: Path, config: Callable[..., Path]) -> None:
    """`ai.reference_embedding_model` prices the embedding tokens of the report (#1623)."""
    config(ai={"reference_embedding_model": "text-embedding-3-large"})
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    ledger.record_request(
        provider="ollama",
        server="localhost:11434",
        model="bge-m3:latest",
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cost_usd=0.0,
        request_type="embedding",
    )

    report = ledger.get_lifetime_report()

    assert (report.reference_embedding_model, report.local_cost_equivalent_usd) == (
        "text-embedding-3-large",
        0.13,
    )


def test_the_report_counts_a_gateway_call_as_local_by_the_backend_that_served_it(
    tmp_path: Path,
) -> None:
    """Of two calls through one loopback gateway, the one a cluster Ollama served counts in local
    savings and the one a hosted API served does not, and the gateway is not a local server
    (#1631)."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    for served_by, cost in (
        ("http://ollama-16gib.llm.svc.cluster.local:11434", 0.0),
        ("https://api.openai.com", 2.5),
    ):
        ledger.record_request(
            provider="gateway",
            server="localhost:4000",
            served_by=served_by,
            model="gpt-4o",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            cost_usd=cost,
        )

    report = ledger.get_lifetime_report(reference_model="gpt-4o")

    assert (
        report.local_requests,
        report.local_prompt_tokens,
        report.local_cost_equivalent_usd,
        [(s.server, s.is_local) for s in report.servers],
    ) == (1, 1_000_000, 2.5, [("localhost:4000", False)])


def _local_chat_and_embedding_ledger(db_path: Path) -> SpendLedger:
    """A ledger with one local chat request and one local embedding request, of 1M tokens each."""
    ledger = SpendLedger(db_path=db_path)
    for model, request_type in (("qwen3:8b", "chat"), ("bge-m3:latest", "embedding")):
        ledger.record_request(
            provider="ollama",
            server="localhost:11434",
            model=model,
            prompt_tokens=1_000_000,
            completion_tokens=0,
            cost_usd=0.0,
            request_type=request_type,
        )
    return ledger


def test_an_unknown_reference_model_leaves_local_savings_unpriced_and_warns_once(
    tmp_path: Path, config: Callable[..., Path], caplog: pytest.LogCaptureFixture
) -> None:
    """The typo `gpt-4o-mni` in `ai.reference_model`, which genai-prices does not know, made the
    savings of every local request $0 with no warning. Now each report leaves the savings of chat
    tokens unpriced, embedding tokens keep their price at the embedding reference, no hardware
    pay-off is calculated, and the process logs one warning that names the model and the setting
    (#1672)."""
    config(ai={"reference_model": "gpt-4o-mni"})
    ledger = _local_chat_and_embedding_ledger(tmp_path / "spend.db")
    caplog.set_level(logging.WARNING)

    report, _ = (ledger.get_lifetime_report(hardware_cost_usd=100.0) for _ in range(2))

    assert (
        report.unpriced_reference_models,
        report.local_cost_equivalent_usd,
        report.counterfactual_spend_usd,
        report.counterfactual_savings_usd,
        report.hardware_payoff,
        sorted((m.model, m.cost_equivalent_usd) for m in report.models),
        [s.cost_equivalent_usd for s in report.servers],
        [s.cost_equivalent_usd for s in report.stages],
        [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING],
    ) == (
        ["gpt-4o-mni"],
        None,
        None,
        None,
        None,
        [("bge-m3:latest", 0.02), ("qwen3:8b", None)],
        [None],
        [None],
        [
            "genai-prices and the price overrides hold no price for gpt-4o-mni (ai.reference_model) under provider openai, so the local savings of chat tokens are unpriced."
        ],
    )


def test_devops_ai_cost_says_local_savings_are_unpriced_instead_of_printing_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """`devops ai cost` with a reference model that genai-prices does not know shows the savings
    as unpriced in the table, null in JSON, and no hardware pay-off, and the warning names the
    option (#1672)."""
    from typer.testing import CliRunner

    from devops_cli.commands.ai_cost import app

    runner = CliRunner(env={"COLUMNS": "250"})
    ledger = _local_chat_and_embedding_ledger(tmp_path / "spend.db")
    monkeypatch.setattr("devops_cli.commands.ai_cost.get_spend_ledger", lambda: ledger)
    caplog.set_level(logging.WARNING)
    unknown = ["--reference-model", "gpt-4o-mni"]

    table = runner.invoke(app, ["report", *unknown])
    data = json.loads(runner.invoke(app, ["report", *unknown, "--json"]).stdout)
    roi = runner.invoke(app, ["roi", *unknown, "--hardware-cost", "100"])
    summary = {
        label: next((line for line in table.stdout.splitlines() if label in line), "")
        for label in ("Local Calls Hosted Equivalent", "Estimated Cloud Spend Avoided")
    }

    assert (
        table.exit_code,
        {label: ("unpriced" in line, "$" in line) for label, line in summary.items()},
        (data["local_cost_equivalent_usd"], data["unpriced_reference_models"]),
        (roi.exit_code, "unpriced" in roi.stdout, "gpt-4o-mni" in roi.stdout),
        sorted({r.getMessage() for r in caplog.records if r.levelno == logging.WARNING}),
    ) == (
        0,
        {
            "Local Calls Hosted Equivalent": (True, False),
            "Estimated Cloud Spend Avoided": (True, False),
        },
        (None, ["gpt-4o-mni"]),
        (0, True, True),
        [
            "genai-prices and the price overrides hold no price for gpt-4o-mni (--reference-model) under provider openai, so the local savings of chat tokens are unpriced."
        ],
    )


def test_spend_ledger_records_reasoning_tokens_and_aggregates(tmp_path: Path) -> None:
    """Record reasoning tokens in spend ledger and verify aggregations include them."""
    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    rec = ledger.record_request(
        provider="openai",
        server="api.openai.com",
        model="o1-preview",
        prompt_tokens=100,
        completion_tokens=60,
        cost_usd=0.005,
        served_by="gateway-node-1",
        stage="planner",
        reasoning_tokens=40,
    )
    assert rec is not None
    assert rec.reasoning_tokens == 40

    report = ledger.get_lifetime_report()
    assert report.total_reasoning_tokens == 40
    assert len(report.servers) == 1
    assert report.servers[0].reasoning_tokens == 40
    assert len(report.models) == 1
    assert report.models[0].reasoning_tokens == 40
    assert len(report.backends) == 1
    assert report.backends[0].reasoning_tokens == 40
    assert len(report.stages) == 1
    assert report.stages[0].reasoning_tokens == 40


def test_track_request_spend_emits_reasoning_tokens_telemetry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """track_request_spend emits AI_TOKENS_TOTAL with type reasoning when reasoning tokens are present."""
    from devops_cli.telemetry.instruments import AI_TOKENS_TOTAL

    db_path = tmp_path / "spend.db"
    ledger = SpendLedger(db_path=db_path)

    emitted: list[tuple[Any, int, dict[str, str]]] = []
    monkeypatch.setattr(
        "devops_cli.telemetry.instruments.emit",
        lambda instrument, value, labels: emitted.append((instrument, value, labels)),
    )

    track_request_spend(
        provider="openai",
        model="o1-mini",
        server="api.openai.com",
        prompt_tokens=50,
        completion_tokens=30,
        reasoning_tokens=20,
        ledger=ledger,
    )

    token_emits = [e for e in emitted if e[0] == AI_TOKENS_TOTAL]
    assert len(token_emits) == 3
    assert (token_emits[0][1], token_emits[0][2]["type"]) == (50, "prompt")
    assert (token_emits[1][1], token_emits[1][2]["type"]) == (30, "completion")
    assert (token_emits[2][1], token_emits[2][2]["type"]) == (20, "reasoning")


def test_schema_migration_adds_reasoning_tokens_column(tmp_path: Path) -> None:
    """A legacy spend table without reasoning_tokens column gains it via _init_db."""
    db_path = tmp_path / "legacy.db"
    legacy_create_table = """
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
        duration_seconds REAL NOT NULL DEFAULT 0.0,
        stage TEXT,
        finish_reason TEXT,
        pricing_source TEXT
    );
    """
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        conn.execute(legacy_create_table)

    # Initialize SpendLedger on top of legacy DB
    SpendLedger(db_path=db_path)

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ai_spend_records);").fetchall()}
    assert "reasoning_tokens" in cols
