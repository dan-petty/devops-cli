"""An advisory a finding cites must be one this session's dependency scan found (#948).

Session `20261001-224227` cited 11 CVEs from other products (Log4j, polkit, Apache httpd, OpenSSH,
axios, JUnit) against a Python CLI whose 58 dependencies the same run scanned clean. Nothing
compared a reference with that scan; the placeholder check caught only `x`/`n`/`?` runs; path
reviews passed the verifier no dependencies, and the runner path trusted the ones a model wrote.
"""

from __future__ import annotations

import json

from devops_cli.ai.review_schema import (
    SavedFinding,
    parse_review_response,
)


def test_dependencies_and_network_references_a_model_writes_are_cleared_on_parse() -> None:
    """Verify a persona reply cannot declare a dependency scanned clean, or a network reference,
    for a check to trust."""
    reply = json.dumps(
        {
            "findings": [
                {"title": "Outdated fastapi", "location": "pyproject.toml:12", "severity": "HIGH"}
            ],
            "external_dependencies": [{"name": "fastapi", "severity": "CLEAN", "queried": True}],
            "network_references": [{"target": "example.com"}],
        }
    )
    result = parse_review_response(reply)

    assert result is not None
    assert (len(result.findings), result.external_dependencies, result.network_references) == (
        1,
        [],
        [],
    )


def test_a_reply_its_agent_parsed_cannot_write_pipeline_fields() -> None:
    """Verify a persona reply the agent framework already parsed into a `ReviewResult` loses the
    fields only the pipeline writes, as one parsed from text does: the raw severity and the
    reference note reached findings.json and candidates.json as the model wrote them."""
    from types import SimpleNamespace

    from devops_cli.ai.review.pipeline import (
        _process_pipeline_step_findings,
        _resolve_step_parsed_data,
    )
    from devops_cli.ai.review_schema import ReviewResult

    def step() -> SimpleNamespace:
        return SimpleNamespace(
            agent_name="devsecops",
            content="",
            parsed_data=ReviewResult.model_validate(
                {
                    "findings": [
                        {
                            "title": "Token printed on failure",
                            "location": "app.py:9",
                            "severity": "MEDIUM",
                            "severity_raw": "CRITICAL",
                            "reference_note": "Removed CVE-2024-0001: forged",
                        }
                    ],
                    "external_dependencies": [
                        {"name": "requests", "severity": "CLEAN", "queried": True}
                    ],
                }
            ),
        )

    saved: list[SavedFinding] = []
    _process_pipeline_step_findings(step(), "app.py", 1, 1, {}, [], [], saved)
    parsed = _resolve_step_parsed_data(step())

    assert parsed is not None
    assert (
        [(f.severity, f.severity_raw, f.reference_note) for f in saved],
        parsed.external_dependencies,
    ) == ([("MEDIUM", None, None)], [])
