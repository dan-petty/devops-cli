# Tasks

## 1. Intake plans over a read-only roadmap

Reads: `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/duplicate_eval.py`, `src/devops_cli/roadmap/store.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/duplicate_eval.py`, `tests/roadmap/test_roadmap_duplicate_eval.py`.

- [x] 1.1 Write `tests/roadmap/test_roadmap_duplicate_eval.py` cases first: a `SeededRoadmap` holds the item and the labels file and nothing else, and offers only reads
  - Verification: `uv run pytest tests/roadmap/test_roadmap_duplicate_eval.py -q`
- [x] 1.2 Add `IntakeReads` to `store.py`, retype the planning path of `intake.py` to it, add `SeededRoadmap` to `duplicate_eval.py`, and make `judge_case` plan intake over it
  - Verification: `uv run pytest tests/roadmap/test_roadmap_duplicate_eval.py -q`

## 2. The fake leaves src and gets a fault mode

Reads: `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap_faults.py`, `tests/roadmap_github_fake.py`. Changes: `tests/support/fakes/roadmap_store.py` (moved), `tests/roadmap_faults.py` (deleted), `tests/roadmap_github_fake.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_run.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_alternatives.py`, and the import line of each test-side file that uses the fake.

- [x] 2.1 Write the two contract cases first: a write that fails before it applies changes nothing, and a write that fails after it applies keeps the change, on both adapters
  - Verification: `uv run pytest tests/roadmap/test_roadmap_store_contract.py -q`
- [x] 2.2 Move `memory_store.py` to `tests/support/fakes/roadmap_store.py` with `git mv`, move the three constants and the `WRITES` set into it, add `fail_write`, `writes`, `fail_listing` and `listed`, and add `fail_write` to `GitHubFake`
  - Verification: `! git grep -nF -e InMemoryRoadmapStore -e DEFAULT_ROADMAP_MEMORY -- src`
- [x] 2.3 Replace the three users of `StoppingStore` and `ListingStore` with the fake's fault mode, delete `tests/roadmap_faults.py`, and change the import line of every other test-side file
  - Verification: `! git grep -nF -e memory_store -e roadmap_faults -e StoppingStore -e ListingStore -- src tests`

## 3. Documents

Reads: `docs/TESTING.md`, `openspec/changes/3187-group-the-job-modules-in-subpackages/`, `openspec/changes/3254-list-the-registry-and-ratchet-entries/`. Changes: the same.

- [x] 3.1 Name the new path and the fault mode in `docs/TESTING.md`, remove `memory_store.py` from the plan of `3187`, and name the fake in place of `tests/roadmap_faults.py` in the plan of `3254`
  - Verification: `! git grep -nF -e memory_store -e roadmap_faults -- openspec/changes/3187-group-the-job-modules-in-subpackages openspec/changes/3254-list-the-registry-and-ratchet-entries`
