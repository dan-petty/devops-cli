"""The spend ledger keeps the cache read and cache write tokens of a call and prices them (#3658).

A Claude group of the gateway asks Anthropic to cache its prefix. Both cache counts are parts of the
prompt tokens. A cache read costs the cache read rate of the model and a cache write the cache
write rate, so a cached call does not cost the full input price for each prompt token.
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

import pytest

from devops_cli.ai.spend.ledger import SpendLedger, track_request_spend

# The ledger table before the cache token columns existed.
_SCHEMA_BEFORE_CACHE_TOKENS = """
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
    pricing_source TEXT,
    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    served_model TEXT
);
"""


def _cache_rows(db_path: Path) -> list[tuple[str, int, int, int]]:
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(
            "SELECT model, prompt_tokens, cache_read_tokens, cache_write_tokens"
            " FROM ai_spend_records ORDER BY id"
        ).fetchall()


def test_a_ledger_row_keeps_the_cache_read_and_cache_write_tokens(tmp_path: Path) -> None:
    """A row keeps both cache counts of a reply, and the record that the ledger gives back holds
    them too."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")

    record = ledger.record_request(
        provider="gateway",
        server="llm.example.com",
        model="claude-sonnet-5-5",
        prompt_tokens=1_550,
        completion_tokens=10,
        cost_usd=0.0,
        cache_read_tokens=300,
        cache_write_tokens=1_200,
    )

    assert (
        (record.cache_read_tokens, record.cache_write_tokens) if record else None,
        _cache_rows(ledger.db_path),
    ) == ((300, 1_200), [("claude-sonnet-5-5", 1_550, 300, 1_200)])


def test_an_existing_ledger_gains_the_cache_token_columns_and_keeps_its_rows(
    tmp_path: Path,
) -> None:
    """A ledger written before the cache columns existed gains both in place. Its old rows read 0
    cache tokens, and a new row keeps its counts."""
    db_path = tmp_path / "spend.db"
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(_SCHEMA_BEFORE_CACHE_TOKENS)
        conn.execute(
            "INSERT INTO ai_spend_records (timestamp, provider, server, model, prompt_tokens) "
            "VALUES ('2026-11-01T00:00:00+00:00', 'gateway', 'llm.example.com', 'old', 500)"
        )

    SpendLedger(db_path=db_path).record_request(
        provider="gateway",
        server="llm.example.com",
        model="new",
        prompt_tokens=1_000,
        completion_tokens=5,
        cost_usd=0.0,
        cache_read_tokens=400,
        cache_write_tokens=600,
    )

    assert _cache_rows(db_path) == [("old", 500, 0, 0), ("new", 1_000, 400, 600)]


@pytest.mark.parametrize(
    ("model", "prompt", "read", "written", "cost"),
    [
        # 1,000,000 reads at 0.10 USD and 1,000,000 writes at 2.50 USD per million, not 4.00 USD
        # at the input price of 2.00 USD.
        ("claude-sonnet-5-5", 2_000_000, 1_000_000, 1_000_000, 2.6),
        # 10,000 new tokens at 0.10 USD, 20,000 reads at 0.01 USD and 20,000 writes at 0.125 USD
        # per million, below the 100,000-token tier of Haiku 5.5.
        ("claude-haiku-5-5", 50_000, 20_000, 20_000, 0.0037),
    ],
    ids=["sonnet", "haiku"],
)
def test_a_claude_gateway_call_costs_its_cache_reads_and_writes_at_the_cache_rates(
    spend_ledger: SpendLedger, model: str, prompt: int, read: int, written: int, cost: float
) -> None:
    """genai-prices prices the cache reads and the cache writes of a Claude group at the cache
    rates of the model, and the row keeps both counts."""
    record = track_request_spend(
        provider="gateway",
        model=model,
        server="llm.example.com",
        prompt_tokens=prompt,
        completion_tokens=0,
        cache_read_tokens=read,
        cache_write_tokens=written,
        ledger=spend_ledger,
    )

    assert (
        (record.cost_usd, record.pricing_source) if record else None,
        _cache_rows(spend_ledger.db_path),
    ) == ((pytest.approx(cost), "genai_prices:anthropic"), [(model, prompt, read, written)])
