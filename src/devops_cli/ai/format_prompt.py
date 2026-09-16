"""Native Pydantic AI prompt formatting and XML serialization helpers.

Integrates native ``pydantic_ai.format_prompt`` (specifically ``format_as_xml``)
for serializing semi-structured data (context, examples, RAG chunks, findings,
plan reminders, and metadata) into clean XML representations for LLMs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic_ai.format_prompt import format_as_xml

from devops_cli.config.defaults import (
    DEFAULT_XML_CONTEXT_ROOT_TAG,
    DEFAULT_XML_EXAMPLE_ITEM_TAG,
    DEFAULT_XML_EXAMPLES_ROOT_TAG,
    DEFAULT_XML_FINDING_ITEM_TAG,
    DEFAULT_XML_FINDINGS_ROOT_TAG,
    DEFAULT_XML_INDENT,
    DEFAULT_XML_ITEM_TAG,
    DEFAULT_XML_METADATA_ROOT_TAG,
    DEFAULT_XML_NONE_STR,
    DEFAULT_XML_PLAN_REMINDER_ITEM_TAG,
    DEFAULT_XML_PLAN_REMINDER_ROOT_TAG,
    DEFAULT_XML_RAG_ITEM_TAG,
    DEFAULT_XML_RAG_ROOT_TAG,
)

__all__ = (
    "format_as_xml",
    "format_context_as_xml",
    "format_examples_as_xml",
    "format_findings_as_xml",
    "format_metadata_as_xml",
    "format_plan_reminder_as_xml",
    "format_prompt_data",
    "format_rag_context_as_xml",
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


def format_context_as_xml(
    context: Any,
    root_tag: str = DEFAULT_XML_CONTEXT_ROOT_TAG,
    item_tag: str = DEFAULT_XML_ITEM_TAG,
    none_str: str = DEFAULT_XML_NONE_STR,
    indent: str | None = DEFAULT_XML_INDENT,
    include_field_info: Literal["once"] | bool = False,
) -> str:
    """Format structured context data into an XML block."""
    return format_as_xml(
        obj=context,
        root_tag=root_tag,
        item_tag=item_tag,
        none_str=none_str,
        indent=indent,
        include_field_info=include_field_info,
    )


def format_examples_as_xml(
    examples: Iterable[Any],
    root_tag: str = DEFAULT_XML_EXAMPLES_ROOT_TAG,
    item_tag: str = DEFAULT_XML_EXAMPLE_ITEM_TAG,
    include_field_info: Literal["once"] | bool = "once",
    indent: str | None = DEFAULT_XML_INDENT,
) -> str:
    """Format few-shot examples or benchmark cases into XML with field descriptions."""
    items = list(examples)
    return format_as_xml(
        obj=items,
        root_tag=root_tag,
        item_tag=item_tag,
        include_field_info=include_field_info,
        indent=indent,
    )


def format_rag_context_as_xml(
    chunks: Iterable[Any],
    root_tag: str = DEFAULT_XML_RAG_ROOT_TAG,
    item_tag: str = DEFAULT_XML_RAG_ITEM_TAG,
    indent: str | None = DEFAULT_XML_INDENT,
) -> str:
    """Format retrieved RAG context chunks or documentation excerpts into XML."""
    chunk_list = list(chunks)
    return format_as_xml(
        obj=chunk_list,
        root_tag=root_tag,
        item_tag=item_tag,
        indent=indent,
    )


def format_findings_as_xml(
    findings: Iterable[Any],
    root_tag: str = DEFAULT_XML_FINDINGS_ROOT_TAG,
    item_tag: str = DEFAULT_XML_FINDING_ITEM_TAG,
    include_field_info: Literal["once"] | bool = False,
    indent: str | None = DEFAULT_XML_INDENT,
) -> str:
    """Format review findings into structured XML for LLM verification and deduplication."""
    finding_list = list(findings)
    return format_as_xml(
        obj=finding_list,
        root_tag=root_tag,
        item_tag=item_tag,
        include_field_info=include_field_info,
        indent=indent,
    )


def format_plan_reminder_as_xml(
    items: Iterable[Any],
    root_tag: str = DEFAULT_XML_PLAN_REMINDER_ROOT_TAG,
    item_tag: str = DEFAULT_XML_PLAN_REMINDER_ITEM_TAG,
    indent: str | None = DEFAULT_XML_INDENT,
) -> str:
    """Format plan task items into a structured XML reminder block."""
    task_list = list(items)
    return format_as_xml(
        obj=task_list,
        root_tag=root_tag,
        item_tag=item_tag,
        indent=indent,
    )


def format_metadata_as_xml(
    metadata: Mapping[str, Any],
    root_tag: str = DEFAULT_XML_METADATA_ROOT_TAG,
    indent: str | None = DEFAULT_XML_INDENT,
) -> str:
    """Format execution or session metadata into XML."""
    return format_as_xml(
        obj=metadata,
        root_tag=root_tag,
        indent=indent,
    )
