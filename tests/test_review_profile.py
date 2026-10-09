"""Review profiles: wall time, LLM calls, tokens and serving backends per stage."""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.ai import context_budget, personas
from devops_cli.ai.client import LLMClient, LLMResponse
from devops_cli.ai.personas import review_prompt_digest
from devops_cli.ai.rag import investigator
from devops_cli.ai.response_cache import LLMResponseCache
from devops_cli.ai.review import pipeline as pipeline_module
from devops_cli.ai.review import profile as profile_module
from devops_cli.ai.review import runner
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.profile import (
    BenchmarkSummary,
    ReviewProfile,
    ReviewProfiler,
    StageProfile,
    active_profiler,
    collect_profiles,
    profiling,
    report_profile,
    review_stage,
    summarize_profiles,
)
from devops_cli.ai.review.runner import (
    _corpus_digest,
    _run_orchestrator_review,
    _write_review_profile,
)
from devops_cli.ai.review.verification import _VALIDATION_SYSTEM
from devops_cli.ai.spend.ledger import SpendLedger, observe_llm_calls, track_request_spend
from devops_cli.commands import review as review_commands
from devops_cli.commands.review import _backend_host
from devops_cli.config.settings import AIConfig
from devops_cli.lang import MESSAGES
from devops_cli.main import app
from devops_cli.models.ai import ChatMessage, FileAnalysisMeta
from devops_cli.tools_lock import tools_lock_digest

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})

VLLM = "http://vllm.example.com:8000/v1"
OLLAMA = "http://ollama-0.example.com:11434"


def _call(
    ledger: SpendLedger, served_by: str | None, completion: int = 10, *, cached: bool = False
) -> None:
    track_request_spend(
        provider="gateway",
        model="devops-review",
        server="gateway.example.com:4000",
        served_by=served_by,
        prompt_tokens=100,
        completion_tokens=completion,
        cached=cached,
        duration_seconds=1.0,
        ledger=ledger,
    )


def test_every_llm_call_reaches_the_observers(tmp_path: Path) -> None:
    """Verify observers see each recorded call, and only inside the block."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    seen: list[dict[str, Any]] = []

    with observe_llm_calls(seen.append):
        _call(ledger, VLLM, completion=7)
    _call(ledger, OLLAMA)

    assert [(c["served_by"], c["prompt_tokens"], c["completion_tokens"]) for c in seen] == [
        (VLLM, 100, 7)
    ]


def test_profiler_attributes_calls_to_stages_across_worker_threads(tmp_path: Path) -> None:
    """Verify calls are credited to the running stage, including calls made in worker threads."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")

    async def persona_calls() -> None:
        await asyncio.gather(
            asyncio.to_thread(_call, ledger, VLLM), asyncio.to_thread(_call, ledger, OLLAMA)
        )

    with profiling() as profiler:
        with review_stage("persona_review"):
            asyncio.run(persona_calls())
        with review_stage("verification"):
            _call(ledger, VLLM, completion=40)
        profiler.set_findings(candidates=10, verified=4, reported=3)
        profile = profiler.build(session_id="s1", target="playbooks")

    assert (
        [(s.name, s.llm_calls, s.completion_tokens, s.backends) for s in profile.stages],
        (profile.llm_calls, profile.candidate_findings, profile.reported_findings),
        active_profiler() is None,
    ) == (
        [
            ("persona_review", 2, 20, {VLLM: 1, OLLAMA: 1}),
            ("verification", 1, 40, {VLLM: 1}),
        ],
        (3, 10, 3),
        True,
    )


def test_cached_replies_are_counted_apart_from_backend_calls(tmp_path: Path) -> None:
    """Verify a cached reply adds no backend call or tokens, only a cached-call count."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")

    with profiling() as profiler:
        with review_stage("persona_review"):
            _call(ledger, VLLM)
            _call(ledger, None, cached=True)
        profile = profiler.build(session_id="s", target="t")

    assert (profile.llm_calls, profile.cached_calls, profile.completion_tokens) == (1, 1, 10)


def _observed(profiler: ReviewProfiler, served_by: str | None, reason: str | None) -> None:
    """Show the profiler one served reply, as the spend ledger does when a call finishes."""
    profiler.observe({"served_by": served_by, "finish_reason": reason, "completion_tokens": 10})


@pytest.fixture
def fixed_prompt_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip hashing every review prompt on disk; the digest is not under test here."""
    monkeypatch.setattr(profile_module, "review_prompt_digest", lambda: "digest")


@pytest.mark.usefixtures("fixed_prompt_digest")
def test_profile_counts_replies_by_finish_reason_and_cut_replies_by_backend(
    tmp_path: Path,
) -> None:
    """Verify each stage counts replies per reason, and `length` replies per serving backend."""
    with profiling() as profiler:
        with review_stage("persona_review"):
            for reason in ("stop", "stop", "length"):
                _observed(profiler, "b1", reason)
        with review_stage("verification"):
            _observed(profiler, None, None)
        profiler.build(session_id="s", target="t").write(tmp_path)

    loaded = ReviewProfile.load(tmp_path)
    stages = loaded.stages if loaded else []
    assert [(s.name, s.finish_reasons, s.truncated) for s in stages] == [
        ("persona_review", {"stop": 2, "length": 1}, {"b1": 1}),
        ("verification", {"unknown": 1}, {}),
    ]


@pytest.mark.usefixtures("fixed_prompt_digest")
@pytest.mark.parametrize(
    ("reasons", "summary"),
    [
        (["stop", "length"], "2 LLM calls, 1 hit the reply cap; persona_review 1s (2 calls)"),
        (["stop"], "1 LLM calls; persona_review 1s (1 calls)"),
    ],
    ids=["one-cut", "none-cut"],
)
def test_the_profile_summary_says_how_many_replies_hit_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reasons: list[str], summary: str
) -> None:
    """Verify the summary line counts replies cut at their cap, and is unchanged with none."""
    lines: list[str] = []
    monkeypatch.setattr(runner, "print_info", lambda message, **kwargs: lines.append(message))
    monkeypatch.setattr(runner, "format_duration", lambda seconds: "1s")
    orchestrator = MagicMock(session_id="s1", session_dir=tmp_path)

    with profiling() as profiler:
        with review_stage("persona_review"):
            for reason in reasons:
                _observed(profiler, VLLM, reason)
        _write_review_profile(profiler, orchestrator, "playbooks", 2)

    assert lines == [f"[dim]Profile: 1s, {summary} -> {tmp_path / 'profile.json'}[/dim]"]


def test_stage_is_a_no_op_without_a_profiler() -> None:
    """Verify stage markers cost nothing when no review is being profiled."""
    with review_stage("persona_review"):
        pass

    assert active_profiler() is None


def _profile(wall: float, persona: float, calls: int, candidates: int) -> ReviewProfile:
    return ReviewProfile(
        session_id="s",
        target="t",
        total_wall_seconds=wall,
        llm_calls=calls,
        candidate_findings=candidates,
        stages=[StageProfile(name="persona_review", wall_seconds=persona, llm_calls=calls)],
    )


def test_benchmark_summary_takes_medians_across_runs() -> None:
    """Verify repeated runs are summarised by their medians, stage by stage."""
    summary = summarize_profiles(
        [_profile(300, 200, 80, 50), _profile(200, 150, 60, 40), _profile(250, 180, 70, 70)]
    )

    assert (
        summary.runs,
        summary.median_wall_seconds,
        summary.median_candidate_findings,
        summary.median_seconds_per_candidate,
        [(s.name, s.median_wall_seconds, s.median_llm_calls) for s in summary.stages],
    ) == (3, 250.0, 50.0, 5.0, [("persona_review", 180.0, 70.0)])


def test_orchestrated_review_profiles_each_stage_and_its_findings() -> None:
    """Verify the review marks its stages and records candidate, verified and reported counts."""
    finding = MagicMock(verified=True, reportable=True)
    payload = MagicMock(findings=[finding, MagicMock(verified=False, reportable=False)])
    orchestrator = MagicMock()
    orchestrator.init_per_file_payloads.return_value = [payload]
    orchestrator.generate_consolidated_report.return_value = ({}, "report")

    with profiling() as profiler:
        _run_orchestrator_review(orchestrator, ["a.yaml"], {}, None, ["a.yaml"], ["qa"], None)
        profile = profiler.build(session_id="s", target="t")

    assert (
        [s.name for s in profile.stages],
        (profile.candidate_findings, profile.verified_findings, profile.reported_findings),
    ) == (
        ["payloads", "persona_review", "verification", "reranking", "report"],
        (2, 1, 1),
    )


def test_profile_is_written_as_json(tmp_path: Path) -> None:
    """Verify a profile round-trips through the session's profile.json."""
    profile = _profile(120, 90, 12, 8)
    path = profile.write(tmp_path)

    assert (path.name, ReviewProfile(**json.loads(path.read_text())).llm_calls) == (
        "profile.json",
        12,
    )


def test_profiler_is_isolated_per_block() -> None:
    """Verify each profiling block gets its own profiler."""
    with profiling() as first:
        pass
    with profiling() as second:
        pass

    assert (isinstance(first, ReviewProfiler), first is second) == (True, False)


def test_written_profiles_reach_the_collecting_benchmark(tmp_path: Path) -> None:
    """Verify a review's profile is written to its session and handed to a collecting benchmark."""
    orchestrator = MagicMock(session_id="20260924-120000", session_dir=tmp_path)

    with collect_profiles() as profiles:
        with profiling() as profiler:
            _write_review_profile(profiler, orchestrator, "playbooks", 15)
    report_profile(_profile(1, 1, 1, 1))

    assert (
        [(p.session_id, p.target, p.files) for p in profiles],
        (tmp_path / "profile.json").exists(),
    ) == ([("20260924-120000", "playbooks", 15)], True)


def test_the_profile_records_a_digest_of_the_conventions_the_review_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify profile.json says which conventions the prompts carried (#946).

    The prompt digest covers the prompts devops-cli ships, so arms of a benchmark reviewed
    under different conventions looked alike. A review whose target has no conventions records
    an empty digest, as one that never read them does, not the digest of an empty text.
    """
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.ai.run_store import digest

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    recorded: list[tuple[str | None, str]] = []
    for name, rules in (("a", "Rule a.\n"), ("b", "Rule b.\n"), ("none", "")):
        project = tmp_path / name
        (project / ".git").mkdir(parents=True)
        if rules:
            (project / ".devops").mkdir()
            (project / ".devops" / "review.md").write_text(rules, encoding="utf-8")
        orchestrator = ReviewPipelineOrchestrator(
            session_id=name, llm_client=MagicMock(), target_dir=project
        )
        with profiling() as profiler:
            conventions = orchestrator._read_target_conventions()
            _write_review_profile(profiler, orchestrator, str(project), 1)
        saved = ReviewProfile.load(orchestrator.session_dir)
        recorded.append((saved.conventions_digest if saved else None, conventions))
    digests = [kept for kept, _ in recorded]
    used = [conventions for _, conventions in recorded]

    assert (
        digests,
        used[2],
        digests[0] != digests[1],
        ReviewProfiler().build(session_id="s", target="t").conventions_digest,
    ) == ([digest(used[0]), digest(used[1]), ""], "", True, "")


def test_benchmark_summary_is_saved_under_the_reviews_directory(tmp_path: Path) -> None:
    """Verify each benchmark is saved as its own JSON file, which loads back unchanged."""
    summary = summarize_profiles([_profile(300, 200, 80, 50)])
    saved = summary.write(tmp_path)

    assert (saved.parent.name, BenchmarkSummary(**json.loads(saved.read_text()))) == (
        "benchmarks",
        summary,
    )


def test_benchmark_command_reviews_each_run_without_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the benchmark runs the review N times uncached and saves the median summary."""
    corpus, reviews = tmp_path / "corpus", tmp_path / "reviews"
    corpus.mkdir()
    (corpus / "site.yaml").write_text("- hosts: all\n", encoding="utf-8")
    calls: list[dict[str, Any]] = []

    def fake_review(**kwargs: Any) -> None:
        calls.append(kwargs)
        report_profile(_profile(100.0 * len(calls), 60, 10, 5))

    monkeypatch.setattr(review_commands, "path", fake_review)
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: reviews)

    result = cli.invoke(app, ["review", "benchmark", str(corpus), "-n", "3", "--all"])
    saved = list((reviews / "benchmarks").glob("*.json"))
    summary = BenchmarkSummary(**json.loads(saved[0].read_text()))

    assert (
        result.exit_code,
        [(c["no_cache"], c["all_personas"], c["targets"]) for c in calls],
        (summary.runs, summary.median_wall_seconds, summary.corpus_digest),
        "Median per Stage" in result.output,
    ) == (0, [(True, True, [corpus])] * 3, (3, 200.0, _corpus_digest([corpus], "*")), True)


def test_corpus_digest_changes_only_with_the_reviewed_files(tmp_path: Path) -> None:
    """Verify the corpus fingerprint is stable for the same files and changes with their content."""
    playbook = tmp_path / "site.yaml"
    playbook.write_text("- hosts: all\n", encoding="utf-8")
    first = _corpus_digest([tmp_path], "*.yaml")
    (tmp_path / "notes.txt").write_text("not reviewed", encoding="utf-8")
    unmatched = _corpus_digest([tmp_path], "*.yaml")
    playbook.write_text("- hosts: web\n", encoding="utf-8")

    assert (unmatched == first, _corpus_digest([tmp_path], "*.yaml") == first) == (True, False)


def test_benchmark_fails_when_no_review_was_profiled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a benchmark whose runs reviewed nothing exits non-zero and saves nothing."""
    monkeypatch.setattr(review_commands, "path", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: tmp_path)

    result = cli.invoke(app, ["review", "benchmark", str(tmp_path), "-n", "2"])

    assert (result.exit_code, (tmp_path / "benchmarks").exists()) == (1, False)


def test_backend_labels_drop_the_cluster_dns_suffix() -> None:
    """Verify in-cluster backends are labelled by pod or service, other backends by host."""
    assert [
        _backend_host("http://ollama-0.ollama-nodes.llm.svc.cluster.local:11434"),
        _backend_host("http://vllm-16gib.llm.svc.cluster.local:8000/v1"),
        _backend_host(VLLM),
    ] == ["ollama-0", "vllm-16gib", "vllm.example.com"]


def test_profiler_accumulates_cost_usd_per_stage(tmp_path: Path) -> None:
    """Verify ReviewProfiler accumulates cost_usd on StageProfile and ReviewProfile."""
    ledger = SpendLedger(db_path=tmp_path / "spend.db")
    with profiling() as profiler:
        with review_stage("persona_review"):
            track_request_spend(
                provider="openai",
                model="gpt-4o",
                server="api.openai.com",
                prompt_tokens=1000,
                completion_tokens=200,
                duration_seconds=0.5,
                ledger=ledger,
            )
        with review_stage("verification"):
            track_request_spend(
                provider="openai",
                model="gpt-4o",
                server="api.openai.com",
                prompt_tokens=2000,
                completion_tokens=400,
                duration_seconds=0.8,
                ledger=ledger,
            )
        profile = profiler.build(session_id="s_cost", target="playbooks")

    stage_costs = [round(s.cost_usd, 6) for s in profile.stages]
    assert (stage_costs, profile.cost_usd) == ([0.0045, 0.009], 0.0135)


def _change_one_character(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(("Y" if text[0] == "X" else "X") + text[1:], encoding="utf-8")


def test_the_prompt_digest_changes_with_any_review_prompt_and_nothing_else(tmp_path: Path) -> None:
    """Verify the digest is 16 stable hex characters, moves with one character of a task or
    persona prompt, and ignores files that are not prompts (#413)."""
    personas_dir = Path(personas.__file__).parent
    tasks, roles = tmp_path / "tasks", tmp_path / "personas"
    shutil.copytree(personas_dir.parent / "tasks", tasks)
    shutil.copytree(personas_dir, roles, ignore=shutil.ignore_patterns("__pycache__"))
    package = review_prompt_digest()
    copy = review_prompt_digest(tasks, roles)
    _change_one_character(tasks / "review.md")
    task_edit = review_prompt_digest(tasks, roles)
    _change_one_character(roles / "devsecops" / "prompt.md")
    persona_edit = review_prompt_digest(tasks, roles)
    (tasks / "helper.py").write_text("x = 1\n", encoding="utf-8")
    (roles / "helper.py").write_text("x = 1\n", encoding="utf-8")

    assert (
        (len(package), int(package, 16) >= 0, review_prompt_digest() == package),
        copy == package,
        len({copy, task_edit, persona_edit}),
        review_prompt_digest(tasks, roles) == persona_edit,
    ) == ((16, True, True), True, 3, True)


def test_a_profile_records_the_digest_of_the_prompts_it_ran_with() -> None:
    """Verify every built profile names the package's review prompts (#413)."""
    profile = ReviewProfiler().build(session_id="s", target="t")

    assert profile.prompt_digest == review_prompt_digest()


def test_a_profile_records_the_tools_lock_it_started_with(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tools lock digest is a review input, read when the review starts (#1142)."""
    packaged = ReviewProfiler().build(session_id="s", target="t").tools_lock_digest
    monkeypatch.setattr(profile_module, "tools_lock_digest", lambda: "at-start")
    profiler = ReviewProfiler()
    monkeypatch.setattr(profile_module, "tools_lock_digest", lambda: "at-end")

    assert (packaged, profiler.build(session_id="s", target="t").tools_lock_digest) == (
        tools_lock_digest(),
        "at-start",
    )


@pytest.mark.parametrize(
    ("at_start", "at_end", "changed"),
    [
        (("commit-a", "diff-a"), ("commit-b", "diff-a"), True),
        (("commit-a", "diff-a"), ("commit-a", "diff-b"), True),
        (("commit-a", "diff-a"), ("commit-a", "diff-a"), False),
        (None, None, False),
    ],
    ids=["committed", "edited", "unchanged", "installed-copy"],
)
def test_a_review_warns_when_its_own_source_changes_during_the_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    at_start: tuple[str, str] | None,
    at_end: tuple[str, str] | None,
    changed: bool,
) -> None:
    """A commit or an edit to devops-cli's own checkout between a review's start and its end is
    recorded in profile.json and printed as a warning (#1050, #1142)."""
    states = iter([at_start, at_end])
    monkeypatch.setattr(profile_module, "own_source_state", lambda: next(states))
    warnings: list[str] = []
    monkeypatch.setattr(runner, "print_warning", lambda message, **kwargs: warnings.append(message))
    orchestrator = MagicMock(session_id="s1", session_dir=tmp_path)

    with profiling() as profiler:
        profile = _write_review_profile(profiler, orchestrator, "playbooks", 1)
    saved = ReviewProfile.load(tmp_path)

    assert (
        profile.code_changed_during_run,
        saved.code_changed_during_run if saved else None,
        warnings,
    ) == (changed, changed, [MESSAGES.review.code_changed_during_run] if changed else [])


# ── A review whose replies the response cache answered (#816) ─────────────────────────────────

_REVIEWED = "deploy.yaml"
_REVIEWED_TEXT = "".join(f"key_{line}: value_{line}\n" for line in range(40))
_PERSONA_REPLY = (
    "```json\n"
    + json.dumps(
        {
            "findings": [
                {
                    "title": "Plaintext value",
                    "severity": "HIGH",
                    "location": f"{_REVIEWED}:3",
                    "description": "value_2 is stored in plain text.",
                    "category": "security",
                }
            ]
        }
    )
    + "\n```"
)
_VERDICT = json.dumps(
    [
        {
            "finding_id": 1,
            "status": "VERIFIED",
            "verified": True,
            "citation_line": 3,
            "reason": "Line 3 holds value_2.",
        }
    ]
)


def _review_in_two_pages(client: LLMClient, target: Path) -> None:
    """Review one file in two pages with one persona, then verify its finding, stage by stage.

    No static scanner runs, and the file is no Python source, so no check starts a process.
    """
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s", llm_client=client, verification_client=client, target_dir=target
    )
    flags = ReviewStageFlags(static_scan=False)
    meta = {_REVIEWED: FileAnalysisMeta(path=_REVIEWED, key_symbols=[], dependencies=[])}
    payloads = orchestrator.init_per_file_payloads([_REVIEWED], meta, stage_flags=flags)
    diffs = {_REVIEWED: _REVIEWED_TEXT}
    with review_stage("persona_review"):
        orchestrator.execute_multi_persona_review(
            payloads, diff_text_by_file=diffs, personas=["devsecops"], stage_flags=flags
        )
    with review_stage("verification"):
        orchestrator.execute_finding_verification(
            payloads, stage_flags=flags, diff_text_by_file=diffs
        )


@pytest.mark.usefixtures("fixed_prompt_digest")
def test_a_profiled_review_counts_cached_persona_pages_and_verifier_replies_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spend_ledger: SpendLedger
) -> None:
    """Verify a reply the response cache answers, to a persona page or to the verifier, is a
    cached call of its stage and its spend stage, and no LLM call (#816).

    A first review records each request's cache key; the cache then keeps page 1's reply and
    the verifier's, so the profiled review sends only page 2 to the model.
    """
    target = tmp_path / "repo"
    target.mkdir()
    (target / _REVIEWED).write_text(_REVIEWED_TEXT, encoding="utf-8")
    # Payloads probe the working directory for manifests, which is otherwise this repository.
    monkeypatch.chdir(target)
    # Persona agents count tokens; loading the tokenizer is not under test.
    monkeypatch.setattr(context_budget, "_get_tiktoken_encoding", lambda *_args: None)
    monkeypatch.setattr(pipeline_module, "review_page_chars", lambda _window: 400)
    monkeypatch.setattr(investigator, "investigate_rag_context", lambda *_a, **_k: None)
    keys: list[str] = []

    def model(
        _self: LLMClient, system: str, messages: list[ChatMessage], **options: Any
    ) -> LLMResponse:
        keys.append(
            LLMResponseCache.generate_key(
                "ollama",
                "llama3:8b",
                system,
                messages,
                {"enable_thinking": options["enable_thinking"]},
            )
        )
        return LLMResponse(_VERDICT if system == _VALIDATION_SYSTEM else _PERSONA_REPLY)

    monkeypatch.setattr(LLMClient, "_ollama_messages", model)
    client = LLMClient(AIConfig(provider="ollama", model="llama3:8b"))
    _review_in_two_pages(client, target)
    # The first review sent page 1, page 2 and then the verifier's request.
    client.cache.clear()
    for key, reply in ((keys[0], _PERSONA_REPLY), (keys[2], _VERDICT)):
        client.cache.set(key, "ollama", "llama3:8b", "", "", reply)
    spend_ledger.reset()

    with profiling() as profiler:
        _review_in_two_pages(client, target)
        profiler.build(session_id="s", target="t").write(tmp_path)

    profile = ReviewProfile.load(tmp_path)
    with sqlite3.connect(spend_ledger.db_path) as conn:
        rows = conn.execute("SELECT stage, cached FROM ai_spend_records").fetchall()
    assert (
        len(keys),
        [(s.name, s.llm_calls, s.cached_calls) for s in profile.stages] if profile else [],
        sorted(rows),
    ) == (
        4,
        [("persona_review", 1, 1), ("verification", 0, 1)],
        [("review.file_review", 0), ("review.file_review", 1), ("review.verification", 1)],
    )
