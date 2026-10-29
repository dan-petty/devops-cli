"""Read the stages of a Dockerfile, for the tests that check an image offline."""

from __future__ import annotations

import shlex


def stages(dockerfile: str) -> dict[str, list[list[str]]]:
    """Each stage of a Dockerfile by name, in file order, with its instructions as shell-split words.

    A backslash at the end of a line joins it to the next; a comment line and a blank line are
    dropped. The words of `COPY --from=node ...` are `["COPY", "--from=node", ...]`.
    """
    found: dict[str, list[list[str]]] = {}
    stage: list[list[str]] = []
    joined = dockerfile.replace("\\\n", " ")
    for raw_line in joined.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        words = shlex.split(line)
        if words[0].upper() == "FROM":
            stage = found.setdefault(words[-1] if words[-2].upper() == "AS" else words[1], [])
        stage.append(words)
    return found


def env_of(stage: list[list[str]]) -> dict[str, str]:
    """The variables the ENV instructions of a stage set."""
    return dict(
        word.partition("=")[::2]
        for words in stage
        if words[0].upper() == "ENV"
        for word in words[1:]
    )
