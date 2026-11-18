# Design: Preserve stage plan kind when PR numbers collide

## Technical Design
Update `kind_of(item: Item | None, pull: int | None = None, title: str | None = None) -> DraftKind` in `src/devops_cli/roadmap/implement/implement_pull.py`.
When both `implement.pr` and `stage.pr` equal the target pull request number:
1. If `title is not None and title.startswith("docs(openspec): plan")`, return `DraftKind.STAGE_PLAN`.
2. Otherwise, return `DraftKind.IMPLEMENT`.

Update `read_draft` to pass `pull.title` to `kind_of`:
`kind = kind_of(item, number, pull.title)`

Update `stage_ready.py` to pass `status.title` to `kind_of`:
`draft = Draft(kind_of(item, number, status.title), status, item, checks, change=change)`

Update callers in `fix_checks.py` to pass `facts.status.title` to `kind_of`.

## Implementation Details
The check `title.startswith("docs(openspec): plan")` matches the standard stage plan pull request title convention established across the roadmap workflow.
No new dependencies are required.
`_judge_completeness` remains unchanged.

## Verification Plan
1. Unit tests in `tests/roadmap/test_roadmap_draft_readiness.py`:
   - `test_kind_of_resolves_colliding_pr_as_stage_plan_when_title_is_plan`
   - `test_kind_of_resolves_colliding_pr_as_implement_when_title_is_implement`
   - `test_kind_of_defaults_to_implement_on_collision_when_no_title_given`
   - `test_read_draft_classifies_colliding_stage_plan_pr`
   - `test_draft_readiness_accepts_colliding_stage_plan_with_unticked_tasks`
2. Run `pytest tests/roadmap/test_roadmap_draft_readiness.py`.
3. Run `devops openspec check`.
4. Run fail-to-pass verification.
