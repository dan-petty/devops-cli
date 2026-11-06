"""The ADRs of a repository, as the alternatives check reads them (#3505).

An ADR is a file of `docs/adr/` named `<four digits>-<name>.md`. The check keeps its number, the
title of its first level-1 heading, the status paragraphs under that title and its
`Considered Options` section: each ADR of the project records there the tools it chose and the
tools it rejected, and a whole ADR holds many times the tokens of its options. An ADR that a later
ADR supersedes is not in force, so the check drops it. A repository with no `docs/adr/` has no ADR,
and that is no error.

`names` is the test of the check whether a text names a tool. The check applies it to the title and
the body of an item, and to the text of an ADR.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from markdown_it.token import Token

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import CONST_ROADMAP_ADR_DIRECTORY
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.roadmap.step_files import MARKDOWN, section_text
from devops_cli.roadmap.store import RoadmapStore

logger = logging.getLogger(__name__)

_ADR_NAME = re.compile(r"(?P<number>\d{4})-.+\.md")
_OPTIONS_TITLE = frozenset({"considered options"})
# A status paragraph names another ADR and says that it supersedes or amends. The ADRs of the
# project have no structured status field, so the paragraphs right under the title are the status.
_STATUS_VERB = re.compile(r"\b(?:supersede[sd]?|amend(?:s|ed)?)\b", re.IGNORECASE)
_ADR_REFERENCE = re.compile(r"\bADR \d{4}\b")
# An ADR that another one supersedes in whole says so in its own note, "ADR 0015 supersedes this
# ADR.", and the later ADR says "ADR 0015 supersedes ADR 0002.". A partial supersession, such as
# "supersedes the webhook clause of ADR 0003", matches neither form.
_SUPERSEDED_BY = re.compile(r"\bADR (?P<number>\d{4}) supersedes this ADR\b")
_SUPERSEDES = re.compile(r"\bsupersedes ADR (?P<number>\d{4})\b")
# A space, `-`, `_` or `.` between the words of a tool name is one separator, so "Argo Workflows"
# names `argo-workflows`.
_SEPARATOR = r"[\s._-]+"


@dataclass(frozen=True)
class Adr:
    """What the check keeps of one ADR: its number, its title, its status paragraphs as plain text
    (a line for each paragraph, or no text when it has none) and its `Considered Options` section
    with the heading (or no text when it has none)."""

    number: int
    title: str
    options: str
    status: str = ""

    @property
    def entry(self) -> str:
        """The ADR as the request to the model shows it: its number as four digits and its title,
        then its status lines, then its options."""
        return "\n".join(
            part
            for part in (f"ADR {self.number:04d}: {self.title}", self.status, self.options)
            if part
        )


def _number_of(path: str) -> int | None:
    """The number in the file name of `path`, or None when the name is no ADR name."""
    found = _ADR_NAME.fullmatch(PurePosixPath(path).name)
    return int(found["number"]) if found else None


def _plain(inline: Token) -> str:
    """The text of an inline token with the marks of the markdown taken away: a link is its text."""
    return "".join(
        " " if child.type in {"softbreak", "hardbreak"} else child.content
        for child in inline.children or ()
        if child.type in {"text", "code_inline", "softbreak", "hardbreak"}
    )


def _title_and_status(tokens: Sequence[Token]) -> tuple[str, str] | None:
    """The text of the first level-1 heading of `tokens`, and the status under it, or None when it
    has no such heading. The status is each paragraph straight after the heading that names an ADR
    and says that it supersedes or amends, up to the first block that is not one."""
    for index, token in enumerate(tokens[:-1]):
        if token.type == "heading_open" and token.tag == "h1" and token.level == 0:
            title = tokens[index + 1].content.strip()
            if not title:
                return None
            break
    else:
        return None
    notes: list[str] = []
    position = index + 3
    while position + 1 < len(tokens) and tokens[position].type == "paragraph_open":
        note = _plain(tokens[position + 1]).strip()
        if not (_ADR_REFERENCE.search(note) and _STATUS_VERB.search(note)):
            break
        notes.append(note)
        position += 3
    return title, "\n".join(notes)


def adr_of(path: str, text: str) -> Adr | None:
    """The ADR that the file `path` holds as `text`, or None when its name is no ADR name or it
    has no title."""
    number = _number_of(path)
    head = _title_and_status(MARKDOWN.parse(text))
    if number is None or head is None:
        return None
    title, status = head
    return Adr(number, title, section_text(text, _OPTIONS_TITLE), status)


def _superseded(adrs: Iterable[Adr]) -> set[int]:
    """The numbers of the ADRs that a later ADR supersedes in whole, as either of the two ADRs says
    so in its status."""
    numbers: set[int] = set()
    for adr in adrs:
        numbers.update(
            adr.number
            for found in _SUPERSEDED_BY.finditer(adr.status)
            if int(found["number"]) > adr.number
        )
        numbers.update(
            int(found["number"])
            for found in _SUPERSEDES.finditer(adr.status)
            if int(found["number"]) < adr.number
        )
    return numbers


def read_adrs(store: RoadmapStore) -> tuple[Adr, ...]:
    """The ADRs of the repository on its default branch that are in force, the highest number
    first. An ADR that a later ADR supersedes is left out. A repository with no `docs/adr/` has
    none. Any other failed read raises."""
    try:
        paths = store.repository_files(CONST_ROADMAP_ADR_DIRECTORY)
    except GitHubFileNotFoundError:
        return ()
    found = [
        adr
        for path in paths
        if _number_of(path) is not None
        and (adr := adr_of(path, store.repository_file(path))) is not None
    ]
    superseded = _superseded(found)
    return tuple(
        sorted((adr for adr in found if adr.number not in superseded), key=lambda adr: -adr.number)
    )


def fit_to_budget(adrs: Sequence[Adr], *, max_tokens: int) -> tuple[Adr, ...]:
    """The entries of `adrs`, in their order, whose text joined by blank lines holds at most
    `max_tokens` tokens. The cut takes whole entries: an entry that does not fit is left out, and
    a later entry that fits stays. A warning names each ADR that the cut leaves out."""
    kept: list[Adr] = []
    left_out: list[Adr] = []
    text = ""
    for adr in adrs:
        joined = f"{text}\n\n{adr.entry}" if text else adr.entry
        if count_tokens(joined) <= max_tokens:
            kept.append(adr)
            text = joined
        else:
            left_out.append(adr)
    if left_out:
        logger.warning(
            "The ADRs of the repository do not fit the cap of %d tokens: the alternatives check "
            "leaves out %s.",
            max_tokens,
            ", ".join(f"ADR {adr.number:04d}" for adr in left_out),
        )
    return tuple(kept)


def _spans(text: str) -> tuple[list[str], list[str]]:
    """The prose of `text` and its marked spans: the code spans, the text and the target of each
    link, and the text in strong emphasis. A fenced block is prose."""
    prose: list[str] = []
    marked: list[str] = []
    for token in MARKDOWN.parse(text):
        if token.type in {"fence", "code_block"}:
            prose.append(token.content)
        if token.type != "inline":
            continue
        depth = 0
        for child in token.children or ():
            if child.type in {"strong_open", "link_open"}:
                depth += 1
                marked.append(str(child.attrGet("href") or ""))
            elif child.type in {"strong_close", "link_close"}:
                depth -= 1
            elif child.type == "code_inline":
                marked.append(child.content)
            elif child.type == "text":
                (marked if depth else prose).append(child.content)
    return prose, marked


def _whole(word: str) -> re.Pattern[str]:
    """The pattern of `word` as a whole word: a letter, a digit, `_` or `-` next to it means it is
    part of a longer word, so `pytest-cov` does not name `pytest`."""
    return re.compile(rf"(?<![\w-]){word}(?![\w-])", re.IGNORECASE)


def names(text: str, *tool_names: str) -> bool:
    """Whether `text` names a tool by one of `tool_names`, each a repository (`owner/name`), a
    package name or the name that a person writes for the tool. Case does not matter, and a space,
    `-`, `_` or `.` is one separator. A name of two words or more, such as `argo-workflows`, names
    the tool anywhere in the text. A name of one word, such as `just` or `task`, is also a word of
    prose, so it names the tool only in a code span, in a link or in strong emphasis; the full
    `owner/name` names it anywhere."""
    prose, marked = _spans(text)
    anywhere = [*prose, *marked]
    for name in filter(None, tool_names):
        owner, _, short = name.rpartition("/")
        if owner and short and any(_whole(re.escape(name)).search(span) for span in anywhere):
            return True
        words = [re.escape(word) for word in re.split(_SEPARATOR, short) if word]
        spans = anywhere if len(words) > 1 else marked
        if words and any(_whole(_SEPARATOR.join(words)).search(span) for span in spans):
            return True
    return False


__all__ = ["Adr", "adr_of", "fit_to_budget", "names", "read_adrs"]
