# Tasks

## 1. Add the review budget setting and the review step messages

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`.

- [ ] 1.1 Add `review_runs` to the `roadmap.implement` settings model with a default of 2, and the review step names and the finding, disposition and budget messages in `src/devops_cli/config/constants.py`, and verify that `uv run devops config show` passes

## 2. Review the diff and check plan conformance before the ready mark

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/roadmap/implement_review.py` (new), `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_implement_review.py` (new).

- [ ] 2.1 Write `tests/roadmap/test_implement_review.py` with a replayed review session that seeds a high-severity finding, and assert that the run spends one fix step, re-runs the review and marks ready only after the finding is cleared, and verify that `uv run devops ci test tests/roadmap/test_implement_review.py` fails on the base
- [ ] 2.2 Write `src/devops_cli/roadmap/implement_review.py` with `review_diff`, which runs `devops review` on the item's diff, and `plan_conformance`, which reads the change folder and returns the unticked tasks and the undelivered criteria. Give the result a disposition per finding. Call both from `_ItemRun._checks` after the checks pass, add the repair round and the budget of `roadmap.implement.review_runs`, and gate `_ready` on a clean result, and verify that `uv run devops ci test tests/roadmap/test_implement_review.py` passes

## 3. Post the findings and their disposition in the pull request comment

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_review.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_implement_review.py`.

- [ ] 3.1 Add a test to `tests/roadmap/test_implement_review.py` that asserts the comment holds one line per finding with its location, severity and disposition, and verify that `uv run devops ci test tests/roadmap/test_implement_review.py` fails on the base
- [ ] 3.2 Extend `_scoped_lines` and `_comment` in `src/devops_cli/roadmap/implement_run.py` so the review findings and their dispositions follow the scoped runs in the same marked comment, and verify that `uv run devops ci test tests/roadmap/test_implement_review.py` passes

## 4. Document the review gate

Reads: `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`.

- [ ] 4.1 Add the review step, the two-run budget and the blocked reason to `docs/ROADMAP_WORKFLOW.md`, and name the review gate in the Implementing entry of `CONTEXT.md`, and verify that `uv run devops ci docs` passes
- [ ] 4.2 `docs/ROADMAP_WORKFLOW.md` and `CONTEXT.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
