# Tasks

## 1. Name the same-name files of a cited bare path in the probe

Reads: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_stage_probe.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage_probe.py`, `tests/roadmap/test_roadmap_stage_probe.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_probe.py`, add a case that probes a body citing `stage_specs.py` against a staged repository that holds `src/devops_cli/roadmap/stage_specs.py` and no root `stage_specs.py`, and assert that the probe text names `src/devops_cli/roadmap/stage_specs.py` as the candidate and that `missing` holds `stage_specs.py`; add a case that cites `README.md` at the root and asserts one present line and no same-name file; add a case with six same-name files and assert at most five are named, in sorted order
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stage_probe.py`, add a candidate text to the roadmap messages of `src/devops_cli/lang/`, and read the staged tree once per run with `git ls-tree -r --name-only <sha>` through the run's command budget, building a `StagedTree` from `src/devops_cli/roadmap/stage_paths.py`. In `_Run.path`, when `git cat-file` reports the cited path missing, take `same_name` of the path and write the existing files as candidates in the missing line, keeping the removal commit text and the bound `SAME_NAME_MAX`. Charge the tree read to the run's command budget and list the path as skipped when no command is left
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` passes

## Criteria

- Group 1: A cited bare name with a file under a folder makes the probe name that file, and the probe gives the file as the candidate.
- Group 1: A test asserts that the probe names the file of a cited bare name that has no root file.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
