"""The text and the JSON of a replay, of a score and of a dry run of the golden set (#3028)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from devops_cli.config.constants import CONST_ROADMAP_STAGE_MAX_REQUESTS
from devops_cli.dry_run import PlannedRequest
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage import CALLS_PER_ITEM_MAX
from devops_cli.roadmap.stage_eval_cases import GateName, StageCase
from devops_cli.roadmap.stage_eval_gates import DefectStatus, ReplayReport
from devops_cli.roadmap.stage_eval_score import DefectScore, StageScore, pending_reference
from devops_cli.roadmap.stage_eval_usage import RunUsage


def _percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else MESSAGES.roadmap.stage_eval_no_value


def _count(value: int | None) -> str:
    return str(value) if value is not None else MESSAGES.roadmap.stage_eval_no_value


def render_replay(report: ReplayReport) -> str:
    """The replay as text: what each gate caught, the counts of each type of defect, the share of
    the defects that a gate judges, the defects that wait for a gate, the good plans, and each
    failure."""
    texts = MESSAGES.roadmap
    good, goods = report.good()
    lines = [texts.stage_eval_replay_title.format(cases=len(report.replays), good=goods), ""]
    lines.append(texts.stage_eval_replay_header)
    lines += [
        texts.stage_eval_replay_row.format(
            gate=total.gate.name,
            reference=total.gate.reference,
            known=total.known,
            caught=total.caught,
            missed=total.missed,
        )
        for total in report.totals()
    ]
    judged, known = report.judged()
    lines += ["", texts.stage_eval_replay_types_header]
    lines += [
        texts.stage_eval_replay_types_row.format(
            type=total.type,
            caught=total.caught,
            missed=total.missed,
            pending=total.pending,
            unjudged=total.unjudged,
            total=total.total,
        )
        for total in report.by_type()
    ]
    lines.append(
        texts.stage_eval_replay_share.format(
            judged=judged, total=known, percent=_percent(judged / known if known else None)
        )
    )
    pending = report.count(DefectStatus.PENDING)
    if pending:
        lines += ["", texts.stage_eval_replay_pending]
        lines += [
            texts.stage_eval_replay_pending_row.format(
                type=kind, count=count, reference=pending_reference(kind)
            )
            for kind, count in pending.items()
        ]
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


def render_score(score: StageScore, *, gateway: str, usage: RunUsage | None = None) -> str:
    """The score as text: a row for each type of defect, the total, how the cases ended, and with
    `usage`, the tokens and the spend of the run."""
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
    if usage is not None:
        spend = usage.spend_usd(score.model)
        lines += [
            texts.stage_eval_usage_tokens.format(
                input=usage.input_tokens, output=usage.output_tokens
            ),
            texts.stage_eval_usage_spend.format(spend=spend)
            if spend is not None
            else texts.stage_eval_usage_unpriced,
        ]
    return "\n".join(lines) + "\n"


def score_json(
    score: StageScore, *, gateway: str, taken: str, usage: RunUsage | None = None
) -> str:
    """The score as JSON, for the file under `.data/` and for `--json`. With `usage` it holds the
    tokens and the spend in USD of the run; `spend_usd` is null when the model
    has no price."""
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
    if usage is not None:
        data["usage"] = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "spend_usd": usage.spend_usd(score.model),
        }
    return json.dumps(data, indent=2, default=str) + "\n"


def replay_json(report: ReplayReport) -> str:
    """The replay as JSON: the totals of each gate and of each type, the share of the defects that
    a gate judges, and the failures."""
    good, goods = report.good()
    judged, known = report.judged()
    data: dict[str, Any] = {
        "cases": len(report.replays),
        "defects": {"judged": judged, "known": known},
        "types": [
            {
                "type": str(total.type),
                "caught": total.caught,
                "missed": total.missed,
                "pending": total.pending,
                "unjudged": total.unjudged,
            }
            for total in report.by_type()
        ],
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


def planned_calls(
    cases: Sequence[StageCase], gateway: str, *, toolbox: bool = True
) -> list[PlannedRequest]:
    """The model calls of a run, making none: the planner call of each case, with the calls it
    may add. With the toolbox, each of the two plan runs of a case can make
    `CONST_ROADMAP_STAGE_MAX_REQUESTS` requests, and the split makes one."""
    texts = MESSAGES.roadmap
    count = (
        (CALLS_PER_ITEM_MAX - 1) * CONST_ROADMAP_STAGE_MAX_REQUESTS + 1
        if toolbox
        else CALLS_PER_ITEM_MAX
    )
    return [
        PlannedRequest(
            method="POST",
            target=f"{gateway}/chat/completions",
            stdin=texts.stage_eval_dry_run_case.format(name=case.name),
            repeat=texts.stage_eval_dry_run_repeat.format(count=count),
        )
        for case in cases
    ]
