# Design

## Decisions
- **Title at first verdict label**: Order `timelineItems` events (`LABELED_EVENT` and `RENAMED_TITLE_EVENT`). For the first verdict label event at index `i`, take `previous_title` of the earliest `RENAMED_TITLE_EVENT` after `i` (or `node.title` if none follows `i`) so pre-rename labels use the prior title and post-rename labels use the renamed title. When a PR has no verdict label event, use `node.title`.
- **Single-page timeline guard**: Add `pageInfo { hasNextPage }` to `timelineItems` (defaulting to `False` in Pydantic when omitted by older mocks) and raise `GitHubUnreadError` naming the PR number and timeline page limit when true.
- **Loki row isolation on GitHub failure**: Add `GradeReport.verdict_error: str | None = None`. Catch `GitHubUnreadError` in `grade_report` and store `str(exc)` so `render_grade_report` renders `verdicts not read: <reason>` while preserving all Loki workflow rows and JSON output.
- **Single `FIX_PLAN_LABEL` source without startup penalty**: Define `FIX_PLAN_LABEL = "verdict/fix-plan"` in `workflow_labels.py` and re-export it from `stage_verify.py` (`__all__` unchanged). Importing `stage_verify.py` directly in `phase.py` loads `pydantic_ai` during `devops gh --help` (via `github/metrics.py`), and importing it in `workflow_labels.py` or `failure.py` causes a circular import.

## Rejected alternatives
- **Current title or initial title for every event**: Using current title loses pre-rename stage verdicts; forcing initial title on post-rename delivery verdicts misattributes implement verdicts to stage.
- **Keep literal `"verdict/fix-plan"` in `stage_verify.py` alone**: Impossible without lazy imports in `phase.py` and circular imports in `workflow_labels.py`/`failure.py`.
- **Paginate nested `timelineItems`**: Adds extra GraphQL round trips and complexity instead of matching `_search_page`'s fail-closed overflow guard.
