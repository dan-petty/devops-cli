"""The rules of the decision records of `docs/adr/` (#5225), as `docs/adr/README.md` gives them.

The body of a record is its text with no front matter and no `Status History` section
(`devops_cli.roadmap.adr.body_tokens`). Its hash leaves out the target of each link and image, so a
fix of a broken link keeps the hash, and every other edit of an accepted body changes it. The hash
reads the tokens of markdown-it-py, so a release of the parser that tokenizes a body another way
changes the hash of that body too.

`render_index` gives the index table of the README from the front matter of each record, and
`sync_index` puts it between the markers of the README for `devops docs generate`.
`record_problems` gives each break of a rule, for the invariant test of the repository.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Final

from markdown_it.token import Token

from devops_cli.exceptions.validation import ValidationError
from devops_cli.roadmap.adr import Adr, AdrStatus, adr_of, body_tokens, number_of
from devops_cli.roadmap.body_hash import hash_text

# The README of `docs/adr/`, by its path under `docs/`, and the markers of its generated index.
ADR_INDEX_PAGE: Final = "adr/README.md"
ADR_INDEX_START: Final = "<!-- ADR_INDEX_START -->"
ADR_INDEX_END: Final = "<!-- ADR_INDEX_END -->"
# The limits of length apply to each record after the last one that the rules found (#5225).
_LAST_RECORD_BEFORE_RULES: Final = 25
_MAX_BODY_WORDS: Final = 1000
_MAX_TITLE_WORDS: Final = 10
_MAX_SLUG_CHARACTERS: Final = 60
# A record names the roles that decided it, never a person.
_ROLES: Final = frozenset({"owner"})
# Each link key of the front matter and the key of the other record that names this one back.
_LINK_KEYS: Final[tuple[tuple[str, str], ...]] = (
    ("supersedes", "superseded_by"),
    ("superseded_by", "supersedes"),
    ("amends", "amended_by"),
    ("amended_by", "amends"),
)
_INDEX_HEAD: Final = (
    "| Record | Title | Status | Date | Links |",
    "| :--- | :--- | :--- | :--- | :--- |",
)


def read_record_texts(directory: Path) -> dict[str, str]:
    """The text of each file of `directory` that has the name of a record, by its file name."""
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(directory.glob("*.md"))
        if number_of(path.name) is not None
    }


def _canonical(tokens: Sequence[Token]) -> Iterator[str]:
    """One line for each token and each inline child: its type, its tag and its content. The
    attributes, and so the target of a link or an image, are left out."""
    for token in tokens:
        if token.type == "inline":
            yield from (f"{child.type}:{child.content}" for child in token.children or ())
        else:
            yield f"{token.type}:{token.tag}:{token.content}"


def body_hash(text: str) -> str:
    """The SHA-256 of the body of the record `text`, with no link target."""
    return hash_text("\n".join(_canonical(body_tokens(text))))


def _body_words(text: str) -> int:
    """The words of the body of the record `text` after its title: its prose and its code."""
    words = 0
    in_title = False
    for token in body_tokens(text):
        if token.type in {"heading_open", "heading_close"} and token.tag == "h1":
            in_title = token.type == "heading_open"
        elif token.type == "inline" and not in_title:
            words += sum(len(child.content.split()) for child in token.children or ())
        elif token.type in {"fence", "code_block", "html_block"}:
            words += len(token.content.split())
    return words


def _links(adr: Adr) -> str:
    """The links of `adr` to other records, as the index shows them."""
    front_matter = adr.front_matter
    return "; ".join(
        f"{label} {', '.join(numbers)}"
        for label, numbers in (
            ("supersedes", front_matter.supersedes),
            ("superseded by", front_matter.superseded_by),
            ("amends", front_matter.amends),
            ("amended by", front_matter.amended_by),
        )
        if numbers
    )


def _records(texts: Mapping[str, str]) -> list[tuple[str, Adr]]:
    """Each record of `texts` with its file name, the lowest number first."""
    found = [(name, adr) for name, text in texts.items() if (adr := adr_of(name, text))]
    return sorted(found, key=lambda pair: pair[1].number)


def render_index(texts: Mapping[str, str]) -> str:
    """The index table of the records of `texts` (file name to text): one row for each record with
    its number, its title, its status, its date and its links."""
    rows = [
        f"| [{adr.number:04d}]({name}) | {adr.title.replace('|', chr(92) + '|')} | "
        f"{adr.front_matter.status or ''} | {adr.front_matter.date or ''} | {_links(adr)} |"
        for name, adr in _records(texts)
    ]
    return "\n".join((*_INDEX_HEAD, *rows))


def sync_index(page: str, texts: Mapping[str, str]) -> str | None:
    """`page` with the index of the records of `texts` between its markers, or None when it has
    no markers."""
    head, start, rest = page.partition(ADR_INDEX_START)
    _, end, tail = rest.partition(ADR_INDEX_END)
    if not start or not end:
        return None
    return f"{head}{ADR_INDEX_START}\n\n{render_index(texts)}\n\n{ADR_INDEX_END}{tail}"


def _link_problems(name: str, adr: Adr, numbers: Mapping[str, Adr]) -> Iterator[str]:
    """A problem for each link of `adr` to a record that does not exist or does not link back."""
    own = f"{adr.number:04d}"
    for key, back in _LINK_KEYS:
        for number in getattr(adr.front_matter, key):
            other = numbers.get(number)
            if other is None:
                yield f"{name}: {_key(key)} names ADR {number}, which does not exist."
            elif own not in getattr(other.front_matter, back):
                yield (
                    f"{name}: {_key(key)} names ADR {number}, and ADR {number} has no "
                    f"{_key(back)} link back."
                )


def _key(field: str) -> str:
    """The front matter key of the field `field`."""
    return field.replace("_", "-")


def _length_problems(name: str, adr: Adr, text: str) -> Iterator[str]:
    """A problem for each limit of length that a record after the rules breaks."""
    words = _body_words(text)
    if words > _MAX_BODY_WORDS:
        yield f"{name}: the body has {words} words, more than {_MAX_BODY_WORDS}."
    title_words = len(adr.title.split())
    if title_words > _MAX_TITLE_WORDS:
        yield f"{name}: the title has {title_words} words, more than {_MAX_TITLE_WORDS}."
    slug = name.removesuffix(".md").partition("-")[2]
    if len(slug) > _MAX_SLUG_CHARACTERS:
        yield f"{name}: the slug has {len(slug)} characters, more than {_MAX_SLUG_CHARACTERS}."


def _key_problems(name: str, adr: Adr) -> Iterator[str]:
    """A problem for each key that the front matter of `adr` lacks or holds in a wrong form."""
    front_matter = adr.front_matter
    if front_matter.status is None:
        yield f"{name}: the front matter has no status."
    if front_matter.date is None:
        yield f"{name}: the front matter has no date."
    if not front_matter.decision_makers:
        yield f"{name}: the front matter has no decision-makers."
    for person in sorted(set(front_matter.decision_makers) - _ROLES):
        yield f"{name}: decision-makers holds a name that is not a role: {person}."
    if front_matter.status is AdrStatus.SUPERSEDED and not front_matter.superseded_by:
        yield f"{name}: the status is superseded, and superseded-by names no record."
    if front_matter.superseded_by and front_matter.status is not AdrStatus.SUPERSEDED:
        yield f"{name}: superseded-by names a record, and the status is {front_matter.status}."


def _hash_problems(name: str, adr: Adr, text: str) -> Iterator[str]:
    """A problem when a record after its acceptance has no body hash or another body."""
    if adr.front_matter.status in {None, AdrStatus.PROPOSED}:
        return
    found = body_hash(text)
    if adr.front_matter.body_hash is None:
        yield f"{name}: the front matter has no body-hash: the hash of the body is {found}."
    elif adr.front_matter.body_hash != found:
        yield f"{name}: the body changed after acceptance: its hash is {found}."


def _record_problems(name: str, adr: Adr, text: str, numbers: Mapping[str, Adr]) -> Iterator[str]:
    """Each rule of `docs/adr/README.md` that the record `adr` in the file `name` breaks."""
    yield from _key_problems(name, adr)
    yield from _link_problems(name, adr, numbers)
    yield from _hash_problems(name, adr, text)
    if adr.number > _LAST_RECORD_BEFORE_RULES:
        yield from _length_problems(name, adr, text)


def record_problems(texts: Mapping[str, str]) -> list[str]:
    """Each rule of `docs/adr/README.md` that a record of `texts` (file name to text) breaks, as one
    line that names the file. No line means that every record keeps the rules."""
    problems: list[str] = []
    records: list[tuple[str, Adr]] = []
    for name, text in sorted(texts.items()):
        try:
            adr = adr_of(name, text)
        except ValidationError as error:
            problems.append(str(error))
            continue
        if adr is None:
            problems.append(f"{name}: the file has the name of a record and no title.")
            continue
        records.append((name, adr))
    numbers = {f"{adr.number:04d}": adr for _, adr in records}
    for name, adr in records:
        problems.extend(_record_problems(name, adr, texts[name], numbers))
    return problems


__all__ = [
    "ADR_INDEX_END",
    "ADR_INDEX_PAGE",
    "ADR_INDEX_START",
    "body_hash",
    "read_record_texts",
    "record_problems",
    "render_index",
    "sync_index",
]
