"""SQLite-backed lifetime AI spend and token usage ledger."""

from __future__ import annotations

import contextlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.spend.models import (
    LifetimeSpendReport,
    ModelSpendSummary,
    ProviderSpendSummary,
    ServerSpendSummary,
    SpendRecord,
)
from devops_cli.config.constants import CONST_AI_SPEND_TABLE_NAME
from devops_cli.config.defaults import DEFAULT_AI_SPEND_DB_FILENAME
from devops_cli.config.settings import load_settings


class SpendLedger:
    """Persistent SQLite ledger tracking lifetime AI requests, token usage, and costs."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            settings = load_settings()
            self.db_path = settings.data.dir / "ai" / DEFAULT_AI_SPEND_DB_FILENAME
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
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {CONST_AI_SPEND_TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    server TEXT NOT NULL,
                    backend_info TEXT,
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
                f"CREATE INDEX IF NOT EXISTS idx_spend_timestamp ON {CONST_AI_SPEND_TABLE_NAME}(timestamp);"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_spend_server ON {CONST_AI_SPEND_TABLE_NAME}(server);"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_spend_model ON {CONST_AI_SPEND_TABLE_NAME}(model);"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_spend_provider ON {CONST_AI_SPEND_TABLE_NAME}(provider);"
            )

    def record_request(
        self,
        *,
        provider: str,
        server: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        backend_info: str | None = None,
        cached: bool = False,
        request_type: str = "chat",
        duration_seconds: float = 0.0,
        timestamp: str | None = None,
    ) -> SpendRecord | None:
        """Record an individual AI request execution in the lifetime ledger."""
        ts = timestamp or datetime.now(UTC).isoformat()
        total_tokens = prompt_tokens + completion_tokens
        round_cost = round(cost_usd, 6)

        try:
            with contextlib.closing(self._get_connection()) as conn, conn:
                cursor = conn.execute(
                    f"""
                    INSERT INTO {CONST_AI_SPEND_TABLE_NAME} (
                        timestamp, provider, server, backend_info, model,
                        prompt_tokens, completion_tokens, total_tokens,
                        cost_usd, cached, request_type, duration_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ts,
                        provider,
                        server,
                        backend_info,
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

    def _build_where_clause(self, days: int | None) -> tuple[str, list[Any]]:
        """Construct parameterized WHERE filter for date range."""
        if days is None or days <= 0:
            return "", []
        return "WHERE timestamp >= datetime('now', ?)", [f"-{days} days"]

    def get_lifetime_report(
        self, days: int | None = None, group_by: str = "server"
    ) -> LifetimeSpendReport:
        """Aggregate lifetime spend metrics grouped by server, model, and provider."""
        where_clause, params = self._build_where_clause(days)
        with contextlib.closing(self._get_connection()) as conn:
            summary = self._query_overall_summary(conn, where_clause, params)
            servers = self._query_server_breakdown(conn, where_clause, params)
            models = self._query_model_breakdown(conn, where_clause, params)
            providers = self._query_provider_breakdown(conn, where_clause, params)

        summary.servers = servers
        summary.models = models
        summary.providers = providers
        return summary

    def _query_overall_summary(
        self, conn: sqlite3.Connection, where_sql: str, params: list[Any]
    ) -> LifetimeSpendReport:
        """Fetch high-level aggregate summary across all records."""
        query = f"""
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
            FROM {CONST_AI_SPEND_TABLE_NAME}
            {where_sql};
        """
        row = conn.execute(query, params).fetchone()
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
        self, conn: sqlite3.Connection, where_sql: str, params: list[Any]
    ) -> list[ServerSpendSummary]:
        """Aggregate spend records grouped by backend service/server."""
        query = f"""
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
            FROM {CONST_AI_SPEND_TABLE_NAME}
            {where_sql}
            GROUP BY server, provider
            ORDER BY s_cost DESC, t_tokens DESC;
        """
        results: list[ServerSpendSummary] = []
        for r in conn.execute(query, params).fetchall():
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
        self, conn: sqlite3.Connection, where_sql: str, params: list[Any]
    ) -> list[ModelSpendSummary]:
        """Aggregate spend records grouped by model."""
        query = f"""
            SELECT
                model,
                provider,
                COUNT(*) as req_count,
                COALESCE(SUM(prompt_tokens), 0) as p_tokens,
                COALESCE(SUM(completion_tokens), 0) as c_tokens,
                COALESCE(SUM(total_tokens), 0) as t_tokens,
                COALESCE(SUM(cost_usd), 0.0) as m_cost
            FROM {CONST_AI_SPEND_TABLE_NAME}
            {where_sql}
            GROUP BY model, provider
            ORDER BY m_cost DESC, t_tokens DESC;
        """
        results: list[ModelSpendSummary] = []
        for r in conn.execute(query, params).fetchall():
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
        self, conn: sqlite3.Connection, where_sql: str, params: list[Any]
    ) -> list[ProviderSpendSummary]:
        """Aggregate spend records grouped by provider."""
        query = f"""
            SELECT
                provider,
                COUNT(*) as req_count,
                COALESCE(SUM(total_tokens), 0) as t_tokens,
                COALESCE(SUM(cost_usd), 0.0) as p_cost,
                COUNT(DISTINCT server) as s_count
            FROM {CONST_AI_SPEND_TABLE_NAME}
            {where_sql}
            GROUP BY provider
            ORDER BY p_cost DESC;
        """
        results: list[ProviderSpendSummary] = []
        for r in conn.execute(query, params).fetchall():
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

    def reset_ledger(self) -> int:
        """Truncate all spend records in the ledger and return count of removed items."""
        with contextlib.closing(self._get_connection()) as conn:
            with conn:
                row = conn.execute(f"SELECT COUNT(*) FROM {CONST_AI_SPEND_TABLE_NAME};").fetchone()
                count = int(row[0]) if row else 0
                conn.execute(f"DELETE FROM {CONST_AI_SPEND_TABLE_NAME};")
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


def track_request_spend(
    *,
    provider: str,
    model: str,
    server: str,
    backend_info: str | None = None,
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
            cached=cached,
            request_type=request_type,
            duration_seconds=duration_seconds,
        )
    except Exception:
        rec = None
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
