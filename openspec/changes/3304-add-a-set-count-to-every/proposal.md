# Proposal

## Why

#3304: a requirement or a scenario that says "every X" or "no X" makes a claim about a set, and no gate asks the plan to count the set. The plan of #3236 listed three tools of a set of 60, and the guard of #3230 missed `k8s_diff_helm.values`, so the implementation would fail on its first run of the audit. The planner cannot run a command, so the rule takes its count from a tool of the plan run or from a probe line, and marks the count unverified when no tool can give it.

## What Changes

- Add the count rule to the planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`: a claim about every member of a set, or a new guard over a set, gives a count from a tool of the plan run or from a probe line, and a plan that cannot count the set says so and makes the census the `verify` of its first group.
- Add the same phrase to the proposal rule of `openspec/config.yaml`, so the prompt and the config give one rule.
- Assert each phrase of the rule in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, and pin the phrase that the config and the prompt share.
- Add a test that `check_proposal` refuses no plan for the word `every`, so the change keeps no word gate.
- The change carries a spec delta, because the stage job plans different content and a consumer of the stage job observes it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The stage prompt asks for a count of a claimed set, The plan check refuses no word of a requirement text

## Impact

- Code: `openspec/config.yaml`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes confirm the two files that the rule changes: "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit." and "The path `openspec/config.yaml` is a file of the staging commit."
- The issue cites `tests/roadmap/test_roadmap_stage_prompt_rules.py`, and the probe shows that a commit renamed it: "The path `tests/roadmap/test_roadmap_stage_prompt_rules.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." The plan writes the test at the current path and compensates for nothing else.
- The example of the issue holds at the commit: `openspec/changes/3230-decide-the-free-text-mcp-parameters/proposal.md` names the allowlist entry for `k8s_diff_helm.values` with its reason, and `openspec/changes/3236-read-only-tools-take-paths-that/design.md` records the census of 60 tools with a path-like parameter. The probe reports that `k8s_diff_helm.values` is no file of the commit, because it names a published parameter and no path.
- The prompt that the rule changes is the copy that the planner reads, and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` already pins each phrase of the prompt against the document that states the same rule, so the new phrase goes there.
- First check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the new phrases at the base and passes after the rule lands.
- Second check: `uv run devops ci test tests/commands/test_openspec_scaffold.py` passes after the config rule lands, so the new rule is a folded scalar that OpenSpec reads as written.
- Third check: `uv run devops roadmap eval stage --replay` states the score of the stage model before and after the change, which the stage job asks of a plan that changes the prompt.
- The call `load_task_prompt` needs a checkout of the repository, because it reads `src/devops_cli/ai/tasks/`.
- The command `uv run devops roadmap eval stage --replay` needs a checkout of the repository and a client of the model service, because it plans each golden case with the stage model.

## Existing Tool Considered

No open, maintained tool covers the need: no linter or checker counts the members of a set that only a running program produces, and no tool reconciles a CLI schema with a project guard. The change adds one prompt rule, one config rule and their test, and it deletes no internal code. Cost: 3k tokens and 1 hour of elapsed time to build, keep and fix, against about 15k tokens and 1 hour for a check in `devops roadmap stage`.

## Dependencies

None. Commit 5520193a merged #3957, which changed `src/devops_cli/ai/tasks/roadmap_stage_change.md`, so the prompt file is ready for this change.
