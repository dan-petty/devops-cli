"""Live model evaluation for research judge (#3909)."""

from __future__ import annotations

import os
from typing import Any

import pytest

from devops_cli.ai.client.factory import get_task_model
from devops_cli.research.judge import (
    LABELED_FINDINGS,
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


@pytest.mark.skipif(
    not os.environ.get("DEVOPS_CLI_RESEARCH_JUDGE_LIVE"),
    reason="Live evaluation requires DEVOPS_CLI_RESEARCH_JUDGE_LIVE=1",
)
def test_live_judge_agreement_rate(capsys: Any) -> None:
    model = get_task_model("chat")
    corpus = EvalCorpus()
    records = [item.record for item in LABELED_FINDINGS]
    report = judge_records(records, corpus, model)

    fn = false_negative_ids(LABELED_FINDINGS, report)
    assert fn == [], f"False negatives found: {fn}"

    rate = judge_agreement_rate(LABELED_FINDINGS, report)
    print(f"Live judge agreement rate: {rate:.2f}")
    captured = capsys.readouterr()
    assert f"{rate:.2f}" in captured.out
