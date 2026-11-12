# Proposal

## Why

`check_proposal` accepts a plan that deletes a guard check, so the review of PR #3277 found the weakened threshold by reading the tasks (#3320). AGENTS.md rule 5 says only the owner may lower a quality threshold, so the plan must record the check, what it stopped and its safeguard.

## What Changes

- Show the `weakened_checks` list of `StageProposal` in the reply schema, and name the key in the planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Each entry holds `check`, `stopped` and `safeguard`. #3490 added the model and `read_change` reads the section.
- Refuse a plan whose work texts delete a test or a `CONST_*` entry that no `weakened_checks` entry names.
- Render a `## Weakened checks` section in `proposal.md` after `## Impact` and before `## Feasibility`, and only when the list is not empty. The section uses `stage_weakened_checks_title` and `stage_weakened_entry` of `MESSAGES.roadmap`, the form that `read_change` reads.
- Add the message text of the new problem to `MESSAGES.roadmap`.
- Add the proposal rule of `openspec/config.yaml` that asks for the section.
- Add a replay case of a plan that deletes the guard test and records nothing, and score the same model before and after.
- The change carries a spec delta because `check_proposal` decides whether the stage job accepts a plan, and a consumer observes that answer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/plan-text`: A plan that deletes a guard check records it; the proposal file shows each weakened check.

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `openspec/config.yaml`, `src/devops_cli/roadmap/stage_eval_cases.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_weakened_checks.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Weakened checks

- **`tests/roadmap/test_roadmap_plan_read_weakened.py::test_the_reply_schema_of_the_stage_model_does_not_show_the_field`**: Stopped: a reply key that the stage job cannot write, so the job would lose the value. Safeguard: Task 2.1 shows that `render_change` writes an entry and that `read_change` reads it back.

## Feasibility

- `probes` states "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit." The module holds `check_proposal` and `render_change`, the two functions that the issue names.
- `probes` states "The path `tests/ai/mcp/test_mcp_exposure_table.py` is a file of the staging commit." Its `test_all_cli_commands_are_either_exposed_or_excluded` holds the hand-written `mcp_command_exclusions` tuple that the issue cites.
- `probes` states "The path `openspec/config.yaml` is a file of the staging commit." It holds a `rules:` block with a `proposal:` list, so a proposal rule is a data edit.
- `probes` states "The path `src/devops_cli/config/constants.py` is a file of the staging commit." It holds the `CONST_*` inventories that the issue cites as guard lists.
- `probes` states "The path `AGENTS.md` is a file of the staging commit." Its rule 5 reads "Never lower a security or quality threshold: only the owner can allow it."
- `probes` states "The path `proposal.md` is no file of the staging commit. No commit in the history deleted or renamed it." The section is a heading of a rendered file, not a file of the repository, so the plan creates no such path.
- `tests/roadmap/test_roadmap_stage_prompt_rules.py` holds `test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal`, which compares the top-level key bullets of `roadmap_stage_change.md` with the properties of the schema of `StageProposal`. A field that the schema shows and that has no key bullet fails this test, so the plan changes the prompt in the same group.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_weakened_checks.py` fails on the missing `weakened_checks` field.
- Second check: `uv run devops openspec check` accepts the change folder after the delta is written.
- Third check: `uv run devops roadmap eval stage --dry-run` lists the new replay case with no model call.

## Existing Tool Considered

No open, maintained tool or library covers the need: the rule refuses a plan of this repository, so it lives in `check_proposal`. To build it instead costs about 40k tokens to write, about 5k tokens a month to keep and fix, and about 3 hours of elapsed time. The change deletes no internal code: `check_proposal`, `render_change` and `MESSAGES.roadmap` stay and gain one rule, one field and one section.
