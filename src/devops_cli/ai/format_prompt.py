"""Prompt data serialization to XML through ``pydantic_ai.format_prompt.format_as_xml``."""

from __future__ import annotations

from typing import Any, Literal

from pydantic_ai.format_prompt import format_as_xml

from devops_cli.config.defaults import (
    DEFAULT_XML_INDENT,
    DEFAULT_XML_ITEM_TAG,
    DEFAULT_XML_NONE_STR,
)

__all__ = (
    "format_as_xml",
    "format_prompt_data",
)


def format_prompt_data(
    data: Any,
    root_tag: str | None = None,
    item_tag: str = DEFAULT_XML_ITEM_TAG,
    none_str: str = DEFAULT_XML_NONE_STR,
    indent: str | None = DEFAULT_XML_INDENT,
    include_field_info: Literal["once"] | bool = False,
) -> str:
    """Format an arbitrary Python object as XML for prompt inclusion."""
    return format_as_xml(
        obj=data,
        root_tag=root_tag,
        item_tag=item_tag,
        none_str=none_str,
        indent=indent,
        include_field_info=include_field_info,
    )
