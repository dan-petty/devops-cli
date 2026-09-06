"""Unit test suite for native Pydantic AI format_prompt integration and XML serialization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

import pydantic_ai.format_prompt as p_fp
from pydantic import BaseModel, Field

from devops_cli.ai.format_prompt import (
    format_as_xml,
    format_context_as_xml,
    format_examples_as_xml,
    format_findings_as_xml,
    format_metadata_as_xml,
    format_plan_reminder_as_xml,
    format_prompt_data,
    format_rag_context_as_xml,
)


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


class SamplePlanItem(BaseModel):
    """Test plan task item."""

    id: str
    content: str
    status: str
    active_form: str | None = None


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


def test_format_prompt_data_wrapper() -> None:
    """Verify format_prompt_data wraps objects with default and custom tags."""
    data = {"project": "devops-cli", "version": "0.2.10"}
    xml_out = format_prompt_data(data, root_tag="metadata")
    assert "<metadata>" in xml_out
    assert "<project>devops-cli</project>" in xml_out
    assert "<version>0.2.10</version>" in xml_out
    assert "</metadata>" in xml_out

    # Rootless formatting
    rootless = format_prompt_data(data, root_tag=None)
    assert "<project>devops-cli</project>" in rootless
    assert "<metadata>" not in rootless


def test_format_examples_as_xml() -> None:
    """Verify format_examples_as_xml formats few-shot examples with field info."""
    examples = [
        {"input": "find vulnerabilities in auth.py", "expected_action": "run_security_scan"},
        {"input": "deploy valkey helm chart", "expected_action": "k8s_deploy_stack"},
    ]
    xml_out = format_examples_as_xml(examples)
    assert "<examples>" in xml_out
    assert "<example>" in xml_out
    assert "<input>find vulnerabilities in auth.py</input>" in xml_out
    assert "<expected_action>run_security_scan</expected_action>" in xml_out
    assert "</examples>" in xml_out


def test_format_rag_context_as_xml() -> None:
    """Verify format_rag_context_as_xml serializes retrieved chunks."""
    chunks = [
        {
            "file": "src/auth.py",
            "lines": "10-25",
            "score": 0.89,
            "snippet": "def authenticate(user, password): ...",
        },
        {
            "file": "src/tokens.py",
            "lines": "40-60",
            "score": 0.95,
            "snippet": "def generate_jwt(payload): ...",
        },
    ]
    xml_out = format_rag_context_as_xml(chunks)
    assert "<rag_context>" in xml_out
    assert "<chunk>" in xml_out
    assert "<file>src/auth.py</file>" in xml_out
    assert "<lines>10-25</lines>" in xml_out
    assert "<snippet>def authenticate(user, password): ...</snippet>" in xml_out
    assert "</rag_context>" in xml_out


def test_format_findings_as_xml() -> None:
    """Verify format_findings_as_xml serializes finding objects."""
    findings = [
        SampleFinding(
            id="F-1",
            title="Unchecked Subprocess",
            severity="CRITICAL",
            file_path="src/shell.py",
            line=12,
        )
    ]
    xml_out = format_findings_as_xml(findings)
    assert "<findings>" in xml_out
    assert "<SampleFinding>" in xml_out or "<finding>" in xml_out
    assert "<id>F-1</id>" in xml_out
    assert "<title>Unchecked Subprocess</title>" in xml_out
    assert "</findings>" in xml_out


def test_format_plan_reminder_as_xml() -> None:
    """Verify format_plan_reminder_as_xml converts tasks into structured XML."""
    items = [
        SamplePlanItem(id="task-1", content="Setup tests", status="completed"),
        SamplePlanItem(
            id="task-2", content="Implement feature", status="in_progress", active_form="Coding"
        ),
    ]
    xml_out = format_plan_reminder_as_xml(items)
    assert "<plan_reminder>" in xml_out
    assert "<task>" in xml_out or "<SamplePlanItem>" in xml_out
    assert "<id>task-1</id>" in xml_out
    assert "<status>completed</status>" in xml_out
    assert "<active_form>Coding</active_form>" in xml_out
    assert "</plan_reminder>" in xml_out


def test_format_metadata_as_xml() -> None:
    """Verify format_metadata_as_xml serializes session metadata."""
    meta = {"session_id": "sess-12345", "persona": "devsecops", "dry_run": True}
    xml_out = format_metadata_as_xml(meta)
    assert "<metadata>" in xml_out
    assert "<session_id>sess-12345</session_id>" in xml_out
    assert "<persona>devsecops</persona>" in xml_out
    assert "<dry_run>True</dry_run>" in xml_out
    assert "</metadata>" in xml_out


def test_format_context_as_xml() -> None:
    """Verify format_context_as_xml handles arbitrary context dicts and models."""
    ctx_data = {
        "repo": "devops-cli",
        "branch": "main",
        "diff_stats": {"files_changed": 3, "insertions": 120, "deletions": 15},
    }
    xml_out = format_context_as_xml(ctx_data, root_tag="context")
    assert "<context>" in xml_out
    assert "<repo>devops-cli</repo>" in xml_out
    assert "<diff_stats>" in xml_out
    assert "<files_changed>3</files_changed>" in xml_out
    assert "</context>" in xml_out


def test_managed_prompt_xml_formatting() -> None:
    """Verify ManagedPrompt renders XML-formatted variables into templates."""
    from devops_cli.ai.agents.prompt import ManagedPrompt

    mp = ManagedPrompt(
        name="test_prompt",
        fallback_template="Review instructions:\n{context_block}\nBegin analysis.",
    )

    finding = SampleFinding(
        id="CVE-2026-9999",
        title="RCE in parser",
        severity="CRITICAL",
        file_path="src/parser.py",
        line=10,
    )
    rendered = mp.render(
        extra_vars={"context_block": mp.format_xml_variable("finding_context", finding)}
    )

    assert "Review instructions:" in rendered
    assert "<finding_context>" in rendered
    assert "<id>CVE-2026-9999</id>" in rendered
    assert "</finding_context>" in rendered
    assert "Begin analysis." in rendered


def test_planning_harness_uses_format_as_xml() -> None:
    """Verify harness planning uses format_plan_reminder_as_xml cleanly."""
    from devops_cli.ai.harness.planning import PlanningStore

    store = PlanningStore()
    store.add("Step 1: Test", status="completed")
    store.add("Step 2: Code", status="in_progress", active_form="Implementing")

    items = store.get_items()
    xml_out = format_plan_reminder_as_xml(items)
    assert "<plan_reminder>" in xml_out
    assert "Step 1: Test" in xml_out
    assert "Step 2: Code" in xml_out
    assert "</plan_reminder>" in xml_out


def test_public_package_reexports() -> None:
    """Verify format_as_xml and helpers are re-exported across public package tiers."""
    import devops_cli.ai as ai
    import devops_cli.ai.agents as agents
    import devops_cli.ai.agents.pydantic_agent as pydantic_agent

    assert hasattr(ai, "format_as_xml")
    assert hasattr(ai, "format_prompt_data")
    assert hasattr(ai, "format_examples_as_xml")
    assert hasattr(ai, "format_rag_context_as_xml")
    assert hasattr(ai, "format_findings_as_xml")
    assert hasattr(ai, "format_plan_reminder_as_xml")
    assert hasattr(ai, "format_metadata_as_xml")
    assert hasattr(ai, "format_context_as_xml")

    assert hasattr(agents, "format_as_xml")
    assert hasattr(pydantic_agent, "format_as_xml")
