# Proposal

## Why

The stage job cannot run commands, so `## Feasibility` of most plans holds only checks that the implementation will run later. Four plans of the 2026-11-01 evaluation were built on a premise that was already false (#2984, #2981, #2985, #2857). The job must probe the premise at the staging commit and return an item whose premise is false (#3011).

## What Changes

- Add `src/devops_cli/roadmap/stage_probe.py`: it extracts the backtick-quoted paths and identifiers of the issue body, runs at most a stated number of read-only git commands at the staging commit, and returns the probe text with the probes it skipped.
- Add the probe text to the model input of `_Planner._request` in `src/devops_cli/roadmap/stage.py`.
- Add the `premise_failed` field to `StageProposal` in `src/devops_cli/roadmap/stage_change.py`, and return the item with the evidence and no pull request when it is set.
- Ask `feasibility` to quote the probe output in `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Add the constants for the probe bound and the probe output size to `src/devops_cli/config/constants.py`.
- Add the messages of the probe and the premise failure to `src/devops_cli/lang/en/messages.py`.
- Add tests for the probe in `tests/roadmap/test_roadmap_stage_probe.py`, and for the model input and the premise failure in `tests/roadmap/test_roadmap_stage_plan.py`.
- Add the spec delta of `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The job probes the premise at the staging commit, A false premise returns the item, The Feasibility section quotes the probe output

## Impact

- Code: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `openspec/changes/3011-stage-premise-probe/specs/roadmap-stage/spec.md`
- Tests: `tests/roadmap/test_roadmap_stage_probe.py`, `tests/roadmap/test_roadmap_stage_plan.py`

## Feasibility

- `read_file` on `src/devops_cli/roadmap/stage.py` showed `_Planner._request` at line 646 builds the model input from the issue body, `collect_context`, the capabilities and the budget. The probe output has a place there.
- `read_file` on `src/devops_cli/roadmap/stage_change.py` showed `StageProposal` at line 239 with no `premise_failed` field, so the reply cannot signal a false premise today.
- `search_code` for `premise_failed` found no match, so the field and its handling are new.
- `search_code` for `roadmap return` found the command in `AGENTS.md` line 10 and `src/devops_cli/roadmap/return_item.py`, so the job can call it.
- `read_file` on `src/devops_cli/ai/tasks/roadmap_stage_change.md` showed the prompt asks `feasibility` for the checks that the implementation runs later, not for probe output.
- `file_symbols` on `src/devops_cli/roadmap/stage_tools.py` showed the read-only `git_log`, `git_show` and `callers` tools of the planner, so the probe reuses their git access.
- The first checks of the implementation: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` for the probe, and `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` for the model input and the premise failure.

## Existing Tool Considered

The probes use the `git` binary that the job already calls through `src/devops_cli/roadmap/stage_tools.py` and `src/devops_cli/roadmap/clone_git.py`: `git cat-file -e <sha>:<path>`, `git grep -n <identifier> <sha>`, and `git log --diff-filter=DR --format=%h %s <sha> -- <path>`. No library covers this need, so the change builds about 120 lines of Python and prompt text: about 3,000 tokens to build, keep and fix, and about 1 hour of elapsed agent time. It deletes no internal code.
