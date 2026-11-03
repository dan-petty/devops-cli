# Proposal

## Why

Issue #3295 reports a plan from PR #3234 whose task group 2 listed `openspec/specs/config-commands/spec.md` in `changes` and told the implement step to edit the living spec by hand. Neither `StageGroup` in `src/devops_cli/roadmap/stage_change.py` nor `check_proposal` in `src/devops_cli/roadmap/stage_eval_gates.py` refused it, so a plan can contradict `openspec archive`, which is the only writer of living specs.

## What Changes

- `StageGroup` in `src/devops_cli/roadmap/stage_change.py` refuses a `changes` or `creates` path under `openspec/specs/` and names the path in the error.
- A message `stage_bad_living_spec` in `src/devops_cli/lang/en/messages.py` states that only `openspec archive` writes living specs.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` tells the planner that a task group never changes or creates a path under `openspec/specs/`.
- `tests/roadmap/test_roadmap_stage_paths.py` covers the refusal in `changes` and in `creates`, and the acceptance of a living spec in `reads`.
- `tests/roadmap/test_roadmap_stage_prompt_rules.py` covers the living-spec rule of the prompt.
- The change has a spec delta: `StageGroup` is the schema of every stage reply, so the job's behavior changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A task group writes no living spec, The stage prompt states the living-spec rule

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `probes` confirms that the cited paths exist at the staging commit: "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit." and "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit."
- `probes` confirms the premise that no such validator exists: "The path `src/devops_cli/roadmap/stage_eval_gates.py` is a file of the staging commit." and its context shows `check_proposal` checking only the spec delta, the form and the paths. The context of `src/devops_cli/roadmap/stage_change.py` shows `StageGroup` with `_creates_are_changes` and `_kind_rules` alone, and `_repository_path` checking only that a path is relative, has no `..` and is plain.
- `probes` confirms that `tests/roadmap/test_stage_change.py` does not exist: "The path `tests/roadmap/test_stage_change.py` is no file of the staging commit. No commit in the history deleted or renamed it." The tests go into the existing modules `tests/roadmap/test_roadmap_stage_paths.py` and `tests/roadmap/test_roadmap_stage_prompt_rules.py`.
- `search_code` on `stage_bad_creates` showed the message text in `src/devops_cli/lang/en/messages.py`, so the new message sits in that file, beside the other `stage_*` messages.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py tests/roadmap/test_roadmap_stage_prompt_rules.py`, then `uv run devops openspec check` on the change folder.

## Existing Tool Considered

Pydantic provides the `model_validator` that `StageGroup` already uses for `_creates_are_changes` and `_kind_rules`, so the rule extends that layer with no new dependency. Written cost to build, keep and fix the validator, the message and the test cases: about 5,000 tokens and 30 minutes. The change deletes no internal code.
