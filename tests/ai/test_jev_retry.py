"""The Jev provider retries a 429 and a 529 with backoff (#5286)."""

from __future__ import annotations

import httpx2
import pytest
from tenacity import wait_none


def _answers(*statuses: int) -> tuple[httpx2.MockTransport, list[int]]:
    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(len(calls) + 1)
        return httpx2.Response(statuses[len(calls) - 1], json={"ok": True}, request=request)

    return httpx2.MockTransport(handler), calls


async def _get(transport: httpx2.AsyncBaseTransport) -> httpx2.Response:
    async with httpx2.AsyncClient(transport=transport) as client:
        return await client.post("https://example.com/v1/answers", json={})


@pytest.mark.asyncio
async def test_a_429_and_then_a_200_gives_the_answer_after_one_retry() -> None:
    from devops_cli.ai.providers import jev_retry_transport

    wrapped, calls = _answers(429, 200)
    transport = jev_retry_transport(wrapped, wait=wait_none())

    response = await _get(transport)

    assert (response.status_code, len(calls)) == (200, 2)


@pytest.mark.asyncio
async def test_a_529_and_then_a_200_gives_the_answer_after_one_retry() -> None:
    from devops_cli.ai.providers import jev_retry_transport

    wrapped, calls = _answers(529, 200)
    transport = jev_retry_transport(wrapped, wait=wait_none())

    response = await _get(transport)

    assert (response.status_code, len(calls)) == (200, 2)


@pytest.mark.asyncio
async def test_a_400_makes_one_attempt() -> None:
    from devops_cli.ai.providers import jev_retry_transport

    wrapped, calls = _answers(400)
    transport = jev_retry_transport(wrapped, wait=wait_none())

    response = await _get(transport)

    assert (response.status_code, len(calls)) == (400, 1)


@pytest.mark.asyncio
async def test_three_429_answers_stop_after_three_attempts() -> None:
    from devops_cli.ai.providers import jev_retry_transport

    wrapped, calls = _answers(429, 429, 429)
    transport = jev_retry_transport(wrapped, wait=wait_none())

    with pytest.raises(httpx2.HTTPStatusError, match="429"):
        await _get(transport)

    assert len(calls) == 3
