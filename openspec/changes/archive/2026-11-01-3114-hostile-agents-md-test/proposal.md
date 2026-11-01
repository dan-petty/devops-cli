# Proposal

## Why

Issue #3114: on `main`, `tests/roadmap/test_roadmap_implement_step_rules.py::test_a_hostile_agents_md_is_data_and_never_changes_the_instructions` fails. Pull request #3107 added the test. Pull request #3111 then made `build_step_inputs` fill the two placeholders of the prompt with `fill_prompt`. The test still compares the instructions with the raw prompt, so the required check Tests & Coverage is red on `main`.

## Feasibility

- `uv run pytest tests/roadmap/test_roadmap_implement_step_rules.py -k hostile -n0` fails on `origin/main` with `assert (False, True, True) == (True, True, True)`.
- `fill_prompt` is in `src/devops_cli/roadmap/implement_shell_policy.py` and replaces the two placeholders with the programs table and the refusals table.

## Existing Tool Considered

No external tool covers this. The change edits one assertion.

## What Changes

- `tests/roadmap/test_roadmap_implement_step_rules.py` compares the instructions with `fill_prompt(load_task_prompt("roadmap_implement_step.md"))`. The test still shows that a hostile `AGENTS.md` leaves the instructions unchanged.
- The change has no spec delta: no `devops` command, option or message changes.

## Impact

- Tests only. The required check Tests & Coverage passes on `main` again.
