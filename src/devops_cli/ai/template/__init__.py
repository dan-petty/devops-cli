"""Native Pydantic AI template subsystem for devops-cli.

Provides dynamic Handlebars template string compilation and rendering against
RunContext dependencies, dictionaries, and Pydantic data models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, TypeAdapter
from pydantic_ai.template import TemplateStr


def create_template_str(
    source: str,
    *,
    deps_type: type[Any] | None = None,
    deps_schema: dict[str, Any] | None = None,
) -> TemplateStr[Any]:
    """Construct a native TemplateStr instance for dynamic instruction rendering."""
    return TemplateStr(source, deps_type=deps_type, deps_schema=deps_schema)


def render_template(template: str | TemplateStr[Any], deps: Any = None) -> str:
    """Render a raw template string or TemplateStr against provided dependencies."""
    if deps is None:
        return str(template)

    if isinstance(template, TemplateStr):
        return template.render(deps)

    source_str = str(template)
    if "{{" not in source_str:
        return source_str

    if isinstance(deps, BaseModel):
        tmpl = TemplateStr(source_str, deps_type=type(deps))
        return tmpl.render(deps)

    if isinstance(deps, dict):
        tmpl = TemplateStr(source_str)
        return tmpl.render(deps)

    try:
        ta = TypeAdapter(type(deps))
        dumped = ta.dump_python(deps, mode="python")
        if isinstance(dumped, dict):
            tmpl = TemplateStr(source_str)
            return tmpl.render(dumped)
    except Exception:
        pass

    tmpl = TemplateStr(source_str)
    return tmpl.render(deps)


def is_template_str(val: Any) -> bool:
    """Check whether a value is a TemplateStr instance or a string containing Handlebars template syntax."""
    if isinstance(val, TemplateStr):
        return True
    if isinstance(val, str) and "{{" in val and "}}" in val:
        return True
    return False


__all__ = [
    "TemplateStr",
    "create_template_str",
    "is_template_str",
    "render_template",
]
