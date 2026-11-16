"""The decision point `alternatives.reply_fixable` for refused alternatives replies (ADR 0020, #4864).

The point resolves whether a refused reply is fixable with one return to the model:
- *review*: the refusal reason is a fixable form or schema error, and the reason code does not
  match an earlier refusal recorded on the item. The job sends the reason back once when `on`.
- *continue*: the refusal is not fixable or the reason code repeated. The job makes no second
  model call and keeps the 3-day retry wait.
- *flag*: unused by the rule.

The rule reads its fixable codes table from the cuts file `alternatives_cuts.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from devops_cli.roadmap.decision_point import DecisionPoint
from devops_cli.roadmap.decision_step import Band

if TYPE_CHECKING:
    from collections.abc import Mapping

CUTS_FILE: Final[Path] = Path(__file__).with_name("alternatives_cuts.json")


def load_fixable_codes(path: Path = CUTS_FILE) -> frozenset[str]:
    """The set of fixable reason codes, loaded from `path`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    report = data.get("report") or {}
    codes = report.get("fixable_codes") or ()
    return frozenset(codes)


def reply_fixable_rule(state: Mapping[str, Any]) -> Band | None:
    """Judge whether the refusal in `state` is fixable.

    Returns `Band.REVIEW` when the code is in the fixable codes table and differs from
    `earlier_code`. Returns `Band.CONTINUE` otherwise.
    """
    code = state.get("code")
    earlier = state.get("earlier_code")
    if not code:
        return Band.CONTINUE
    codes = load_fixable_codes(CUTS_FILE)
    if code in codes and code != earlier:
        return Band.REVIEW
    return Band.CONTINUE


REPLY_FIXABLE: Final[DecisionPoint[Mapping[str, Any]]] = DecisionPoint(
    name="alternatives.reply_fixable",
    questions={},
    evidence=lambda given: dict(given),
    bands={
        Band.CONTINUE: "Keep the 3-day wait with no second model call.",
        Band.REVIEW: "Send the refused reply back once with its reason.",
        Band.FLAG: "Flagged refusal.",
    },
    cuts=CUTS_FILE,
    rule=reply_fixable_rule,
    asks_model=False,
    counts_only=True,
)

__all__ = ["CUTS_FILE", "REPLY_FIXABLE", "load_fixable_codes", "reply_fixable_rule"]
