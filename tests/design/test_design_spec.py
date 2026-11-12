"""docs/DESIGN.md states the values that no token type holds as the package and the tokens hold
them: the dash pattern of each chart line, and the widths of the `@media` rules, which cannot read
a custom property."""

from __future__ import annotations

import re
from typing import Final

from devops_cli.design import REFERENCE_DASH, SERIES_DASHES, tokens
from tests.support.design_tokens import DESIGN_SPEC, PACKAGE_DESIGN_DIR
from tests.support.markdown_tables import tables

_DASH_HEADER: Final[list[str]] = ["Line", "Dash array (px)", "Use"]
_MEDIA_WIDTH = re.compile(r"@media[^{`]*\((?:min|max)-width:\s*([0-9.]+[a-z]+)\)")


def _dash(cell: str) -> tuple[int, ...]:
    """The dash array of a cell such as "`6 3`"; "`solid`" is no dash."""
    text = cell.strip("`")
    return () if text == "solid" else tuple(int(length) for length in text.split())


def test_the_spec_names_the_dash_pattern_of_each_series_and_of_a_reference_line() -> None:
    rows = next(rows for header, *rows in tables(DESIGN_SPEC) if header == _DASH_HEADER)

    assert {line: _dash(dash) for line, dash, _use in rows} == {
        "Series 1": SERIES_DASHES[0],
        "Series 2": SERIES_DASHES[1],
        "Series 3": SERIES_DASHES[2],
        "Reference": REFERENCE_DASH,
    }


def test_each_media_width_is_a_breakpoint_token() -> None:
    """The spec and the hand-written CSS of the design package write each breakpoint as a literal
    in `@media`, and each literal is the value of `breakpoint.md` or `breakpoint.lg`."""
    texts = [DESIGN_SPEC.read_text(encoding="utf-8")] + [
        path.read_text(encoding="utf-8") for path in sorted(PACKAGE_DESIGN_DIR.glob("css/*.css"))
    ]
    widths = {width for text in texts for width in _MEDIA_WIDTH.findall(text)}
    breakpoints = {tokens("light")["breakpoint-md"], tokens("light")["breakpoint-lg"]}

    assert (sorted(widths), sorted(widths - breakpoints)) == (["40rem", "75rem"], [])
