"""`load_session_payload`: a findings.json that does not validate is a project error (#2644)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.ai.review_schema import ReviewSessionPayload
from devops_cli.exceptions.validation import ValidationError
from devops_cli.review.session import load_session_payload

_OLD_NETWORK_REFERENCE = {
    "target": "203.0.113.7",
    "reference_type": "ip",
    "reputation": {
        "target": "203.0.113.7",
        "ip": "203.0.113.7",
        "reputation_summary": "Clean",
    },
}


def test_the_loader_names_the_file_and_the_failing_field(tmp_path: Path) -> None:
    """Verify a file that lacks a required field raises the project's error with both names."""
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps({"findings": [], "network_references": [_OLD_NETWORK_REFERENCE]}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as raised:
        load_session_payload(path)

    message = raised.value.message
    assert (str(path) in message, "network_references.0.reputation.outcome" in message) == (
        True,
        True,
    )


def test_the_loader_returns_the_payload_of_a_valid_file(tmp_path: Path) -> None:
    """Verify a file that validates loads as it does with pydantic."""
    path = tmp_path / "findings.json"
    payload = ReviewSessionPayload(subject={"type": "path", "ref": "src"})
    path.write_text(payload.model_dump_json(), encoding="utf-8")

    assert load_session_payload(path) == payload
