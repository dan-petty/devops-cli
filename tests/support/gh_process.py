"""The `gh` program as a command test reaches it: through `process_fake`, with a fresh quota
(#4085).

The rate limiter reads `gh api rate_limit` before it lets a `gh` command start, so a command test
that scripts a `gh` answer also needs a fresh quota. `gh_edge` records one in the limiter, sends
the limiter's waits to the `clock` fixture (#4666), and returns the `ProcessFake` the test scripts
the rest on. `answer_origin` answers the origin remote of the
working directory, which the commands read to find the repository when `--repo` is not given.
`gh_argv` lists the `gh` commands the fake saw, without the quota reads.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from tests.support.fakes.clock import ClockFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_RESOURCES = ("core", "graphql", "search")


def fresh_quota() -> None:
    """Record a fresh quota in the rate limiter's ledger, so no pacing runs `gh api rate_limit`."""
    from devops_cli.github.rate_limiter import get_github_rate_limiter

    limiter = get_github_rate_limiter()
    for resource in _RESOURCES:
        limiter.update_quota(resource, remaining=5000, limit=5000, reset_epoch=time.time() + 600.0)


@pytest.fixture
def gh_edge(process_fake: ProcessFake, clock: ClockFake) -> ProcessFake:
    """`process_fake`, with a fresh quota in the rate limiter's ledger, so a test may script any
    `gh api` answer. The rate limiter's waits, such as the interval between two gh writes, go to
    `clock`, so they take no real time; a test that reads them requests `clock` too."""
    fresh_quota()
    return process_fake


def answer_origin(fake: ProcessFake, repo: str) -> None:
    """Answer the origin remote of the working directory with the GitHub repository `repo`."""
    fake.answer(
        ["git", "remote", "get-url", "origin"],
        ProcessAnswer(stdout=f"git@github.com:{repo}.git\n"),
    )


def mentions(*words: str) -> Callable[[ProcessCall], bool]:
    """A matcher for a `gh` command whose arguments hold every one of `words` as part of an
    argument, such as the name of a GraphQL query."""

    def matches(call: ProcessCall) -> bool:
        return call.argv[:1] == ("gh",) and all(
            any(word in arg for arg in call.argv[1:]) for word in words
        )

    return matches


def gh_argv(fake: ProcessFake) -> list[list[str]]:
    """The arguments of each `gh` command the fake saw, in order, without the quota reads."""
    return [
        list(call.argv[1:])
        for call in fake.calls
        if call.argv[:1] == ("gh",) and call.argv[1:3] != ("api", "rate_limit")
    ]


def answer_gh(
    fake: ProcessFake, *prefix: str, stdout: str = "", stderr: str = "", returncode: int = 0
) -> None:
    """Answer each `gh` command that starts with `prefix` (every `gh` command when none is given)."""
    fake.answer(["gh", *prefix], ProcessAnswer(returncode=returncode, stdout=stdout, stderr=stderr))


def script_gh(fake: ProcessFake, *replies: ProcessAnswer) -> None:
    """Answer the `gh` commands one after another with `replies`; a command past the last reply
    fails the test."""
    pending = iter(replies)

    def next_reply(call: ProcessCall) -> ProcessAnswer:
        try:
            return next(pending)
        except StopIteration:
            pytest.fail(f"no scripted answer is left for `{' '.join(call.argv)}`", pytrace=False)

    fake.answer(lambda call: call.argv[:1] == ("gh",), next_reply)
