"""The table of the decision points (ADR 0020): the name and the cuts file of each registered point.

The settings check the keys and the modes of `roadmap.decisions` against this table when they load.
The table imports no point module, so a config that sets the key makes a command import no
pydantic_ai (#4501). `REGISTRY` of `decision_registry` holds the points themselves, and a test keeps
the names and the cuts files of the two equal.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_DECISION_POINT_FIT_MIN_CASES,
    CONST_ROADMAP_DECISION_POINT_FIT_MIN_PER_LABEL,
)
from devops_cli.lang import MESSAGES

_ROADMAP_DIR: Final[Path] = Path(__file__).parent
_SHOWN_FROM: Final[Path] = Path(__file__).resolve().parents[2]
# The modes that need a fitted cuts file: `off` and `rule` run a point with no cuts file (#4847, #5272).
_FITTED_MODES: Final[frozenset[str]] = frozenset({"shadow", "on"})
FIT_BAR_POINTS: Final[frozenset[str]] = frozenset(
    {"brain.reference_relevance", "implement.extension"}
)

POINT_CUTS: Final[Mapping[str, Path]] = MappingProxyType(
    {
        "alternatives.reply_fixable": _ROADMAP_DIR / "alternatives_cuts.json",
        "brain.reference_relevance": (
            _ROADMAP_DIR / "references" / "reference_relevance_cuts.json"
        ),
        "implement.extension": _ROADMAP_DIR / "implement" / "implement_extension_cuts.json",
        "stage.verify_screen": _ROADMAP_DIR / "stage" / "jev_screen_cuts.json",
    }
)


def _shown(path: Path) -> str:
    """`path` from the `src` folder of the checkout, or whole when it is not under it."""
    return str(path.relative_to(_SHOWN_FROM)) if path.is_relative_to(_SHOWN_FROM) else str(path)


def _halves_passed(report: Mapping[str, Any]) -> bool:
    """Return whether halves evaluation metadata in `report` passes (#4847)."""
    if isinstance(report.get("halves_passed"), bool):
        return bool(report["halves_passed"])
    for key in ("other_half", "halves"):
        section = report.get(key)
        if not isinstance(section, Mapping) or not section:
            continue
        entries = [v for v in section.values() if isinstance(v, Mapping) and "bar_met" in v]
        if entries:
            return all(bool(entry["bar_met"]) for entry in entries)
    return False


def fit_bar_problems_from_data(data: Mapping[str, Any]) -> list[str]:
    """Return fit-bar violations for decoded cuts metadata (#4847)."""
    problems: list[str] = []
    cases = data.get("cases")
    if (
        not isinstance(cases, int)
        or isinstance(cases, bool)
        or cases < CONST_ROADMAP_DECISION_POINT_FIT_MIN_CASES
    ):
        problems.append(f"cases={cases!r} (< {CONST_ROADMAP_DECISION_POINT_FIT_MIN_CASES})")
    report = data.get("report")
    if not isinstance(report, Mapping) or not report:
        problems.append("missing non-empty report")
        return problems
    label_counts = report.get("label_counts")
    if not isinstance(label_counts, Mapping) or not label_counts:
        problems.append("missing label_counts in report")
    else:
        low = {
            str(key): count
            for key, count in label_counts.items()
            if not isinstance(count, int)
            or isinstance(count, bool)
            or count < CONST_ROADMAP_DECISION_POINT_FIT_MIN_PER_LABEL
        }
        if low:
            problems.append(
                f"label counts below {CONST_ROADMAP_DECISION_POINT_FIT_MIN_PER_LABEL}: {low}"
            )
    if not _halves_passed(report):
        problems.append("halves check did not pass")
    return problems


def check_modes(modes: Mapping[str, str], cuts: Mapping[str, Path] = POINT_CUTS) -> None:
    """Refuse a key of `modes` that names no point of `cuts`, the fitted modes `shadow` and `on`
    for a point whose cuts file is absent, and `on` when fit-bar-gated cuts fail the fit bar
    (#4847, #5272). `off` and `rule` run without a cuts file."""
    unknown = sorted(set(modes) - set(cuts))
    if unknown:
        raise ValueError(
            MESSAGES.roadmap.decision_point_unknown.format(
                names=", ".join(unknown), points=", ".join(sorted(cuts))
            )
        )
    for name, mode in modes.items():
        if mode in _FITTED_MODES and not cuts[name].is_file():
            raise ValueError(
                MESSAGES.roadmap.decision_point_unfitted.format(point=name, path=_shown(cuts[name]))
            )
        if mode == "on" and name in FIT_BAR_POINTS:
            try:
                raw = json.loads(cuts[name].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    MESSAGES.roadmap.decision_point_fit_bar.format(point=name, problems=str(exc))
                ) from exc
            if not isinstance(raw, Mapping) or (problems := fit_bar_problems_from_data(raw)):
                summary = (
                    "; ".join(problems) if isinstance(raw, Mapping) else "invalid cuts JSON object"
                )
                raise ValueError(
                    MESSAGES.roadmap.decision_point_fit_bar.format(point=name, problems=summary)
                )


__all__ = ["FIT_BAR_POINTS", "POINT_CUTS", "check_modes", "fit_bar_problems_from_data"]
