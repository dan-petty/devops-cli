"""The `openspec` reader of the project review catalog (#4692): the deltas of the changes that the
window archived, and the requirement totals at the base and at the head.

git names the files that the window added under `openspec/changes/archive/`, and `git cat-file
--batch` gives their text at the head in one read. The reader writes each archived change that
holds `specs/` into a temporary root as an active change, and `openspec show <change> --json
--deltas-only` reads its deltas there, through `isolated_openspec`, in a few workers. `git grep
-c` counts the `### Requirement:` headings under `openspec/specs` at the base and at the head. The
reader changes no file of the checkout. The git reads give text, so a test answers them from a
recorded transcript.
"""

from __future__ import annotations

import json
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from devops_cli.config.defaults import DEFAULT_ROADMAP_REVIEW_OPENSPEC_WORKERS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.git.operations import git_argv
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool, output_of
from devops_cli.roadmap.project_review.catalog import ReaderKind
from devops_cli.roadmap.project_review.git_read import query_text, run_git
from devops_cli.roadmap.project_review.readers import Reads

ARCHIVE: Final = "openspec/changes/archive"
SPECS: Final = "openspec/specs"
REQUIREMENT: Final = "^### Requirement:"
_GIT_TIMEOUT_SECONDS: Final = 300.0
# The exit code of `git grep` that finds no line.
_NO_MATCH: Final = 1


def archived_args(base: str, head: str) -> tuple[str, ...]:
    """The files that the window from `base` to `head` added under the archive of changes."""
    return ("diff", "--name-only", "-z", "--diff-filter=A", base, head, "--", f"{ARCHIVE}/")


def batch_args() -> tuple[str, ...]:
    """The text of each `<rev>:<path>` on standard input."""
    return ("cat-file", "--batch")


def requirement_args(rev: str) -> tuple[str, ...]:
    """The `### Requirement:` headings of each spec at `rev`, counted for each file."""
    return ("grep", "-c", "-E", "-e", REQUIREMENT, rev, "--", SPECS)


def show_args(change: str) -> tuple[str, ...]:
    """The deltas of the active change `change`, as JSON."""
    return ("show", change, "--json", "--deltas-only", "--no-interactive")


@dataclass(frozen=True)
class ArchivedChange:
    """A change that the window archived: its folder name and the text of each of its files, by
    the path under the folder."""

    name: str
    files: Mapping[str, str]


def _blobs(text: str) -> list[str | None]:
    """The text of each object of a `git cat-file --batch` answer, in order; None for a missing
    one. The size of an object is in bytes, so the answer is read as bytes."""
    data = text.encode("utf-8")
    found: list[str | None] = []
    at = 0
    while at < len(data):
        end = data.index(b"\n", at)
        header = data[at:end].split(b" ")
        at = end + 1
        if header[-1] == b"missing":
            found.append(None)
            continue
        size = int(header[2])
        found.append(data[at : at + size].decode("utf-8"))
        at += size + 1
    return found


def archived_changes(checkout: Path, base: str, head: str) -> list[ArchivedChange]:
    """Each change that the window archived and that holds `specs/`, by folder name, with the
    text of its files at `head`."""
    names = [name for name in run_git(checkout, archived_args(base, head)).split("\0") if name]
    by_change: dict[str, list[str]] = defaultdict(list)
    for name in names:
        parts = PurePosixPath(name).relative_to(ARCHIVE).parts
        if len(parts) >= 2:
            by_change[parts[0]].append("/".join(parts[1:]))
    kept = {
        change: sorted(files)
        for change, files in by_change.items()
        if any(path.startswith("specs/") for path in files)
    }
    wanted = [f"{ARCHIVE}/{change}/{path}" for change, files in kept.items() for path in files]
    if not wanted:
        return []
    stdin = "".join(f"{head}:{path}\n" for path in wanted)
    texts = iter(_blobs(run_git(checkout, batch_args(), stdin=stdin)))
    changes: list[ArchivedChange] = []
    for change, files in sorted(kept.items()):
        held = {path: text for path in files if (text := next(texts)) is not None}
        changes.append(ArchivedChange(change, held))
    return changes


def requirement_total(checkout: Path, rev: str) -> int:
    """The `### Requirement:` headings under `openspec/specs` at `rev`; 0 when none."""
    args = requirement_args(rev)
    done = run_subprocess(
        git_argv(checkout, *args), quiet=True, local_read=True, timeout=_GIT_TIMEOUT_SECONDS
    )
    if done.returncode == _NO_MATCH and not (done.stdout or "").strip():
        return 0
    if done.returncode != 0:
        error = (done.stderr or "").strip().splitlines()
        raise RoadmapReviewError(
            MESSAGES.roadmap.review_git_failed.format(
                command=query_text(args), error=error[0] if error else done.returncode
            )
        )
    return sum(int(line.rpartition(":")[2]) for line in (done.stdout or "").splitlines() if line)


def _deltas(answer: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "spec": delta.get("spec"),
            "operation": delta.get("operation"),
            "requirement": (delta.get("requirement") or {}).get("name"),
        }
        for delta in answer.get("deltas", [])
    ]


def _refusal(run: Any) -> str:
    """Why `openspec show` refused a change: the messages of its JSON status, else the first
    line of its output."""
    try:
        status = json.loads(run.stdout or "").get("status", [])
        messages = [str(entry["message"]) for entry in status if "message" in entry]
    except ValueError, AttributeError, TypeError, KeyError:
        messages = []
    if messages:
        return "; ".join(messages)
    lines = (output_of(run) or "").strip().splitlines()
    return lines[0] if lines else f"exit code {run.returncode}"


def _show(tool: OpenSpecTool, change: str, root: Path) -> dict[str, Any] | str:
    """The JSON of `openspec show` for `change`, or the reason when the tool refuses it. A
    change that the tool cannot parse, such as a proposal with no Why section, is data of the
    review, so the other changes are still read."""
    run = tool.run(show_args(change), root)
    if run.returncode != 0:
        return _refusal(run)
    try:
        answer: dict[str, Any] = json.loads(run.stdout)
    except ValueError as error:
        raise RoadmapReviewError(
            MESSAGES.roadmap.review_openspec_not_json.format(change=change, text=run.stdout[:128])
        ) from error
    return answer


def _shown(
    checkout: Path, changes: Sequence[ArchivedChange]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """The deltas of each change, read by `openspec show` in a temporary root, and each change
    that the tool refused with its reason."""
    from devops_cli.openspec.tool import isolated_openspec

    with tempfile.TemporaryDirectory(prefix="project-review-openspec-") as scratch:
        root = Path(scratch)
        for change in changes:
            for path, text in change.files.items():
                target = root / "openspec" / "changes" / change.name / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
        with (
            isolated_openspec(checkout) as tool,
            ThreadPoolExecutor(DEFAULT_ROADMAP_REVIEW_OPENSPEC_WORKERS) as pool,
        ):
            answers = list(pool.map(lambda change: _show(tool, change.name, root), changes))
    shown = [
        {"id": change.name, "deltas": _deltas(answer)}
        for change, answer in zip(changes, answers, strict=True)
        if not isinstance(answer, str)
    ]
    unread = [
        {"id": change.name, "reason": answer}
        for change, answer in zip(changes, answers, strict=True)
        if isinstance(answer, str)
    ]
    return shown, unread


def read_openspec(checkout: Path, base: str, head: str, reads: Reads) -> dict[str, Any]:
    """The deltas of each change that the window archived, each change that `openspec show`
    refused with its reason, and the requirement totals at the base and at the head, as
    `{"changes": [{"id", "deltas"}], "unread": [{"id", "reason"}], "requirements": {"base",
    "head"}}`."""
    changes = archived_changes(checkout, base, head)
    reads.add(ReaderKind.OPENSPEC, len(changes))
    shown, unread = _shown(checkout, changes) if changes else ([], [])
    return {
        "changes": shown,
        "unread": unread,
        "requirements": {
            "base": requirement_total(checkout, base),
            "head": requirement_total(checkout, head),
        },
    }
