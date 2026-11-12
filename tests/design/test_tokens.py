"""The design tokens that the package ships: each theme reads the base tokens and its own colors,
and the light and the dark theme hold the same names in the sources and in every build output
(docs/DESIGN.md, "Token pipeline")."""

from __future__ import annotations

from coloraide import Color

from devops_cli.design import THEME_MODES, tokens
from devops_cli.roadmap.workflow_labels import LabelColor
from tests.support.design_tokens import (
    CSS_FILES,
    DOCS_TOKEN_CSS_DIR,
    PACKAGE_DESIGN_DIR,
    SOURCE_FILES,
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


def test_the_hex_of_each_source_color_is_the_color_of_its_components() -> None:
    """A DTCG source color holds its value in `components` and again in `hex`. The build reads
    only `components`, so a `hex` that differs shows a color that no output has (docs/DESIGN.md,
    "Change a token")."""
    colors = [
        (f"{file}:{dotted}", node["$value"])
        for file in SOURCE_FILES
        for dotted, node in source_tokens(file).items()
        if isinstance(node["$value"], dict) and "components" in node["$value"]
    ]

    assert (
        len(colors),
        {
            name: value["hex"]
            for name, value in colors
            if Color(value["colorSpace"], value["components"]).to_string(hex=True)
            != value["hex"].lower()
        },
    ) == (66, {})


def test_the_docs_site_and_the_package_hold_the_same_token_css() -> None:
    """Jekyll cannot run the build, so the build writes each CSS file twice: one copy for the
    docs site and one as package data."""
    assert [
        file
        for file in CSS_FILES
        if (DOCS_TOKEN_CSS_DIR / f"tokens-{file}.css").read_bytes()
        != (PACKAGE_DESIGN_DIR / f"tokens-{file}.css").read_bytes()
    ] == []


def test_each_label_color_is_a_light_token_color() -> None:
    """A label takes the light hex value of a token (docs/DESIGN.md, "Rules for each target"), so
    a token change that a label color does not follow fails here."""
    light = {str(value).removeprefix("#").upper() for value in tokens("light").values()}

    assert sorted(color.name for color in LabelColor if color.value not in light) == []
