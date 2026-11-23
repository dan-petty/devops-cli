"""Evaluation tests for research judge on labeled findings (#3909)."""

from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from devops_cli.research.judge import (
    LABELED_FINDINGS,
    JudgeVerdict,
    ReadOnlyCorpus,
    false_negative_ids,
    judge_agreement_rate,
    judge_records,
)
from tests.research.test_research_judge import FakeCorpus


class EvalCorpus(FakeCorpus):
    """Corpus pre-populated with evaluation records and URLs."""

    def __init__(self) -> None:
        super().__init__()
        for item in LABELED_FINDINGS:
            self.records[item.record.id] = item.record.text
            self.urls.add(item.record.url)


def test_labeled_evaluation_run(capsys: Any) -> None:
    record_map = {item.record.id: item for item in LABELED_FINDINGS}

    def reply(messages: list[Any], info: AgentInfo) -> ModelResponse:
        user_text = ""
        for m in messages:
            for p in getattr(m, "parts", []):
                if hasattr(p, "content"):
                    user_text += str(p.content)

        matching_rec = None
        for rec_id, item in record_map.items():
            if rec_id in user_text:
                matching_rec = item
                break
        if matching_rec is None:
            matching_rec = LABELED_FINDINGS[0]

        return ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "affects_us": matching_rec.label.value,
                        "why": "Matches labeled ground truth",
                        "severity": "high",
                        "action": "upgrade package",
                        "evidence_record_ids": [matching_rec.record.id],
                        "evidence_urls": [matching_rec.record.url],
                    },
                )
            ]
        )

    model = FunctionModel(reply)
    corpus: ReadOnlyCorpus = EvalCorpus()
    records = [item.record for item in LABELED_FINDINGS]
    report = judge_records(records, corpus, model)

    assert len(report.findings) == 20
    fn = false_negative_ids(LABELED_FINDINGS, report)
    assert fn == []
    rate = judge_agreement_rate(LABELED_FINDINGS, report)
    assert rate == 1.0
    print(f"Agreement rate: {rate}")
    captured = capsys.readouterr()
    assert "1.0" in captured.out


def test_a_false_no_fails_the_gate() -> None:
    record_map = {item.record.id: item for item in LABELED_FINDINGS}
    first_yes = next(item for item in LABELED_FINDINGS if item.label == JudgeVerdict.yes)

    def reply(messages: list[Any], info: AgentInfo) -> ModelResponse:
        user_text = ""
        for m in messages:
            for p in getattr(m, "parts", []):
                if hasattr(p, "content"):
                    user_text += str(p.content)

        matching_rec = None
        for rec_id, item in record_map.items():
            if rec_id in user_text:
                matching_rec = item
                break
        if matching_rec is None:
            matching_rec = LABELED_FINDINGS[0]

        verdict = matching_rec.label
        if matching_rec.record.id == first_yes.record.id:
            verdict = JudgeVerdict.no

        return ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "affects_us": verdict.value,
                        "why": "Evaluation response",
                        "severity": "high",
                        "action": "upgrade package",
                        "evidence_record_ids": [matching_rec.record.id],
                        "evidence_urls": [matching_rec.record.url],
                    },
                )
            ]
        )

    model = FunctionModel(reply)
    corpus = EvalCorpus()
    records = [item.record for item in LABELED_FINDINGS]
    report = judge_records(records, corpus, model)

    fn = false_negative_ids(LABELED_FINDINGS, report)
    assert fn == [first_yes.record.id]
    rate = judge_agreement_rate(LABELED_FINDINGS, report)
    assert rate == 0.95
