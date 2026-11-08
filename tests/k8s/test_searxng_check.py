"""What a reply of the SearXNG service must hold for `devops k8s searxng-check` to pass it (#3929).

The pinned image answers `GET /search?format=json` with a JSON object of seven keys (`answers`,
`corrections`, `infoboxes`, `query`, `results`, `suggestions` and `unresponsive_engines`). The
format `json` must be in `search.formats`, or the service answers HTTP 403 (`searx/webapp.py`).
Six scraping and keyed engines must stay off. `reply_problems` returns one text for each point
that fails, and an empty list is a pass.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from devops_cli.k8s import searxng_check, service_probe
from devops_cli.k8s.searxng_check import OFF_ENGINES, REPLY_KEYS, SEARXNG_IMAGE, reply_problems
from tests.support.paths import FIXTURES

_KEYS = (
    "answers",
    "corrections",
    "infoboxes",
    "query",
    "results",
    "suggestions",
    "unresponsive_engines",
)
_HIT = {"url": "https://example.com/a", "title": "A", "content": "B", "engine": "duckduckgo"}


def _reply(**changes: Any) -> dict[str, Any]:
    reply: dict[str, Any] = {
        "query": "test",
        "results": [_HIT],
        "answers": [],
        "corrections": [],
        "infoboxes": [],
        "suggestions": [],
        "unresponsive_engines": [],
    }
    reply.update(changes)
    return reply


def _body(reply: object) -> bytes:
    return json.dumps(reply).encode()


def test_the_reply_keys_are_the_seven_of_the_search_api() -> None:
    assert sorted(REPLY_KEYS) == sorted(_KEYS)


def test_the_engines_that_stay_off_are_the_keyed_and_suspended_ones() -> None:
    assert sorted(OFF_ENGINES) == sorted(
        ["brave", "braveapi", "google", "bing", "startpage", "mojeek", "qwant"]
    )


def test_a_full_reply_with_a_hit_has_no_problem() -> None:
    assert reply_problems(200, _body(_reply())) == []


@pytest.mark.parametrize("key", _KEYS)
def test_a_reply_without_a_key_has_one_problem_that_names_the_key(key: str) -> None:
    reply = _reply()
    del reply[key]

    problems = reply_problems(200, _body(reply))

    assert [key in problem for problem in problems] == [True]


def test_unresponsive_engines_that_is_a_string_is_a_problem_that_names_it() -> None:
    problems = reply_problems(200, _body(_reply(unresponsive_engines="duckduckgo: timeout")))

    assert [("unresponsive_engines" in problem) for problem in problems] == [True]


def test_http_403_is_a_problem_that_names_the_search_formats_setting() -> None:
    problems = reply_problems(403, b"<html>Forbidden</html>")

    assert [("search.formats" in problem) for problem in problems] == [True]


@pytest.mark.parametrize("status", [400, 500, 502])
def test_another_status_is_a_problem_that_names_the_status(status: int) -> None:
    problems = reply_problems(status, _body(_reply()))

    assert [str(status) in problem for problem in problems] == [True]


@pytest.mark.parametrize("body", [b"not json", b"[]", b'"text"', b""])
def test_a_body_that_is_no_json_object_is_one_problem(body: bytes) -> None:
    assert len(reply_problems(200, body)) == 1


def test_a_reply_without_a_hit_is_a_problem_unless_the_caller_expects_none() -> None:
    body = _body(_reply(results=[]))

    assert (
        [("hit" in problem) for problem in reply_problems(200, body)],
        reply_problems(200, body, expect_hits=False),
    ) == ([True], [])


@pytest.mark.parametrize(
    "engine", ["google", "bing", "brave", "brave.news", "braveapi", "startpage", "mojeek", "qwant"]
)
def test_a_hit_of_an_engine_that_stays_off_is_a_problem_that_names_the_engine(engine: str) -> None:
    body = _body(_reply(results=[_HIT, {**_HIT, "engine": engine}]))

    problems = reply_problems(200, body)

    assert [engine in problem for problem in problems] == [True]


def test_an_engine_that_stays_off_and_is_listed_as_unresponsive_is_a_problem() -> None:
    body = _body(_reply(unresponsive_engines=[["bing", "CAPTCHA"], ["duckduckgo", "timeout"]]))

    problems = reply_problems(200, body)

    assert [("bing" in problem) for problem in problems] == [True]


def test_a_kept_engine_that_is_unresponsive_is_no_problem() -> None:
    body = _body(_reply(unresponsive_engines=[["duckduckgo", "timeout"]]))

    assert reply_problems(200, body) == []


def test_an_engine_that_the_caller_names_is_a_problem_in_the_hits() -> None:
    body = _body(_reply(results=[{**_HIT, "engine": "pypi"}]))

    assert (
        reply_problems(200, body),
        [("pypi" in problem) for problem in reply_problems(200, body, also_off=("pypi",))],
    ) == ([], [True])


def test_the_image_names_a_release_tag_and_its_digest() -> None:
    """The gate compares this value with the image of the Deployment, so a bump of the digest
    fails until a person runs the command against the new image."""
    assert re.fullmatch(
        r"docker\.io/searxng/searxng:\d{4}\.\d+\.\d+-[0-9a-f]{7,9}@sha256:[0-9a-f]{64}",
        SEARXNG_IMAGE,
    )


def test_the_check_uses_the_probe_code_that_crawl4ai_check_uses() -> None:
    assert (
        searxng_check.probe_from_pod is service_probe.probe_from_pod,
        searxng_check.plan_probe_from_pod is service_probe.plan_probe_from_pod,
        searxng_check.service_cluster_ip is service_probe.service_cluster_ip,
    ) == (True, True, True)


def test_the_saved_reply_is_a_live_reply_of_the_pinned_image_that_the_check_passes() -> None:
    """`search_reply.json` is a reply that the pinned image gave to `devops k8s searxng-check`
    (the first hits of the `it` row), and the file next to it names that image. A bump of the
    digest fails here until a person saves a new reply."""
    folder = FIXTURES / "searxng"
    saved = (folder / "search_reply.json").read_bytes()
    image = (folder / "search_reply_image.txt").read_text(encoding="utf-8").strip()

    assert (image, sorted(json.loads(saved)), reply_problems(200, saved)) == (
        SEARXNG_IMAGE,
        sorted(REPLY_KEYS),
        [],
    )
