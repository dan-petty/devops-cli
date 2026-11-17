# Design: #3584

## Decisions

### 1. Shared helper in `stage_change.py`
- Put `group_title_problems` in `src/devops_cli/roadmap/stage/stage_change.py`.
- It accepts a `str` of `tasks.md` content, a `Sequence[StageGroup]`, or a `StageProposal`.
- It extracts group number and title, checks `is_placeholder(title)`, and formats `stage_problem_text_placeholder`.
- `content_problems` calls it on `proposal.groups`.
- `draft_readiness` calls it on `draft.change` (or `draft.change.tasks_text`).

### 2. Group title skips length floor
- The rule checks `is_placeholder(title)` only.
- It never applies `PLAN_FIELD_MIN_CHARS` to group titles.
- Short legitimate titles like `Archive` pass without error.

### 3. Stage ready passes `tasks.md` to `Draft.change`
- `Draft.change` accepts `ChangeFacts | str | None`.
- In `_settle` of `stage_ready.py`, read `tasks.md` at `status.head_sha` using `client.get_file_at` and pass it to `Draft.change`.
- In `_judge_completeness` of `implement_pull.py`, check `group_title_problems` when `draft.kind == DraftKind.STAGE_PLAN` and `tasks_text` is available.
