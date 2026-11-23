"""Tests for research judge agent and tools (#3909)."""

from __future__ import annotations

from typing import Any

from pydantic_ai.models.test import TestModel

from devops_cli.ai.toolsets import extract_tools_from_toolset
from devops_cli.research.judge import (
    JUDGE_INSTRUCTIONS,
    CitationCheck,
    JudgeFinding,
    JudgeVerdict,
    ReadOnlyCorpus,
    build_judge_agent,
    build_judge_toolset,
    check_judged_citations,
    file_judged_findings,
    judge_intake_candidate,
)
from devops_cli.research.models import Component, ComponentKind, Ecosystem
from devops_cli.roadmap.intake.intake import NewCandidate


class FakeCorpus:
    """In-memory test implementation of ReadOnlyCorpus."""

    def __init__(self) -> None:
        self.records: dict[str, str] = {"rec-1": "Advisory for package A"}
        self.urls: set[str] = {"https://example.com/advisory-1"}
        self.comp_list: list[Component] = [
            Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="aiofile",
                version="3.12.3",
                file="pyproject.toml",
                line=10,
            )
        ]

    def record_text(self, record_id: str) -> str | None:
        return self.records.get(record_id)

    def holds_url(self, url: str) -> bool:
        return url in self.urls

    def stored_texts(self, query: str, regex: bool = False) -> list[str]:
        return [t for t in self.records.values() if query in t]

    def components(self) -> list[Component]:
        return list(self.comp_list)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return [{"path": "src/devops_cli/ai/main.py", "score": 0.95}]


def test_tool_inventory() -> None:
    corpus: ReadOnlyCorpus = FakeCorpus()
    toolset = build_judge_toolset(corpus)
    tools = extract_tools_from_toolset(toolset)
    assert len(tools) == 4
    tool_names = {t.name for t in tools}
    expected_names = {"store_lookup", "repository_search", "component_list", "match_stored_text"}
    assert tool_names == expected_names


def test_no_write_tool() -> None:
    corpus = FakeCorpus()
    toolset = build_judge_toolset(corpus)
    tools = extract_tools_from_toolset(toolset)
    for tool in tools:
        assert not any(
            verb in tool.name.lower()
            for verb in (
                "write",
                "create",
                "delete",
                "post",
                "update",
                "shell",
                "cluster",
                "issue",
                "comment",
            )
        )
        desc = (tool.description or "").lower()
        assert not any(
            verb in desc
            for verb in ("create issue", "post comment", "run shell", "write to cluster")
        )


def test_judge_instructions_name_the_verdicts() -> None:
    assert "yes" in JUDGE_INSTRUCTIONS
    assert "no" in JUDGE_INSTRUCTIONS
    assert "unknown" in JUDGE_INSTRUCTIONS
    assert "record id" in JUDGE_INSTRUCTIONS.lower() or "record_id" in JUDGE_INSTRUCTIONS.lower()
    assert "url" in JUDGE_INSTRUCTIONS.lower()

    corpus = FakeCorpus()
    agent = build_judge_agent(TestModel(), corpus)
    raw_instructions = getattr(agent, "_instructions", [])
    instruction_texts = [getattr(inst, "instruction", str(inst)) for inst in raw_instructions]
    combined = " ".join(instruction_texts)
    assert JUDGE_INSTRUCTIONS in combined


def test_typed_finding_from_the_test_model() -> None:
    corpus = FakeCorpus()
    agent = build_judge_agent(TestModel(), corpus)
    result = agent.run_sync("Evaluate record rec-1")
    finding = result.output
    assert isinstance(finding, JudgeFinding)
    assert finding.affects_us in (JudgeVerdict.yes, JudgeVerdict.no, JudgeVerdict.unknown)
    assert isinstance(finding.why, str)
    assert isinstance(finding.severity, str)
    assert isinstance(finding.action, str)
    assert isinstance(finding.evidence_record_ids, list)
    assert isinstance(finding.evidence_urls, list)


def test_citation_check_files_a_kept_finding() -> None:
    corpus = FakeCorpus()
    finding = JudgeFinding(
        affects_us=JudgeVerdict.yes,
        why="Vulnerability in used component",
        severity="high",
        action="upgrade to 3.12.4",
        evidence_record_ids=["rec-1"],
        evidence_urls=["https://example.com/advisory-1"],
    )
    filed: list[NewCandidate] = []
    direct_check = check_judged_citations([finding], corpus)
    assert isinstance(direct_check, CitationCheck)
    assert len(direct_check.kept) == 1
    candidate_direct = judge_intake_candidate(finding, None)
    assert isinstance(candidate_direct, NewCandidate)
    check = file_judged_findings([finding], corpus, filed.append)
    assert len(check.kept) == 1
    assert len(check.dropped) == 0
    assert len(filed) == 1
    candidate = filed[0]
    assert "fix(deps):" in candidate.title
    assert "upgrade to 3.12.4" in candidate.body or "Vulnerability" in candidate.body


def test_record_id_absent_from_the_store() -> None:
    corpus = FakeCorpus()
    finding = JudgeFinding(
        affects_us=JudgeVerdict.yes,
        why="Vulnerability in used component",
        severity="high",
        action="upgrade",
        evidence_record_ids=["absent-rec-999"],
        evidence_urls=["https://example.com/advisory-1"],
    )
    filed: list[NewCandidate] = []
    check = file_judged_findings([finding], corpus, filed.append)
    assert len(check.kept) == 0
    assert len(check.dropped) == 1
    assert len(filed) == 0
    assert len(check.reasons) == 1
    assert "absent-rec-999" in check.reasons[0]


def test_url_absent_from_the_store() -> None:
    corpus = FakeCorpus()
    finding = JudgeFinding(
        affects_us=JudgeVerdict.yes,
        why="Vulnerability in used component",
        severity="high",
        action="upgrade",
        evidence_record_ids=["rec-1"],
        evidence_urls=["https://unknown-domain.org/advisory"],
    )
    filed: list[NewCandidate] = []
    check = file_judged_findings([finding], corpus, filed.append)
    assert len(check.kept) == 0
    assert len(check.dropped) == 1
    assert len(filed) == 0
    assert len(check.reasons) == 1
    assert "https://unknown-domain.org/advisory" in check.reasons[0]
