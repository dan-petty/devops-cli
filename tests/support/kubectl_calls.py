"""Readers of the `kubectl` calls that `ProcessFake` records, so a test names a call by its verb and
its flags and not by the position of its words."""

from __future__ import annotations

from collections.abc import Sequence

from tests.support.fakes.process import ProcessFake


class RunningForward:
    """The `kubectl port-forward` child while it runs. Its pid is one that no process holds, so a
    stop of the forward signals nothing real."""

    pid = -1

    def poll(self) -> int | None:
        return None


def without_context(argv: Sequence[str]) -> list[str]:
    """`argv` without its `--context` flag and the value of the flag."""
    kept: list[str] = []
    skip = False
    for word in argv:
        if skip:
            skip = False
        elif word == "--context":
            skip = True
        elif not word.startswith("--context="):
            kept.append(word)
    return kept


def kubectl_calls(fake: ProcessFake) -> list[tuple[str, ...]]:
    """The argv of each `kubectl` call that `fake` recorded, in order."""
    return [call.argv for call in fake.calls if call.argv[:1] == ("kubectl",)]


def verb(argv: Sequence[str]) -> str:
    """The first word of a `kubectl` call that is no flag: `run`, `exec`, `delete`..."""
    return next(word for word in without_context(argv)[1:] if not word.startswith("-"))


def flag(argv: Sequence[str], name: str) -> str:
    """The value of the flag `name`, written `name value` or `name=value`."""
    words = list(argv)
    for position, word in enumerate(words):
        if word == name:
            return words[position + 1]
        if word.startswith(f"{name}="):
            return word[len(name) + 1 :]
    raise AssertionError(f"{name} is not in {words}")


def context_of(argv: Sequence[str]) -> str | None:
    """The kubeconfig context that `argv` names, or None."""
    try:
        return flag(argv, "--context")
    except AssertionError:
        return None


def namespace_of(argv: Sequence[str]) -> str:
    """The namespace of a call, from `-n` or `--namespace`."""
    for name in ("-n", "--namespace"):
        try:
            return flag(argv, name)
        except AssertionError:
            continue
    raise AssertionError(f"no namespace in {list(argv)}")


def after_separator(argv: Sequence[str]) -> list[str]:
    """The words after the first `--`: the command that runs in the pod."""
    words = list(argv)
    return words[words.index("--") + 1 :]
