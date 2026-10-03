"""The claim a person's INVALIDATED verdict suppresses, keyed so a later review finds it (#950).

A person who disproves a finding has judged one claim about one piece of code. A later review
words that claim its own way, and may raise it through another tool or persona: review session
20261002-214641 reported Semgrep's `exec` finding at a test's line 439 under Bandit's B102
title. So the claim leaves out the tool, the persona and the prose around the code, and holds:

- the project the code belongs to, so a verdict in one repository never reaches another's code,
  though the two share a data directory;
- the file, relative to the checkout holding it, so a scanner's absolute path and a persona's
  relative one name the same file;
- the first line the location cites, and a hash of the lines it cites, each stripped of
  surrounding whitespace. The line tells apart places whose code reads the same, such as two
  `except Exception as err:` handlers, which a person may judge differently. A change to those
  lines, or an edit above them that moves them, raises the claim again for a person to judge;
- the code names of those lines that the title names, or the description when the title names
  none. A language keyword or a common English word names no code, and in a file of prose or
  configuration, such as Markdown, YAML or JSON, where every word is a name in the grammar, only
  a name shaped like an identifier does: one with an underscore or a camelCase hump. A finding that
  names no code name of its lines teaches nothing, because a claim stated only in prose cannot
  be told apart from another claim about the same line.

The review records the code each finding cites when it saves the session (`CitedCode`), and a
verdict keys its claim on that record, never on the file as it reads when the verdict is given:
that may hold code the person never saw. A session saved without one teaches nothing. The cited
lines are read with secrets masked, as the review pages are, and only from a file inside the
reviewed checkout that is not a secret file: they are saved in the session and the feedback
dataset, and a model's location can name any path.
"""

from __future__ import annotations

import hashlib
import keyword
import re
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.review_schema import CitedCode, Finding, _parse_location
from devops_cli.config.constants import (
    CONST_CONFIG_EXTENSIONS,
    CONST_DOC_EXTENSIONS,
    CONST_JUDGED_CLAIM_STOP_WORDS,
)
from devops_cli.config.defaults import (
    DEFAULT_CITED_EXCERPT_MAX_LINES,
    DEFAULT_MAX_AST_FILE_SIZE_BYTES,
)
from devops_cli.core.repo import main_worktree_root
from devops_cli.security.sanitizer import mask_secrets

# A name in Python's grammar: a letter or underscore, then letters, digits or underscores. The
# identifiers of the other languages a review reads are names in it too.
_IDENTIFIER = re.compile(r"[^\W\d]\w*")
# The names that are no code name: Python's keywords and soft keywords, and common words.
_NOT_CODE_NAMES = frozenset(
    name.casefold()
    for name in (*keyword.kwlist, *keyword.softkwlist, *CONST_JUDGED_CLAIM_STOP_WORDS)
)
# A name shaped like an identifier rather than a word: it holds an underscore or a camelCase hump.
_IDENTIFIER_SHAPED = re.compile(r"_|[a-z][A-Z]")
# The files that are prose or configuration rather than code, where every word is a name.
_TEXT_SUFFIXES = CONST_DOC_EXTENSIONS | CONST_CONFIG_EXTENSIONS


class JudgedClaim(BaseModel):
    """One claim about one piece of code, as a person's verdict judged it.

    Two findings make the same claim when every field agrees, whichever tool or persona raised
    them and however they are worded.
    """

    model_config = ConfigDict(frozen=True)

    # The repository the code belongs to; it also labels the claim for that repository's reviews.
    project: str
    file: str
    line: int
    code_sha256: str
    claim: tuple[str, ...]


def project_of(path: Path) -> str:
    """The repository `path` belongs to: the name of its main checkout.

    A pull request's head, which `devops review pr` writes outside any repository, is a directory
    named after the checkout the review runs in, so it resolves to that checkout's project.
    """
    return main_worktree_root(path).name


def cited_code(location: str, file_path: Path, checkout: Path) -> CitedCode | None:
    """The code `location` cites in `file_path`, a file of the checkout rooted at `checkout`: at
    most DEFAULT_CITED_EXCERPT_MAX_LINES lines, with secrets masked.

    None when the location cites no line, or none the file holds, or the file lies outside the
    checkout.
    """
    _, start, end = _parse_location(location)
    resolved, root = file_path.resolve(), checkout.resolve()
    if start is None or start < 1 or not resolved.is_relative_to(root):
        return None
    try:
        if resolved.stat().st_size > DEFAULT_MAX_AST_FILE_SIZE_BYTES:
            return None
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if start > len(lines):
        return None
    last = min(end or start, len(lines), start + DEFAULT_CITED_EXCERPT_MAX_LINES - 1)
    return CitedCode(
        project=project_of(root),
        file=resolved.relative_to(root).as_posix(),
        line=start,
        excerpt=mask_secrets("\n".join(lines[start - 1 : last])),
    )


def judged_claim(finding: Finding, cited: CitedCode) -> JudgedClaim | None:
    """The claim `finding` makes about `cited`, the code its location cites.

    None when neither its title nor its description names a code name of that code.
    """
    names = _code_names(cited.excerpt, cited.file)
    claim = _named(finding.title, names) or _named(finding.description, names)
    if not claim:
        return None
    stripped = "\n".join(line.strip() for line in cited.excerpt.splitlines())
    return JudgedClaim(
        project=cited.project,
        file=cited.file,
        line=cited.line,
        code_sha256=hashlib.sha256(stripped.encode()).hexdigest(),
        claim=claim,
    )


def _code_names(code: str, file: str) -> list[str]:
    """The names in `code`, a part of `file`, that a claim can be keyed on."""
    names = [name for name in _IDENTIFIER.findall(code) if name.casefold() not in _NOT_CODE_NAMES]
    if PurePosixPath(file).suffix.lower() not in _TEXT_SUFFIXES:
        return names
    return [name for name in names if _IDENTIFIER_SHAPED.search(name)]


def _named(text: str, names: list[str]) -> tuple[str, ...]:
    """The identifiers among `names` that `text` names, ignoring case, in sorted order."""
    words = {word.casefold() for word in _IDENTIFIER.findall(text)}
    return tuple(sorted({name for name in names if name.casefold() in words}))
