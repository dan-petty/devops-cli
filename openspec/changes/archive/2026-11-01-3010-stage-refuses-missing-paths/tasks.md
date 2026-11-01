# Tasks

## 1. Find the paths of a plan that the commit lacks

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/step_files.py`. Changes: `src/devops_cli/roadmap/stage_paths.py` (new), `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py` (new).

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_stage_paths.py` for the scenarios of "The plan names files that exist at the staged commit": a moved test file, a created path of the same and of an earlier group, a path in a task code span and in `verify`, a folder, a glob, a location suffix, and the words that are no path; and a replay of the groups of the plans of #2260, #2162 and #2116
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [x] 1.2 Add `StagedTree` and `path_problems` in `src/devops_cli/roadmap/stage_paths.py`, `code_spans` in `src/devops_cli/roadmap/step_files.py`, and the problem messages
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 2. Return a plan with a missing path, and stop at the second

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/support/roadmap_stage.py`.

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_stage_plan.py` for a first reply with a missing path (the model gets the problem with the same-name file and the second reply is staged), a second reply with the same path (the item fails and no draft opens), and a split reply with a missing path; change `tests/roadmap/test_roadmap_stage_apply.py` so the comment holds no line about a missing path
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_apply.py` fails on the base
- [x] 2.2 Pass the tree to `check_proposal`, read it once in `plan_stage`, check the groups again after a split, and delete `missing_paths`, `StagedChange.missing`, `_notes` and `stage_comment_missing`; make `heavy_group` commit its files
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_apply.py tests/roadmap/test_roadmap_stage_measure.py tests/roadmap/test_roadmap_stage_job.py`

## 3. List the read in the dry run

Reads: `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 3.1 Write a failing test in `tests/roadmap/test_roadmap_dry_runs.py` that the stage plan lists one `git ls-files -z` read, once for the round
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` fails on the base
- [x] 3.2 Add the read to `stage_requests`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`

## 4. The prompt and the documents

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `k8s/README.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `k8s/README.md`, `src/devops_cli/roadmap/stage.py`.

- [x] 4.1 Tell the model in the stage prompt that the job checks every path against the staged commit, that a path belongs in a code span, and what a second miss does
  - Verification: `git grep -n "staged commit" src/devops_cli/ai/tasks/roadmap_stage_change.md` prints the rule
- [x] 4.2 Change step 15 of `k8s/README.md` and the module text of `src/devops_cli/roadmap/stage.py` to the new behavior
  - Verification: `git grep -n "A person checks" src k8s` prints nothing

## 5. Review fix: a name with no folder

Reads: `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_paths.py`, `openspec/specs/roadmap-stage/spec.md`.

- [x] 5.1 Write failing tests in `tests/roadmap/test_roadmap_stage_paths.py` that a bare `ruff.toml` in a task and a bare name in `verify` give no problem, and that the same name in `changes` still does
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the commit before the fix
- [x] 5.2 Count only a word with a folder in `StagedTree.as_path`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py tests/roadmap/test_roadmap_stage_plan.py`

## 6. Documents, fail-to-pass and archive

- [x] 6.1 Regenerate the command documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`
- [x] 6.2 Run the fail-to-pass check on the new tests
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] 6.3 Archive the change
  - Verification: `uv run devops openspec archive 3010-stage-refuses-missing-paths` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
