"""Spec contracts for Qdrant retry waits (#6762)."""

from __future__ import annotations

import re
from typing import Final

from devops_cli.config.constants import CONST_OPENSPEC_SPECS_DIR
from tests.support.paths import REPO_ROOT

_SPECS: Final = REPO_ROOT / CONST_OPENSPEC_SPECS_DIR
_REQUIREMENT_HEADER: Final = "### Requirement: qdrant-retry-wait-uses-clock-seam"


def _extract_section(text: str, heading: str) -> str:
    """Return the section starting at `heading` up to the next sibling heading."""
    pattern = re.compile(
        rf"^{re.escape(heading)}\n.*?(?=^###|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, f"missing heading: {heading}"
    return match.group(0)


def test_rag_lookup_pause_has_no_qdrant_retry_requirement() -> None:
    """`rag-lookup-pause` no longer holds `qdrant-retry-wait-uses-clock-seam`."""
    text = (_SPECS / "rag-lookup-pause" / "spec.md").read_text(encoding="utf-8")
    assert _REQUIREMENT_HEADER not in text


def test_qdrant_request_retry_has_clock_seam_requirement() -> None:
    """`qdrant-request-retry` names `sleep` and clock seam without `tenacity`."""
    text = (_SPECS / "qdrant-request-retry" / "spec.md").read_text(encoding="utf-8")
    section = _extract_section(text, _REQUIREMENT_HEADER)
    lowered = section.lower()
    assert "sleep" in lowered
    assert "clock seam" in lowered
    assert "tenacity" not in lowered


def test_qdrant_retry_scenario_has_two_waits() -> None:
    """Three attempts of `DEFAULT_MAX_RETRIES` make waits of 0.5 s and 1.0 s, with no 1.5 s."""
    text = (_SPECS / "qdrant-request-retry" / "spec.md").read_text(encoding="utf-8")
    section = _extract_section(text, "#### Scenario: retry backoff sequence is recorded in order")
    assert "0.5" in section
    assert "1.0" in section
    assert "1.5" not in section
