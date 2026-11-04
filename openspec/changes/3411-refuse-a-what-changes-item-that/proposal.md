# Proposal

## Why

The stage job renders the `## Impact` section of `proposal.md` from the paths of the task groups, and nothing compares those groups with the free text of `what_changes` (#3411). The first staged plan of #3379 for #3373 named `src/devops_cli/lang/en/messages.py` in What Changes, and no group listed that file in `changes` then, so the rendered Impact left the file out and every gate accepted the plan. A later commit of that plan added the file to a group. A reader of the first plan could not see that the file changes, and the implement step had no group that edits it.

## What Changes

- `check_proposal` in `src/devops_cli/roadmap/stage_change.py` refuses a repository path in a code span of a `what_changes` item that no group lists in `changes` or `creates`
- The check accepts a path under the living spec folder, because `openspec archive` writes it and no group may write there
- The code-span path rule of `src/devops_cli/roadmap/stage_paths.py` becomes one shared function that the group texts and the What Changes items both use, and it reads the staged tree that decides whether a word is a repository path
- `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` gains the message that names the unlisted path
- `tests/roadmap/test_roadmap_stage_content.py` holds a case for each rule: an unlisted path, a changed path, a created path, an item with no path, a code span that is no path and a living spec path
- The golden set gains a case whose What Changes names a path that no group lists, so the replay refuses it
- The new golden case is a folder of four files in the stage golden set
- `openspec/specs/roadmap-stage/spec.md` gains the scenario of the What Changes path rule, written by `openspec archive`
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a What Changes path that no group lists, Ignore a What Changes item with no unlisted path

## Impact

- Code: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py`, the four files of the new case under `tests/fixtures/roadmap_eval/stage/`

## Feasibility

- `read_file` of `src/devops_cli/roadmap/stage_change.py` showed `check_proposal` at the code that the job and the replay call with a `StagedTree`, so the check reads no git and no file.
- `read_file` of `src/devops_cli/roadmap/stage_paths.py` showed that `StagedTree.as_path` and `StagedTree.paths_in` decide whether a word is a repository path from the suffixes and the top folders of the tree, so the shared function takes the tree and adds no second path grammar.
- `read_file` of `src/devops_cli/roadmap/stage_change.py` showed `_LIVING_SPEC_DIRECTORY`, which no group may change or create, so the check must accept a What Changes path under the living spec folder that `openspec archive` writes.
- The probes said `The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.` and `The path `tests/roadmap/test_roadmap_stage_content.py` is a file of the staging commit.`, so the two files that the issue names exist and the check has a home and a test module.
- The probes said `The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit.`, so the new message goes into the catalog that holds every user-facing text.
- `search_code` for `what_changes` showed it as a field of `StageProposal` and as a bullet list of `_proposal_file`, and no check reads its code spans, so the gap of the issue is real.
- First check: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` must fail on the new unlisted-path case before the check exists.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` must keep passing, because the shared code-span rule keeps the group behaviour.
- Third check: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py` and `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_run.py` must fail on the new golden case until the case and the gate agree.

## Existing Tool Considered

The change builds its own code. It extends the path rule of `src/devops_cli/roadmap/stage_paths.py`, which already reads the code spans of the group texts, so the What Changes items reuse that rule and no second grammar appears. The cost is about 2k tokens to build, keep and fix the check, and 30 minutes. The change deletes no internal code.

## Dependencies

None.
