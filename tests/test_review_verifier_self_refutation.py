"""The verifier does not invalidate a finding its own reason confirms (#536).

In the first sample validation (#505) all three unpinned `:latest` image findings were
INVALIDATED although the verifier's reason confirmed the defect: it filed the finding's own
verification criterion, or its fix, as the invalidation criterion it matched.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.review.verification import _apply_single_finding_verification
from devops_cli.ai.review_schema import Finding

NOW = "2026-09-25T00:00:00+00:00"


def _unpinned(image: str = "alpine") -> Finding:
    return Finding(
        severity="MEDIUM",
        location="docker/Dockerfile:6",
        title="Unpinned base image tag",
        description=f"`FROM {image}:latest` pulls whatever the tag points at when built.",
        fix=f"Pin {image} to a specific version tag such as {image}:1.22.3 and verify its checksum.",
        verification_criteria=["The FROM directive uses the 'latest' tag"],
        invalidation_criteria=["The base image is pinned to a version or digest"],
    )


def _outcome(finding: Finding, verdict: dict[str, Any]) -> tuple[str, bool]:
    result = _apply_single_finding_verification(finding, verdict, NOW)
    return result.status, result.reportable


@pytest.mark.parametrize(
    "verdict",
    [
        # The verification criterion, filed as the invalidation it matched.
        {
            "status": "INVALIDATED",
            "invalidated": True,
            "reason": "Line 6 contains `FROM alpine:latest`, which uses the unpinned `latest` tag.",
            "invalidated_criteria_matched": [
                "The FROM directive still uses 'latest' as the image tag."
            ],
        },
        {
            "status": "INVALIDATED",
            "reason": "Line 6 specifies 'FROM debian:latest', which uses the ':latest' tag.",
            "invalidated_criteria_matched": [
                "Verify that the FROM directive uses the 'latest' tag."
            ],
        },
        # The fix, filed as the invalidation it matched.
        {
            "status": "INVALIDATED",
            "reason": "Using the latest tag makes builds non-deterministic.",
            "invalidated_criteria_matched": [
                "The FROM directive contains a specific version tag (e.g., `alpine:1.22.3`) and "
                "a checksum."
            ],
        },
        # No criteria at all, and a reason that states the defect.
        {
            "status": "INVALIDATED",
            "reason": "The FROM directive uses the latest tag on line 6.",
            "invalidated_criteria_matched": [],
        },
    ],
)
def test_an_invalidation_that_restates_the_defect_keeps_the_finding(
    verdict: dict[str, Any],
) -> None:
    """Verify the finding stays in the report, unverified, not refuted."""
    assert _outcome(_unpinned(), verdict) == ("UNVERIFIED", True)


@pytest.mark.parametrize(
    "verdict",
    [
        {
            "status": "INVALIDATED",
            "reason": "The image is pinned by digest on line 6: `FROM alpine@sha256:4bc...`.",
            "invalidated_criteria_matched": ["The base image is pinned to a version or digest"],
        },
        {
            "invalidated": True,
            "reason": "This Dockerfile is a test fixture that is never built.",
            "invalidated_criteria_matched": ["The file is a test fixture"],
        },
        # A genuine refutation beside a restatement still refutes.
        {
            "status": "INVALIDATED",
            "reason": "Line 6 is `FROM alpine:3.20@sha256:4bc...`; the tag is not latest.",
            "invalidated_criteria_matched": [
                "The FROM directive still uses 'latest' as the image tag.",
                "The base image is pinned to a version or digest",
            ],
        },
    ],
)
def test_a_genuine_refutation_still_invalidates(verdict: dict[str, Any]) -> None:
    """Verify evidence against the finding still removes it."""
    assert _outcome(_unpinned(), verdict) == ("INVALIDATED", False)


def test_a_confirmation_is_left_as_it_was() -> None:
    """Verify a verdict that confirms the finding is untouched."""
    verdict = {
        "verified": True,
        "status": "VERIFIED",
        "reason": "Line 6 uses `alpine:latest`.",
        "verified_criteria_matched": ["The FROM directive uses the 'latest' tag"],
    }

    assert _outcome(_unpinned(), verdict) == ("VERIFIED", True)
