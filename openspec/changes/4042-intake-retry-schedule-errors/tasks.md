# Tasks

## 1. An Item that a person changed is no failed placement

Reads: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/claim.py`, `tests/roadmap/intake/test_roadmap_intake_github_requests.py`. Changes: `src/devops_cli/roadmap/intake/intake.py`, `tests/roadmap/intake/test_roadmap_intake_item_changed.py` (new), `tests/roadmap/intake/test_roadmap_intake_github_requests.py`.

- [x] 1.1 Add `tests/roadmap/intake/test_roadmap_intake_item_changed.py` (item changed for one of three candidates, and for the intake record in a round) and change the two tests of `tests/roadmap/intake/test_roadmap_intake_github_requests.py` that asserted a failed placement for a changed Item. Run them and see them fail
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_item_changed.py tests/roadmap/intake/test_roadmap_intake_github_requests.py` fails on the base
- [ ] 1.2 In `apply_intake`, catch `RoadmapItemChangedError` after the rate-limit errors and before `GitHubOperationError`. Log one INFO line that names the candidate (a new `MESSAGES.roadmap.intake_item_changed`), and add no `PlacementFailure`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_item_changed.py tests/roadmap/intake/test_roadmap_intake_github_requests.py tests/roadmap/intake/test_roadmap_intake_write_failures.py` passes

## 2. The refine stamp survives a failed placement

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/intake/intake.py`, `tests/roadmap/test_roadmap_run_intake_row.py`. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/intake/intake.py`, `tests/roadmap/intake/test_roadmap_intake_item_changed.py`.

- [x] 2.1 Add the `refine_due` tests to `tests/roadmap/intake/test_roadmap_intake_item_changed.py`: a P0 placed in a round with a real placement failure stamps before the round raises; a P0 whose own write failed or changed stamps nothing. Run them and see the first and the last fail
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_item_changed.py` fails on the base
- [ ] 2.2 Add to `IntakeApplied` the count of critical or P0 decisions that `apply_intake` placed. In `run.py`, replace the two identical blocks of `_run_intake_adapter` and `_intake_one` with one helper that applies the plan, writes the `refine_due` stamp when that count is above zero, and then calls `raise_for_failed_placements`. Delete `_places_critical_or_p0`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_item_changed.py tests/roadmap/test_roadmap_run_intake_row.py tests/roadmap/test_roadmap_run_scoped_update.py` passes

## 3. An unreadable schedule stops the round

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_schedule_unreadable.py` (new).

- [x] 3.1 Add `tests/roadmap/test_roadmap_schedule_unreadable.py`: a corrupt file, a file that is not an object, a value that is not a string and a bad timestamp each raise `RoadmapRunError` that names the file, run no row and leave the file; a missing file is a first run. Run it and see the four cases fail
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_schedule_unreadable.py` fails on the base
- [ ] 3.2 Add `MESSAGES.roadmap.run_schedule_unreadable` (path, reason, remedy). Make `_read_schedule` raise `RoadmapRunError` with it and `details={"path": ...}` for the four cases, and keep a missing file empty
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_schedule_unreadable.py tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_retitle.py` passes

## 4. Regenerate and fix the documents

Reads: `k8s/README.md`, `docs/CONFIGURATION.md`. Changes: `k8s/README.md`.

- [ ] 4.1 In item 17 of `k8s/README.md`, say that a `schedule.json` that cannot be read fails the round with an error that names the file, and that a person repairs or removes the file; add that an Item a person changed between the plan and the write of intake is not a failed placement
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Run `uv run devops docs generate --sync-readme` so the generated message documents match
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The failure count and the class of a placement belong to #4061.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
