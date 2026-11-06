# Tasks

## 1. Name the gate of each problem

Reads: `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_gates.py` (new).

- [x] 1.1 Write `tests/roadmap/test_roadmap_stage_gates.py` with cases for the problems of each gate under its name, for a key of every member of `ProposalGate`, and for the flat list of `check_proposal`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_gates.py` fails on the base
- [x] 1.2 Add the enum `ProposalGate` and the function `check_gates` to `src/devops_cli/roadmap/stage_change.py`, and make `check_proposal` join the problems of `check_gates`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_gates.py` passes

## 2. Compare a branch with the default branch

Reads: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/planned.py`. Changes: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_recheck.py`.

- [x] 2.1 Add cases to `tests/roadmap/test_roadmap_plan_recheck.py` for the gate name of a refusal, the read of both sides, the refusals of each gate for both sides, a refusal that the branch adds, and a folder that the reader refuses
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` fails on the base
- [x] 2.2 Give each refusal its gate in `src/devops_cli/roadmap/plan_recheck.py`, judge the folders of a ref with `recheck_plans`, and list the refusals of each gate, the added refusals and the folders that are not read in `render_recheck`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` passes

## 3. Add the option to the command

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`.

- [x] 3.1 Add cases to `tests/commands/test_roadmap_plan_recheck_cmd.py` for the option `--branch` in the dry run and in the JSON output
  - Verification: `uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [x] 3.2 Add the option `--branch` to `plan_recheck_cmd`, its dry-run reads and its help
  - Verification: `uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` passes
- [x] 3.3 Run the command with `--branch` over the default branch and record the run time in `design.md`
  - Verification: `uv run devops roadmap plan-recheck --source . --branch HEAD` ends in under 5 minutes

## 4. State the rule

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`, `docs/roadmap/plan-recheck.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`, `docs/roadmap/plan-recheck.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`.

- [ ] 4.1 Write the rule that a plan or a pull request that adds a gate gives the refusals of that gate and a replay of its cited defect, and what `plan-recheck` judges less than the job, in `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md` and `docs/roadmap/plan-recheck.md`, and regenerate the command reference with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: A test: `check_proposal` gives the problems of each gate under the name of the gate, and the flat list of problems does not change.
- Group 2: A test: with `--branch`, the run reads each change folder of the branch and of the default branch with `read_change`, and it makes no model request.
- Group 2: A test: the output lists the refusals of each gate for the branch and for the default branch.
- Group 2: A test: the output names the folder, the gate and the message of each refusal that the branch adds, and it marks each one as a case to review.
- Group 2: A test: a change folder that the reader cannot read appears as not read, and the run goes on.
- Group 4: `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-check.md` state the rule that a plan or a pull request that adds a gate gives this result and a replay of its cited defect, and they state what `plan-recheck` judges less than the job.
- Group 3: The run time of `plan-recheck` with `--branch` on `origin/main` is below 5 minutes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
