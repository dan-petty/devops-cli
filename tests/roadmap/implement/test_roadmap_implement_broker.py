"""The loopback gateway broker of an implement step (#3820).

The broker runs in the job process, holds the AI key, and gives one step a token that dies with
it. It forwards only the exact pairs of `ALLOWED_REQUESTS` under the path prefix of
`ai.gateway_url`, and counts each forwarded answer in the budget of the step and in the record of
the tier that served it. The upstream request is the HTTP fake, which records what the broker
sent; the step side is a real client on the loopback socket that the test process binds.

The broker module is imported inside the test call, never at the top of this file: on the base
commit the module does not exist, and a test that fails on its assertion there is the proof of the
change.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import httpx2
import pytest
from fastapi.testclient import TestClient

from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.roadmap.implement.implement_limits import StepBudget
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring

if TYPE_CHECKING:
    from devops_cli.roadmap.implement.implement_broker import StepBroker

_GATEWAY = "https://gateway.example.com/v1"
_CHAT = f"{_GATEWAY}/chat/completions"
_KEY = "gateway-secret-key"
_USAGE = {
    "prompt_tokens": 120,
    "completion_tokens": 30,
    "prompt_tokens_details": {"cached_tokens": 20},
}


def _budget() -> StepBudget:
    """A budget of a step with no progress digest."""
    return StepBudget(progress=lambda: None)


def _authorization(token: str) -> dict[str, str]:
    """The header that carries the step token."""
    return {"authorization": f"Bearer {token}"}


@contextmanager
def _live_broker() -> Iterator[tuple[StepBroker, StepBudget]]:
    """The live broker of one step, and the budget that its shell calls count against."""
    from devops_cli.roadmap.implement.implement_broker import start_step_broker, stop_step_broker

    budget = _budget()
    broker = start_step_broker(budget)
    assert broker is not None
    try:
        yield broker, budget
    finally:
        stop_step_broker(broker)


@pytest.fixture
def gateway(config: Callable[..., Path], keyring_store: FakeKeyring) -> None:
    """The gateway as the provider, with its key in the credential store."""
    config(ai={"provider": "gateway", "gateway_url": _GATEWAY})
    keyring_store.set_password("devops-cli", "ai_api_key", _KEY)


# ── An allowed request ─────────────────────────────────────────────────────────────────────


def test_an_allowed_request_reaches_the_recorded_gateway(web: WebFake, gateway: None) -> None:
    from devops_cli.roadmap.implement.implement_broker import BrokerSpend, live_broker

    answer = {"model": "devops-coder", "choices": [], "usage": _USAGE}
    web.respond("POST", _CHAT, 200, answer)
    body = b'{"model": "devops-coder", "messages": []}'

    with _live_broker() as (broker, budget), httpx2.Client() as step:
        response = step.post(
            f"{broker.url}/chat/completions", headers=_authorization(broker.token), content=body
        )

    assert (response.status_code, response.json()) == (200, answer)
    assert [(record.method, record.url) for record in web.recorded] == [("POST", _CHAT)]
    assert web.recorded[0].headers["authorization"] == f"Bearer {_KEY}"
    assert json.loads(web.recorded[0].body) == json.loads(body)
    assert broker.spend_by_tier() == {
        "": BrokerSpend(requests=1, input_tokens=120, cache_read_tokens=20, output_tokens=30)
    }
    assert budget.used == 130
    assert live_broker() is None


def test_an_embedding_request_reaches_the_recorded_gateway(web: WebFake, gateway: None) -> None:
    from devops_cli.roadmap.implement.implement_broker import BrokerSpend

    web.respond("POST", f"{_GATEWAY}/embeddings", 200, {"usage": {"prompt_tokens": 8}})

    with _live_broker() as (broker, budget), httpx2.Client() as step:
        response = step.post(
            f"{broker.url}/embeddings",
            headers=_authorization(broker.token),
            content=b'{"input": "a query"}',
        )

    assert response.status_code == 200
    assert [record.url for record in web.recorded] == [f"{_GATEWAY}/embeddings"]
    assert broker.spend_by_tier() == {
        "": BrokerSpend(requests=1, input_tokens=8, cache_read_tokens=0, output_tokens=0)
    }
    assert budget.used == 8


def test_the_answer_holds_no_ai_key(web: WebFake, gateway: None) -> None:
    web.respond("POST", _CHAT, 200, {"choices": [], "usage": _USAGE})

    with _live_broker() as (broker, _), httpx2.Client() as step:
        response = step.post(
            f"{broker.url}/chat/completions", headers=_authorization(broker.token), content=b"{}"
        )

    assert _KEY not in response.text
    assert _KEY not in json.dumps(dict(response.headers))


def test_a_json_content_type_reaches_the_recorded_gateway(web: WebFake, gateway: None) -> None:
    web.respond("POST", _CHAT, 200, {"usage": {"prompt_tokens": 5}})

    with _live_broker() as (broker, _), httpx2.Client() as step:
        response = step.post(
            f"{broker.url}/chat/completions",
            headers={**_authorization(broker.token), "content-type": "application/json"},
            content=b'{"model": "m"}',
        )

    assert response.status_code == 200
    assert json.loads(web.recorded[0].body) == {"model": "m"}


def test_an_answer_without_usage_counts_no_tokens(web: WebFake, gateway: None) -> None:
    from devops_cli.roadmap.implement.implement_broker import BrokerSpend

    web.respond("POST", _CHAT, 200, {"choices": []})

    with _live_broker() as (broker, budget), httpx2.Client() as step:
        response = step.post(
            f"{broker.url}/chat/completions", headers=_authorization(broker.token), content=b"{}"
        )

    assert response.status_code == 200
    assert broker.spend_by_tier() == {"": BrokerSpend(requests=1)}
    assert budget.used == 0


def test_an_answer_that_is_no_json_counts_no_tokens(web: WebFake, gateway: None) -> None:
    from devops_cli.roadmap.implement.implement_broker import BrokerSpend

    web.answer(_CHAT, 200, method="POST", headers={"content-type": "text/plain"}, body=b"not json")

    with _live_broker() as (broker, budget), httpx2.Client() as step:
        response = step.post(
            f"{broker.url}/chat/completions", headers=_authorization(broker.token), content=b"{}"
        )

    assert response.status_code == 200
    assert broker.spend_by_tier() == {"": BrokerSpend(requests=1)}
    assert budget.used == 0


# ── A refused request ──────────────────────────────────────────────────────────────────────


def test_a_request_to_another_path_is_refused(web: WebFake, gateway: None) -> None:
    with _live_broker() as (broker, _), httpx2.Client() as step:
        response = step.post(
            f"{broker.url}/other", headers=_authorization(broker.token), content=b"{}"
        )

    assert response.status_code == 404
    assert web.recorded == []


def test_a_method_other_than_post_is_refused(web: WebFake, gateway: None) -> None:
    with _live_broker() as (broker, _), httpx2.Client() as step:
        response = step.get(f"{broker.url}/chat/completions", headers=_authorization(broker.token))

    assert response.status_code == 405
    assert web.recorded == []


def test_a_request_with_another_token_is_refused(web: WebFake, gateway: None) -> None:
    with _live_broker() as (broker, _), httpx2.Client() as step:
        token = broker.token
        response = step.post(
            f"{broker.url}/chat/completions",
            headers=_authorization("not-the-step-token"),
            content=b"{}",
        )

    assert response.status_code == 401
    assert web.recorded == []
    assert token not in response.text


# ── The end of the step ───────────────────────────────────────────────────────────────────


def test_the_token_stops_working_when_the_step_ends(web: WebFake, gateway: None) -> None:
    from devops_cli.roadmap.implement.implement_broker import (
        live_broker,
        start_step_broker,
        stop_step_broker,
    )

    broker = start_step_broker(_budget())
    assert broker is not None
    try:
        web.respond("POST", _CHAT, 200, {"usage": _USAGE})
        token = broker.token
        headers = _authorization(token)

        before = TestClient(broker.app).post("/v1/chat/completions", headers=headers, content=b"{}")
        stop_step_broker(broker)
        after = TestClient(broker.app).post("/v1/chat/completions", headers=headers, content=b"{}")

        assert (before.status_code, after.status_code) == (200, 401)
        assert len(web.recorded) == 1
        assert live_broker() is None
    finally:
        stop_step_broker(broker)


def test_a_host_that_is_not_loopback_is_refused(gateway: None) -> None:
    from devops_cli.roadmap.implement.implement_broker import live_broker, start_step_broker

    with pytest.raises(RoadmapImplementError, match=r"192\.0\.2\.1"):
        start_step_broker(_budget(), host="192.0.2.1")

    assert live_broker() is None


def test_a_hostname_that_is_not_an_address_is_refused(gateway: None) -> None:
    from devops_cli.roadmap.implement.implement_broker import live_broker, start_step_broker

    with pytest.raises(RoadmapImplementError, match="localhost"):
        start_step_broker(_budget(), host="localhost")

    assert live_broker() is None


# ── A step with no gateway ────────────────────────────────────────────────────────────────


def test_a_gateway_provider_with_no_url_is_refused(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    from devops_cli.roadmap.implement.implement_broker import live_broker, start_step_broker

    config(ai={"provider": "gateway", "gateway_url": None})
    keyring_store.set_password("devops-cli", "ai_api_key", _KEY)

    with pytest.raises(RoadmapImplementError, match=r"ai\.gateway_url"):
        start_step_broker(_budget())

    assert live_broker() is None


def test_a_provider_that_is_not_the_gateway_gets_no_broker(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    from devops_cli.roadmap.implement.implement_broker import live_broker, start_step_broker

    config(ai={"provider": "ollama"})
    keyring_store.set_password("devops-cli", "ai_api_key", _KEY)

    assert start_step_broker(_budget()) is None
    assert live_broker() is None


def test_a_step_with_no_ai_key_gets_no_broker(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    from devops_cli.roadmap.implement.implement_broker import live_broker, start_step_broker

    config(ai={"provider": "gateway", "gateway_url": _GATEWAY})

    assert keyring_store.values == {}
    assert start_step_broker(_budget()) is None
    assert live_broker() is None
