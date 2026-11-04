# Proposal

## Why

The stage job renders the `## Impact` section of `proposal.md` from the paths of the task groups, and nothing compares those groups with the free text of `what_changes` (#3411). The plan of #3379 for #3373 named `src/devops_cli/lang/en/messages.py` in What Changes, yet no group listed that file in `changes`, so the rendered Impact left the file out and every gate accepted the plan. A reader of the plan cannot see that the file changes, and the implement step has no group that edits it.

## What Changes

- `content_problems` in `src/devops_cli/roadmap/stage_change.py` refuses a repository path in a code span of a `what_changes` item that no group lists in `changes` or `creates`
- The code-span path rule of `src/devops_cli/roadmap/stage_paths.py` becomes one shared function that the group texts and the What Changes items both use
- `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` gains the message that names the unlisted path
- `tests/roadmap/test_roadmap_stage_content.py` holds a case for each rule: an unlisted path, a changed path, a created path, an item with no path and a code span that is no path
- The golden set gains a case whose What Changes names a path that no group lists, so the replay refuses it
- `openspec/specs/roadmap-stage/spec.md` gains the scenario of the What Changes path rule, written by `openspec archive`
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a What Changes path that no group lists, Ignore a What Changes item with no unlisted path

## Impact

- Code: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`

## Feasibility

- `read_file` of `src/devops_cli/roadmap/stage_change.py` showed `content_problems` at the code that `check_proposal` calls, so a reply-only rule runs in the job and in the replay with no git call.
- `read_file` of `src/devops_cli/roadmap/stage_paths.py` showed the code-span path rule that the group texts already use, so the check extends that rule and adds no second path grammar.
- The probes said `The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.` and `The path `tests/roadmap/test_roadmap_stage_content.py` is a file of the staging commit.`, so the two files that the issue names exist and the check has a home and a test module.
- The probes said `The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit.`, so the new message goes into the catalog that holds every user-facing text.
- `search_code` for `what_changes` showed it as a field of `StageProposal` and as a bullet list of `_proposal_file`, and no check reads its code spans, so the gap of the issue is real.
- First check: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` must fail on the new unlisted-path case before the check exists.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` must keep passing, because the shared code-span rule keeps the group behaviour.
- Third check: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_run.py` must fail on the new golden case until the gate refuses it.

## Existing Tool Considered

The change builds its own code. It extends the path rule of `src/devops_cli/roadmap/stage_paths.py`, which already reads the code spans of the group texts, so the What Changes items reuse that rule and no second grammar appears. The cost is about 2k tokens to build, keep and fix the check, and 30 minutes. The change deletes no internal code.

## Dependencies

None.
