"""Tests for Socratic inquiry and knowledge gap formulator (devops ai research socratic)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from devops_cli.ai.research.models import (
    ClarifyingQuestion,
    CodeLookupInstruction,
    KnowledgeGap,
    KnowledgeGapType,
    SocraticInquiryResult,
)
from devops_cli.ai.research.socratic import SocraticFormulator, render_socratic_markdown
from devops_cli.config.defaults import DEFAULT_AI_SOCRATIC_MAX_PROBES
from tests.support.fakes.model import ModelFake

CONST_SOCRATIC_GAP_TYPES: tuple[str, ...] = ("GAP", "AMBIGUITY", "UNDERSPECIFIED_CONTRACT")
CONST_SOCRATIC_LOOKUP_TYPES: tuple[str, ...] = ("file", "symbol", "search")


def _canned_result() -> SocraticInquiryResult:
    """The inquiry result that the model returns in the happy-path tests."""
    return SocraticInquiryResult(
        task="Add caching to review pipeline",
        summary="Identified cache storage and key hashing ambiguities.",
        gaps=[
            KnowledgeGap(
                type="GAP",
                description="Missing cache backend specification",
                rationale="Unclear if Valkey or disk cache is expected",
            ),
            KnowledgeGap(
                type="AMBIGUITY",
                description="Cache invalidation semantics unspecified",
                rationale="TTL vs event-driven eviction not specified",
            ),
        ],
        questions=[
            ClarifyingQuestion(
                question="Should caching use Valkey L2 or disk JSONL?",
                target_gap="Missing cache backend specification",
                rationale="Determines external service dependency vs local storage",
            ),
        ],
        lookups=[
            CodeLookupInstruction(
                target="src/devops_cli/ai/response_cache.py",
                lookup_type="file",
                rationale="Inspect existing caching implementation patterns",
                target_gap="Missing cache backend specification",
            ),
        ],
    )


def test_socratic_constants_and_types() -> None:
    expected_gaps = ("GAP", "AMBIGUITY", "UNDERSPECIFIED_CONTRACT")
    expected_lookups = ("file", "symbol", "search")
    gap_values = tuple(t.value for t in KnowledgeGapType)
    assert (CONST_SOCRATIC_GAP_TYPES, CONST_SOCRATIC_LOOKUP_TYPES) == (
        expected_gaps,
        expected_lookups,
    )
    assert (gap_values, DEFAULT_AI_SOCRATIC_MAX_PROBES) == (expected_gaps, 5)


def test_knowledge_gap_model_validation() -> None:
    gap = KnowledgeGap(
        type="UNDERSPECIFIED_CONTRACT",
        description="Missing schema definition",
        rationale="Payload structure is undefined",
    )
    assert (gap.type, gap.description, gap.rationale) == (
        "UNDERSPECIFIED_CONTRACT",
        "Missing schema definition",
        "Payload structure is undefined",
    )

    with pytest.raises(ValidationError) as raised:
        KnowledgeGap.model_validate(
            {
                "type": "UNKNOWN_TYPE",
                "description": "desc",
                "rationale": "rat",
            }
        )
    assert len(raised.value.errors()) > 0


def test_clarifying_question_model_validation() -> None:
    question = ClarifyingQuestion(
        question="What is the expected timeout?",
        target_gap="Missing timeout contract",
        rationale="Prevents unbounded blocking calls",
    )
    assert (question.question, question.target_gap, question.rationale) == (
        "What is the expected timeout?",
        "Missing timeout contract",
        "Prevents unbounded blocking calls",
    )


def test_code_lookup_instruction_model_validation() -> None:
    lookup = CodeLookupInstruction(
        target="src/devops_cli/config/settings.py",
        lookup_type="file",
        rationale="Check existing timeout defaults",
        target_gap="Missing timeout contract",
    )
    assert (lookup.target, lookup.lookup_type, lookup.target_gap, lookup.rationale) == (
        "src/devops_cli/config/settings.py",
        "file",
        "Missing timeout contract",
        "Check existing timeout defaults",
    )

    with pytest.raises(ValidationError) as raised:
        CodeLookupInstruction.model_validate(
            {
                "target": "target",
                "lookup_type": "invalid_lookup_type",
                "rationale": "rat",
                "target_gap": "gap",
            }
        )
    assert len(raised.value.errors()) > 0


def test_socratic_inquiry_result_serialization() -> None:
    result = SocraticInquiryResult(
        task="Test task",
        summary="A brief summary",
        gaps=[
            KnowledgeGap(
                type="GAP",
                description="Test gap",
                rationale="Test rationale",
            )
        ],
        questions=[
            ClarifyingQuestion(
                question="Test question?",
                target_gap="Test gap",
                rationale="Test rationale",
            )
        ],
        lookups=[
            CodeLookupInstruction(
                target="test.py",
                lookup_type="file",
                rationale="Test lookup",
                target_gap="Test gap",
            )
        ],
    )
    data = result.model_dump()
    reconstituted = SocraticInquiryResult.model_validate(data)
    assert (len(reconstituted.gaps), len(reconstituted.questions), len(reconstituted.lookups)) == (
        1,
        1,
        1,
    )
    assert (reconstituted.task, reconstituted.summary) == ("Test task", "A brief summary")


def test_the_prompt_holds_the_task_the_context_the_root_and_the_probe_limit(
    tmp_path: Path, model_fake: ModelFake
) -> None:
    model_fake.answer(_canned_result())

    SocraticFormulator(max_probes=3).formulate(
        task="Optimize SQL queries", context="PostgreSQL 16", repo_root=tmp_path
    )

    prompt = model_fake.calls[0].prompt
    assert "Task Description:\nOptimize SQL queries" in prompt
    assert "Context / Instructions:\nPostgreSQL 16" in prompt
    assert f"Repository Root:\n{tmp_path}" in prompt
    assert "at most 3" in prompt


def test_the_result_is_cut_to_the_probe_limit(model_fake: ModelFake) -> None:
    questions = [
        ClarifyingQuestion(question=f"Q{i}?", target_gap="G", rationale="R") for i in range(10)
    ]
    lookups = [
        CodeLookupInstruction(target=f"T{i}", lookup_type="file", rationale="R", target_gap="G")
        for i in range(8)
    ]
    model_fake.answer(
        SocraticInquiryResult(
            task="",
            summary="Summary",
            gaps=[KnowledgeGap(type="GAP", description="G", rationale="R")],
            questions=questions,
            lookups=lookups,
        )
    )

    bounded = SocraticFormulator(max_probes=4).formulate("Original Task")

    assert (len(bounded.questions), len(bounded.lookups), bounded.task) == (
        4,
        4,
        "Original Task",
    )


def test_socratic_formulator_empty_task_raises() -> None:
    formulator = SocraticFormulator()
    with pytest.raises(ValueError, match="Task description must not be empty"):
        formulator.formulate("   ")


def test_socratic_formulator_happy_path(model_fake: ModelFake) -> None:
    model_fake.answer(_canned_result())
    formulator = SocraticFormulator(client=model_fake, max_probes=3)
    res = formulator.formulate(task="Refactor pipeline orchestrator", context="Phase 1")

    assert (res.task, len(res.gaps), len(res.questions), len(res.lookups)) == (
        "Refactor pipeline orchestrator",
        2,
        1,
        1,
    )
    assert model_fake.call_count == 1
    assert "Task Description:\nRefactor pipeline orchestrator" in model_fake.calls[0].prompt


def test_socratic_formulator_resolves_default_client(model_fake: ModelFake) -> None:
    model_fake.answer(_canned_result())

    res = SocraticFormulator(client=None).formulate("Inspect network egress")

    assert (model_fake.call_count, res.task) == (1, "Inspect network egress")


def test_render_socratic_markdown() -> None:
    result = SocraticInquiryResult(
        task="Implement Valkey store",
        summary="Need storage contract details.",
        gaps=[
            KnowledgeGap(
                type="GAP",
                description="Cluster | standalone mode?",
                rationale="Impacts connection pool",
            )
        ],
        questions=[
            ClarifyingQuestion(
                question="Is Valkey clustered?",
                target_gap="Cluster mode",
                rationale="Determines client topology",
            )
        ],
        lookups=[
            CodeLookupInstruction(
                target="src/valkey.py",
                lookup_type="file",
                rationale="Check driver",
                target_gap="Cluster mode",
            )
        ],
    )
    md = render_socratic_markdown(result)
    assert "# Socratic Inquiry & Knowledge Gap Analysis" in md
    assert "**Task**: Implement Valkey store" in md
    assert "Cluster \\| standalone mode?" in md
    assert "Is Valkey clustered?" in md
    assert "`src/valkey.py` (file)" in md


def test_render_socratic_markdown_empty_lists() -> None:
    result = SocraticInquiryResult(task="Clean task", summary="")
    md = render_socratic_markdown(result)
    assert "*No knowledge gaps identified.*" in md
    assert "*No clarifying questions required.*" in md
    assert "*No code lookup instructions required.*" in md


def test_cli_socratic_requires_task(cli: Any) -> None:
    result = cli(["ai", "research", "socratic"])
    assert result.exit_code != 0
    assert "A task description must be provided" in result.output


def test_cli_socratic_dry_run(cli: Any) -> None:
    result = cli(
        ["ai", "research", "socratic", "Add rate limiter", "--dry-run"],
    )
    assert (
        result.exit_code,
        "Plan for AI research socratic inquiry" in result.output,
        "Add rate limiter" in result.output,
    ) == (0, True, True)


def test_cli_socratic_happy_path_text(cli: Any, model_fake: ModelFake) -> None:
    model_fake.answer(_canned_result())

    result = cli(["ai", "research", "socratic", "Add caching"])
    assert result.exit_code == 0
    assert "Socratic Metacognitive Analysis" in result.output
    assert "Identified Knowledge Gaps" in result.output


def test_cli_socratic_option_task_and_format_json(cli: Any, model_fake: ModelFake) -> None:
    model_fake.answer(_canned_result())

    result = cli(
        ["ai", "research", "socratic", "--task", "Add caching", "--format", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert (payload["task"], len(payload["gaps"])) == ("Add caching", 2)
    assert payload["questions"][0]["question"] == "Should caching use Valkey L2 or disk JSONL?"


def test_cli_socratic_format_yaml(cli: Any, model_fake: ModelFake) -> None:
    model_fake.answer(_canned_result())

    result = cli(
        ["ai", "research", "socratic", "Add caching", "--format", "yaml"],
    )
    assert result.exit_code == 0
    payload = yaml.safe_load(result.output)
    assert (payload["task"], len(payload["lookups"])) == ("Add caching", 1)


def test_cli_socratic_format_markdown(cli: Any, model_fake: ModelFake) -> None:
    model_fake.answer(_canned_result())

    result = cli(
        ["ai", "research", "socratic", "Add caching", "--format", "markdown"],
    )
    assert result.exit_code == 0
    assert "# Socratic Inquiry & Knowledge Gap Analysis" in result.output
    assert "Targeted Clarifying Questions" in result.output


def test_cli_socratic_failure_handles_gracefully(cli: Any, model_fake: ModelFake) -> None:
    model_fake.answer(RuntimeError("Inference timeout"))

    result = cli(["ai", "research", "socratic", "Failing task"])
    assert result.exit_code == 1
    assert "Socratic inquiry failed: Inference timeout" in result.output
