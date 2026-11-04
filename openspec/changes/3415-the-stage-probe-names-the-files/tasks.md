# Tasks

## 1. Name the same-name files of a cited bare path in the probe

Reads: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_probe.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_probe.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_probe.py`, add a case that probes a body citing `stage_specs.py` against a staged repository that holds `src/devops_cli/roadmap/stage_specs.py` and no root `stage_specs.py`, and assert that the probe text names `src/devops_cli/roadmap/stage_specs.py` as the candidate and that `missing` holds `stage_specs.py`; add a case that cites `README.md` at the root and asserts one present line and no same-name file; add a case with six same-name files and assert at most five are named, in sorted order; add `ls-tree` to the command kinds that `test_every_command_reads_and_the_checkout_does_not_change` asserts
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` fails on the base
- [ ] 1.2 In `src/devops_cli/lang/en/messages.py`, add a missing-at-root message that names the cited path, the removal text and the candidate names. In `src/devops_cli/roadmap/stage_probe.py`, read the staged tree with `git ls-tree -r -z --name-only <sha>` on the first missing cited path, build a `StagedTree` from `src/devops_cli/roadmap/stage_paths.py`, and keep it for the run. In `_Run.path`, when `git cat-file` reports the cited path missing, take `same_name` of the path: when it finds files, write the new root-specific line with the candidates and the removal text; when it finds none, keep the present line. Charge the tree read to the run's command budget, keep the bound `SAME_NAME_MAX`, and list the path as skipped when no command is left
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` passes

## Criteria

- Group 1: A cited bare name with a file under a folder makes the probe name that file, and the probe gives the file as the candidate.
- Group 1: A test asserts that the probe names the file of a cited bare name that has no root file.
- Group 1: The probe test that pins the command kinds names `ls-tree`.
- Group 1: A cited path at the root keeps its present line.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
