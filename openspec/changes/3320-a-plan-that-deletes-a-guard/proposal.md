# Proposal

## Why

`check_proposal` accepts a plan that deletes a guard check, so the review of PR #3277 found the weakened threshold by reading the tasks (#3320). AGENTS.md rule 5 says only the owner may lower a quality threshold, so the plan must record the check, what it stopped and its safeguard.

## What Changes

- Add a `weakened_checks` list to `StageProposal`, each entry holding `check`, `stopped` and `safeguard`.
- Refuse a plan whose work texts delete a test or a `CONST_*` entry that no `weakened_checks` entry names.
- Render a `## Weakened checks` section in `proposal.md` after `## Impact` and before `## Feasibility`, and only when the list is not empty.
- Add the message texts of the new problem and section to `MESSAGES.roadmap`.
- Add the proposal rule of `openspec/config.yaml` that asks for the section.
- Add a replay case of a plan that deletes the guard test and records nothing, and score the same model before and after.
- The change carries a spec delta because `check_proposal` decides whether the stage job accepts a plan, and a consumer observes that answer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan that deletes a guard check records it, The proposal file shows each weakened check

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `openspec/config.yaml`, `src/devops_cli/roadmap/stage_eval_cases.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_weakened_checks.py`

## Feasibility

- `probes` states "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit." The module holds `check_proposal` and `render_change`, the two functions that the issue names.
- `probes` states "The path `tests/ai/mcp/test_mcp.py` is a file of the staging commit." Its `test_all_cli_commands_are_either_exposed_or_excluded` holds the hand-written `mcp_command_exclusions` tuple that the issue cites.
- `probes` states "The path `openspec/config.yaml` is a file of the staging commit." It holds a `rules:` block with a `proposal:` list, so a proposal rule is a data edit.
- `probes` states "The path `src/devops_cli/config/constants.py` is a file of the staging commit." It holds the `CONST_*` inventories that the issue cites as guard lists.
- `probes` states "The path `AGENTS.md` is a file of the staging commit." Its rule 5 reads "Never lower a security or quality threshold: only the owner can allow it."
- `probes` states "The path `proposal.md` is no file of the staging commit. No commit in the history deleted or renamed it." The section is a heading of a rendered file, not a file of the repository, so the plan creates no such path.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_weakened_checks.py` fails on the missing `weakened_checks` field.
- Second check: `uv run devops openspec check` accepts the change folder after the delta is written.
- Third check: `uv run devops roadmap eval stage --dry-run` lists the new replay case with no model call.

## Existing Tool Considered

No open, maintained tool or library covers the need: the rule refuses a plan of this repository, so it lives in `check_proposal`. To build it instead costs about 40k tokens to write, about 5k tokens a month to keep and fix, and about 3 hours of elapsed time. The change deletes no internal code: `check_proposal`, `render_change` and `MESSAGES.roadmap` stay and gain one rule, one field and one section.
