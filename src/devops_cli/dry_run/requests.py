"""The external requests a command makes, as its dry run lists them without making any.

A dry run makes no external request, reads included (#412): it returns the requests the real
run would make, in order, each value that needs a read shown as a named `<placeholder>`. A
request that runs only when an earlier one returns something names that in `condition`.
"""

from __future__ import annotations

import shlex
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedRequest:
    """One external request: what runs, against what, and when. It never holds a value.

    `argv` is the exact command, `stdin` the body it sends and `env` the variables set for it,
    with a named placeholder wherever a value would go. A request without argv, such as a
    keyring call, is named by `method` and `target`.
    """

    method: str
    target: str
    argv: tuple[str, ...] = ()
    stdin: str | None = None
    env: tuple[tuple[str, str], ...] = ()
    condition: str = ""
    repeat: str = ""

    def line(self) -> str:
        """The request as one line: environment, command, then when it runs."""
        command = shlex.join(self.argv) if self.argv else f"{self.method} {self.target}"
        env = (f"{name}={shlex.quote(value)}" for name, value in self.env)
        text = " ".join([*env, command])
        if self.condition:
            text += f"  [only if {self.condition}]"
        if self.repeat:
            text += f"  [repeated {self.repeat}]"
        return text


def both(*conditions: str) -> str:
    """Conditions that must all hold, the empty ones left out."""
    return " and ".join(condition for condition in conditions if condition)


def render_request_plan(
    heading: str, requests: Sequence[PlannedRequest], notes: Sequence[str] = ()
) -> None:
    """Print the requests numbered, each body indented beneath its request, then the notes.

    Written as plain text, so a command can be copied as printed.
    """
    from devops_cli.output import write_stdout

    lines = [heading]
    for number, request in enumerate(requests, start=1):
        lines.append(f"{number:>3}. {request.line()}")
        if request.stdin is not None:
            lines.extend(f"       {body}" for body in request.stdin.splitlines())
    lines.extend(notes)
    write_stdout("\n".join(lines) + "\n")
