"""Tests for review benchmark command and run persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.profile import ReviewProfile, StageProfile, report_profile
from devops_cli.ai.run_store import Mechanism, load_runs
from devops_cli.commands import review as review_commands
from devops_cli.config.settings import reset_settings_cache
from devops_cli.main import app

runner = CliRunner()


def test_a_review_benchmark_is_kept_with_its_setup_and_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a benchmark's record carries its personas and page size, and names its corpus by
    content."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "site.yaml").write_text("- hosts: all\n", encoding="utf-8")

    def fake_review(**_: Any) -> None:
        report_profile(
            ReviewProfile(
                session_id="s",
                target=str(corpus),
                total_wall_seconds=10,
                stages=[StageProfile(name="persona_review", wall_seconds=5)],
            )
        )

    monkeypatch.setattr(review_commands, "path", fake_review)

    result = runner.invoke(app, ["review", "benchmark", str(corpus), "-n", "1"])
    (record,) = load_runs(Mechanism.REVIEW_BENCHMARK)

    assert (
        result.exit_code,
        "page_chars" not in record.setup,
        record.subject == {"corpus_digest": record.results["corpus_digest"], "target": "corpus"},
        "Kept on this workstation only" in result.output,
    ) == (0, True, True, True)


@pytest.mark.parametrize(
    ("flags", "no_static_scan"), [(["--no-static-scan"], True), ([], False)], ids=["off", "on"]
)
def test_a_review_benchmark_can_review_without_static_scanners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str], no_static_scan: bool
) -> None:
    """Verify `--no-static-scan` reaches every review of a benchmark and the run's setup, so a
    scanner hit on an injected defect does not count as the model's recall (#475)."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "site.yaml").write_text("- hosts: all\n", encoding="utf-8")
    calls: list[bool] = []

    def fake_review(**kwargs: Any) -> None:
        calls.append(kwargs["no_static_scan"])
        report_profile(
            ReviewProfile(
                session_id=f"s{len(calls)}",
                target=str(corpus),
                total_wall_seconds=10,
                stages=[StageProfile(name="persona_review", wall_seconds=5)],
            )
        )

    monkeypatch.setattr(review_commands, "path", fake_review)

    result = runner.invoke(review_commands.app, ["benchmark", str(corpus), "-n", "2", *flags])
    (record,) = load_runs(Mechanism.REVIEW_BENCHMARK)

    assert (result.exit_code, calls, record.setup["static_scan"]) == (
        0,
        [no_static_scan, no_static_scan],
        not no_static_scan,
    )


@pytest.mark.parametrize(("provider", "recorded"), [("gateway", 3), ("ollama", 8)])
def test_a_review_benchmark_records_the_concurrency_its_reviews_ran_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str, recorded: int
) -> None:
    """Verify a benchmark's setup records the file workers its reviews ran with. Through the
    gateway, `--concurrency 8` runs at the gateway's 3 backend slots, so benchmarks at 4, 8 and
    16 record one setup; another provider runs and records the 8 asked for (#1354)."""
    from devops_cli.ai import run_store

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "site.yaml").write_text("- hosts: all\n", encoding="utf-8")
    requested: list[int | None] = []

    def fake_review(**kwargs: Any) -> None:
        requested.append(kwargs["concurrency"])
        report_profile(
            ReviewProfile(
                session_id="s",
                target=str(corpus),
                total_wall_seconds=10,
                stages=[StageProfile(name="persona_review", wall_seconds=5)],
            )
        )

    monkeypatch.setenv("DEVOPS_CLI_AI_TASK_ANALYSIS_PROVIDER", provider)
    reset_settings_cache()
    monkeypatch.setattr(run_store, "gateway_pool", lambda task: [])
    monkeypatch.setattr(review_commands, "path", fake_review)

    result = runner.invoke(review_commands.app, ["benchmark", str(corpus), "-n", "1", "-c", "8"])
    (record,) = load_runs(Mechanism.REVIEW_BENCHMARK)

    assert (result.exit_code, requested, record.setup["concurrency"]) == (0, [8], recorded)
