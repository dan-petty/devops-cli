"""Unit tests for local context budgeting and tiktoken BPE tokenizer engine."""

from __future__ import annotations

import base64
import hashlib
import logging
import socket
from pathlib import Path

import pytest
import tiktoken.load
import tiktoken.registry
from typer.testing import CliRunner

from devops_cli.ai.context_budget import (
    TokenBudgetReport,
    count_file_tokens,
    count_tokens,
    reset_tiktoken_encoding_cache,
    truncate_to_token_limit,
    validate_and_budget_prompt,
)
from devops_cli.commands.ai import app as ai_app
from tests.support.paths import REPO_ROOT

runner = CliRunner()


def test_count_tokens_empty_and_text() -> None:
    assert count_tokens("") == 0
    assert count_tokens("Hello, world!") > 0
    code_text = (
        "def calculate_hash(data: bytes) -> str:\n    return hashlib.sha256(data).hexdigest()"
    )
    assert count_tokens(code_text) >= 10


def test_count_file_tokens(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.py"
    test_file.write_text("import sys\nprint(sys.version)\n", encoding="utf-8")

    assert count_file_tokens(test_file) > 0
    assert count_file_tokens(tmp_path / "non_existent.py") == 0


def test_truncate_to_token_limit() -> None:
    long_text = "word " * 500
    truncated = truncate_to_token_limit(long_text, max_tokens=20)
    assert count_tokens(truncated) <= 30
    assert "...[truncated" in truncated

    short_text = "Short sentence."
    assert truncate_to_token_limit(short_text, max_tokens=100) == short_text
    assert truncate_to_token_limit("", max_tokens=10) == ""


def test_validate_and_budget_prompt() -> None:
    short_text = "This is a short prompt."
    budgeted, was_condensed = validate_and_budget_prompt(short_text, max_tokens=100)
    assert budgeted == short_text
    assert was_condensed is False

    long_text = "word " * 500
    budgeted, was_condensed = validate_and_budget_prompt(long_text, max_tokens=20)
    assert was_condensed is True
    assert "...[content condensed to fit context window budget]" in budgeted


def test_token_budget_report_model() -> None:
    rep = TokenBudgetReport(
        text_length=100,
        estimated_tokens=25,
        max_budget=1000,
        fits_budget=True,
        model="gpt-4o",
        chunk_count=1,
    )
    assert rep.fits_budget is True
    assert rep.estimated_tokens == 25


def test_ai_token_count_cli(tmp_path: Path) -> None:
    sample_file = tmp_path / "code.py"
    sample_file.write_text("x = 42\ny = 100\n", encoding="utf-8")

    res_file = runner.invoke(ai_app, ["token-count", str(sample_file)])
    assert res_file.exit_code == 0
    assert "AI Context Token Budget Report" in res_file.stdout

    res_json = runner.invoke(ai_app, ["token-count", str(sample_file), "--json"])
    assert res_json.exit_code == 0
    assert '"estimated_tokens"' in res_json.stdout

    res_text = runner.invoke(ai_app, ["token-count", "some raw prompt text", "--budget", "100"])
    assert res_text.exit_code == 0
    assert "AI Context Token Budget Report" in res_text.stdout


def _prepare_o200k_cache_dir(cache_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate `cache_dir` with a synthetic o200k_base BPE file and matching SHA-256 hash."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    ranks = {bytes([i]): i for i in range(256)}
    ranks[b"hello"] = 256
    ranks[b" world"] = 257
    bpe_bytes = b"".join(
        base64.b64encode(token) + f" {rank}\n".encode("ascii") for token, rank in ranks.items()
    )
    expected_hash = hashlib.sha256(bpe_bytes).hexdigest()
    blob_url = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
    cache_key = hashlib.sha1(blob_url.encode("utf-8"), usedforsecurity=False).hexdigest()
    (cache_dir / cache_key).write_bytes(bpe_bytes)

    tiktoken.registry._find_constructors()
    assert tiktoken.registry.ENCODING_CONSTRUCTORS is not None
    monkeypatch.setitem(
        tiktoken.registry.ENCODING_CONSTRUCTORS,
        "o200k_base",
        lambda: {
            "name": "o200k_base",
            "pat_str": r" ?\p{L}+|\s+|\S+",
            "mergeable_ranks": tiktoken.load.load_tiktoken_bpe(
                blob_url, expected_hash=expected_hash
            ),
            "special_tokens": {},
        },
    )
    # tiktoken stores the encoding it builds in its registry. A registry of the test's own goes
    # with the test, so the synthetic encoding never reaches a later test (#2002).
    monkeypatch.setattr(tiktoken.registry, "ENCODINGS", {})


def test_count_tokens_loads_encoding_from_prepared_cache_dir_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With sockets blocked, count_tokens loads the encoding from TIKTOKEN_CACHE_DIR with no connection (#1421)."""
    cache_dir = tmp_path / "tiktoken-cache"
    _prepare_o200k_cache_dir(cache_dir, monkeypatch)
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(cache_dir))

    connect_attempts: list[object] = []

    def _forbid_connect(self: socket.socket, address: object) -> None:
        connect_attempts.append(address)
        raise RuntimeError(f"Unexpected socket connection to {address!r}")

    monkeypatch.setattr(socket.socket, "connect", _forbid_connect)

    tokens = count_tokens("hello world", model="gpt-4o-prepared-cache")

    # Under the loaded BPE encoding, "hello world" is 2 tokens ([256, 257]), whereas the
    # 4-characters-per-token fallback heuristic would return ceil(11 / 4) == 3.
    assert (tokens, connect_attempts) == (2, [])


def test_the_synthetic_encoding_leaves_tiktokens_registry_with_its_test(tmp_path: Path) -> None:
    """Verify the prepared-cache encoding does not outlive its test in tiktoken's registry (#2002).

    On a fresh worker the registry has no o200k_base. A synthetic encoding left there makes
    every later count on that worker about one token per byte.
    """
    with pytest.MonkeyPatch.context() as worker:
        worker.delitem(tiktoken.registry.ENCODINGS, "o200k_base", raising=False)
        with pytest.MonkeyPatch.context() as monkeypatch:
            cache_dir = tmp_path / "tiktoken-cache"
            _prepare_o200k_cache_dir(cache_dir, monkeypatch)
            monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(cache_dir))
            count_tokens("hello world", model="gpt-4o-prepared-cache")
        reset_tiktoken_encoding_cache()
        left_behind = tiktoken.registry.ENCODINGS.get("o200k_base")

    assert left_behind is None


def test_failed_encoding_load_logs_one_warning_naming_cache_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When the tiktoken encoding cannot load, _get_tiktoken_encoding logs one WARNING naming the cache dir (#1421)."""
    missing_cache = tmp_path / "missing-tiktoken-cache"
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(missing_cache))
    monkeypatch.delitem(tiktoken.registry.ENCODINGS, "o200k_base", raising=False)

    with caplog.at_level(logging.WARNING, logger="devops_cli.ai.context_budget"):
        first = count_tokens("hello world", model="gpt-4o-missing-cache")
        second = count_tokens("hello world", model="gpt-4o-missing-cache")

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert (
        first,
        second,
        len(warnings),
        any(str(missing_cache) in msg for msg in warnings),
    ) == (3, 3, 1, True)


def test_service_and_devcontainer_dockerfiles_populate_tiktoken_cache() -> None:
    """Service and DevContainer Dockerfiles populate TIKTOKEN_CACHE_DIR at image build (#1421)."""
    service_dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    devcontainer_dockerfile = (REPO_ROOT / ".devcontainer" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert (
        "TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken" in service_dockerfile,
        "COPY --from=builder /app/.cache/tiktoken /app/.cache/tiktoken" in service_dockerfile,
        "cl100k_base" in service_dockerfile and "o200k_base" in service_dockerfile,
        "TIKTOKEN_CACHE_DIR=" in devcontainer_dockerfile,
        "cl100k_base" in devcontainer_dockerfile and "o200k_base" in devcontainer_dockerfile,
    ) == (True, True, True, True, True)
