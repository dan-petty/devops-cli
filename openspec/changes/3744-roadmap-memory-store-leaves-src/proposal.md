# Proposal

## Why

Issue #3744 (part 1 of 6 of #1335). `InMemoryRoadmapStore` is the fake of the roadmap store. It sat in `src/devops_cli/roadmap/memory_store.py` and shipped in the wheel. `docs/TESTING.md` says that fakes live in `tests/support/` and never ship in the wheel. Production used the class in one place: `judge_case` in `src/devops_cli/roadmap/duplicate_eval.py`, which the command `devops roadmap eval intake` runs. That run needs two reads of the store and no write.

Two wrappers of the store, `StoppingStore` and `ListingStore`, sat in `tests/roadmap_faults.py`. Neither had a contract suite.

## What Changes

- Add the Protocol `IntakeReads` to `src/devops_cli/roadmap/store.py`. It holds the five reads that the plan of intake makes. `plan_intake` and the helpers of the plan take it, so the type checker shows that a plan writes nothing. `apply_intake` and `intake_candidate` keep `RoadmapStore`.
- Add `SeededRoadmap` to `src/devops_cli/roadmap/duplicate_eval.py`: a frozen, read-only roadmap that holds one issue and the text of `.github/labels.yml`. `judge_case` plans intake over it and reads the one decision. Its verdicts do not change.
- Move `memory_store.py` to `tests/support/fakes/roadmap_store.py`. The three `DEFAULT_ROADMAP_MEMORY_*` constants move into it and leave `config/defaults.py`.
- Add the fault mode to the fake: `fail_write` fails the Nth matching write with `GitHubOperationError`, before or after the write applies; `writes` lists every write tried; `fail_listing` fails the next directory listing; `listed` lists each directory listed. The `WRITES` set moves into the fake. `StoppingStore`, `ListingStore` and `tests/roadmap_faults.py` are deleted, and their three users call the fake.
- Add `fail_write` to `GitHubFake` (the `gh` process edge) and two cases to the contract suite. They run on both adapters: a write that fails before it applies changes nothing, and a write that fails after it applies keeps the change.
- Change the import line in the test-side files that import the fake.
- Update `docs/TESTING.md`, and the open changes `3187-group-the-job-modules-in-subpackages` and `3254-list-the-registry-and-ratchet-entries`, whose plans name `memory_store.py` and `tests/roadmap_faults.py`.
- The change alters no behavior that a consumer observes, so it has no spec delta and sets `skip_specs: true`. The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/duplicate_eval.py`, `src/devops_cli/roadmap/memory_store.py` (moved), `src/devops_cli/config/defaults.py`.
- Tests: `tests/support/fakes/roadmap_store.py`, `tests/roadmap_github_fake.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_duplicate_eval.py`, `tests/roadmap/test_roadmap_run.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap_faults.py` (deleted), and the import line of the other test-side files that use the fake.
- Documents: `docs/TESTING.md`, `openspec/changes/3187-group-the-job-modules-in-subpackages/`, `openspec/changes/3254-list-the-registry-and-ratchet-entries/`.

## Acceptance

- `test ! -e src/devops_cli/roadmap/memory_store.py`, and `git grep -n -E "InMemoryRoadmapStore|memory_store|DEFAULT_ROADMAP_MEMORY" -- src` prints nothing.
- `judge_case` gives the same verdict and reason for each case of `intake_duplicate_cases.json`.
- `git grep -n -E "memory_store|roadmap_faults" -- src tests openspec/changes ':!openspec/changes/archive'` prints nothing.
- `uv run devops ci` passes.

## Feasibility

Checked on 2026-11-06 at `origin/main` (c7145511).

- `git grep -n "memory_store" -- src` showed one importer in `src`: `duplicate_eval.py`. `plan_intake` reads the roadmap through `issues`, `repository_file`, `closures`, `comments_on` and `evidence_holds`, and `intake_candidate` writes only when `confirm` is true. `judge_case` never sets it. So a read-only roadmap is enough.
- `uv run pytest tests/roadmap/test_roadmap_duplicate_eval.py` passes with its old assertions after the change, so the verdicts hold.
- Both adapters raise `GitHubOperationError` for a failed write: the new contract cases run on `InMemoryRoadmapStore` and on `GitHubRoadmapStore` over `GitHubFake` and pass.
- `uv run mypy` passes with `IntakeReads` on the planning path.

## Existing Tool Considered

No open library gives a fake of this roadmap store, so the fake stays hand-written; its contract suite keeps it equal to `GitHubRoadmapStore` (ADR 0007). For the evaluation, a narrow Protocol and a read-only class of about 60 lines replace a class of 779 lines in `src`. The cost to build is about 150,000 tokens, most of it for the import edits in 97 files. It costs about 20,000 tokens a year to keep. The work takes about one day. The change deletes `memory_store.py` from `src`, `tests/roadmap_faults.py`, and three constants.
