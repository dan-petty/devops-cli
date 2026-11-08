# Proposal

## Why

A plan that moves a module of `src/devops_cli/roadmap/` rewrites the imports of its callers only. String literals such as a `monkeypatch.setattr` target, `caplog` logger names, snapshot files keyed by a test path and the docstring of `src/devops_cli/roadmap/__init__.py` still name the old module, so the tests fail after the implement step and the plan's Impact list hides the work (#3373).

## What Changes

- Add `StageReference` to `src/devops_cli/roadmap/stage/stage_change.py`: a path, a kind, an `unchanged` flag and a reason, with a reason required for an unchanged entry.
- Add the `references` list to `StageProposal` and render each unchanged reference with its path, its kind and its reason in `_design_file`.
- Add `reference_files` to `src/devops_cli/roadmap/stage/stage_references.py`: the path of each file of the staged commit that holds a text, with no cap, so the check sees every hit.
- Derive each moved Python module of each group from `changes` and `creates`, and probe its old path and its dotted name after the reply in `src/devops_cli/roadmap/stage/stage.py`.
- Make `check_proposal` refuse a probed path that no group lists in `changes` and that the reply does not mark unchanged with a reason.
- Name the `references` tool on the old module path and its dotted name, the quoted target, the logger name, the snapshot file and the `! git grep` verification of a move in `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Add the stage messages for the reference problems to `src/devops_cli/lang/en/messages.py`.
- The change carries a spec delta because it changes what the stage job accepts and what its prompt asks.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The job probes each reference of a moved module, A reference is covered by a group or left unchanged, The design records each unchanged reference, The prompt names the references that an import rewrite misses

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_references.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes confirm that the files the issue cites are in the staging commit: The path `src/devops_cli/roadmap/stage/stage_references.py` is a file of the staging commit.
- The probes confirm the other cited files: The path `src/devops_cli/roadmap/stage/stage_change.py` is a file of the staging commit. The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.
- The dotted name of the issue is a docstring reference and no path: The path `devops_cli.roadmap.store` is no file of the staging commit. No commit in the history deleted or renamed it.
- The stage reply already has the shape to extend: `StageProposal` in `src/devops_cli/roadmap/stage/stage_change.py` holds `specs`, `groups` and `criteria`, and `check_proposal` already joins `_delta_problems`, `content_problems`, `form_problems`, `path_problems` and `criterion_problems`.
- The job already reads the staging commit after the reply: `_settle` in `src/devops_cli/roadmap/stage/stage.py` reads `self._source` and `self._sha`, so it can probe the references before it checks the plan.
- The tool that finds the hits exists: `reference_answer` in `src/devops_cli/roadmap/stage/stage_references.py` runs `git grep -n -F` over the staged commit and keeps files of the source, tests, specs, docs and changes groups. It keeps at most 60 files, so the job uses a new `reference_files` with no cap for the check, and the model still reads the capped answer.
- First check against the real system: `uv run devops roadmap eval stage --replay`, which runs the recorded plans through `check_proposal` and must keep its verdict on every case.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, which holds the stage checks and the prompt rules offline.

## Existing Tool Considered

git grep through the existing `references` stage tool in `src/devops_cli/roadmap/stage/stage_references.py` finds a dotted name in an import, a string literal and a snapshot path, so no new scanner is needed; the change adds only the structured coverage check over its answer, at a cost of about 10k tokens and 1 hour.
