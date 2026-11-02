# Tasks

## 1. Name the creating group in the path problem

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_paths.py`, change `test_a_path_that_a_later_group_creates_is_missing_in_the_earlier_group` to assert that the problem names `group 1` and `group 2`, and add `test_a_plan_whose_groups_create_what_they_read_has_no_problem` for a plan where group 1 creates a path and group 2 reads it, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stage_paths.py`, build a map from each path and its parent folders to the first group number that lists it in `creates`. In `_problem`, take that number and add the sentence that names the creating group. In `src/devops_cli/lang/en/messages.py`, add `stage_path_later_group` and `stage_path_no_later_group` and a `later` field to `stage_problem_path`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 2. Write the change folder and its spec delta

Reads: `openspec/specs/roadmap-stage/spec.md`, `openspec/changes/archive/2026-11-01-3010-stage-refuses-missing-paths/specs/roadmap-stage/spec.md`. Changes: `openspec/changes/3017-stage-names-the-creating-group/proposal.md` (new), `openspec/changes/3017-stage-names-the-creating-group/design.md` (new), `openspec/changes/3017-stage-names-the-creating-group/tasks.md` (new), `openspec/changes/3017-stage-names-the-creating-group/specs/roadmap-stage/spec.md` (new).

- [ ] 2.1 Write the proposal, the design and the tasks of the change, and the `roadmap-stage` spec delta that modifies `The plan names files that exist at the staged commit` with the new scenario, and verify that `openspec validate --strict` passes
- [ ] 2.2 openspec/changes/3017-stage-names-the-creating-group/proposal.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
