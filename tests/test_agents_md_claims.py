"""Offline test suite asserting claims made in AGENTS.md and related documentation."""

from __future__ import annotations

import re
from pathlib import Path

from devops_cli.ai.instruction_generator import (
    generate_instruction_content,
    parse_project_metadata,
)
from devops_cli.ai.personas import Persona

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_issue_templates(agents_md_content: str) -> set[str]:
    """Extract all issue template filenames referenced under .github/ISSUE_TEMPLATE/ in AGENTS.md."""
    templates = set(
        re.findall(r"\.github/ISSUE_TEMPLATE/([a-zA-Z0-9_\-]+\.ya?ml)", agents_md_content)
    )
    for line in agents_md_content.splitlines():
        if ".github/ISSUE_TEMPLATE/" in line:
            for fname in re.findall(r"`([a-zA-Z0-9_\-]+\.ya?ml)`", line):
                templates.add(fname)
    return templates


def test_issue_templates_named_in_agents_md_exist() -> None:
    """Every .github/ISSUE_TEMPLATE/*.yml named in AGENTS.md must exist on disk."""
    agents_path = _REPO_ROOT / "AGENTS.md"
    assert agents_path.is_file(), "AGENTS.md must exist at repo root"

    templates = _extract_issue_templates(agents_path.read_text(encoding="utf-8"))
    assert len(templates) > 0, "AGENTS.md must reference at least one issue template"

    template_dir = _REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
    missing = [t for t in templates if not (template_dir / t).is_file()]
    assert not missing, f"Missing issue templates referenced in AGENTS.md: {missing}"

    # Also assert that deprecated/unsupported templates are not referenced
    assert "security_advisory.yml" not in templates and "task.yml" not in templates, (
        "Deprecated templates must not be referenced in AGENTS.md"
    )


def test_personas_in_self_improvement_are_valid() -> None:
    """Every persona listed as active in docs/SELF_IMPROVEMENT.md is a Persona enum value."""
    doc_path = _REPO_ROOT / "docs" / "SELF_IMPROVEMENT.md"
    assert doc_path.is_file(), "docs/SELF_IMPROVEMENT.md must exist"

    content = doc_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # The line 187 negation of performance/sre is accepted and must be the only reference
    negation_lines = [
        line for line in lines if "performance" in line.lower() or "sre" in line.lower()
    ]
    assert len(negation_lines) == 1, (
        f"Expected exactly 1 line referencing performance/sre, found {len(negation_lines)}"
    )
    assert "no `performance` or `sre` persona" in negation_lines[0], (
        "Reference to performance/sre must be the explicit non-existence negation"
    )

    valid_enum_values = {p.value for p in Persona}
    active_personas: set[str] = set()
    for line in lines:
        if line in negation_lines:
            continue
        if "persona" in line.lower():
            for word in re.findall(r"\b([a-zA-Z]+)\b", line):
                if word.lower() in valid_enum_values:
                    active_personas.add(word.lower())

    assert active_personas == valid_enum_values, (
        f"Active personas in docs ({active_personas}) must match Persona enum values ({valid_enum_values})"
    )


def test_instruction_stubs_byte_equal_to_generator() -> None:
    """CLAUDE.md and .github/copilot-instructions.md must match generator output byte-for-byte."""
    meta = parse_project_metadata(_REPO_ROOT)
    for target in ("CLAUDE.md", ".github/copilot-instructions.md"):
        expected = generate_instruction_content(target, meta)
        actual = (_REPO_ROOT / target).read_text(encoding="utf-8")
        assert actual == expected, f"{target} differs from generator output"
