"""The chart palettes of the tokens pass the gates of docs/DESIGN.md ("Chart palettes") in both
themes: the categorical colors stay apart under simulated color vision deficiency and keep away
from status, "Other" and the Google logo colors; the sequential ramp runs in one lightness
direction; the diverging ramp means the same in both themes.

Color vision deficiency is simulated with the method of Machado 2009 at severity 1.0, and
distances are CIEDE2000 and OKLab (x 100), all computed by coloraide.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from itertools import combinations
from typing import Final

import pytest
from coloraide import Color

from devops_cli.design import THEME_MODES, ThemeMode, TokenValue, tokens

_VISIONS: Final[tuple[str | None, ...]] = (None, "protan", "deutan", "tritan")
_DEFICIENT: Final[tuple[str, ...]] = ("protan", "deutan", "tritan")
# The four colors of the Google logo, which the palette keeps away from.
_GOOGLE_LOGO: Final[tuple[str, ...]] = ("#4285f4", "#ea4335", "#fbbc05", "#34a853")
_STATUSES: Final[tuple[str, ...]] = ("ok", "warn", "error")


def _seen(hex_value: str, vision: str | None) -> Color:
    """The color as a reader with `vision` sees it; None is normal vision."""
    color = Color(hex_value)
    return color if vision is None else color.filter(vision, 1.0, method="machado").clip()


def _de2000(first: str, second: str, vision: str | None = None) -> float:
    return _seen(first, vision).delta_e(_seen(second, vision), method="2000")


def _oklab(first: str, second: str, vision: str | None = None) -> float:
    return _seen(first, vision).delta_e(_seen(second, vision), method="ok") * 100


def _ramp(values: Mapping[str, TokenValue], name: str) -> list[str]:
    return [str(values[f"color-data-{name}-{step}"]) for step in range(1, 10)]


def _least(
    distance: Callable[..., float], pairs: list[tuple[str, str]], vision: str | None
) -> float:
    return min(distance(first, second, vision) for first, second in pairs)


@pytest.mark.parametrize("theme", THEME_MODES)
def test_the_categorical_colors_stay_apart_under_each_simulated_vision(theme: ThemeMode) -> None:
    values = tokens(theme)
    series = [str(values[f"color-data-cat-{slot}"]) for slot in (1, 2, 3)]
    pairs = list(combinations(series, 2))

    assert (
        [vision for vision in _VISIONS if _least(_de2000, pairs, vision) < 12],
        _least(_oklab, pairs, None) >= 15,
        [vision for vision in _DEFICIENT if _least(_oklab, pairs, vision) < 8],
        [color for color in series if Color(color).convert("oklch")["chroma"] < 0.10],
    ) == ([], True, [], [])


@pytest.mark.parametrize("theme", THEME_MODES)
def test_the_categorical_colors_keep_away_from_status_other_and_the_google_logo(
    theme: ThemeMode,
) -> None:
    values = tokens(theme)
    series = [str(values[f"color-data-cat-{slot}"]) for slot in (1, 2, 3)]
    status = {name: str(values[f"color-status-{name}"]) for name in _STATUSES}
    other = str(values["color-data-neutral"])

    assert (
        min(_de2000(color, logo) for color in series for logo in _GOOGLE_LOGO) >= 15,
        min(_de2000(color, mark) for color in series for mark in status.values()) >= 15,
        min(
            _de2000(color, status[name], vision)
            for color in series
            for name in ("warn", "error")
            for vision in _DEFICIENT
        )
        >= 8,
        min(_de2000(color, other, vision) for color in series for vision in _VISIONS) >= 10,
    ) == (True, True, True, True)


@pytest.mark.parametrize("theme", THEME_MODES)
def test_the_sequential_ramp_runs_in_one_lightness_direction_to_the_most_contrast(
    theme: ThemeMode,
) -> None:
    """Step 9 is the highest value, so it has the most contrast on the background of its theme."""
    values = tokens(theme)
    ramp = _ramp(values, "seq")
    lightness = [Color(step).convert("lab-d65")["lightness"] for step in ramp]
    background = str(values["color-bg"])

    assert (
        lightness == sorted(lightness) or lightness == sorted(lightness, reverse=True),
        len(set(lightness)),
        Color(ramp[8]).contrast(background, method="wcag21")
        > Color(ramp[0]).contrast(background, method="wcag21"),
    ) == (True, 9, True)


@pytest.mark.parametrize("theme", THEME_MODES)
def test_the_diverging_ramp_is_red_for_worse_and_blue_for_better_in_both_themes(
    theme: ThemeMode,
) -> None:
    """Step 1 (worse) is red and step 9 (better) is blue in each theme, and step 5 (no change)
    is near the background."""
    values = tokens(theme)
    ramp = _ramp(values, "div")
    hues = [Color(ramp[index]).convert("oklch")["hue"] for index in (0, 8)]

    assert (
        hues[0] < 45 or hues[0] > 345,
        220 < hues[1] < 290,
        Color(ramp[4]).contrast(str(values["color-bg"]), method="wcag21") < 1.1,
    ) == (True, True, True)
