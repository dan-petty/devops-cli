# Tasks

## 1. The Planned label

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_status_labels.py`: the Status family has six values in order, `.github/labels.yml` declares the six labels, an issue with `status/planned` reads as Planned, `devops pr create` replaces Planned with In Progress, and refine holds a Planned item
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_status_labels.py`
- [x] 1.2 Add `CONST_ROADMAP_STATUS_PLANNED` to `src/devops_cli/config/constants.py` and to the Status values and the held Statuses of refine, add `status/planned` to `.github/labels.yml`, and let `src/devops_cli/roadmap/pull_status.py` replace Planned
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_status_labels.py tests/roadmap/test_roadmap_refine.py`

## 2. The one function

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_status_sync.py` for the scenarios of the requirements "The Service sets the Status from the job record" and "The Service never reverts a person's Status": `derive_status` for each order of the facts, a drift that is repaired, a label of a person that stays, an item with no record, an item in another Status, a stale view that is skipped, and one failed item that does not stop the others
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_status_sync.py`
- [x] 2.2 Write `src/devops_cli/roadmap/status_sync.py` with `StatusFacts`, `derive_status`, `facts_of`, `sync_status` and `sync_statuses`, and the message of a failed sweep
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_status_sync.py`

## 3. The rows use it

- [x] 3.1 Write failing tests: the implement job accepts Ready, Planned and the In Progress item of a recorded Job, and leaves out the other Statuses; the default filter names Planned; a lost stop of a Planned item is reported
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_implement_submit.py`
- [x] 3.2 Accept the Statuses in `src/devops_cli/roadmap/implement.py` and `src/devops_cli/roadmap/implement_submit.py`, add `status=planned` to the default filter, and let `plan_implement` take the plans of the round
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_implement_submit.py`
- [x] 3.3 Write failing tests that replay a round (staged, plan merged, Job running, pull request ready, issue closed) through the rows `stage`, `implement` and `stage_ready`, and check the label at each point
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_status_round.py`
- [x] 3.4 Run the sweep in the row `implement` (after the report of the Jobs, and for the item of the Job it creates), in the row `stage` (with the plans of its plan) and in the row `stage_ready` (for a merged plan pull request)
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_status_round.py tests/roadmap/test_roadmap_stage_ready.py tests/roadmap/test_roadmap_run.py`

## 4. The documents

- [x] 4.1 Amend ADR 0016 (six Status labels, the Service as writer) and update `CONTEXT.md`, `k8s/README.md`, `docs/ROUTINE_TASKS.md` and the help text of `devops roadmap implement`, then regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Review fixes

- [x] 5.1 Remove the facts that no round reaches (Blocked, delivery pull request), read the issue again before a write, and make `clear-status` read the labels of the closed issue
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_status_sync.py tests/roadmap/test_roadmap_status_round.py`

## 6. Archive

- [x] 6.1 Archive the change
  - Verification: `uv run devops openspec archive 2920-status-planned-and-status-writer`

## Workflow follow-up

- The stop path that sets Blocked and its clearing on a new runner image are the work of #2912.
- The claim labels that mark a manual claim are the work of #2910.
- Pending a person: sync the label with `devops gh labels sync`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
