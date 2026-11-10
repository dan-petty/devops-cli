"""The fit of the cuts of a decision step on labelled data (ADR 0019).

A `FitCase` holds the probability that Jev gave for each question and two labels: `must_run`,
whether the costly path must run for the case, and `weight`, how many defects a skip of the case
loses. `fit_cuts` sets one `continue_below` cut for each question so that the cuts skip as many
cases as they can, and lose no case with `must_run` on the fitted cases. `evaluate_cuts` counts
the skips and the loss of fixed cuts on other cases, so a report can give the half that the fit
did not see. `halves` makes the fixed split of the cases.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from devops_cli.roadmap.decision_step import Cut

# A flag cut needs at least this many cases above it, and no case below that needs no run.
_FLAG_SUPPORT = 3


@dataclass(frozen=True)
class FitCase:
    """One labelled case: the probability for each question, whether the costly path must run,
    and how many defects a skip loses."""

    name: str
    probabilities: Mapping[str, float]
    must_run: bool
    weight: int = 1


@dataclass(frozen=True)
class CutScore:
    """What fixed cuts do on cases: the cases, the skipped ones, the skipped ones that must run
    (`lost`, with their `lost_weight`) and the skipped ones that need no run."""

    cases: int
    skipped: int
    lost: int
    lost_weight: int

    @property
    def skip_rate(self) -> float:
        """The share of the cases that the cuts skip."""
        return self.skipped / self.cases if self.cases else 0.0


def _caught(case: FitCase, floor: Mapping[str, float]) -> bool:
    """Whether some question of `case` reaches its cut, so the costly path runs."""
    return any(case.probabilities[name] >= cut for name, cut in floor.items())


def _lowered(
    cases: Sequence[FitCase], floor: Mapping[str, float], values: Mapping[str, list[float]]
) -> dict[str, float] | None:
    """The cuts after the best single lowering: the one that catches the most cases that must run
    and are not caught yet, for the fewest cases that need no run. None when no lowering catches
    one more case that must run."""
    open_ = [case for case in cases if case.must_run and not _caught(case, floor)]
    best: tuple[float, dict[str, float]] | None = None
    for name, options in values.items():
        for value in (v for v in options if v < floor[name]):
            trial = {**floor, name: value}
            gained = sum(_caught(case, trial) for case in open_)
            wasted = sum(
                _caught(case, trial) and not _caught(case, floor)
                for case in cases
                if not case.must_run
            )
            if gained and (best is None or gained / (wasted + 0.5) > best[0]):
                best = (gained / (wasted + 0.5), trial)
    return None if best is None else best[1]


def _flag_cut(cases: Sequence[FitCase], name: str) -> float:
    """The lowest probability from which every case must run and at least `_FLAG_SUPPORT` cases
    reach it; 1.0 when no probability does."""
    for value in sorted({case.probabilities[name] for case in cases}):
        above = [case for case in cases if case.probabilities[name] >= value]
        if len(above) >= _FLAG_SUPPORT and all(case.must_run for case in above):
            return value
    return 1.0


def fit_cuts(cases: Sequence[FitCase]) -> dict[str, Cut]:
    """One cut for each question. The climb starts with no case caught and lowers one cut at a
    time, the one that catches the most cases that must run for the fewest cases that need no run,
    until every case that must run is caught. A cut sits half way between the value that it
    catches and the next lower value, so it keeps a margin on the fitted values."""
    names = sorted(cases[0].probabilities) if cases else []
    values = {name: sorted({case.probabilities[name] for case in cases}) for name in names}
    floor = dict.fromkeys(names, float("inf"))
    while (lowered := _lowered(cases, floor, values)) is not None:
        floor = lowered
    cuts: dict[str, Cut] = {}
    for name in names:
        if floor[name] == float("inf"):
            cuts[name] = Cut(continue_below=1.0, flag_at=1.0)
            continue
        below = [value for value in values[name] if value < floor[name]]
        edge = floor[name] if not below else (below[-1] + floor[name]) / 2
        cuts[name] = Cut(
            continue_below=round(edge, 4), flag_at=round(max(_flag_cut(cases, name), edge), 4)
        )
    return cuts


def fit_shared_cut(cases: Sequence[FitCase]) -> dict[str, Cut]:
    """One cut for all questions: a case is skipped when its highest probability is under the cut.
    The cut sits half way between the lowest highest-probability of a case that must run and the
    next lower one, or at nine tenths of it when no case is lower. One number leaves little room to
    fit the noise of a small set, and the report of the other half shows whether it holds."""
    names = sorted(cases[0].probabilities) if cases else []

    def top(case: FitCase) -> float:
        return max(case.probabilities.values())

    must = [top(case) for case in cases if case.must_run]
    if not must:
        return {name: Cut(continue_below=1.0, flag_at=1.0) for name in names}
    lowest = min(must)
    below = [top(case) for case in cases if top(case) < lowest]
    edge = round((max(below) + lowest) / 2 if below else lowest * 0.9, 4)
    return {
        name: Cut(continue_below=edge, flag_at=round(max(_flag_cut(cases, name), edge), 4))
        for name in names
    }


def evaluate_cuts(cases: Sequence[FitCase], cuts: Mapping[str, Cut]) -> CutScore:
    """The skips and the loss of `cuts` on `cases`."""
    floor = {name: cut.continue_below for name, cut in cuts.items()}
    skipped = [case for case in cases if not _caught(case, floor)]
    lost = [case for case in skipped if case.must_run]
    return CutScore(len(cases), len(skipped), len(lost), sum(case.weight for case in lost))


def halves(
    names: Sequence[str], strata: Mapping[str, str], *, seed: int
) -> tuple[list[str], list[str]]:
    """Two halves of `names`, the same for the same names and seed: each stratum is sorted,
    ordered by a hash of the seed and the name and dealt out by turns, so each half holds about half
    of each stratum."""
    first: list[str] = []
    second: list[str] = []
    for stratum in sorted(set(strata[name] for name in names)):
        members = sorted(
            (name for name in names if strata[name] == stratum),
            key=lambda name: hashlib.sha256(f"{seed}:{name}".encode()).hexdigest(),
        )
        for index, name in enumerate(members):
            (first if index % 2 == 0 else second).append(name)
    return sorted(first), sorted(second)


__all__ = ["CutScore", "FitCase", "evaluate_cuts", "fit_cuts", "fit_shared_cut", "halves"]
