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
from tests.research.test_research_judge_eval import EvalCorpus


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
