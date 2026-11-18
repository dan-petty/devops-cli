"""The `gh auth token` lookup retries a timeout on a loaded host (#4940)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator

import pytest

from devops_cli.core import process
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

TOKEN_COMMAND = ["gh", "auth", "token"]


@pytest.fixture(autouse=True)
def _clean_token() -> Iterator[None]:
    process.reset_github_token()
    yield
    process.reset_github_token()


def test_a_lookup_returns_the_token_of_its_second_attempt(process_fake: ProcessFake) -> None:
    calls: list[ProcessCall] = []

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        calls.append(call)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(call.argv, 5.0)
        return subprocess.CompletedProcess(call.argv, 0, "gh-token\n", "")

    process_fake.answer(TOKEN_COMMAND, ProcessAnswer(side_effect=answer))

    assert (process._lookup_github_token(), len(process_fake.calls)) == (
        ("gh-token", ""),
        2,
    )


def test_every_attempt_that_times_out_reports_the_limit(process_fake: ProcessFake) -> None:
    process_fake.answer(
        TOKEN_COMMAND, ProcessAnswer(side_effect=subprocess.TimeoutExpired(TOKEN_COMMAND, 5.0))
    )

    token, why = process._lookup_github_token()

    assert (token, "no answer within 5 s" in why, len(process_fake.calls)) == ("", True, 2)


def test_a_missing_gh_is_not_retried(process_fake: ProcessFake) -> None:
    process_fake.answer(TOKEN_COMMAND, ProcessAnswer(side_effect=FileNotFoundError()))

    token, why = process._lookup_github_token()

    assert (token, "FileNotFoundError" in why, len(process_fake.calls)) == ("", True, 1)


def test_a_failed_gh_call_is_not_retried(process_fake: ProcessFake) -> None:
    process_fake.answer(TOKEN_COMMAND, ProcessAnswer(returncode=1))

    token, why = process._lookup_github_token()

    assert (token, bool(why), len(process_fake.calls)) == ("", True, 1)


def test_the_process_keeps_the_token_that_a_retry_found(process_fake: ProcessFake) -> None:
    calls: list[ProcessCall] = []

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        calls.append(call)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(call.argv, 5.0)
        return subprocess.CompletedProcess(call.argv, 0, "gh-token\n", "")

    process_fake.answer(TOKEN_COMMAND, ProcessAnswer(side_effect=answer))

    assert (process.github_token(), process.github_token(), len(calls)) == (
        "gh-token",
        "gh-token",
        2,
    )
