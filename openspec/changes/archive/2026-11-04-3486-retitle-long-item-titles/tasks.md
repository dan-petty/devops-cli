# Tasks

## 1. Intake refuses, jobs share the title reason (behavior)

- [x] 1.1 Write the tests: intake refuses a summary of 61 characters and files no issue, and `_planned_target` leaves out a Planned item with a long summary with no request.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_retitle.py tests/roadmap/test_roadmap_implement_planned.py`
- [x] 1.2 Add `commit_summary`, `long_title_reason` and `NewCandidate.refuse_long_summary`, and use them in the stage job, the implement job and the intake command.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_retitle.py tests/roadmap/test_roadmap_implement_planned.py`

## 2. The retitle job (behavior)

- [x] 2.1 Write the tests of the pass: preview and confirm, type and scope kept, plan title for a Planned item, model call and retry, a person's edit, a changed title, the limit, and the inbox line.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_retitle.py`
- [x] 2.2 Add `set_title`, `pull_title` and `last_renamed_at` to the store and its two adapters, the module `retitle.py`, the prompt, the request plan of the dry run, and the command.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_retitle.py`

## 3. Documents (documents)

- [x] 3.1 Update `docs/roadmap/intake.md` and `docs/roadmap/implement.md`, and regenerate the documentation with `devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- The Service row that runs `retitle` on a schedule: #3535.
- Pending a person: run `devops roadmap retitle --confirm` on the live roadmap until that row exists.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
