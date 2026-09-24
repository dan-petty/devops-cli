"""SQLite-backed lifetime AI spend and token usage ledger."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.spend.models import (
    BackendSpendSummary,
    LifetimeSpendReport,
    ModelSpendSummary,
    ProviderSpendSummary,
    ServerSpendSummary,
    SpendRecord,
)
from devops_cli.config.defaults import DEFAULT_AI_SPEND_DB_FILENAME
from devops_cli.config.settings import load_settings

_QUERY_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ai_spend_records (
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
_QUERY_IDX_TIMESTAMP = (
    "CREATE INDEX IF NOT EXISTS idx_spend_timestamp ON ai_spend_records(timestamp);"
)
_QUERY_IDX_SERVER = "CREATE INDEX IF NOT EXISTS idx_spend_server ON ai_spend_records(server);"
_QUERY_IDX_MODEL = "CREATE INDEX IF NOT EXISTS idx_spend_model ON ai_spend_records(model);"
_QUERY_IDX_PROVIDER = "CREATE INDEX IF NOT EXISTS idx_spend_provider ON ai_spend_records(provider);"
_QUERY_IDX_SERVED_BY = (
    "CREATE INDEX IF NOT EXISTS idx_spend_served_by ON ai_spend_records(served_by);"
)
# Ledgers created before served_by existed gain the column in place, keeping their rows.
_QUERY_TABLE_COLUMNS = "PRAGMA table_info(ai_spend_records);"
_QUERY_ADD_SERVED_BY = "ALTER TABLE ai_spend_records ADD COLUMN served_by TEXT;"

_QUERY_INSERT_RECORD = """
INSERT INTO ai_spend_records (
    timestamp, provider, server, backend_info, served_by, model,
    prompt_tokens, completion_tokens, total_tokens,
    cost_usd, cached, request_type, duration_seconds
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_QUERY_OVERALL_SUMMARY = """
SELECT
    COUNT(*) as total_requests,
    COALESCE(SUM(prompt_tokens), 0) as total_prompt,
    COALESCE(SUM(completion_tokens), 0) as total_comp,
    COALESCE(SUM(total_tokens), 0) as total_tok,
    COALESCE(SUM(cost_usd), 0.0) as total_spend,
    COALESCE(SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END), 0) as total_cached,
    COUNT(DISTINCT server) as srv_count,
    COUNT(DISTINCT model) as mdl_count,
    MIN(timestamp) as first_ts,
    MAX(timestamp) as last_ts
FROM ai_spend_records
WHERE (? IS NULL OR timestamp >= datetime('now', ?));
"""

_QUERY_SERVER_BREAKDOWN = """
SELECT
    server,
    provider,
    COUNT(*) as req_count,
    COALESCE(SUM(prompt_tokens), 0) as p_tokens,
    COALESCE(SUM(completion_tokens), 0) as c_tokens,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(SUM(cost_usd), 0.0) as s_cost,
    GROUP_CONCAT(DISTINCT model) as model_list,
    MIN(timestamp) as f_seen,
    MAX(timestamp) as l_seen
FROM ai_spend_records
WHERE (? IS NULL OR timestamp >= datetime('now', ?))
GROUP BY server, provider
ORDER BY s_cost DESC, t_tokens DESC;
"""

_QUERY_MODEL_BREAKDOWN = """
SELECT
    model,
    provider,
    COUNT(*) as req_count,
    COALESCE(SUM(prompt_tokens), 0) as p_tokens,
    COALESCE(SUM(completion_tokens), 0) as c_tokens,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(SUM(cost_usd), 0.0) as m_cost
FROM ai_spend_records
WHERE (? IS NULL OR timestamp >= datetime('now', ?))
GROUP BY model, provider
ORDER BY m_cost DESC, t_tokens DESC;
"""

_QUERY_PROVIDER_BREAKDOWN = """
SELECT
    provider,
    COUNT(*) as req_count,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(SUM(cost_usd), 0.0) as p_cost,
    COUNT(DISTINCT server) as s_count
FROM ai_spend_records
WHERE (? IS NULL OR timestamp >= datetime('now', ?))
GROUP BY provider
ORDER BY p_cost DESC;
"""

_QUERY_BACKEND_BREAKDOWN = """
SELECT
    served_by,
    GROUP_CONCAT(DISTINCT model) as model_list,
    COUNT(*) as req_count,
    COALESCE(SUM(prompt_tokens), 0) as p_tokens,
    COALESCE(SUM(completion_tokens), 0) as c_tokens,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(AVG(duration_seconds), 0.0) as mean_duration
FROM ai_spend_records
WHERE served_by IS NOT NULL AND (? IS NULL OR timestamp >= datetime('now', ?))
GROUP BY served_by
ORDER BY req_count DESC, t_tokens DESC;
"""

_QUERY_COUNT_RECORDS = "SELECT COUNT(*) FROM ai_spend_records;"
_QUERY_DELETE_RECORDS = "DELETE FROM ai_spend_records;"


class SpendLedger:
    """Persistent thread-safe SQLite ledger recording AI token spend across backends."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            settings = load_settings()
            from devops_cli.core.repo import resolve_data_path

            self.db_path = (
                resolve_data_path(settings.data.dir) / "ai" / DEFAULT_AI_SPEND_DB_FILENAME
            )

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and pragmas configured."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initialize spend table schema and indexes if not already present."""
        with contextlib.closing(self._get_connection()) as conn, conn:
            conn.execute(_QUERY_CREATE_TABLE)
            columns = {row["name"] for row in conn.execute(_QUERY_TABLE_COLUMNS).fetchall()}
            if "served_by" not in columns:
                conn.execute(_QUERY_ADD_SERVED_BY)
            conn.execute(_QUERY_IDX_SERVED_BY)
            conn.execute(_QUERY_IDX_TIMESTAMP)
            conn.execute(_QUERY_IDX_SERVER)
            conn.execute(_QUERY_IDX_MODEL)
            conn.execute(_QUERY_IDX_PROVIDER)

    def record_request(
        self,
        *,
        provider: str,
        server: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        cached: bool = False,
        request_type: str = "chat",
        backend_info: str | None = None,
        served_by: str | None = None,
        duration_seconds: float = 0.0,
        timestamp: str | None = None,
    ) -> SpendRecord | None:
        """Record an inference request in the persistent SQLite ledger."""
        ts = timestamp or datetime.now(UTC).isoformat()
        total_tokens = prompt_tokens + completion_tokens
        round_cost = round(cost_usd, 6)

        try:
            with contextlib.closing(self._get_connection()) as conn, conn:
                cursor = conn.execute(
                    _QUERY_INSERT_RECORD,
                    (
                        ts,
                        provider,
                        server,
                        backend_info,
                        served_by,
                        model,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        round_cost,
                        1 if cached else 0,
                        request_type,
                        round(duration_seconds, 4),
                    ),
                )
                rec_id = cursor.lastrowid
                return SpendRecord(
                    id=rec_id,
                    timestamp=ts,
                    provider=provider,
                    server=server,
                    backend_info=backend_info,
                    served_by=served_by,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=round_cost,
                    cached=cached,
                    request_type=request_type,
                    duration_seconds=duration_seconds,
                )
        except Exception:
            # Defensive logging: database failure must never crash user workflows
            return None

    def _build_where_params(self, days: int | None) -> tuple[str | None, str | None]:
        """Construct parameterized filter values for date range."""
        if days is None or days <= 0:
            return (None, None)
        offset = f"-{days} days"
        return (offset, offset)

    def get_lifetime_report(
        self, days: int | None = None, group_by: str = "server"
    ) -> LifetimeSpendReport:
        """Aggregate lifetime spend metrics grouped by server, model, and provider."""
        params = self._build_where_params(days)
        with contextlib.closing(self._get_connection()) as conn:
            summary = self._query_overall_summary(conn, params)
            servers = self._query_server_breakdown(conn, params)
            models = self._query_model_breakdown(conn, params)
            providers = self._query_provider_breakdown(conn, params)
            backends = self._query_backend_breakdown(conn, params)

        summary.servers = servers
        summary.models = models
        summary.providers = providers
        summary.backends = backends
        return summary

    def _query_overall_summary(
        self, conn: sqlite3.Connection, params: tuple[str | None, str | None]
    ) -> LifetimeSpendReport:
        """Fetch high-level aggregate summary across all records."""
        row = conn.execute(_QUERY_OVERALL_SUMMARY, params).fetchone()
        if not row:
            return LifetimeSpendReport()

        return LifetimeSpendReport(
            total_spend_usd=round(float(row["total_spend"] or 0.0), 6),
            total_requests=int(row["total_requests"] or 0),
            total_prompt_tokens=int(row["total_prompt"] or 0),
            total_completion_tokens=int(row["total_comp"] or 0),
            total_tokens=int(row["total_tok"] or 0),
            cached_requests=int(row["total_cached"] or 0),
            active_servers_count=int(row["srv_count"] or 0),
            active_models_count=int(row["mdl_count"] or 0),
            first_recorded_at=row["first_ts"],
            last_recorded_at=row["last_ts"],
        )

    def _query_server_breakdown(
        self, conn: sqlite3.Connection, params: tuple[str | None, str | None]
    ) -> list[ServerSpendSummary]:
        """Aggregate spend records grouped by backend service/server."""
        results: list[ServerSpendSummary] = []
        for r in conn.execute(_QUERY_SERVER_BREAKDOWN, params).fetchall():
            m_list = [m.strip() for m in (r["model_list"] or "").split(",") if m.strip()]
            results.append(
                ServerSpendSummary(
                    server=r["server"],
                    provider=r["provider"],
                    request_count=int(r["req_count"] or 0),
                    prompt_tokens=int(r["p_tokens"] or 0),
                    completion_tokens=int(r["c_tokens"] or 0),
                    total_tokens=int(r["t_tokens"] or 0),
                    approx_spend_usd=round(float(r["s_cost"] or 0.0), 6),
                    models=m_list,
                    first_seen=r["f_seen"],
                    last_seen=r["l_seen"],
                )
            )
        return results

    def _query_model_breakdown(
        self, conn: sqlite3.Connection, params: tuple[str | None, str | None]
    ) -> list[ModelSpendSummary]:
        """Aggregate spend records grouped by model."""
        results: list[ModelSpendSummary] = []
        for r in conn.execute(_QUERY_MODEL_BREAKDOWN, params).fetchall():
            results.append(
                ModelSpendSummary(
                    model=r["model"],
                    provider=r["provider"],
                    request_count=int(r["req_count"] or 0),
                    prompt_tokens=int(r["p_tokens"] or 0),
                    completion_tokens=int(r["c_tokens"] or 0),
                    total_tokens=int(r["t_tokens"] or 0),
                    approx_spend_usd=round(float(r["m_cost"] or 0.0), 6),
                )
            )
        return results

    def _query_provider_breakdown(
        self, conn: sqlite3.Connection, params: tuple[str | None, str | None]
    ) -> list[ProviderSpendSummary]:
        """Aggregate spend records grouped by provider."""
        results: list[ProviderSpendSummary] = []
        for r in conn.execute(_QUERY_PROVIDER_BREAKDOWN, params).fetchall():
            results.append(
                ProviderSpendSummary(
                    provider=r["provider"],
                    request_count=int(r["req_count"] or 0),
                    total_tokens=int(r["t_tokens"] or 0),
                    approx_spend_usd=round(float(r["p_cost"] or 0.0), 6),
                    server_count=int(r["s_count"] or 1),
                )
            )
        return results

    def _query_backend_breakdown(
        self, conn: sqlite3.Connection, params: tuple[str | None, str | None]
    ) -> list[BackendSpendSummary]:
        """Aggregate gateway calls by the backend that served them."""
        results: list[BackendSpendSummary] = []
        for r in conn.execute(_QUERY_BACKEND_BREAKDOWN, params).fetchall():
            requests = int(r["req_count"] or 0)
            completion = int(r["c_tokens"] or 0)
            results.append(
                BackendSpendSummary(
                    served_by=r["served_by"],
                    models=[m.strip() for m in (r["model_list"] or "").split(",") if m.strip()],
                    request_count=requests,
                    prompt_tokens=int(r["p_tokens"] or 0),
                    completion_tokens=completion,
                    total_tokens=int(r["t_tokens"] or 0),
                    completion_tokens_per_request=round(completion / requests, 2)
                    if requests
                    else 0.0,
                    mean_duration_seconds=round(float(r["mean_duration"] or 0.0), 3),
                )
            )
        return results

    def reset_ledger(self) -> int:
        """Truncate all spend records in the ledger and return count of removed items."""
        with contextlib.closing(self._get_connection()) as conn:
            with conn:
                row = conn.execute(_QUERY_COUNT_RECORDS).fetchone()
                count = int(row[0]) if row else 0
                conn.execute(_QUERY_DELETE_RECORDS)
            conn.isolation_level = None
            conn.execute("VACUUM;")
            return count

    def reset(self) -> int:
        """Alias for reset_ledger."""
        return self.reset_ledger()


_GLOBAL_LEDGER: SpendLedger | None = None


def get_spend_ledger(db_path: Path | str | None = None) -> SpendLedger:
    """Return singleton SpendLedger instance."""
    global _GLOBAL_LEDGER
    if _GLOBAL_LEDGER is None or db_path is not None:
        _GLOBAL_LEDGER = SpendLedger(db_path=db_path)
    return _GLOBAL_LEDGER


LLMCallObserver = Callable[[dict[str, Any]], None]

# Callbacks shown every LLM call recorded in this context, e.g. a review profiler. The spend
# ledger is the one place every call passes through, with its tokens and serving backend.
_CALL_OBSERVERS: ContextVar[tuple[LLMCallObserver, ...]] = ContextVar(
    "llm_call_observers", default=()
)


@contextlib.contextmanager
def observe_llm_calls(observer: LLMCallObserver) -> Iterator[None]:
    """Show ``observer`` every LLM call recorded inside the block, worker threads included."""
    token = _CALL_OBSERVERS.set((*_CALL_OBSERVERS.get(), observer))
    try:
        yield
    finally:
        _CALL_OBSERVERS.reset(token)


def _notify_call_observers(call: dict[str, Any]) -> None:
    for observer in _CALL_OBSERVERS.get():
        observer(call)


def track_request_spend(
    *,
    provider: str,
    model: str,
    server: str,
    backend_info: str | None = None,
    served_by: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached: bool = False,
    request_type: str = "chat",
    duration_seconds: float = 0.0,
    ledger: SpendLedger | None = None,
) -> SpendRecord | None:
    """Calculate pricing, persist to lifetime ledger, and emit OpenTelemetry metrics."""
    from devops_cli.ai.spend.pricing import get_pricing_registry
    from devops_cli.telemetry.tracer import record_metric

    active_ledger = ledger or get_spend_ledger()
    pricing = get_pricing_registry().get_pricing(model, server)
    cost = pricing.calculate_cost(prompt_tokens, completion_tokens) if not cached else 0.0
    try:
        rec = active_ledger.record_request(
            provider=provider,
            server=server,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            backend_info=backend_info,
            served_by=served_by,
            cached=cached,
            request_type=request_type,
            duration_seconds=duration_seconds,
        )
    except Exception:
        rec = None
    _notify_call_observers(
        {
            "provider": provider,
            "model": model,
            "served_by": served_by,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached": cached,
            "request_type": request_type,
            "duration_seconds": duration_seconds,
        }
    )
    record_metric(
        "devops_cli_ai_estimated_cost_usd",
        cost,
        attributes={"provider": provider, "model": model, "server": server},
    )
    record_metric(
        "devops_cli_ai_tokens_total",
        prompt_tokens + completion_tokens,
        attributes={"provider": provider, "model": model, "server": server},
    )
    return rec
