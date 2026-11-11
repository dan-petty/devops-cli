"""The design tokens that the package ships: each theme reads the base tokens and its own colors,
and the light and the dark theme hold the same names in the sources and in every build output
(docs/DESIGN.md, "Token pipeline")."""

from __future__ import annotations

from devops_cli.design import THEME_MODES, tokens
from tests.support.design_tokens import (
    CSS_FILES,
    DOCS_TOKEN_CSS_DIR,
    PACKAGE_DESIGN_DIR,
    css_variables,
    source_tokens,
)


def test_a_theme_holds_the_base_tokens_and_its_own_colors() -> None:
    light, dark = tokens("light"), tokens("dark")

    assert (
        THEME_MODES,
        len(light),
        (light["color-bg"], dark["color-bg"]),
        (light["breakpoint-md"], dark["breakpoint-md"]),
        (light["font-weight-semibold"], light["chart-max-series"]),
        (light["color-data-cat-1"], dark["color-data-cat-1"]),
        (light["color-data-cat-3"], dark["color-data-cat-3"]),
    ) == (
        ("light", "dark"),
        88,
        ("#ffffff", "#151514"),
        ("40rem", "40rem"),
        (600, 3),
        ("#a463f2", "#a463f2"),
        ("#002d9c", "#82cfff"),
    )


def test_the_light_and_dark_themes_hold_the_same_token_names() -> None:
    """A token that one theme lacks draws with no value in that theme, so every name of one
    theme is in the other, in the sources, in the flat JSON and in each CSS file."""
    css = {
        (place, file): css_variables(directory, file)
        for place, directory in (("package", PACKAGE_DESIGN_DIR), ("docs", DOCS_TOKEN_CSS_DIR))
        for file in CSS_FILES[1:]
    }
    light_css = css[("package", "light")]

    assert (
        sorted(source_tokens("light")) == sorted(source_tokens("dark")),
        sorted(tokens("light")) == sorted(tokens("dark")),
        {key: names for key, names in css.items() if names != light_css},
        len(light_css),
    ) == (True, True, {}, 38)


def test_the_docs_site_and_the_package_hold_the_same_token_css() -> None:
    """Jekyll cannot run the build, so the build writes each CSS file twice: one copy for the
    docs site and one as package data."""
    assert [
        file
        for file in CSS_FILES
        if (DOCS_TOKEN_CSS_DIR / f"tokens-{file}.css").read_bytes()
        != (PACKAGE_DESIGN_DIR / f"tokens-{file}.css").read_bytes()
    ] == []
