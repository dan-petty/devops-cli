"""The phrases that a plan declares and must quote with one text (#4039).

A plan that changes a prompt and its phrase test can quote the same rule with two texts: one in
`tasks.md`, another in `proposal.md` or a spec scenario. The static gates pass, and the
implementation then fails the phrase test. The plan check compares every code span of the change
folder with each phrase that a `("<document>", "<phrase>")` pair declares in `tasks.md`, and
reports a span that shares four consecutive words with a phrase but differs from it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from devops_cli.lang import MESSAGES


@dataclass(frozen=True)
class PhraseProblem:
    """A code span of the change folder that differs from a declared phrase."""

    path: str
    message: str


# The pair of a declared phrase: a document path and the phrase, as the plan writes it in a code
# span of `tasks.md`.
_PAIR: Final[re.Pattern[str]] = re.compile(r'\("(?P<doc>[^"]+)",\s*"(?P<phrase>[^"]+)"\)')
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`(?P<span>[^`\n]+)`")
_WORD: Final[re.Pattern[str]] = re.compile(r"[\w&.-]+")
# The count of consecutive words that make a variant of a declared phrase, not another sentence.
SHARED_WORDS: Final[int] = 4
# The artifacts of the change folder that the check reads.
_READ: Final[tuple[str, ...]] = ("proposal.md", "tasks.md")


def declared_phrases(tasks: str) -> list[str]:
    """The phrase of each `("<document>", "<phrase>")` pair of `tasks`."""
    return [found.group("phrase") for found in _PAIR.finditer(tasks)]


def _grams(words: Sequence[str]) -> set[tuple[str, ...]]:
    return {
        tuple(words[index : index + SHARED_WORDS]) for index in range(len(words) - SHARED_WORDS + 1)
    }


def _variant(span: str, phrase: str) -> bool:
    """Whether `span` shares four consecutive words with `phrase` and is not that phrase."""
    if span == phrase:
        return False
    span_words = _WORD.findall(span.lower())
    phrase_words = _WORD.findall(phrase.lower())
    return bool(_grams(span_words) & _grams(phrase_words))


def phrase_problems(files: Mapping[str, str]) -> list[PhraseProblem]:
    """The spans of the change folder that differ from a declared phrase (#4039)."""
    tasks = next(
        (text for path, text in files.items() if path.rsplit("/", 1)[-1] == "tasks.md"), ""
    )
    declared = declared_phrases(tasks)
    if not declared:
        return []
    problems: list[PhraseProblem] = []
    for path, text in files.items():
        name = path.rsplit("/", 1)[-1]
        if name not in _READ and not ("/specs/" in path and name == "spec.md"):
            continue
        for found in _CODE_SPAN.finditer(text):
            span = found.group("span")
            if _PAIR.fullmatch(span):
                continue
            phrase = next((phrase for phrase in declared if _variant(span, phrase)), None)
            if phrase is not None:
                problems.append(
                    PhraseProblem(
                        path,
                        MESSAGES.roadmap.plan_phrase_variant.format(span=span, phrase=phrase),
                    )
                )
    return problems
