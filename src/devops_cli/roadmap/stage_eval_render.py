"""The text and the JSON of a replay, of a score and of a dry run of the golden set (#3028)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from devops_cli.dry_run import PlannedRequest
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage import CALLS_PER_ITEM_MAX
from devops_cli.roadmap.stage_eval_cases import GateName, StageCase
from devops_cli.roadmap.stage_eval_gates import DefectStatus, ReplayReport
from devops_cli.roadmap.stage_eval_score import DefectScore, StageScore, pending_reference


def _percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else MESSAGES.roadmap.stage_eval_no_value


def _count(value: int | None) -> str:
    return str(value) if value is not None else MESSAGES.roadmap.stage_eval_no_value


def render_replay(report: ReplayReport) -> str:
    """The replay as text: what each gate caught, the defects that wait for a gate, the defects no
    gate judges, the good plans, and each failure."""
    texts = MESSAGES.roadmap
    good, goods = report.good()
    lines = [texts.stage_eval_replay_title.format(cases=len(report.replays), good=goods), ""]
    lines.append(texts.stage_eval_replay_header)
    lines += [
        texts.stage_eval_replay_row.format(
            gate=total.gate.name,
            reference=total.gate.reference,
            type=total.gate.catches,
            known=total.known,
            caught=total.caught,
            missed=total.missed,
        )
        for total in report.totals()
    ]
    pending = report.count(DefectStatus.PENDING)
    lines += ["", texts.stage_eval_replay_pending]
    lines += [
        texts.stage_eval_replay_pending_row.format(
            type=kind, count=count, reference=pending_reference(kind)
        )
        for kind, count in pending.items()
    ]
    unjudged = report.count(DefectStatus.UNJUDGED)
    lines.append(
        texts.stage_eval_replay_unjudged.format(
            types=", ".join(f"{kind} {count}" for kind, count in unjudged.items())
            or texts.stage_eval_no_value
        )
    )
    lines += ["", texts.stage_eval_replay_good.format(good=good, cases=goods)]
    failures = report.failures
    lines.append(
        texts.stage_eval_replay_failed.format(count=len(failures))
        if failures
        else texts.stage_eval_replay_ok
    )
    lines += [f"- {failure}" for failure in failures]
    return "\n".join(lines) + "\n"


def _score_row(row: DefectScore) -> str:
    texts = MESSAGES.roadmap
    gate = (
        texts.stage_eval_pending_gate.format(reference=pending_reference(row.type))
        if row.gate is GateName.PENDING
        else row.gate.value
    )
    return texts.stage_eval_score_row.format(
        type=row.type,
        gate=gate,
        cases=row.cases,
        avoided=_count(row.avoided),
        caught=_count(row.caught),
        rate=_percent(row.rate),
    )


def render_score(score: StageScore, *, gateway: str) -> str:
    """The score as text: a row for each type of defect, the total, and how the cases ended."""
    texts = MESSAGES.roadmap
    lines = [
        texts.stage_eval_score_title.format(cases=score.cases, model=score.model, gateway=gateway),
        "",
        texts.stage_eval_score_header,
        *(_score_row(row) for row in score.rows),
    ]
    avoided, cases = score.scored
    lines += [
        "",
        texts.stage_eval_score_total.format(
            avoided=avoided, cases=cases, rate=_percent(score.total)
        ),
        texts.stage_eval_score_ended.format(
            ended=", ".join(f"{outcome} {count}" for outcome, count in score.ended.items())
        ),
    ]
    return "\n".join(lines) + "\n"


def score_json(score: StageScore, *, gateway: str, taken: str) -> str:
    """The score as JSON, for the file under `.data/` and for `--json`."""
    data: dict[str, Any] = {
        "model": score.model,
        "gateway": gateway,
        "taken": taken,
        "cases": score.cases,
        "avoided": score.scored[0],
        "scored_cases": score.scored[1],
        "total": score.total,
        "ended": {str(outcome): count for outcome, count in score.ended.items()},
        "rows": [asdict(row) | {"rate": row.rate} for row in score.rows],
    }
    return json.dumps(data, indent=2, default=str) + "\n"


def replay_json(report: ReplayReport) -> str:
    """The replay as JSON: the totals of each gate, and the failures."""
    good, goods = report.good()
    data: dict[str, Any] = {
        "cases": len(report.replays),
        "gates": [
            {
                "gate": str(total.gate.name),
                "reference": total.gate.reference,
                "type": str(total.gate.catches),
                "known": total.known,
                "caught": total.caught,
                "missed": total.missed,
            }
            for total in report.totals()
        ],
        "pending": {str(kind): count for kind, count in report.count(DefectStatus.PENDING).items()},
        "unjudged": {
            str(kind): count for kind, count in report.count(DefectStatus.UNJUDGED).items()
        },
        "good": {"passed": good, "cases": goods},
        "failures": report.failures,
    }
    return json.dumps(data, indent=2) + "\n"


def planned_calls(cases: Sequence[StageCase], gateway: str) -> list[PlannedRequest]:
    """The model calls of a run, making none: the planner call of each case, with the calls it
    may add."""
    texts = MESSAGES.roadmap
    return [
        PlannedRequest(
            method="POST",
            target=f"{gateway}/chat/completions",
            stdin=texts.stage_eval_dry_run_case.format(name=case.name),
            repeat=texts.stage_eval_dry_run_repeat.format(count=CALLS_PER_ITEM_MAX),
        )
        for case in cases
    ]
