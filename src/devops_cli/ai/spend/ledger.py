"""SQLite-backed lifetime AI spend and token usage ledger."""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from devops_cli.ai.spend.models import (
    BackendSpendSummary,
    LifetimeSpendReport,
    ModelPricing,
    ModelSpendSummary,
    ProviderSpendSummary,
    ServerSpendSummary,
    SpendRecord,
    StageSpendSummary,
)
from devops_cli.config import options as opt
from devops_cli.config.constants import (
    CONST_PRICING_SOURCE_LOCAL,
    CONST_RESPONSE_CACHE_SERVER,
    CONST_SPEND_REQUEST_TYPE_EMBEDDING,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_REFERENCE_EMBEDDING_MODEL,
    DEFAULT_AI_REFERENCE_MODEL,
    DEFAULT_AI_REFERENCE_PROVIDER,
    DEFAULT_AI_SPEND_DB_FILENAME,
)
from devops_cli.config.settings import load_settings

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason

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
    duration_seconds REAL NOT NULL DEFAULT 0.0,
    stage TEXT,
    finish_reason TEXT,
    pricing_source TEXT
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
_QUERY_IDX_STAGE = "CREATE INDEX IF NOT EXISTS idx_spend_stage ON ai_spend_records(stage);"
# Ledgers created before a column existed gain it in place, keeping their rows.
_QUERY_TABLE_COLUMNS = "PRAGMA table_info(ai_spend_records);"
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("served_by", "ALTER TABLE ai_spend_records ADD COLUMN served_by TEXT;"),
    ("stage", "ALTER TABLE ai_spend_records ADD COLUMN stage TEXT;"),
    ("finish_reason", "ALTER TABLE ai_spend_records ADD COLUMN finish_reason TEXT;"),
    ("pricing_source", "ALTER TABLE ai_spend_records ADD COLUMN pricing_source TEXT;"),
)

_QUERY_INSERT_RECORD = """
INSERT INTO ai_spend_records (
    timestamp, provider, server, backend_info, served_by, model,
    prompt_tokens, completion_tokens, total_tokens,
    cost_usd, cached, request_type, duration_seconds, stage, finish_reason, pricing_source
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_QUERY_STAGE_BREAKDOWN = """
SELECT
    COALESCE(stage, 'unattributed') as stage_name,
    COUNT(*) as req_count,
    COALESCE(SUM(prompt_tokens), 0) as p_tokens,
    COALESCE(SUM(completion_tokens), 0) as c_tokens,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(SUM(CASE WHEN request_type = :embedding THEN prompt_tokens ELSE 0 END), 0) as e_tokens,
    COALESCE(SUM(cost_usd), 0.0) as s_cost
FROM ai_spend_records
WHERE (:cutoff IS NULL OR timestamp >= :cutoff)
GROUP BY stage_name
ORDER BY s_cost DESC, t_tokens DESC;
"""

_QUERY_OVERALL_SUMMARY = """
SELECT
    COUNT(*) as total_requests,
    COALESCE(SUM(prompt_tokens), 0) as total_prompt,
    COALESCE(SUM(completion_tokens), 0) as total_comp,
    COALESCE(SUM(total_tokens), 0) as total_tok,
    COALESCE(SUM(CASE WHEN request_type = :embedding THEN prompt_tokens ELSE 0 END), 0) as total_emb,
    COALESCE(SUM(cost_usd), 0.0) as total_spend,
    COALESCE(SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END), 0) as total_cached,
    COUNT(DISTINCT CASE WHEN cached=0 THEN server END) as srv_count,
    COUNT(DISTINCT model) as mdl_count,
    MIN(timestamp) as first_ts,
    MAX(timestamp) as last_ts
FROM ai_spend_records
WHERE (:cutoff IS NULL OR timestamp >= :cutoff);
"""

_QUERY_SERVER_BREAKDOWN = """
SELECT
    server,
    provider,
    COUNT(*) as req_count,
    COALESCE(SUM(prompt_tokens), 0) as p_tokens,
    COALESCE(SUM(completion_tokens), 0) as c_tokens,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(SUM(CASE WHEN request_type = :embedding THEN prompt_tokens ELSE 0 END), 0) as e_tokens,
    COALESCE(SUM(cost_usd), 0.0) as s_cost,
    GROUP_CONCAT(DISTINCT model) as model_list,
    MIN(timestamp) as f_seen,
    MAX(timestamp) as l_seen
FROM ai_spend_records
WHERE (:cutoff IS NULL OR timestamp >= :cutoff)
GROUP BY server, provider
ORDER BY s_cost DESC, t_tokens DESC;
"""

# The backend that served a call decides whether it ran locally, so local usage is tallied by
# server, provider and serving backend (#1631).
_QUERY_SERVED_USAGE = """
SELECT
    server,
    provider,
    served_by,
    COUNT(*) as req_count,
    COALESCE(SUM(prompt_tokens), 0) as p_tokens,
    COALESCE(SUM(completion_tokens), 0) as c_tokens,
    COALESCE(SUM(CASE WHEN request_type = :embedding THEN prompt_tokens ELSE 0 END), 0) as e_tokens
FROM ai_spend_records
WHERE (:cutoff IS NULL OR timestamp >= :cutoff)
GROUP BY server, provider, served_by;
"""

_QUERY_MODEL_BREAKDOWN = """
SELECT
    model,
    provider,
    COUNT(*) as req_count,
    COALESCE(SUM(prompt_tokens), 0) as p_tokens,
    COALESCE(SUM(completion_tokens), 0) as c_tokens,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(SUM(CASE WHEN request_type = :embedding THEN prompt_tokens ELSE 0 END), 0) as e_tokens,
    COALESCE(SUM(cost_usd), 0.0) as m_cost,
    COALESCE(SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END), 0) as cached_count
FROM ai_spend_records
WHERE (:cutoff IS NULL OR timestamp >= :cutoff)
GROUP BY model, provider
ORDER BY m_cost DESC, t_tokens DESC;
"""

_QUERY_PROVIDER_BREAKDOWN = """
SELECT
    provider,
    COUNT(*) as req_count,
    COALESCE(SUM(total_tokens), 0) as t_tokens,
    COALESCE(SUM(cost_usd), 0.0) as p_cost,
    COUNT(DISTINCT CASE WHEN cached=0 THEN server END) as s_count
FROM ai_spend_records
WHERE (:cutoff IS NULL OR timestamp >= :cutoff)
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
WHERE served_by IS NOT NULL AND (:cutoff IS NULL OR timestamp >= :cutoff)
GROUP BY served_by
ORDER BY req_count DESC, t_tokens DESC;
"""

_QUERY_COUNT_RECORDS = "SELECT COUNT(*) FROM ai_spend_records;"
_QUERY_DELETE_RECORDS = "DELETE FROM ai_spend_records;"


# Named parameters of the report queries: the date-range cutoff and the embedding request type.
_QueryParams = dict[str, str | None]


def _ai_setting(name: str, default: str) -> str:
    """A string AI setting, stripped; its default when it is blank or the settings cannot load."""
    try:
        value = getattr(load_settings().ai, name)
    except Exception:
        return default
    return value.strip() if isinstance(value, str) and value.strip() else default


# What a warning names as the source of a reference model given to a report, not read from
# `ai.reference_model` (#1672).
_REFERENCE_MODEL_OPTION = "--reference-model"


class ReferencePricing(NamedTuple):
    """The hosted models local tokens are priced against, one for each kind of request.

    A price is None when neither genai-prices nor a price override prices its model (#1672).
    """

    chat_model: str
    embedding_model: str
    chat: ModelPricing | None
    embedding: ModelPricing | None

    @property
    def unpriced_models(self) -> list[str]:
        """The reference models that have no price."""
        return [
            model
            for model, pricing in (
                (self.chat_model, self.chat),
                (self.embedding_model, self.embedding),
            )
            if pricing is None
        ]

    def cost(
        self, prompt_tokens: int, completion_tokens: int, embedding_tokens: int = 0
    ) -> float | None:
        """The hosted cost of the tokens, of which `embedding_tokens` prompt tokens embedded text.

        None when a kind of token that the tokens hold has a reference model with no price, so
        unpriced savings never read as $0 (#1672).
        """
        chat_tokens = (prompt_tokens - embedding_tokens, completion_tokens)
        chat_cost = self.chat.calculate_cost(*chat_tokens) if self.chat else None
        embedding_cost = (
            self.embedding.calculate_cost(embedding_tokens, 0) if self.embedding else None
        )
        if (chat_cost is None and any(chat_tokens)) or (
            embedding_cost is None and embedding_tokens
        ):
            return None
        return round((chat_cost or 0.0) + (embedding_cost or 0.0), 6)


def resolve_reference_pricing(reference_model: str | None = None) -> ReferencePricing:
    """Both reference models and their prices, from genai-prices under `ai.reference_provider`.

    The chat reference is `reference_model` when given, else `ai.reference_model`. The pricing
    registry logs one warning for each reference model that has no price (#1672).
    """
    from devops_cli.ai.spend.pricing import get_pricing_registry

    given = reference_model.strip() if reference_model else ""
    chat_setting = _REFERENCE_MODEL_OPTION if given else opt.AI_REFERENCE_MODEL
    chat_model = given or _ai_setting("reference_model", DEFAULT_AI_REFERENCE_MODEL)
    embedding_model = _ai_setting("reference_embedding_model", DEFAULT_AI_REFERENCE_EMBEDDING_MODEL)
    provider = _ai_setting("reference_provider", DEFAULT_AI_REFERENCE_PROVIDER)
    registry = get_pricing_registry()
    return ReferencePricing(
        chat_model=chat_model,
        embedding_model=embedding_model,
        chat=registry.price_reference(
            chat_model, setting=chat_setting, kind="chat", provider=provider
        ),
        embedding=registry.price_reference(
            embedding_model,
            setting=opt.AI_REFERENCE_EMBEDDING_MODEL,
            kind="embedding",
            provider=provider,
        ),
    )


class _Usage(NamedTuple):
    """The requests and tokens of a set of ledger rows."""

    requests: int
    prompt_tokens: int
    completion_tokens: int
    embedding_tokens: int


class _ServedUsage(NamedTuple):
    """What one backend served of the calls sent to one server; no backend for a direct call."""

    server: str
    provider: str
    served_by: str | None
    usage: _Usage


def _tally_and_annotate_servers(
    servers: list[ServerSpendSummary],
    served: list[_ServedUsage],
    ref_pricing: ReferencePricing,
) -> _Usage:
    """Annotate servers with local status and cost equivalent, tallying local usage.

    The backend that served a call decides whether it ran locally (#1631), so a server is local
    only when every backend that served its calls is local. The response cache ran no model,
    local or hosted, so its replies are no local requests.
    """
    from devops_cli.ai.spend.pricing import is_local

    local: list[_Usage] = []
    hosted: set[tuple[str, str]] = set()
    for group in served:
        if group.server != CONST_RESPONSE_CACHE_SERVER and is_local(
            server=group.server, provider=group.provider, served_by=group.served_by
        ):
            local.append(group.usage)
        else:
            hosted.add((group.server, group.provider))
    for s in servers:
        s.is_local = (s.server, s.provider) not in hosted
        s.cost_equivalent_usd = ref_pricing.cost(
            s.prompt_tokens, s.completion_tokens, s.embedding_tokens
        )
    return _Usage(
        requests=sum(u.requests for u in local),
        prompt_tokens=sum(u.prompt_tokens for u in local),
        completion_tokens=sum(u.completion_tokens for u in local),
        embedding_tokens=sum(u.embedding_tokens for u in local),
    )


def _annotate_models(models: list[ModelSpendSummary], ref_pricing: ReferencePricing) -> None:
    """Annotate model summaries with hosted cost equivalent."""
    for m in models:
        m.cost_equivalent_usd = ref_pricing.cost(
            m.prompt_tokens, m.completion_tokens, m.embedding_tokens
        )


def _annotate_stages(stages: list[StageSpendSummary], ref_pricing: ReferencePricing) -> None:
    """Annotate stage summaries with hosted cost equivalent."""
    for stg in stages:
        stg.cost_equivalent_usd = ref_pricing.cost(
            stg.prompt_tokens, stg.completion_tokens, stg.embedding_tokens
        )


def _add_column(conn: sqlite3.Connection, add_column: str) -> None:
    """Add a column, tolerating another process having added it first."""
    try:
        conn.execute(add_column)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


_JOURNAL_MODE_LOCK = threading.Lock()


class SpendLedger:
    """Persistent thread-safe SQLite ledger recording AI token spend across backends."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            settings = load_settings()
            from devops_cli.core.repo import resolve_review_data_path

            # Every AI command records its spend here, a review too, so a relative data
            # directory resolves under the review data root for all of them (#972).
            self.db_path = (
                resolve_review_data_path(settings.data.dir) / "ai" / DEFAULT_AI_SPEND_DB_FILENAME
            )

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and pragmas configured."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL belongs to the database file, so it is switched on once. The switch needs an
        # exclusive lock that SQLite refuses at once, whatever the timeout, so threads of this
        # process make it one at a time (#1820).
        with _JOURNAL_MODE_LOCK:
            if conn.execute("PRAGMA journal_mode;").fetchone()[0].lower() != "wal":
                conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initialize spend table schema and indexes if not already present."""
        with contextlib.closing(self._get_connection()) as conn, conn:
            conn.execute(_QUERY_CREATE_TABLE)
            columns = {row["name"] for row in conn.execute(_QUERY_TABLE_COLUMNS).fetchall()}
            for column, add_column in _ADDED_COLUMNS:
                if column not in columns:
                    _add_column(conn, add_column)
            conn.execute(_QUERY_IDX_SERVED_BY)
            conn.execute(_QUERY_IDX_STAGE)
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
        stage: str | None = None,
        finish_reason: FinishReason | None = None,
        pricing_source: str | None = None,
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
                        stage,
                        finish_reason,
                        pricing_source,
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
                    stage=stage,
                    finish_reason=finish_reason,
                    pricing_source=pricing_source,
                )
        except Exception:
            # Defensive logging: database failure must never crash user workflows
            return None

    def _build_where_params(self, days: int | None) -> _QueryParams:
        """The report queries' parameters: the cutoff of the date range, and the request type
        whose prompt tokens they count as embedding tokens."""
        cutoff = (
            None
            if days is None or days <= 0
            else (datetime.now(UTC) - timedelta(days=days)).isoformat()
        )
        return {"cutoff": cutoff, "embedding": CONST_SPEND_REQUEST_TYPE_EMBEDDING}

    @staticmethod
    def _resolve_hardware_cost(hardware_cost_usd: float | None = None) -> float:
        """Resolve hardware cost for payoff calculation from parameter or settings."""
        if hardware_cost_usd is not None and hardware_cost_usd >= 0:
            return float(hardware_cost_usd)
        try:
            settings = load_settings()
            if settings.ai.hardware_cost_usd and settings.ai.hardware_cost_usd >= 0:
                return float(settings.ai.hardware_cost_usd)
        except Exception:
            pass
        return 0.0

    def get_lifetime_report(
        self,
        days: int | None = None,
        group_by: str = "server",
        reference_model: str | None = None,
        hardware_cost_usd: float | None = None,
    ) -> LifetimeSpendReport:
        """Aggregate lifetime spend metrics grouped by server, model, provider, and stage.

        Local tokens are priced at the hosted reference models: embedding tokens at
        `ai.reference_embedding_model`, every other token at `reference_model`. A cost
        equivalent is None when a reference model that prices its tokens has no price (#1672).
        """
        params = self._build_where_params(days)
        with contextlib.closing(self._get_connection()) as conn:
            summary = self._query_overall_summary(conn, params)
            servers = self._query_server_breakdown(conn, params)
            served = self._query_served_usage(conn, params)
            models = self._query_model_breakdown(conn, params)
            providers = self._query_provider_breakdown(conn, params)
            backends = self._query_backend_breakdown(conn, params)
            stages = self._query_stage_breakdown(conn, params)

        ref_pricing = resolve_reference_pricing(reference_model)
        ref_model = ref_pricing.chat_model

        local = _tally_and_annotate_servers(servers, served, ref_pricing)
        _annotate_models(models, ref_pricing)
        _annotate_stages(stages, ref_pricing)

        eff_hardware_cost = self._resolve_hardware_cost(hardware_cost_usd)
        summary.hardware_cost_usd = eff_hardware_cost
        summary.reference_model = ref_model
        summary.reference_embedding_model = ref_pricing.embedding_model
        summary.unpriced_reference_models = ref_pricing.unpriced_models
        summary.local_requests = local.requests
        summary.local_prompt_tokens = local.prompt_tokens
        summary.local_completion_tokens = local.completion_tokens
        summary.local_embedding_tokens = local.embedding_tokens
        summary.local_tokens = local.prompt_tokens + local.completion_tokens
        summary.local_cost_equivalent_usd = ref_pricing.cost(
            local.prompt_tokens, local.completion_tokens, local.embedding_tokens
        )
        summary.counterfactual_spend_usd = ref_pricing.cost(
            summary.total_prompt_tokens,
            summary.total_completion_tokens,
            summary.total_embedding_tokens,
        )
        summary.counterfactual_savings_usd = (
            None
            if summary.counterfactual_spend_usd is None
            else round(max(0.0, summary.counterfactual_spend_usd - summary.total_spend_usd), 6)
        )

        local_savings = summary.local_cost_equivalent_usd
        if local_savings is not None and (eff_hardware_cost > 0 or local_savings > 0):
            from devops_cli.ai.spend.payoff import compute_hardware_payoff

            summary.hardware_payoff = compute_hardware_payoff(
                hardware_cost_usd=eff_hardware_cost,
                local_cost_equivalent_usd=local_savings,
                reference_model=ref_model,
                first_recorded_at=summary.first_recorded_at,
                last_recorded_at=summary.last_recorded_at,
                days=days,
            )

        summary.servers = servers
        summary.models = models
        summary.providers = providers
        summary.backends = backends
        summary.stages = stages
        return summary

    def _query_overall_summary(
        self, conn: sqlite3.Connection, params: _QueryParams
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
            total_embedding_tokens=int(row["total_emb"] or 0),
            cached_requests=int(row["total_cached"] or 0),
            active_servers_count=int(row["srv_count"] or 0),
            active_models_count=int(row["mdl_count"] or 0),
            first_recorded_at=row["first_ts"],
            last_recorded_at=row["last_ts"],
        )

    def _query_server_breakdown(
        self, conn: sqlite3.Connection, params: _QueryParams
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
                    embedding_tokens=int(r["e_tokens"] or 0),
                    approx_spend_usd=round(float(r["s_cost"] or 0.0), 6),
                    models=m_list,
                    first_seen=r["f_seen"],
                    last_seen=r["l_seen"],
                )
            )
        return results

    def _query_served_usage(
        self, conn: sqlite3.Connection, params: _QueryParams
    ) -> list[_ServedUsage]:
        """Aggregate spend records by server, provider and the backend that served them."""
        return [
            _ServedUsage(
                server=r["server"],
                provider=r["provider"],
                served_by=r["served_by"],
                usage=_Usage(
                    requests=int(r["req_count"] or 0),
                    prompt_tokens=int(r["p_tokens"] or 0),
                    completion_tokens=int(r["c_tokens"] or 0),
                    embedding_tokens=int(r["e_tokens"] or 0),
                ),
            )
            for r in conn.execute(_QUERY_SERVED_USAGE, params).fetchall()
        ]

    def _query_model_breakdown(
        self, conn: sqlite3.Connection, params: _QueryParams
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
                    embedding_tokens=int(r["e_tokens"] or 0),
                    approx_spend_usd=round(float(r["m_cost"] or 0.0), 6),
                    cached_requests=int(r["cached_count"] or 0),
                )
            )
        return results

    def _query_provider_breakdown(
        self, conn: sqlite3.Connection, params: _QueryParams
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
                    server_count=int(r["s_count"] or 0),
                )
            )
        return results

    def _query_backend_breakdown(
        self, conn: sqlite3.Connection, params: _QueryParams
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

    def _query_stage_breakdown(
        self, conn: sqlite3.Connection, params: _QueryParams
    ) -> list[StageSpendSummary]:
        """Aggregate spend records grouped by execution stage."""
        results: list[StageSpendSummary] = []
        for r in conn.execute(_QUERY_STAGE_BREAKDOWN, params).fetchall():
            results.append(
                StageSpendSummary(
                    stage=r["stage_name"],
                    request_count=int(r["req_count"] or 0),
                    prompt_tokens=int(r["p_tokens"] or 0),
                    completion_tokens=int(r["c_tokens"] or 0),
                    total_tokens=int(r["t_tokens"] or 0),
                    embedding_tokens=int(r["e_tokens"] or 0),
                    approx_spend_usd=round(float(r["s_cost"] or 0.0), 6),
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


def reset_spend_ledger() -> None:
    """Drop the global SpendLedger singleton so the next access opens a fresh one."""
    global _GLOBAL_LEDGER
    _GLOBAL_LEDGER = None


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
    stage: str | None = None,
    ledger: SpendLedger | None = None,
    finish_reason: FinishReason | None = None,
) -> SpendRecord | None:
    """Calculate pricing, persist to lifetime ledger, and emit OpenTelemetry metrics.

    ``finish_reason`` is why the provider says the reply ended, None when it did not say; the
    ledger stores it and observers receive it. The metrics carry the call's GenAI operation:
    `embeddings` for an embedding request, `chat` for every other call. ``served_by``, the
    backend a gateway reply names, decides whether the call is spend or local savings. The
    ledger stores where the price came from. The tokens carry `local`, and no process sends a
    price for them: the cluster prices local tokens at one reference for every process (#1672).
    """
    from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
        GenAiOperationNameValues,
    )

    from devops_cli.ai.spend.pricing import get_pricing_registry
    from devops_cli.ai.spend.stage import resolve_spend_stage
    from devops_cli.telemetry.instruments import (
        AI_REQUESTS_TOTAL,
        AI_SPEND_USD_TOTAL,
        AI_TOKENS_TOTAL,
        backend_name,
        emit,
    )

    active_ledger = ledger or get_spend_ledger()
    now_utc = datetime.now(UTC)
    # The response cache ran no model, so its reply has no price.
    priced = (
        None
        if cached
        else get_pricing_registry().calculate_request_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            server=server,
            provider=provider,
            request_timestamp=now_utc,
            served_by=served_by,
        )
    )
    cost = priced.cost_usd if priced else 0.0
    pricing_source = priced.pricing_source if priced else None
    effective_stage = resolve_spend_stage(stage)
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
            timestamp=now_utc.isoformat(),
            stage=effective_stage,
            finish_reason=finish_reason,
            pricing_source=pricing_source,
        )
    except Exception:
        rec = None
    _notify_call_observers(
        {
            "provider": provider,
            "model": model,
            "served_by": served_by,
            "stage": effective_stage,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost,
            "cached": cached,
            "request_type": request_type,
            "duration_seconds": duration_seconds,
            "finish_reason": finish_reason,
        }
    )
    operation = (
        GenAiOperationNameValues.EMBEDDINGS
        if request_type == CONST_SPEND_REQUEST_TYPE_EMBEDDING
        else GenAiOperationNameValues.CHAT
    )
    source = {
        "provider": provider,
        "model": model,
        "server": server,
        "backend": backend_name(served_by),
        "operation": operation.value,
    }
    emit(AI_REQUESTS_TOTAL, 1, source | {"cached": str(cached).lower()})
    tokens = source | {"local": str(pricing_source == CONST_PRICING_SOURCE_LOCAL).lower()}
    emit(AI_TOKENS_TOTAL, prompt_tokens, tokens | {"type": "prompt"})
    emit(AI_TOKENS_TOTAL, completion_tokens, tokens | {"type": "completion"})
    if cached:
        return rec
    # Every request a model answered adds to the spend counter, a local one 0, so the series
    # exists before the first hosted request and a dashboard shows $0, not "No data" (#1631).
    emit(AI_SPEND_USD_TOTAL, cost, source)
    return rec
