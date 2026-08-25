"""Unit tests for LLM response cache and warm starting point mechanisms."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.client import LLMClient, LLMResponse
from devops_cli.ai.response_cache import (
    LLMResponseCache,
    get_llm_response_cache,
    reset_llm_response_cache,
)
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


@pytest.fixture(autouse=True)
def clean_cache(tmp_path: Path) -> LLMResponseCache:
    """Fixture providing an isolated response cache per test."""
    reset_llm_response_cache()
    cache_dir = tmp_path / "llm_cache"
    cache = get_llm_response_cache(
        cache_dir=cache_dir, enabled=True, ttl_seconds=3600, max_entries=5
    )
    return cache


def test_cache_key_generation_deterministic() -> None:
    """Verify deterministic SHA-256 generation across varied message shapes."""
    k1 = LLMResponseCache.generate_key("ollama", "gemma4:26b", "sys-1", "user prompt")
    k2 = LLMResponseCache.generate_key("ollama", "gemma4:26b", "sys-1", "user prompt")
    assert k1 == k2
    assert k1.startswith("llm_")

    # Change in model produces distinct key
    k3 = LLMResponseCache.generate_key("ollama", "qwen2.5:7b", "sys-1", "user prompt")
    assert k1 != k3

    # ChatMessage list matching string content
    msgs = [ChatMessage(role="user", content="user prompt")]
    k4 = LLMResponseCache.generate_key("ollama", "gemma4:26b", "sys-1", msgs)
    assert k1 != k4  # Structured list includes role prefix


def test_cache_set_and_get_memory_and_disk(clean_cache: LLMResponseCache) -> None:
    """Verify storing and loading from memory and disk cache."""
    key = "llm_test_key_123"
    entry = clean_cache.set(
        key=key,
        provider="ollama",
        model="gemma4:26b",
        system="System instruction",
        prompt="Review file.py",
        content="Here are the findings: 1. No bugs found.",
        thinking="Model thought process",
        context_tag="src/file.py",
        wall_seconds=1.25,
        backend_info="localhost:11434",
    )
    assert entry.key == key
    assert entry.hit_count == 0

    # Retrieve from memory cache
    hit_1 = clean_cache.get(key)
    assert hit_1 is not None
    assert hit_1.content == "Here are the findings: 1. No bugs found."
    assert hit_1.thinking == "Model thought process"
    assert hit_1.hit_count == 1

    # Clear memory cache to force disk load
    clean_cache._memory_cache.clear()
    hit_2 = clean_cache.get(key)
    assert hit_2 is not None
    assert hit_2.content == "Here are the findings: 1. No bugs found."
    assert hit_2.hit_count == 2
    assert key in clean_cache._memory_cache


def test_cache_ttl_expiration(tmp_path: Path) -> None:
    """Verify expired cache entries return None and get evicted."""
    short_cache = LLMResponseCache(
        cache_dir=tmp_path / "short_cache",
        enabled=True,
        ttl_seconds=60.0,
    )
    key = "llm_expiring_key"
    entry = short_cache.set(
        key=key,
        provider="ollama",
        model="gemma4:26b",
        system="sys",
        prompt="prompt",
        content="temporary response",
    )

    # Immediately valid
    assert short_cache.get(key) is not None

    # Simulate expiration by rolling back created_at timestamp
    entry.created_at = time.time() - 120.0
    short_cache._save_to_disk(entry)

    assert entry.is_expired(60.0) is True
    assert short_cache.get(key) is None
    assert short_cache.get_stats()["misses"] >= 1


def test_starting_point_lookup_and_formatting(clean_cache: LLMResponseCache) -> None:
    """Verify looking up cached response by context_tag and formatting baseline starting point."""
    clean_cache.set(
        key="llm_item_v1",
        provider="ollama",
        model="gemma4:26b",
        system="sys",
        prompt="analyze v1",
        content="Initial draft review findings for release.py",
        context_tag="src/devops_cli/commands/release.py",
    )

    sp = clean_cache.get_starting_point(context_tag="src/devops_cli/commands/release.py")
    assert sp == "Initial draft review findings for release.py"

    # Non-existent context tag returns None
    assert clean_cache.get_starting_point(context_tag="src/other.py") is None

    # Format starting point prompt
    formatted = clean_cache.format_starting_point_prompt(
        prompt="Review updated release.py diff",
        starting_point=sp,
    )
    assert "<starting_point>" in formatted
    assert "Initial draft review findings for release.py" in formatted
    assert "<current_request>" in formatted
    assert "Review updated release.py diff" in formatted


def test_cache_capacity_enforcement(tmp_path: Path) -> None:
    """Verify LRU capacity enforcement when max_entries is exceeded."""
    small_cache = LLMResponseCache(
        cache_dir=tmp_path / "small_cache",
        enabled=True,
        max_entries=2,
    )
    small_cache.set("llm_1", "p", "m", "s", "p1", "c1")
    time.sleep(0.01)
    small_cache.set("llm_2", "p", "m", "s", "p2", "c2")
    time.sleep(0.01)
    small_cache.set("llm_3", "p", "m", "s", "p3", "c3")

    stats = small_cache.get_stats()
    assert stats["memory_entries"] <= 2
    assert stats["disk_entries"] <= 2


def test_cache_clear_and_stats(clean_cache: LLMResponseCache) -> None:
    """Verify cache clear and statistics computation."""
    clean_cache.set("llm_k1", "ollama", "gemma4:26b", "sys", "p1", "c1")
    clean_cache.get("llm_k1")  # hit
    clean_cache.get("llm_nonexistent")  # miss

    stats = clean_cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate_percent"] == 50.0
    assert stats["memory_entries"] == 1
    assert stats["disk_entries"] == 1

    cleared = clean_cache.clear()
    assert cleared >= 1
    post_stats = clean_cache.get_stats()
    assert post_stats["hits"] == 0
    assert post_stats["memory_entries"] == 0
    assert post_stats["disk_entries"] == 0


def test_llm_client_exact_cache_hit(
    monkeypatch: pytest.MonkeyPatch, clean_cache: LLMResponseCache
) -> None:
    """Verify LLMClient returns cached response with cached=True without network dispatch."""
    cfg = AIConfig(provider="ollama", model="gemma4:26b")
    client = LLMClient(config=cfg)
    client._cache = clean_cache

    dispatch_mock = MagicMock(
        return_value=LLMResponse("Fresh response from model", wall_seconds=2.5)
    )
    monkeypatch.setattr(client, "_dispatch_messages", dispatch_mock)

    # 1. First call: Cache miss, dispatches to model and caches response
    res1 = client.chat("system prompt", "hello world", use_cache=True)
    assert res1 == "Fresh response from model"
    assert res1.cached is False
    assert dispatch_mock.call_count == 1

    # 2. Second call: Exact match, returns cached response instantly without dispatching
    res2 = client.chat("system prompt", "hello world", use_cache=True)
    assert res2 == "Fresh response from model"
    assert res2.cached is True
    assert res2.backend_info == "cache"
    assert dispatch_mock.call_count == 1  # No additional dispatch!


def test_llm_client_starting_point_warm_refinement(
    monkeypatch: pytest.MonkeyPatch, clean_cache: LLMResponseCache
) -> None:
    """Verify LLMClient injects starting point draft into user prompt on subsequent request."""
    cfg = AIConfig(provider="ollama", model="gemma4:26b")
    client = LLMClient(config=cfg)
    client._cache = clean_cache

    # Prime cache with an initial version tagged with context_tag
    clean_cache.set(
        key="llm_prime_key",
        provider="ollama",
        model="gemma4:26b",
        system="system prompt",
        prompt="Initial version",
        content="Prior review: Finding A on line 10.",
        context_tag="src/module.py",
    )

    dispatched_messages: list[ChatMessage] = []

    def mock_dispatch(system: str, messages: list[ChatMessage], **kw: Any) -> LLMResponse:
        dispatched_messages.extend(messages)
        return LLMResponse("Updated review: Finding A still valid, plus Finding B on line 20.")

    monkeypatch.setattr(client, "_dispatch_messages", mock_dispatch)

    # Call chat with context_tag - should pick up starting point from cache
    res = client.chat(
        "system prompt",
        "Here is the modified module.py diff",
        context_tag="src/module.py",
        use_cache=True,
    )

    assert "Finding B on line 20" in res
    assert len(dispatched_messages) == 1
    # Check that dispatched prompt included the starting point baseline
    assert "<starting_point>" in dispatched_messages[0].content
    assert "Prior review: Finding A on line 10." in dispatched_messages[0].content
    assert "Here is the modified module.py diff" in dispatched_messages[0].content


def test_ai_cache_cli_commands(clean_cache: LLMResponseCache) -> None:
    """Verify devops ai cache status and devops ai cache clear CLI commands."""
    from typer.testing import CliRunner

    from devops_cli.commands.ai import app as ai_app

    runner = CliRunner()

    # Populate cache entry
    clean_cache.set("llm_cmd_test", "ollama", "gemma4:26b", "sys", "prompt", "content")

    # Test status table
    res_status = runner.invoke(ai_app, ["cache", "status"])
    assert res_status.exit_code == 0
    assert "LLM Response Cache Performance" in res_status.output
    assert "In-Memory Entries" in res_status.output

    # Test status json
    res_json = runner.invoke(ai_app, ["cache", "status", "--format", "json"])
    assert res_json.exit_code == 0
    assert '"memory_entries":' in res_json.output

    # Test clear
    res_clear = runner.invoke(ai_app, ["cache", "clear"])
    assert res_clear.exit_code == 0
    assert "Cleared" in res_clear.output
