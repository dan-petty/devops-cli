"""The design tokens of devops-cli, as package data (docs/DESIGN.md).

Style Dictionary builds the files `tokens-<file>.json` and `tokens-<file>.css` of this package from
the W3C DTCG sources in `design/tokens/` (`make design-tokens`). They are generated: never edit
them by hand. `css/` holds the hand-written CSS of the package, which reads only token variables.

The dash pattern of a chart line has no DTCG token type, so this module holds it, and a test
compares it with the table "Line patterns" of docs/DESIGN.md.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Final, Literal

type ThemeMode = Literal["light", "dark"]
type TokenValue = str | int | float

# The themes of the tokens. Each one holds the same names (docs/DESIGN.md, "Token pipeline").
THEME_MODES: Final[tuple[ThemeMode, ...]] = ("light", "dark")

# The dash array, in px, of series 1, 2 and 3 of a line chart: solid, `6 3` and `8 3 2 3`.
SERIES_DASHES: Final[tuple[tuple[int, ...], ...]] = ((), (6, 3), (8, 3, 2, 3))
# The dash array of a threshold, target or SLO line, which no series uses.
REFERENCE_DASH: Final[tuple[int, ...]] = (2, 2)

_BASE_FILE: Final[str] = "base"


def _flat_tokens(file: str) -> dict[str, TokenValue]:
    """The flat JSON that Style Dictionary built for one source file, by CSS variable name."""
    text = files(__name__).joinpath(f"tokens-{file}.json").read_text(encoding="utf-8")
    values: dict[str, TokenValue] = json.loads(text)
    return values


def tokens(mode: ThemeMode) -> dict[str, TokenValue]:
    """The tokens of one theme: the base tokens and the colors of `mode`, by the CSS variable
    name without `--`, such as `color-bg` or `breakpoint-md`."""
    return {**_flat_tokens(_BASE_FILE), **_flat_tokens(mode)}
