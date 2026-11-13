"""What counts as a refusal of an internal target by the Crawl4AI service (#3894).

The pinned image answers a blocked URL with HTTP 400 and the body `{"detail": "URL blocked (SSRF
protection): URL blocked"}` (docs/CLUSTER.md, Crawl4AI). A second source reports 403, so both are
refusals. A refusal holds no page content: its body is a JSON object with the one key `detail`.
"""

from __future__ import annotations

import re

import pytest

from devops_cli.k8s.crawl4ai_check import CRAWL4AI_IMAGE, is_refusal

_BLOCKED = b'{"detail":"URL blocked (SSRF protection): URL blocked"}'


@pytest.mark.parametrize(
    ("status", "body", "refusal"),
    [
        pytest.param(400, _BLOCKED, True, id="the-documented-400"),
        pytest.param(403, b'{"detail":"Forbidden"}', True, id="a-403"),
        pytest.param(200, b'{"markdown":"# A page"}', False, id="a-served-page"),
        pytest.param(200, _BLOCKED, False, id="a-200-with-a-refusal-text"),
        pytest.param(400, b'{"detail":"blocked","markdown":"# A page"}', False, id="page-content"),
        pytest.param(400, b"<html><body>A page</body></html>", False, id="a-400-with-html"),
        pytest.param(400, b'{"detail":["not","text"]}', False, id="a-detail-that-is-no-text"),
        pytest.param(400, b"not json", False, id="a-body-that-is-no-json"),
        pytest.param(500, b'{"detail":"Internal error"}', False, id="a-fault"),
        pytest.param(302, b"", False, id="a-redirect"),
    ],
)
def test_only_a_400_or_403_with_a_detail_text_is_a_refusal(
    status: int, body: bytes, refusal: bool
) -> None:
    assert is_refusal(status, body) is refusal


def test_the_checked_image_names_a_release_tag_and_its_digest() -> None:
    """The gate compares this value with the image of the Deployment, so a bump of the digest
    fails until a person runs the command against the new image."""
    assert re.fullmatch(r"unclecode/crawl4ai:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", CRAWL4AI_IMAGE)
