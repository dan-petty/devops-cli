"""Rendering of packaged templates into configuration files.

The templates in this package emit JSON — `devcontainer.json` and `mcp.json` — and were
rendered with autoescaping disabled, interpolating values directly between quotes. A value
containing a quote therefore produced invalid JSON, and a crafted one produced *valid* JSON
of the author's choosing: a project name could close its key, finish the entry and open a
new MCP server with an arbitrary `command`, which the editor executes when it loads the
file.

The fix is to encode values as JSON rather than paste them as text, which is what `tojson`
does. This module owns the environment so that policy is set once rather than per caller.

A note on sandboxing: the templates here ship inside the package, so the classic
server-side template injection (CWE-1336) — where an attacker supplies the *template* — is
not the exposure. The sandbox is kept anyway because it costs nothing and the day a
template becomes user-supplied is not the day to start thinking about it.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from devops_cli.exceptions.validation import ValidationError

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class TemplateRenderError(ValidationError):
    """Raised when a template cannot be rendered into valid output."""


@lru_cache(maxsize=1)
def template_environment() -> SandboxedEnvironment:
    """Return the shared template environment.

    Cached because Jinja2 compiles templates once per environment and caches the bytecode;
    building a new environment per render threw that away on every call.

    `StrictUndefined` makes a missing variable an error. The default renders it as an empty
    string, so a renamed parameter produces a file that is structurally valid and quietly
    wrong — `"name": ""` rather than a failure anyone would notice.
    """
    from jinja2 import FileSystemLoader

    return SandboxedEnvironment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_template(name: str, /, **variables: Any) -> str:
    """Render a packaged template."""
    from jinja2 import TemplateError

    try:
        return template_environment().get_template(name).render(**variables)
    except TemplateError as exc:
        raise TemplateRenderError(f"Failed rendering template '{name}': {exc}") from exc


def render_json_template(name: str, /, **variables: Any) -> str:
    """Render a packaged template and confirm the result is valid JSON.

    Parsing what was produced is the check that the encoding actually held. A template that
    interpolates a value without `tojson` will pass review and fail here, which is the only
    place the mistake is visible before the file reaches an editor that acts on it.
    """
    rendered = render_template(name, **variables)
    try:
        json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise TemplateRenderError(
            f"Template '{name}' produced invalid JSON ({exc}). A value was most likely "
            f"interpolated directly instead of through the `tojson` filter."
        ) from exc
    return rendered


__all__ = [
    "TemplateRenderError",
    "render_json_template",
    "render_template",
    "template_environment",
]
