"""Unit tests for LLM response cache and warm starting point mechanisms."""

from __future__ import annotations

import functools
import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger

import httpx2
import pytest

from devops_cli.ai.client import LLMClient, LLMResponse
from devops_cli.ai.response_cache import (
    LLMResponseCache,
    get_llm_response_cache,
    reset_llm_response_cache,
)
from devops_cli.config.constants import CONST_AI_GATEWAY_SERVED_BY_HEADER
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import route_client
from tests.support.fakes.clock import ClockFake


@pytest.fixture(autouse=True)
def clean_cache(tmp_path: Path, spend_ledger: SpendLedger) -> LLMResponseCache:
    """Fixture providing an isolated response cache per test."""
    reset_llm_response_cache()
    cache_dir = tmp_path / "llm_cache"
    cache = get_llm_response_cache(
        cache_dir=cache_dir, enabled=True, ttl_seconds=3600, max_entries=5
    )
    return cache


def _valid_test_key(tag: str) -> str:
    """Return a deterministic valid 64-hex SHA-256 cache key for test usage."""
    return f"llm_{hashlib.sha256(tag.encode('utf-8')).hexdigest()}"


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
    key = _valid_test_key("test_key_123")
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
    key = _valid_test_key("expiring_key")
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
    assert short_cache.get_stats().misses >= 1


def test_starting_point_lookup_and_formatting(clean_cache: LLMResponseCache) -> None:
    """Verify looking up cached response by context_tag and formatting baseline starting point."""
    clean_cache.set(
        key=_valid_test_key("item_v1"),
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


def test_cache_capacity_enforcement(tmp_path: Path, clock: ClockFake) -> None:
    """Verify LRU capacity enforcement when max_entries is exceeded."""
    small_cache = LLMResponseCache(
        cache_dir=tmp_path / "small_cache",
        enabled=True,
        max_entries=2,
    )
    small_cache.set(_valid_test_key("1"), "p", "m", "s", "p1", "c1")
    clock.sleep(0.01)
    small_cache.set(_valid_test_key("2"), "p", "m", "s", "p2", "c2")
    clock.sleep(0.01)
    small_cache.set(_valid_test_key("3"), "p", "m", "s", "p3", "c3")

    stats = small_cache.get_stats()
    assert stats.memory_entries <= 2
    assert stats.disk_entries <= 2


def test_cache_clear_and_stats(clean_cache: LLMResponseCache) -> None:
    """Verify cache clear and statistics computation."""
    k_k1 = _valid_test_key("k1")
    k_nonexistent = _valid_test_key("nonexistent")
    clean_cache.set(k_k1, "ollama", "gemma4:26b", "sys", "p1", "c1")
    clean_cache.get(k_k1)  # hit
    clean_cache.get(k_nonexistent)  # miss

    stats = clean_cache.get_stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.hit_rate_percent == 50.0
    assert stats.memory_entries == 1
    assert stats.disk_entries == 1

    cleared = clean_cache.clear()
    assert cleared >= 1
    post_stats = clean_cache.get_stats()
    assert post_stats.hits == 0
    assert post_stats.memory_entries == 0
    assert post_stats.disk_entries == 0


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


def test_a_cache_entry_keeps_the_backend_and_model_that_served_it(
    clean_cache: LLMResponseCache,
) -> None:
    """Verify an entry records the backend and model its reply carried beside the requested alias,
    and one written without them reads back with neither (#1013)."""
    store = functools.partial(
        clean_cache.set,
        provider="gateway",
        model="alias",
        system="sys",
        prompt="prompt",
        content="reply",
    )
    k_served = _valid_test_key("served")
    k_unserved = _valid_test_key("unserved")
    store(
        key=k_served,
        served_by="https://example.com:11434",
        response_model="served-model",
    )
    store(key=k_unserved)
    clean_cache._memory_cache.clear()

    read = [clean_cache.get(key) for key in (k_served, k_unserved)]

    assert [
        (entry.model, entry.served_by, entry.response_model) for entry in read if entry is not None
    ] == [
        ("alias", "https://example.com:11434", "served-model"),
        ("alias", None, None),
    ]


def _served_gateway_client(
    monkeypatch: pytest.MonkeyPatch, clean_cache: LLMResponseCache, served_by: str
) -> tuple[LLMClient, list[httpx2.Request]]:
    """A gateway client, over a transport that answers `served_by` as the backend and
    `served-model` as the model, using the test's cache."""
    config = AIConfig(
        provider="gateway", model="demo-model", gateway_url="http://example.com:4000/v1"
    )
    client = LLMClient(config, api_key="sk")
    client._cache = clean_cache
    body = {
        "model": "served-model",
        "choices": [{"message": {"content": "reply"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    headers = {CONST_AI_GATEWAY_SERVED_BY_HEADER: served_by}
    sent = route_client(
        client,
        monkeypatch,
        lambda _request: httpx2.Response(200, json=body, headers=headers),
    )
    return client, sent


def test_a_cache_hit_returns_the_backend_and_model_that_served_the_reply(
    monkeypatch: pytest.MonkeyPatch, public_dns: str, clean_cache: LLMResponseCache
) -> None:
    """Verify a hit carries the served backend and model of the reply it replays, and still
    names the cache as its backend (#1013)."""
    client, sent = _served_gateway_client(monkeypatch, clean_cache, "https://example.com:11434")

    client.chat("system prompt", "hello world")
    hit = client.chat("system prompt", "hello world")

    assert (len(sent), hit.cached, hit.backend_info, hit.served_by, hit.model) == (
        1,
        True,
        "cache",
        "https://example.com:11434",
        "served-model",
    )


def test_the_backend_a_cached_gateway_reply_records_carries_no_credentials(
    monkeypatch: pytest.MonkeyPatch, public_dns: str, clean_cache: LLMResponseCache
) -> None:
    """Verify a gateway that names its backend with credentials in the URL leaves them out of
    the entry: the cache stores the backend as the client reports it (#1013)."""
    client, _sent = _served_gateway_client(
        monkeypatch, clean_cache, "https://user:secret@example.com:11434"
    )

    client.chat("system prompt", "hello world")
    (entry_file,) = clean_cache.cache_dir.rglob("*.json")
    text = entry_file.read_text(encoding="utf-8")
    entry = json.loads(text)

    assert (
        "secret" in text,
        entry["served_by"],
        entry["response_model"],
        entry["model"],
    ) == (
        False,
        "https://example.com:11434",
        "served-model",
        "demo-model",
    )


def test_llm_client_starting_point_warm_refinement(
    monkeypatch: pytest.MonkeyPatch, clean_cache: LLMResponseCache
) -> None:
    """Verify LLMClient injects starting point draft into user prompt on subsequent request."""
    cfg = AIConfig(provider="ollama", model="gemma4:26b")
    client = LLMClient(config=cfg)
    client._cache = clean_cache

    # Prime cache with an initial version tagged with context_tag
    clean_cache.set(
        key=_valid_test_key("prime_key"),
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


def test_llm_client_append_cache_flag(
    monkeypatch: pytest.MonkeyPatch, clean_cache: LLMResponseCache
) -> None:
    """Verify LLMClient --append-cache injects cached response into prompt and runs live inference."""
    cfg = AIConfig(provider="ollama", model="gemma4:26b")
    client = LLMClient(config=cfg)
    client._cache = clean_cache

    dispatched_messages: list[ChatMessage] = []

    def mock_dispatch(system: str, messages: list[ChatMessage], **kw: Any) -> LLMResponse:
        dispatched_messages.extend(messages)
        if len(dispatched_messages) == 1:
            return LLMResponse("Prior finding: line 5 insecure TLS.")
        return LLMResponse("Refined response: insecure TLS fixed, line 10 verified.")

    monkeypatch.setattr(client, "_dispatch_messages", mock_dispatch)

    # 1. First run: populate cache with initial response
    res1 = client.chat("sys", "Review file", use_cache=True, append_cache=False)
    assert "Prior finding: line 5 insecure TLS." in res1

    # 2. Call with append_cache=True: Should NOT return cache hit, but append cached response to prompt
    res2 = client.chat(
        "sys",
        "Review file",
        use_cache=True,
        append_cache=True,
    )

    assert "Refined response: insecure TLS fixed" in res2
    assert res2.cached is False
    assert len(dispatched_messages) == 2
    assert "<starting_point>" in dispatched_messages[1].content
    assert "Prior finding: line 5 insecure TLS." in dispatched_messages[1].content
    assert "Review file" in dispatched_messages[1].content


def test_ai_cache_cli_commands(clean_cache: LLMResponseCache) -> None:
    """Verify devops ai cache status and devops ai cache clear CLI commands."""
    from typer.testing import CliRunner

    from devops_cli.commands.ai import app as ai_app

    runner = CliRunner()

    # Populate cache entry
    clean_cache.set(_valid_test_key("cmd_test"), "ollama", "gemma4:26b", "sys", "prompt", "content")

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


def test_ai_config_cache_holds_append_cache() -> None:
    """Verify that append_cache is configured under cache and not on AIConfig."""
    cfg = AIConfig()
    dumped = cfg.model_dump(mode="json")
    assert "append_cache" not in dumped
    assert "append_cache" in dumped["cache"]
    assert not hasattr(cfg, "append_cache")
    assert cfg.cache.append_cache is False


def test_cache_refuses_malformed_keys_before_file_access(
    clean_cache: LLMResponseCache,
) -> None:
    """Verify keys not matching 'llm_' followed by 64 hex characters are refused."""
    invalid_keys = [
        "../escaped",
        "/abs/path",
        "llm_short",
        "llm_" + "a" * 63,
        "llm_" + "a" * 65,
        "llm_" + "a" * 63 + "z",
        "not_llm_" + "a" * 60,
    ]
    for bad_key in invalid_keys:
        assert clean_cache.get(bad_key) is None
        entry = clean_cache.set(bad_key, "p", "m", "s", "p", "c")
        assert entry.key == bad_key
        assert bad_key not in clean_cache._memory_cache
        cdir = clean_cache._resolve_cache_dir()
        assert not list(cdir.glob("*"))
        if hasattr(clean_cache, "delete"):
            clean_cache.delete(bad_key)


def test_loaded_entry_with_mismatched_key_is_not_served_and_deleted(
    clean_cache: LLMResponseCache,
) -> None:
    """Verify that a disk entry whose stored key field differs from requested key is deleted
    and not served, and no file is created outside the cache directory."""
    cdir = clean_cache._resolve_cache_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    req_key = "llm_" + "a" * 64

    # 1. Entry stored with key field "../escaped_by_key_field"
    parent_file = cdir.parent / "escaped_by_key_field.json"
    if parent_file.exists():
        parent_file.unlink()

    bad_entry = {
        "key": "../escaped_by_key_field",
        "provider": "ollama",
        "model": "m",
        "system_hash": "sys",
        "prompt_hash": "prompt",
        "content": "malicious content",
    }
    target_file = cdir / f"{req_key}.json"
    target_file.write_text(json.dumps(bad_entry), encoding="utf-8")

    assert clean_cache.get(req_key) is None
    assert not target_file.exists()
    assert not parent_file.exists()

    # 2. Entry stored with absolute key field and empty content
    abs_target = (cdir.parent / "abs_escaped.json").resolve()
    if abs_target.exists():
        abs_target.unlink()

    bad_entry_abs = {
        "key": str(abs_target.with_suffix("")),
        "provider": "ollama",
        "model": "m",
        "system_hash": "sys",
        "prompt_hash": "prompt",
        "content": "",
    }
    target_file.write_text(json.dumps(bad_entry_abs), encoding="utf-8")

    assert clean_cache.get(req_key) is None
    assert not target_file.exists()
    assert not abs_target.exists()


def test_cache_delete_removes_entry_from_memory_and_disk(
    clean_cache: LLMResponseCache,
) -> None:
    """Verify delete() removes entry from memory and disk."""
    valid_key = "llm_" + "b" * 64
    clean_cache.set(valid_key, "ollama", "gemma", "sys", "prompt", "content")
    assert valid_key in clean_cache._memory_cache
    target_file = clean_cache._resolve_cache_dir() / f"{valid_key}.json"
    assert target_file.exists()

    clean_cache.delete(valid_key)
    assert valid_key not in clean_cache._memory_cache
    assert not target_file.exists()


def test_response_cache_resolves_under_data_cache_dir(
    isolate_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that get_llm_response_cache resolves under <DATA_DIR>/cache/llm and AICacheConfig has no dir."""
    from devops_cli.config.constants import CONST_LLM_CACHE_DIR_NAME
    from devops_cli.config.settings import AICacheConfig, reset_settings_cache

    assert "dir" not in AICacheConfig.model_fields

    reset_llm_response_cache()
    reset_settings_cache()
    custom_data = isolate_data_dir / "custom_data_dir"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(custom_data))
    reset_settings_cache()

    cache = get_llm_response_cache()
    expected_cache_dir = custom_data / "cache" / CONST_LLM_CACHE_DIR_NAME
    assert cache.cache_dir == expected_cache_dir


def test_ai_cache_status_and_clear_read_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify devops ai cache status and clear read settings and inspect <DATA_DIR>/cache/llm."""
    from typer.testing import CliRunner

    from devops_cli.commands.ai import app as ai_app
    from devops_cli.config.settings import reset_settings_cache

    data_dir = tmp_path / "custom_data"
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "ai:\n"
        "  provider: ollama\n"
        "  cache:\n"
        "    enabled: false\n"
        "    max_entries: 777\n"
        "    ttl_seconds: 9999\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))
    monkeypatch.setattr("devops_cli.config.settings.CONFIG_PATH", cfg_file)
    reset_llm_response_cache()
    reset_settings_cache()

    runner = CliRunner()
    res_status = runner.invoke(ai_app, ["cache", "status", "--format", "json"])
    assert res_status.exit_code == 0
    data = json.loads(res_status.output)
    assert data["enabled"] is False
    assert data["max_entries"] == 777
    assert data["ttl_seconds"] == 9999
    expected_dir = data_dir / "cache" / "llm"
    assert Path(data["cache_directory"]) == expected_dir

    expected_dir.mkdir(parents=True, exist_ok=True)
    test_key = _valid_test_key("clear_target")
    file_path = expected_dir / f"{test_key}.json"
    file_path.write_text("{}", encoding="utf-8")
    assert file_path.exists()

    res_clear = runner.invoke(ai_app, ["cache", "clear"])
    assert res_clear.exit_code == 0
    assert not file_path.exists()


def test_client_with_cache_disabled_never_reads_or_writes_cache(
    isolate_data_dir: Path, monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify that LLMClient with cache_enabled=False neither reads nor writes the cache even when
    a global singleton cache exists and is enabled."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.config.settings import AIConfig
    from tests.llm_stream_fakes import route_client

    reset_llm_response_cache()
    cache_dir = isolate_data_dir / "cache" / "llm"
    singleton = get_llm_response_cache(cache_dir=cache_dir, enabled=True)

    config = AIConfig(
        provider="gateway", model="demo-model", gateway_url="http://example.com:4000/v1"
    )
    client = LLMClient(config=config, api_key="sk", cache_enabled=False)

    body = {
        "model": "demo-model",
        "choices": [{"message": {"content": "fresh reply"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    sent = route_client(client, monkeypatch, lambda _req: httpx2.Response(200, json=body))

    res1 = client.chat("system", "hello")
    res2 = client.chat("system", "hello")

    assert len(sent) == 2
    assert res1.cached is False
    assert res2.cached is False

    stats = singleton.get_stats()
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.memory_entries == 0
    assert stats.disk_entries == 0

    cache_files = list(cache_dir.glob("*.json"))
    assert cache_files == []


def test_empty_content_with_thinking_is_not_cached(
    isolate_data_dir: Path, monkeypatch: pytest.MonkeyPatch, public_dns: str
) -> None:
    """Verify that an LLM response with empty content and thinking blocks is returned to the
    caller but is never saved to the response cache."""
    reset_llm_response_cache()
    cache_dir = isolate_data_dir / "cache" / "llm"
    cache = get_llm_response_cache(cache_dir=cache_dir, enabled=True)

    config = AIConfig(
        provider="gateway", model="demo-model", gateway_url="http://example.com:4000/v1"
    )
    client = LLMClient(config=config, api_key="sk")

    body = {
        "model": "demo-model",
        "choices": [
            {
                "message": {"content": "   ", "reasoning_content": "deep thoughts"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    route_client(client, monkeypatch, lambda _req: httpx2.Response(200, json=body))

    res = client.chat("system", "prompt")
    assert res.content == "   "
    assert res.thinking == "deep thoughts"
    assert res.cached is False

    stats = cache.get_stats()
    assert stats.disk_entries == 0
    assert stats.memory_entries == 0
    assert list(cache_dir.glob("*.json")) == []


def test_check_chat_cache_deletes_rejected_entry(clean_cache: LLMResponseCache) -> None:
    """Verify that when a cached response fails validator validation during _check_chat_cache,
    the entry is purged from both in-memory cache and disk."""
    from unittest.mock import MagicMock

    config = AIConfig(
        provider="gateway", model="demo-model", gateway_url="http://example.com:4000/v1"
    )
    client = LLMClient(config=config, api_key="sk")
    client._cache = clean_cache
    valid_k = _valid_test_key("rejected_lookup")
    clean_cache.set(valid_k, "gateway", "demo-model", "sys", "prompt", "rejected text")
    assert clean_cache.get(valid_k) is not None
    assert (clean_cache._resolve_cache_dir() / f"{valid_k}.json").exists()

    res = client._check_chat_cache(valid_k, lambda text: False, MagicMock())
    assert res is None
    assert clean_cache.get(valid_k) is None
    assert not (clean_cache._resolve_cache_dir() / f"{valid_k}.json").exists()
