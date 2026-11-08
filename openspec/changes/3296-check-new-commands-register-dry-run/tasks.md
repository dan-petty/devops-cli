# Tasks

## 1. Report the missing companions of a new command

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/pr.py`, `tests/commands/test_pr_dry_run.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_companions.py` (new), `src/devops_cli/roadmap/stage/stage_companions.py` (new), `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`.

- [ ] 1.1 Write `test_a_new_command_with_no_companion_registration_is_refused`, `test_a_new_command_with_every_companion_registration_passes`, `test_an_edit_of_an_existing_command_is_no_new_command`, `test_a_command_of_another_family_is_no_new_command` and `test_a_new_command_with_no_command_module_is_no_new_command` in `tests/roadmap/stage/test_roadmap_stage_companions.py`. Each calls `companion_problems` with a `StageProposal` and a `read_text` that returns a sample `src/devops_cli/commands/pr.py`. Add `test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_companions.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage/stage_companions.py` with `companion_problems(proposal, read_text)`. For each group that changes a path under `src/devops_cli/commands/`, it takes the stem of that path, finds each `devops <stem> <word>` in the task texts of the group, and treats the command as new when the staged text of the module, read through `read_text`, holds no quoted `"<word>"` literal. For a new command it appends one problem for each missing companion: no `command-dry-run-class` spec delta that names the command, no task text that names `tests/commands/test_<stem>_dry_run.py`, and no task text that holds `REGENERATE_DOCUMENTS` and `uv run devops ci docs`. Add the member `COMPANIONS = "companions"` to `ProposalGate`, the line `ProposalGate.COMPANIONS: companion_problems(proposal, read_text)` to `check_gates`, and `src/devops_cli/roadmap/stage/stage_companions.py` to `STAGE_EVAL_TRIGGER_PATHS`. Add the problem texts `stage_problem_companion_dry_run_class`, `stage_problem_companion_callback` and `stage_problem_companion_documents` to `MESSAGES.roadmap`. Run `uv run devops roadmap eval stage --replay` on the base commit and on the change with the same model, and state the score before and after the change in the pull request comment. Run `uv run devops roadmap plan-recheck --source . --branch HEAD` and mark each `companions` refusal as a hit or a false refusal in the same comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_companions.py` passes

## 2. Name the companions gate in the plan-check document

Reads: `docs/roadmap/plan-recheck.md`, `docs/roadmap/plan-check.md`, `openspec/specs/roadmap-stage/spec.md`. Changes: `docs/roadmap/plan-recheck.md`.

- [ ] 2.1 Add the row `| `companions` | A plan that adds a `devops` command and misses its dry-run class, its dry-run callback test or one of the two documentation commands. |` to the gate table of `docs/roadmap/plan-recheck.md`. State under the table that a new command needs no MCP exposure entry and no exclusion entry
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `docs/roadmap/plan-recheck.md` to name the `companions` gate and the registrations of a new command
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: The stage proposal check SHALL report a `devops` command that a task group names and that the command tree at the staged commit does not hold.
- Group 1: The stage proposal check SHALL NOT report a companion registration finding for a task group that names only commands that the staged tree holds.
- Group 1: The stage proposal check SHALL refuse a plan that adds a CLI command without a `command-dry-run-class` spec delta entry for that command.
- Group 1: The stage proposal check SHALL require a task that adds the new command to the dry-run callback table of its family.
- Pending person: The stage proposal check SHALL require a task that adds the new command to `CONST_MCP_EXPOSURE_TABLE` or records its exclusion in `tests/ai/mcp/test_mcp.py`., The premise is false at this commit: `tests/ai/mcp/test_mcp.py` is no file of the commit, and `test_mcp_exposure_table.py` requires no entry for a new command, so the plan adds no MCP rule. A person decides whether to drop the requirement from the issue.
- Group 1: The stage proposal check SHALL require a task for `uv run devops docs generate --sync-readme` and a task for `uv run devops ci docs` when a plan adds a CLI command.
- Group 1: The stage proposal check SHALL report all missing companion registrations of a new CLI command in one finding list.
- Group 1: The roadmap test suite SHALL hold unit tests for a plan that adds a CLI command with and without its companion registrations.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
