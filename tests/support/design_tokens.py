"""The design tokens as the tests of `tests/design` read them (docs/DESIGN.md).

The W3C DTCG sources in `design/tokens/` hold the values and the contrast rules of the color
tokens. Style Dictionary builds them into the package (`src/devops_cli/design/`) and the docs site
(`docs/assets/css/`). This module reads the sources and the built CSS; the package reads its flat
JSON itself (`devops_cli.design.tokens`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final, NamedTuple

from tests.support.paths import REPO_ROOT

TOKEN_SOURCE_DIR: Final[Path] = REPO_ROOT / "design" / "tokens"
PACKAGE_DESIGN_DIR: Final[Path] = REPO_ROOT / "src" / "devops_cli" / "design"
DOCS_TOKEN_CSS_DIR: Final[Path] = REPO_ROOT / "docs" / "assets" / "css"
DESIGN_SPEC: Final[Path] = REPO_ROOT / "docs" / "DESIGN.md"
# The token source files, and the CSS files that the build writes from them.
SOURCE_FILES: Final[tuple[str, ...]] = ("base", "light", "dark")
CSS_FILES: Final[tuple[str, ...]] = ("base", "light", "dark", "dark-explicit")
# The panel and canvas backgrounds of the light and the dark theme of Grafana 13.2.4. Grafana
# draws a fixed hex series color on both themes, so a rule marked `grafana` also holds on these.
GRAFANA_BACKGROUNDS: Final[dict[str, str]] = {
    "grafana.light.panel": "#ffffff",
    "grafana.light.canvas": "#f4f5f5",
    "grafana.dark.panel": "#181b1f",
    "grafana.dark.canvas": "#111217",
}
_EXTENSION_KEY = "devops-cli"
_CSS_VARIABLE = re.compile(r"^\s*--([a-z0-9-]+):", re.MULTILINE)


class ContrastRule(NamedTuple):
    """One rule that a color token declares: its CSS name, the CSS name or Grafana background it
    sits on, and the lowest WCAG 2.x contrast ratio it needs."""

    token: str
    on: str
    minimum: float


def source_tokens(file: str) -> dict[str, dict[str, Any]]:
    """Each token of one DTCG source file by its dotted name, such as `color.status.ok`."""
    document = json.loads((TOKEN_SOURCE_DIR / f"{file}.tokens.json").read_text(encoding="utf-8"))
    found: dict[str, dict[str, Any]] = {}
    pending: list[tuple[tuple[str, ...], dict[str, Any]]] = [((), document)]
    while pending:
        path, node = pending.pop()
        if "$value" in node:
            found[".".join(path)] = node
            continue
        pending.extend(
            (path + (key,), child)
            for key, child in node.items()
            if not key.startswith("$") and isinstance(child, dict)
        )
    return found


def css_name(dotted: str) -> str:
    """The name that Style Dictionary gives a token in CSS and flat JSON: `color.fg` is
    `color-fg`."""
    return dotted.replace(".", "-")


def contrast_rules(theme: str) -> list[ContrastRule]:
    """The contrast rules that apply in `theme`: the rules of the base tokens and of the theme's
    own tokens. A rule marked `grafana` also names the four Grafana backgrounds."""
    rules: list[ContrastRule] = []
    for file in ("base", theme):
        for dotted, node in source_tokens(file).items():
            rule = node.get("$extensions", {}).get(_EXTENSION_KEY, {}).get("contrast")
            if rule is None:
                continue
            backgrounds = [css_name(on) for on in rule["on"]]
            if rule.get("grafana"):
                backgrounds.extend(GRAFANA_BACKGROUNDS)
            rules.extend(
                ContrastRule(css_name(dotted), on, float(rule["min"])) for on in backgrounds
            )
    return rules


def css_variables(directory: Path, file: str) -> list[str]:
    """The custom property names, without `--`, that a built token CSS file declares."""
    return _CSS_VARIABLE.findall((directory / f"tokens-{file}.css").read_text(encoding="utf-8"))
