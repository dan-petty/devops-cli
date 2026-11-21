"""One project review run: the window, its facts, and where `data.json` goes (#4686, #4692).

The run reads the git facts from the checkout, then each fact of the catalog through its reader.
Its dry run starts no program and sends no request: it lists the git commands of the run, the
shared reads and each fact of the catalog, with a placeholder for each value that a read gives.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_data_path
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.git.operations import git_argv
from devops_cli.github.repo_ref import RepoRef
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.project_review.catalog import Catalog, load_catalog, utc_text
from devops_cli.roadmap.project_review.data import Fact, FactStatus, ReviewData
from devops_cli.roadmap.project_review.dispatch import ReadContext, plan_catalog, read_catalog
from devops_cli.roadmap.project_review.facts import review_facts
from devops_cli.roadmap.project_review.git_read import (
    blob_args,
    commit_before_args,
    default_ref_args,
    diff_args,
    generated_args,
    log_args,
    tag_args,
    tag_commit_args,
)
from devops_cli.roadmap.project_review.window import (
    PeriodRequest,
    VersionRequest,
    WindowRequest,
    read_tags,
    resolve_window,
)

_FOLDER: Final = "project-review"
# The longest value that the summary of a fact shows; data.json holds the whole value.
_SHOWN_VALUE: Final = 100


def run_review(
    checkout: Path,
    repo: str,
    request: WindowRequest,
    *,
    catalog: Catalog | None = None,
    now: datetime | None = None,
) -> ReviewData:
    """The data of the window that `request` names: the git facts read from `checkout`, then the
    facts of `catalog`, the shipped catalog by default, read at `now`."""
    tags = read_tags(checkout)
    window = resolve_window(checkout, request, tags)
    facts = review_facts(checkout, window, tags)
    context = ReadContext(
        checkout=checkout,
        repo=repo,
        window=window,
        settings=load_settings(),
        now=now or datetime.now(UTC),
    )
    result = read_catalog(catalog or load_catalog(), context)
    return ReviewData(
        repo=repo,
        window=window,
        facts=[*facts, *result.facts],
        disagreements=result.disagreements,
        collection=result.collection,
    )


def review_folder(repo: str, window_id: str) -> Path:
    """The folder of one review under the data directory: `project-review/<owner>/<name>/<id>`."""
    owner, _, name = repo.partition("/")
    root = resolve_data_path(load_settings().data.dir)
    return root / _FOLDER / owner / name / window_id


def _plan_values(request: WindowRequest, repo: str | None) -> dict[str, str]:
    """The placeholders of a dry run: the times of a period, else a named placeholder for each
    value that a read gives; the repository and the slug of its name when `repo` is given."""
    texts = MESSAGES.roadmap.review_placeholders
    values = {name: texts[name] for name in ("start", "end", "range", "base", "head")}
    values["repo"] = repo or texts["repo"]
    values["name_slug"] = RepoRef(repo).name_slug if repo else texts["name_slug"]
    if isinstance(request, PeriodRequest):
        seconds = int((request.end - request.start).total_seconds())
        values |= {
            "start": utc_text(request.start),
            "end": utc_text(request.end),
            "range": f"{seconds}s",
        }
    return values


def planned_review(
    checkout: Path,
    request: WindowRequest,
    *,
    repo: str | None = None,
    catalog: Catalog | None = None,
) -> list[PlannedRequest]:
    """The git commands that a run of `request` starts, in order, then the reads of `catalog`,
    the shipped catalog by default."""
    texts = MESSAGES.roadmap.review_placeholders
    base, head = texts["base"], texts["head"]
    match request:
        case VersionRequest():
            window = [tag_commit_args(request.base_tag), tag_commit_args(request.head_tag)]
        case PeriodRequest():
            ref = texts["ref"]
            window = [
                default_ref_args(),
                commit_before_args(ref, f"@{int(request.start.timestamp())}"),
                commit_before_args(ref, f"@{int(request.end.timestamp())}"),
            ]
    each = MESSAGES.roadmap.review_plan_each_file
    steps = [
        (tag_args(), ""),
        *((args, "") for args in window),
        (log_args(base, head), ""),
        (diff_args(base, head), ""),
        (generated_args(head), ""),
        (blob_args(base, texts["path"]), each),
        (blob_args(head, texts["path"]), each),
    ]
    git = [
        PlannedRequest(
            method="git", target=str(checkout), argv=tuple(git_argv(checkout, *args)), repeat=repeat
        )
        for args, repeat in steps
    ]
    reads = plan_catalog(catalog or load_catalog(), _plan_values(request, repo), checkout)
    return [*git, *reads]


def _shown(fact: Fact) -> str:
    """The value of a fact in one short line."""
    if fact.status is not FactStatus.OK:
        return f"{fact.status}: {fact.reason}"
    text = json.dumps(fact.value, separators=(",", ":"))
    shown = text if len(text) <= _SHOWN_VALUE else f"{text[: _SHOWN_VALUE - 3]}..."
    return f"{shown} {fact.unit}"


def render_review(data: ReviewData, written: Path) -> str:
    """The window, one line for each fact, and the path of `data.json`."""
    texts = MESSAGES.roadmap
    window = data.window
    lines = [
        texts.review_window_line.format(
            id=window.id,
            kind=window.kind,
            base=window.base_sha,
            head=window.head_sha,
            start=window.start.isoformat(),
            end=window.end.isoformat(),
        ),
        texts.review_previous_line.format(id=window.previous_id or texts.review_no_previous),
        *(f"  {fact.id}: {_shown(fact)}" for fact in data.facts),
        *(
            texts.review_disagreement_line.format(
                id=pair.id,
                left=pair.left,
                left_value=pair.left_value,
                right=pair.right,
                right_value=pair.right_value,
                difference=pair.difference,
                tolerance=pair.tolerance,
            )
            for pair in data.disagreements
        ),
        texts.review_collection_line.format(
            reads=", ".join(f"{kind} {count}" for kind, count in data.collection.reads.items())
            or texts.review_no_reads,
            seconds=data.collection.seconds,
        ),
        texts.review_wrote.format(path=written),
    ]
    return "\n".join(lines)
