"""One project review run: the window, its facts, and where `data.json` goes (#4686).

The run reads the checkout only. Its dry run starts no program: it lists the git commands of the
run with a placeholder for each value that a read gives.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_data_path
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.git.operations import git_argv
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.project_review.data import Fact, FactStatus, ReviewData
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


def run_review(checkout: Path, repo: str, request: WindowRequest) -> ReviewData:
    """The data of the window that `request` names, read from `checkout`."""
    tags = read_tags(checkout)
    window = resolve_window(checkout, request, tags)
    return ReviewData(repo=repo, window=window, facts=review_facts(checkout, window, tags))


def review_folder(repo: str, window_id: str) -> Path:
    """The folder of one review under the data directory: `project-review/<owner>/<name>/<id>`."""
    owner, _, name = repo.partition("/")
    root = resolve_data_path(load_settings().data.dir)
    return root / _FOLDER / owner / name / window_id


def planned_review(checkout: Path, request: WindowRequest) -> list[PlannedRequest]:
    """The git commands that a run of `request` starts, in order."""
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
    return [
        PlannedRequest(
            method="git", target=str(checkout), argv=tuple(git_argv(checkout, *args)), repeat=repeat
        )
        for args, repeat in steps
    ]


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
        texts.review_wrote.format(path=written),
    ]
    return "\n".join(lines)
