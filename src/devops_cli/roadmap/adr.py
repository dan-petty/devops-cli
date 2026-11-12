"""The ADRs of a repository, as the alternatives check reads them (#3505).

An ADR is a file of `docs/adr/` named `<four digits>-<name>.md`. Its front matter holds its status
and its links to other ADRs (#5225): the keys of MADR 4 (`status`, `date`, `decision-makers`,
`consulted` and `informed`) and the keys of this project (`issue`, `tracker`, `supersedes`,
`superseded-by`, `amends`, `amended-by` and `body-hash`). An ADR with no front matter has none of
them. The check keeps the number, the title of the first level-1 heading, the front matter and the
`Considered Options` section: each ADR of the project records there the tools it chose and the
tools it rejected, and a whole ADR holds many times the tokens of its options. Only an ADR in force
reaches the check: one that is accepted, or has no status, and that no ADR supersedes. A repository
with no `docs/adr/` has no ADR, and that is no error. A front matter that does not validate stops
the read with an error that names the file.

`names` is the test of the check whether a text names a tool. The check applies it to the title and
the body of an item, and to the text of an ADR. `rejects` is the test whether an ADR rejects a tool:
only its rejected options name the tool.
"""

from __future__ import annotations

import datetime
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Any

import pydantic
import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.front_matter import front_matter_plugin
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import CONST_ROADMAP_ADR_DIRECTORY
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.roadmap.step_files import MARKDOWN, section_text
from devops_cli.roadmap.stores.store import RoadmapStore

logger = logging.getLogger(__name__)

_ADR_NAME = re.compile(r"(?P<number>\d{4})-.+\.md")
_OPTIONS_TITLE = frozenset({"considered options"})
# The last section of an ADR holds its dated status lines. It is not part of the body that an
# accepted ADR freezes (docs/adr/README.md).
_HISTORY_TITLE = "status history"
_FRONT_MATTER_TOKEN = "front_matter"
_RECORD_MARKDOWN = MarkdownIt("commonmark").use(front_matter_plugin)
# A space, `-`, `_` or `.` between the words of a tool name is one separator, so "Argo Workflows"
# names `argo-workflows`.
_SEPARATOR = r"[\s._-]+"
# An option of an ADR that the decision did not take says so: "rejected", "rejected for now" or
# "not chosen".
_REJECTED_OPTION = re.compile(r"\b(?:rejected|not chosen)\b", re.IGNORECASE)

# The number of another ADR in a link key: four digits in quotes. YAML reads an unquoted `0017` as
# the octal 15, so a strict string refuses it.
AdrNumber = Annotated[str, StringConstraints(strict=True, pattern=r"^\d{4}$")]


class AdrStatus(StrEnum):
    """The status values of MADR 4 that the project uses."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class AdrFrontMatter(BaseModel):
    """The front matter of an ADR. Each key is optional, as in MADR 4; the invariant test of the
    project asks for `status`, `date`, `decision-makers` and, after acceptance, `body-hash`. A file
    names each key by its alias, such as `superseded-by`; code can give the field name."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_by_name=True)

    status: AdrStatus | None = None
    date: datetime.date | None = None
    decision_makers: tuple[str, ...] = Field(default=(), alias="decision-makers")
    consulted: tuple[str, ...] = ()
    informed: tuple[str, ...] = ()
    issue: int | None = None
    tracker: int | None = None
    supersedes: tuple[AdrNumber, ...] = ()
    superseded_by: tuple[AdrNumber, ...] = Field(default=(), alias="superseded-by")
    amends: tuple[AdrNumber, ...] = ()
    amended_by: tuple[AdrNumber, ...] = Field(default=(), alias="amended-by")
    body_hash: str | None = Field(default=None, alias="body-hash")


@dataclass(frozen=True)
class Adr:
    """What the check keeps of one ADR: its number, its title, its `Considered Options` section
    with the heading (or no text when it has none) and its front matter."""

    number: int
    title: str
    options: str
    front_matter: AdrFrontMatter = field(default_factory=AdrFrontMatter)

    @property
    def in_force(self) -> bool:
        """Whether the ADR is accepted, or has no status, and names no ADR that supersedes it."""
        status = self.front_matter.status
        return status in {None, AdrStatus.ACCEPTED} and not self.front_matter.superseded_by

    @property
    def entry(self) -> str:
        """The ADR as the request to the model shows it: its number as four digits and its title,
        then the ADRs that amend it, then its options."""
        amended_by = ", ".join(f"ADR {number}" for number in self.front_matter.amended_by)
        return "\n".join(
            part
            for part in (
                f"ADR {self.number:04d}: {self.title}",
                f"Amended by {amended_by}." if amended_by else "",
                self.options,
            )
            if part
        )


def number_of(path: str) -> int | None:
    """The number in the file name of `path`, or None when the name is no ADR name."""
    found = _ADR_NAME.fullmatch(PurePosixPath(path).name)
    return int(found["number"]) if found else None


def _front_matter(path: str, tokens: Sequence[Token]) -> AdrFrontMatter:
    """The front matter of the ADR `path` that `tokens` start with, or no keys when it has none."""
    if not tokens or tokens[0].type != _FRONT_MATTER_TOKEN:
        return AdrFrontMatter()
    try:
        data: Any = yaml.safe_load(tokens[0].content)
        return AdrFrontMatter.model_validate(
            {} if data is None else data, by_alias=True, by_name=False
        )
    except (yaml.YAMLError, pydantic.ValidationError) as error:
        raise ValidationError(
            f"{path}: the front matter is not valid: {error}", field="front matter"
        ) from error


def _title(tokens: Sequence[Token]) -> str | None:
    """The text of the first level-1 heading of `tokens`, or None when it has none or it is
    blank."""
    for index, token in enumerate(tokens[:-1]):
        if token.type == "heading_open" and token.tag == "h1" and token.level == 0:
            return tokens[index + 1].content.strip() or None
    return None


def body_tokens(text: str) -> list[Token]:
    """The tokens of the body of the ADR `text`: every token but the front matter and the
    `Status History` section. An accepted ADR freezes this body (docs/adr/README.md)."""
    body: list[Token] = []
    history_level: int | None = None
    tokens = _RECORD_MARKDOWN.parse(text)
    for index, token in enumerate(tokens):
        if token.type == _FRONT_MATTER_TOKEN:
            continue
        if token.type == "heading_open" and token.level == 0:
            level = int(token.tag[1:])
            if history_level is not None and level <= history_level:
                history_level = None
            if history_level is None and tokens[index + 1].content.strip().casefold() == (
                _HISTORY_TITLE
            ):
                history_level = level
        if history_level is None:
            body.append(token)
    return body


def adr_of(path: str, text: str) -> Adr | None:
    """The ADR that the file `path` holds as `text`, or None when its name is no ADR name or it
    has no title. A front matter that does not validate raises `ValidationError`."""
    number = number_of(path)
    if number is None:
        return None
    tokens = _RECORD_MARKDOWN.parse(text)
    title = _title(tokens)
    if title is None:
        return None
    front_matter = _front_matter(path, tokens)
    body_start = tokens[0].map[1] if tokens[0].type == _FRONT_MATTER_TOKEN and tokens[0].map else 0
    body = "\n".join(text.splitlines()[body_start:])
    return Adr(number, title, section_text(body, _OPTIONS_TITLE), front_matter)


def read_adrs(store: RoadmapStore) -> tuple[Adr, ...]:
    """The ADRs of the repository on its default branch that are in force, the highest number
    first. An ADR that is not accepted, that names a successor or that another ADR supersedes is
    left out. A repository with no `docs/adr/` has none. Any other failed read raises, and so does a
    front matter that does not validate."""
    try:
        paths = store.repository_files(CONST_ROADMAP_ADR_DIRECTORY)
    except GitHubFileNotFoundError:
        return ()
    found = [
        adr
        for path in paths
        if number_of(path) is not None
        and (adr := adr_of(path, store.repository_file(path))) is not None
    ]
    superseded = {number for adr in found for number in adr.front_matter.supersedes}
    return tuple(
        sorted(
            (adr for adr in found if adr.in_force and f"{adr.number:04d}" not in superseded),
            key=lambda adr: -adr.number,
        )
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


def _options(text: str) -> list[str]:
    """The markdown of each item of the top-level lists of `text`: one option of an ADR each."""
    options: list[str] = []
    inside = False
    for token in MARKDOWN.parse(text):
        if token.type == "list_item_open" and token.level == 1:
            options.append("")
            inside = True
        elif token.type == "list_item_close" and token.level == 1:
            inside = False
        elif inside and token.type == "inline":
            options[-1] = f"{options[-1]}\n{token.content}".strip()
    return options


def rejects(adr: Adr, *tool_names: str) -> bool:
    """Whether `adr` rejects the tool that `tool_names` name (#4661): an option of its `Considered
    Options` that says `rejected` or `not chosen` names the tool, and neither its title nor an
    option that says neither names it. ADR 0010 names OpenSpec in rejected options, but its
    chosen option names OpenSpec too, so it rejects no OpenSpec."""
    if names(adr.title, *tool_names):
        return False
    named = [option for option in _options(adr.options) if names(option, *tool_names)]
    return bool(named) and all(_REJECTED_OPTION.search(option) for option in named)


__all__ = [
    "Adr",
    "AdrFrontMatter",
    "AdrNumber",
    "AdrStatus",
    "adr_of",
    "body_tokens",
    "fit_to_budget",
    "names",
    "number_of",
    "read_adrs",
    "rejects",
]
