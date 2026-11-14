"""The table of the decision points (ADR 0020): the name and the cuts file of each registered point.

The settings check the keys and the modes of `roadmap.decisions` against this table when they load.
The table imports no point module, so a config that sets the key makes a command import no
pydantic_ai (#4501). `REGISTRY` of `decision_registry` holds the points themselves, and a test keeps
the names and the cuts files of the two equal.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from collections.abc import Mapping

_ROADMAP_DIR: Final[Path] = Path(__file__).parent
_SHOWN_FROM: Final[Path] = Path(__file__).resolve().parents[2]
# The modes that need a fitted cuts file: only `off` runs a point with no cuts file (#5272).
_FITTED_MODES: Final[frozenset[str]] = frozenset({"shadow", "on"})

POINT_CUTS: Final[Mapping[str, Path]] = MappingProxyType(
    {"stage.verify_screen": _ROADMAP_DIR / "stage" / "jev_screen_cuts.json"}
)


def _shown(path: Path) -> str:
    """`path` from the `src` folder of the checkout, or whole when it is not under it."""
    return str(path.relative_to(_SHOWN_FROM)) if path.is_relative_to(_SHOWN_FROM) else str(path)


def check_modes(modes: Mapping[str, str], cuts: Mapping[str, Path] = POINT_CUTS) -> None:
    """Refuse a key of `modes` that names no point of `cuts`, and the fitted modes `shadow` and `on`
    for a point whose cuts file is not in the repository: only `off` runs a point with no cuts file.
    The error names the key or the point and the file."""
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


__all__ = ["POINT_CUTS", "check_modes"]
