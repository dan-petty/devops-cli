# Proposal

## Why

No job judges a merged plan again (#3492). A later gate can strand an old plan, a delivered plan can stay Planned, and the folder of a closed issue stays in each count. A person cannot see how many plans a new gate strands before the gate lands. This change adds the report that shows it.

## What Changes

- Add `devops roadmap plan-recheck`. It reads each numbered folder of `openspec/changes/` on the default branch and gives each one result: `ok`, `rewrite`, `new-plan`, `delivered` or `cleanup`.
- Leave the folders of closed issues out of every count.
- Count the folders with no `Verification:` line and the folders that the plan reader refuses.
- Add `--json` and `--dry-run`. The command writes nothing, so it has no `--confirm`.
- State the policy in `docs/roadmap/plan-recheck.md` and `docs/ROADMAP_WORKFLOW.md`: a new gate on merged plans only reports until this pass has run.
- Rename three helpers of `plan_check.py` to public names, and add `created_paths` to the plan reader, so the pass reuses them.
- Split the work (AGENTS.md rule 1). The rewrite, the leave-out of an item with no way forward, and a `--confirm` mode go to the second issue #3556. The order of #3492 puts the report first, and #3393 before the rewrite.
- Carry a spec delta: the command, its results and its counts are observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-plan-recheck`: Plan-recheck gives each change folder one result, Plan-recheck leaves the folder of a closed issue out of every count, Plan-recheck marks a delivered plan, Plan-recheck reports a plan that fails a check, Plan-recheck reports a plan that a rewrite can fix, Plan-recheck writes nothing

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_plan_recheck.py`

## Feasibility

- `read_file src/devops_cli/roadmap/plan_read.py` shows `def read_change(files: Mapping[str, str]) -> StageProposal:`, so the reader takes the files of a folder as text. The pass reads them with `git show` from `origin/<default branch>`.
- `uv run python` over the 53 folders on `origin/main` (2026-11-05) shows that `read_change` accepts 24, raises `ValidationError` for 23 and `PlanReadError` for 10. The pass relies on #3482 (open pull request #3545), which turns each error into `PlanReadError`. So the pass can read every folder only after #3545 merges.
- `read_file openspec/changes/3236-read-only-tools-take-paths-that/tasks.md` shows `Changes: ... (new)` on its own line after `Reads:`, which `read_change` refuses. So the pass reads the `(new)` marks with `created_paths`, which does not need that layout.
- `read_file src/devops_cli/roadmap/store.py` shows `open_items()` and `item(number)` on `RoadmapStore`. One listing of the open issues, and one read for each folder whose issue is not open, tell which issues are closed.
- The first check against the real system is `uv run devops roadmap plan-recheck --dry-run`, which lists the reads, then `uv run devops roadmap plan-recheck` on the default branch.

## Existing Tool Considered

`openspec validate --strict --json` checks the form of a folder, and the pass runs it through `validate_change`. `openspec archive` does the cleanup, and the report names it for a `cleanup` folder. The plan reader, `check_proposal` and `parse_task_groups` give the rest. The change builds one module of about 200 lines that joins them, and no second validator. Cost: about 60k tokens to build, 20k to keep and 1 hour of elapsed time. The change deletes no code.
