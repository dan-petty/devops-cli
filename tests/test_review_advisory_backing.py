"""An advisory a finding cites must be one this session's dependency scan found (#948).

Session `20261001-224227` cited 11 CVEs from other products (Log4j, polkit, Apache httpd, OpenSSH,
axios, JUnit) against a Python CLI whose 58 dependencies the same run scanned clean. Nothing
compared a reference with that scan; the placeholder check caught only `x`/`n`/`?` runs; path
reviews passed the verifier no dependencies, and the runner path trusted the ones a model wrote.
"""

from __future__ import annotations

import json

from devops_cli.ai.review_schema import parse_review_response


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
