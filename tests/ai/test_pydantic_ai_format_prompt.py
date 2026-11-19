"""Unit test suite for native Pydantic AI format_prompt integration."""

from __future__ import annotations

import pydantic_ai.format_prompt as p_fp

from devops_cli.ai.format_prompt import format_as_xml


def test_format_as_xml_reexport() -> None:
    """Verify format_as_xml is directly re-exported from native pydantic_ai.format_prompt."""
    assert format_as_xml is p_fp.format_as_xml
