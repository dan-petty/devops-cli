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
from devops_cli.research.models import Component


class EvalCorpus:
    """Corpus pre-populated with evaluation records and URLs."""

    def __init__(self) -> None:
        self.records: dict[str, str] = {
            item.record.id: item.record.text for item in LABELED_FINDINGS
        }
        self.urls: set[str] = {item.record.url for item in LABELED_FINDINGS}

    def record_text(self, record_id: str) -> str | None:
        return self.records.get(record_id)

    def holds_url(self, url: str) -> bool:
        return url in self.urls

    def stored_texts(self, query: str, regex: bool = False) -> list[str]:
        return [t for t in self.records.values() if query in t]

    def components(self) -> list[Component]:
        return [item.record.component for item in LABELED_FINDINGS]

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return [{"path": "src/devops_cli/research/judge.py", "score": 0.9}]


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
