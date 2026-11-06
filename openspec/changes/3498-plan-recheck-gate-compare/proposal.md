# Proposal

## Why

Nobody states what a plan gate does over real plans before it merges (#3498). The golden set holds few good plans, so it cannot show a false refusal. `devops roadmap plan-recheck` (#3492) already judges each change folder of the default branch with no model. It prints one sentence for each problem, names no gate, compares no branch with the default branch, and marks no refusal as a case to review. A person who adds a gate cannot see the hits and the false refusals of that gate. This change extends `plan-recheck`. It adds no command.

## What Changes

- Name the gate of each problem of `check_proposal`. `src/devops_cli/roadmap/stage_change.py` gets the enum `ProposalGate` and the function `check_gates`, which gives the problems under the name of their gate. `check_proposal` joins them and returns the same list as before.
- Print the gate with each refusal of `plan-recheck`, and print the number of refusals for each gate. A folder that the reader refuses has the gate `read`, and a finding of `openspec validate` has the gate `openspec`.
- Add the option `--branch <ref>`. The command judges the change folders of the ref and of the default branch, lists the refusals under each gate for both sides, and lists the refusals that the branch adds. It marks each added refusal as a case to review. A folder that the reader refuses is listed as not read, and the run goes on.
- Say in `src/devops_cli/roadmap/plan_recheck.py` and in the documents what `plan-recheck` judges less than the stage job: no premise probe, no overlap with open pull requests, no recorded search, no plan of another open item, no group measure, no secret scan, no title check and no model review.
- State the rule in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-check.md`: a plan or a pull request that adds a gate gives the refusals of that gate and a replay of the defect that it cites. Describe the option in `docs/roadmap/plan-recheck.md`.
- Carry a spec delta: the option, the gate names and the report are observable behavior.
- Leave the reader defect for a criterion of `Group 0` in #3591, and the close of #3331 and #3397 and the decision on #3398 in #3706.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-recheck`: Plan-recheck names the gate of each refusal, Plan-recheck compares a branch with the default branch, Plan-recheck lists the refusals of each gate for both sides, A refusal that the branch adds is a case to review, A folder that the reader refuses does not stop a comparison

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`, `docs/roadmap/plan-recheck.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`
- Tests: `tests/roadmap/test_roadmap_stage_gates.py`, `tests/roadmap/test_roadmap_plan_recheck.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`

## Feasibility

- `uv run devops roadmap plan-recheck` (devops-cli 0.63.2, `origin/main` at 396962e6, 2026-11-06) read 56 change folders in 29 seconds and gave 13 `ok`, 38 `new-plan` and 5 `cleanup`. Its lines hold the sentence of each problem and no gate name. So the premise holds: the gap is the gate name, the comparison with a branch and the review mark. The command itself exists.
- `read_file src/devops_cli/roadmap/stage_change.py` shows that `check_proposal` joins the lists of twelve checks (`_delta_problems`, `content_problems`, `form_problems`, `eval_replay_problems`, `path_problems`, `_what_changes_problems`, `move_prefix_problems`, `move_verify_problems`, `search_problems`, `criterion_problems`, `_overlap_problems` and `creates_problems`) into one list of sentences. Each call site is one name, so the gate of a sentence is known where the list is built. A match on the text of a sentence is not needed.
- `read_file src/devops_cli/roadmap/stage.py` and `src/devops_cli/roadmap/implement.py` show the inputs of the job that `plan-recheck` does not give to `check_proposal`: `probes`, `overlaps`, `search_evidence` and `plan_creates`. The job also measures the groups, scans the files for secrets and checks the staging title. This is the list of what `plan-recheck` judges less than the job.
- `read_file src/devops_cli/roadmap/planned.py` shows that `read_planned_changes` lists the folders of `origin/<default>` with one `git ls-tree`. The same listing at any ref gives the folders of a branch.
- `read_file src/devops_cli/roadmap/plan_read.py` shows that `read_change` raises `PlanReadError` for a folder it cannot read, and that a criterion of `Group 0` raises `ValidationError` outside its `try` block. The full pass on `origin/main` ended with exit 0, so no folder of the default branch holds that criterion today. #3591 fixes the reader, and this change catches no `ValidationError`.
- The run time of the pass with `--branch` is measured in `design.md`.

## Existing Tool Considered

No outside tool runs the gates of this project over its change folders. The change extends `devops roadmap plan-recheck`, its plan reader `read_change`, and `check_proposal`. It adds no command and no second reader. The change builds about 150 lines in `plan_recheck.py` and about 40 lines in `stage_change.py`. Written cost: about 50,000 tokens to build, about 5,000 tokens each year to keep and fix, and about 3 hours of elapsed time. The change deletes no code.
