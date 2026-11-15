# Tasks

## 1. Cap, mask and quote one run

Reads: `src/devops_cli/security/sanitizer.py`, `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md`.

Changes: `src/devops_cli/roadmap/run_output.py`, `tests/roadmap/test_roadmap_run_output.py`, `docs/CLUSTER.md`.

- [x] 1.1 Write the six cases of the cap, the trailer, the mask, the key block and the fence, and watch them fail.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_output.py`
- [x] 1.2 Add the module, and state the cap in the Planner run Jobs section.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_output.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
