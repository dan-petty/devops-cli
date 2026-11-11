"""The contrast rules that the color tokens declare in `$extensions.devops-cli.contrast` hold on
the built values of each theme (WCAG 2.x, docs/DESIGN.md, "Palette")."""

from __future__ import annotations

from collections.abc import Mapping

from coloraide import Color

from devops_cli.design import THEME_MODES, ThemeMode, TokenValue, tokens
from tests.support.design_tokens import GRAFANA_BACKGROUNDS, contrast_rules


def _failures(
    theme: ThemeMode, values: Mapping[str, TokenValue]
) -> list[tuple[str, str, str, float]]:
    """Each rule of `theme` whose token, at `values`, is under its minimum ratio on its
    background: the theme, the token, the background and the ratio to two places."""
    backgrounds = {**values, **GRAFANA_BACKGROUNDS}
    found: list[tuple[str, str, str, float]] = []
    for rule in contrast_rules(theme):
        ratio = Color(str(values[rule.token])).contrast(str(backgrounds[rule.on]), method="wcag21")
        if ratio < rule.minimum:
            found.append((theme, rule.token, rule.on, round(ratio, 2)))
    return found


def test_every_declared_contrast_rule_passes_in_both_themes() -> None:
    """37 rules in each theme: text 4.5:1, marks and lines 3:1, and the two fixed series colors
    of Grafana 3:1 on its four backgrounds too."""
    assert (
        {theme: len(contrast_rules(theme)) for theme in THEME_MODES},
        [failure for theme in THEME_MODES for failure in _failures(theme, tokens(theme))],
    ) == ({"light": 37, "dark": 37}, [])


def test_a_token_under_its_declared_minimum_fails_its_rule() -> None:
    """A light `color.fg` of #aaaaaa is 2.32:1 on white and 2.15:1 on the surface, under the 4.5:1 of its rule."""
    faded = {**tokens("light"), "color-fg": "#aaaaaa"}

    assert _failures("light", faded) == [
        ("light", "color-fg", "color-bg", 2.32),
        ("light", "color-fg", "color-surface", 2.15),
    ]
