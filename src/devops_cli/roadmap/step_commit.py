"""The title of an intermediate implementation step commit (#3351).

The title of a step commit is the Conventional Commit type and scope of the item, the title of the
task group, and one issue reference: `docs(security): Correct the Valkey paragraph (#2670)`. It
reuses `commit_type` and `commit_scope` from `commit_title.py`, so one parser decides the type and
the scope of every title of the roadmap jobs.
"""

from __future__ import annotations

from devops_cli.roadmap.commit_title import commit_scope, commit_type


def step_commit_title(item_title: str, step_title: str, item: int) -> str:
    """The title of the step commit of `step_title` for issue `item`, with the type and the scope of
    `item_title`. An item title with no Conventional Commit type gives `chore` and no scope. The
    issue reference `(#<item>)` is added once, also when `step_title` already ends with it."""
    kind = commit_type(item_title) or "chore"
    scope = commit_scope(item_title)
    head = f"{kind}({scope})" if scope else kind
    text = f"{head}: {step_title}"
    reference = f"(#{item})"
    return text if text.rstrip().endswith(reference) else f"{text} {reference}"
