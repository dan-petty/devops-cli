# Tasks

## 1. Share the code-span path rule of the group texts

Reads: `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`.

- [x] 1.1 Add `StagedTree.code_span_paths(text)` to `src/devops_cli/roadmap/stage_paths.py`, which reads the code spans of `text` with `code_spans` and returns the paths that `StagedTree.paths_in` finds, and let the group check call it. Behaviour stays the same: the group texts keep refusing the same paths
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 2. Refuse an unlisted What Changes path

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [ ] 2.1 Add a case to `tests/roadmap/test_roadmap_stage_content.py` where a proposal names `src/devops_cli/lang/en/messages.py` in What Changes and no group lists it, and assert that `check_proposal` returns a problem that names that path; add a case for a changed path, one for a created path, one for an item with no path, one for a code span that is no path and one for a path under the living spec folder
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [ ] 2.2 Add a message to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` that names the path and says that no group lists it in `changes` or `creates`. Add a function to `src/devops_cli/roadmap/stage_change.py` that collects the `changes` and `creates` paths of every group and returns one problem for each code-span path of a `what_changes` item that the set does not hold and that is not under `openspec/specs/`. Call it from `check_proposal` with the staged tree
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 3. Add the golden case of the unlisted What Changes path

Reads: `tests/roadmap/test_roadmap_stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3167-a-comment-by-a-person-on/`. Changes: `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/case.json` (new), `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/facts.json` (new), `tests/roadmap/test_roadmap_stage_eval_cases.py`.

- [ ] 3.1 Add the four files `case.json` (new), `issue.txt` (new), `plan.json` (new) and `facts.json` (new) to the folder `3411-a-what-changes-item-that-names` under the stage golden set. The plan names a repository path in What Changes that no group lists. Give `facts.json` the top folder and the suffix of that path, so the tree rule reads it as a path. Record one `missing_path` defect with gate `paths` and that path. Add the case pull number to `EVALUATED_PULLS` and the count in `tests/roadmap/test_roadmap_stage_eval_cases.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py tests/roadmap/test_roadmap_stage_eval_run.py tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## Criteria

- Group 2: ### Requirement: Refuse an unlisted What Changes path The proposal check SHALL return a problem when a repository path in a code span of a What Changes item is in neither the changes nor the creates list of any task group.
- Group 2: #### Scenario: What Changes names a path that no group lists - **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/lang/en/messages.py`, and no group lists that path in `changes` or `creates`. - **THEN** `check_proposal` returns a problem that names the unlisted path.
- Group 2: ### Requirement: Accept a changed What Changes path The proposal check SHALL accept a repository path in a What Changes code span when a task group lists that path in changes.
- Group 2: #### Scenario: What Changes names a path that a group changes - **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/stage_change.py`, and a group lists that path in `changes`. - **THEN** `check_proposal` returns no problem for that path.
- Group 2: ### Requirement: Accept a created What Changes path The proposal check SHALL accept a repository path in a What Changes code span when a task group lists that path in creates.
- Group 2: #### Scenario: What Changes names a path that a group creates - **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/new_check.py`, and a group lists that path in `creates`. - **THEN** `check_proposal` returns no problem for that path.
- Group 2: ### Requirement: Accept a What Changes item without a path The proposal check SHALL accept a What Changes item that contains no repository path in a code span.
- Group 2: #### Scenario: What Changes item describes behavior only - **WHEN** A proposal has a What Changes item with no code span that is a repository path. - **THEN** `check_proposal` returns no problem for that item.
- Group 2: ### Requirement: Ignore a non-path code span The proposal check SHALL ignore a code span in What Changes that is not a repository path.
- Group 2: #### Scenario: What Changes names a command in a code span - **WHEN** A proposal has a What Changes item with the code span `uv run devops ci test`. - **THEN** `check_proposal` returns no problem for that code span.
- Group 2: ### Requirement: Run the What Changes check without git The proposal check SHALL compare What Changes paths with the group lists without a git call or a file read.
- Group 2: #### Scenario: Replay runs the check without git - **WHEN** The replay calls `check_proposal` with a proposal and the `StagedTree` of its facts, and no checkout. - **THEN** The replay returns the path problem and makes no git call.
- Pending person: ### Requirement: Document the What Changes path rule The roadmap-stage spec SHALL include a scenario that states the What Changes path rule., Only `openspec archive`, run by a person who merges the delivery pull request, writes `openspec/specs/roadmap-stage/spec.md` from the spec delta; a task group must write no living spec.
- Pending person: #### Scenario: Roadmap-stage spec covers What Changes paths - **WHEN** A reader opens `openspec/specs/roadmap-stage/spec.md`. - **THEN** The spec holds a scenario that refuses a What Changes path that no group lists., The scenario reaches the living spec only when a person merges the delivery and `openspec archive` writes it from the spec delta of this plan.
- Group 3: ### Requirement: Add the stage golden case The stage golden set SHALL include a case where a What Changes item names a path that no group lists.
- Group 3: #### Scenario: Golden case for an unlisted What Changes path - **WHEN** The stage golden set runs its cases. - **THEN** The new case reports the path problem.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
