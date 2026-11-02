"""Build the title and the body of the pull request that delivers an issue (#3198).

`devops pr describe` reads three things: the issue, for the type and the scope of the title; the
change folder of the issue, for the "why" of the body and the `Change:` line; and the labels file,
for the scopes. The rules are those of `pull_form`: this module only reads and joins. It cuts no
text, so a summary or a "why" that is too long is refused and the caller writes a shorter one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError as PydanticValidationError

from devops_cli.config.constants import (
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_LABELS_PATH,
)
from devops_cli.exceptions import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import pull_labels
from devops_cli.roadmap.pull_form import build_body, build_title
from devops_cli.roadmap.step_files import section_text
from devops_cli.roadmap.store import RoadmapStore
from devops_cli.roadmap.title_labels import declared_label_names

_WHY_HEADINGS: Final[frozenset[str]] = frozenset({"why"})
_PROPOSAL: Final[str] = "proposal.md"


@dataclass(frozen=True)
class ChangeFolder:
    """The change folder of an issue: the path that the `Change:` line names (the archive folder,
    with the date of `today` when the change is not archived yet), the folder that holds the files
    now, and whether the change is archived."""

    path: str
    folder: Path
    archived: bool


@dataclass(frozen=True)
class Described:
    """The title and the body of a pull request, and whether the date of the archive in its
    `Change:` line is the date of today and not yet the date of an archive."""

    title: str
    body: str
    dated_today: bool = False


def find_change(root: Path, issue: int, *, today: date) -> ChangeFolder:
    """The change folder of `issue` under the checkout `root`: the archived one, else the active
    one. No folder, or more than one of the same kind, raises `ValidationError`."""
    texts = MESSAGES.pr
    archive = root / CONST_OPENSPEC_ARCHIVE_DIR
    pattern = f"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-{issue}-*"
    archived = sorted(p for p in archive.glob(pattern) if p.is_dir())
    active = sorted(p for p in (root / CONST_OPENSPEC_CHANGES_DIR).glob(f"{issue}-*") if p.is_dir())
    found = archived or active
    if not found:
        raise ValidationError(
            texts.describe_no_change.format(
                issue=issue, pattern=f"{CONST_OPENSPEC_CHANGES_DIR}/{issue}-*"
            ),
            field="issue",
        )
    if len(found) > 1:
        raise ValidationError(
            texts.describe_many_changes.format(issue=issue, names=", ".join(p.name for p in found)),
            field="issue",
        )
    folder = found[0]
    if archived:
        return ChangeFolder(f"{CONST_OPENSPEC_ARCHIVE_DIR}/{folder.name}", folder, True)
    return ChangeFolder(
        f"{CONST_OPENSPEC_ARCHIVE_DIR}/{today.isoformat()}-{folder.name}", folder, False
    )


def proposal_why(change: ChangeFolder) -> str:
    """The "why" of the proposal of `change` on one line, with a handle or a link in a code span
    so it pings no one. A proposal with no section `Why` raises `ValidationError`."""
    from devops_cli.roadmap.stage_change import closing_keyword_in, safe_text

    proposal = change.folder / _PROPOSAL
    section = (
        section_text(proposal.read_text(encoding="utf-8"), _WHY_HEADINGS)
        if proposal.is_file()
        else ""
    )
    text = safe_text(section.partition("\n")[2])
    if not text:
        raise ValidationError(
            MESSAGES.pr.describe_no_why.format(path=f"{change.path}/{_PROPOSAL}"), field="why"
        )
    if closing_keyword_in(text) is not None:
        raise ValidationError(MESSAGES.pr.describe_why_closes, field="why")
    return text


def declared_label_set(
    store: RoadmapStore, *, ref: str | None, checkout: Path | None
) -> tuple[str, ...]:
    """The label names that the repository declares in `.github/labels.yml` on `ref`, and, when
    `checkout` is given and holds the file, those of the file there. A pull request that adds a
    scope also adds its label, so the label is in the checkout and not yet on the base branch.
    A file that cannot be read raises `GitHubOperationError` (the base) or `ValidationError` (the
    checkout), and both name the file."""
    names = list(pull_labels.declared_labels(store, ref=ref))
    local = checkout / CONST_ROADMAP_LABELS_PATH if checkout is not None else None
    if local is not None and local.is_file():
        try:
            names += declared_label_names(local.read_text(encoding="utf-8"))
        except (yaml.YAMLError, PydanticValidationError) as exc:
            raise ValidationError(
                MESSAGES.pr.labels_unreadable.format(
                    path=CONST_ROADMAP_LABELS_PATH, error=str(exc)[:200]
                ),
                field="labels",
            ) from exc
    return tuple(dict.fromkeys(names))


def describe_pull(
    store: RoadmapStore,
    *,
    repo: str,
    root: Path,
    issue: int,
    summary: str,
    why: str | None = None,
    attribution: Sequence[str] = (),
    today: date,
    local_labels: bool = True,
) -> Described:
    """The title and the body of the pull request that delivers `issue` of `repo`, which `store`
    reads.

    The type and the scope of the title come from the title of the issue, and its summary is
    `summary`. The body is `why` (the section `Why` of the proposal when None), `Closes #<issue>`,
    the `Change:` line, and the paragraphs `attribution`. `local_labels` adds the labels file of the
    checkout `root` to the scopes. Every refusal is a `ValidationError` that names each problem."""
    item = store.item(issue)
    if item is None:
        raise ValidationError(
            MESSAGES.pr.describe_no_item.format(issue=issue, repo=repo), field="issue"
        )
    change = find_change(root, issue, today=today)
    declared = declared_label_set(store, ref=None, checkout=root if local_labels else None)
    title = build_title(item.title, summary, declared)
    body = build_body(
        why=why if why is not None else proposal_why(change),
        issue=issue,
        change=change.path,
        attribution=attribution,
    )
    return Described(title, body, dated_today=not change.archived)
