"""Unit test suite for native Pydantic AI format_prompt integration and XML serialization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

import pydantic_ai.format_prompt as p_fp
from pydantic import BaseModel, Field

from devops_cli.ai.format_prompt import format_as_xml


class SampleFinding(BaseModel):
    """Test finding schema."""

    id: str = Field(description="Unique finding identifier")
    title: str = Field(description="Concise vulnerability title")
    severity: str = Field(description="Finding severity rating")
    file_path: str = Field(description="Relative source code path")
    line: int = Field(description="Line number in source file")


@dataclass
class SampleDataclassItem:
    """Test dataclass item."""

    key: str = field(metadata={"description": "Item lookup key"})
    value: int = field(metadata={"description": "Item integer counter"})


def test_format_as_xml_reexport() -> None:
    """Verify format_as_xml is directly re-exported from native pydantic_ai.format_prompt."""
    assert format_as_xml is p_fp.format_as_xml


def test_format_as_xml_primitives_and_scalars() -> None:
    """Verify scalar types format with tags and custom none representations."""
    assert format_as_xml("sample text", root_tag="text").strip() == "<text>sample text</text>"
    assert format_as_xml(100, root_tag="count").strip() == "<count>100</count>"
    assert format_as_xml(3.14, root_tag="ratio").strip() == "<ratio>3.14</ratio>"
    assert format_as_xml(True, root_tag="active").strip() == "<active>True</active>"

    # None handling
    assert format_as_xml(None, root_tag="val").strip() == "<val>null</val>"
    assert format_as_xml(None, root_tag="val", none_str="empty").strip() == "<val>empty</val>"

    # Temporal & UUID types
    d = date(2026, 9, 5)
    assert format_as_xml(d, root_tag="date").strip() == "<date>2026-09-05</date>"

    uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert format_as_xml(uid, root_tag="uuid").strip() == f"<uuid>{uid}</uuid>"


def test_format_as_xml_pydantic_model_field_info() -> None:
    """Verify Pydantic models serialize with field descriptions and titles when requested."""
    finding = SampleFinding(
        id="SEC-001",
        title="Insecure Direct Object Reference",
        severity="HIGH",
        file_path="src/api.py",
        line=42,
    )

    xml_with_info = format_as_xml(finding, root_tag="finding", include_field_info=True)
    assert '<id description="Unique finding identifier">SEC-001</id>' in xml_with_info
    assert '<title description="Concise vulnerability title">' in xml_with_info
    assert "<severity " in xml_with_info
    assert "<file_path " in xml_with_info

    xml_without_info = format_as_xml(finding, root_tag="finding", include_field_info=False)
    assert "<id>SEC-001</id>" in xml_without_info
    assert 'description="' not in xml_without_info


def test_format_as_xml_dataclass_metadata() -> None:
    """Verify dataclasses serialize with field metadata descriptions."""
    item = SampleDataclassItem(key="token_limit", value=4096)
    xml_out = format_as_xml(item, root_tag="config", include_field_info=True)
    assert '<key description="Item lookup key">token_limit</key>' in xml_out
    assert '<value description="Item integer counter">4096</value>' in xml_out


def test_format_as_xml_list_once_field_info() -> None:
    """Verify include_field_info='once' includes descriptions only on first element."""
    items = [
        SampleFinding(id="1", title="T1", severity="LOW", file_path="a.py", line=1),
        SampleFinding(id="2", title="T2", severity="MED", file_path="b.py", line=2),
    ]

    xml_out = format_as_xml(items, root_tag="findings", include_field_info="once")
    # Finding 1 has descriptions
    assert '<id description="Unique finding identifier">1</id>' in xml_out
    # Finding 2 does not repeat the description attribute
    assert "<id>2</id>" in xml_out
