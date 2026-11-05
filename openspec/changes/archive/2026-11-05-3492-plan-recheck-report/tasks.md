# Tasks

## 1. Judge each change folder again

Reads: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/planned.py`. Changes: `src/devops_cli/roadmap/plan_recheck.py` (new), `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_plan_recheck.py` (new).

- [x] 1.1 Write `tests/roadmap/test_roadmap_plan_recheck.py` with cases for one result of each folder, the folder of a closed issue, a delivered plan, a plan with no `Verification:` line and an unreadable plan
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` fails on the base
- [x] 1.2 Write `src/devops_cli/roadmap/plan_recheck.py` with `recheck_plans` and `render_recheck`, add `created_paths` to `src/devops_cli/roadmap/plan_read.py`, and make the file helpers of `src/devops_cli/roadmap/plan_check.py` public
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` passes

## 2. Add the command

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py` (new), `tests/ai/mcp/test_mcp.py`.

- [x] 2.1 Write `tests/commands/test_roadmap_plan_recheck_cmd.py` with a case for the dry run and a case for `--json`
  - Verification: `uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [x] 2.2 Add `plan_recheck_cmd` with `--repo`, `--source`, `--json` and `--dry-run`, its dry-run reads, its help and its messages
  - Verification: `uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` passes

## 3. State the policy

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`. Changes: `docs/roadmap/plan-recheck.md` (new), `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 Write `docs/roadmap/plan-recheck.md` with the results, the counts and the policy that a new gate on merged plans only reports until this pass has run, link it from `docs/ROADMAP_WORKFLOW.md`, and regenerate the command reference with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: A test: the report gives each numbered folder one result.
- Group 1: A test: a folder of a closed issue gets `cleanup`, and no denominator counts it.
- Group 1: A test: a plan whose `(new)` file exists on the default branch gets `delivered`.
- Pending person: A test compares the groups before and after a rewrite, and each new line passes `read_verification`., The rewrite goes to #3556, as the issue allows.
- Pending person: A test: an item with no way forward leaves the queue, and `devops roadmap explain` names its first problem., The leave-out goes to #3556, as the issue allows.
- Group 3: `docs/ROADMAP_WORKFLOW.md` states the policy.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
