# Proposal

## Why

Issue #3688 reports that cases of the golden set of the stage job hold a `base_commit` that is no commit. `devops roadmap eval verify` and the live run of `devops roadmap eval stage` check out the `base_commit` of each case with `git worktree add --detach`. Git refuses a commit that does not exist, so these cases cannot run.

- The case of #3372 holds `89682e41` followed by 32 zeros, and its `merge_commit` holds `6c15a64a` followed by 32 zeros. A person shortened the hashes, and a tool filled the rest with zeros.
- The cases of #3411 and #3331 hold 40 zeros in both fields. The change of each was never merged as that plan, so the case reads no commit. The issue names the case of #3411. The case of #3331 came after the issue (#3716) with the same placeholder.

The verify command ends these cases as `failed` and exits 1, so a run of the set never exits 0, and the score counts their defects as not found. The live run of the stage command is worse: `run_case` opens the checkout outside the `try` that ends a case as `failed`, so the `GitOperationError` of the first bad case stops the whole run. The run of a measured 2 hours ended with no stored report.

## What Changes

- The case of #3372 holds the full hash of a real commit in `base_commit` and in `merge_commit`.
- The zeros of the other two cases are the null object id of git, and the code names it: `NO_COMMIT`. A case with `NO_COMMIT` as `base_commit` holds no commit. `StageCase.has_commit` says so.
- `cases_with_commit` is the one rule of both commands. It splits the selected cases into the cases that hold a commit and the names of the cases that hold none. It reads no git, so a dry run, which makes no request to git, applies it too. When the selection holds no case with a commit, it raises `ConfigurationError` that names the cases.
- `devops roadmap eval verify` and `devops roadmap eval stage` apply the rule after the selection of the cases. A case that holds no commit is left out of the run, of the dry run, of the case count and of the score. The text report and the JSON report name it (`left_out`). A left-out case does not change the exit code.
- `devops roadmap eval stage --replay` reads no git, so it keeps all cases.
- `run_case` of the live stage run ends a case as `failed` when git cannot check it out, as it does for a failed model call. The other cases run and the report is stored. The exit code is 1, as for each failed case.
- A test holds that the `base_commit` and the `merge_commit` of each case are the full hash of a commit of this repository, or `NO_COMMIT` with a note that says the case reads no commit.
- The change alters the output and the exit code of two commands, so it carries a spec delta on `roadmap-stage-eval`. The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: A case that holds no commit is left out and named; A run with no case to check out fails, and the replay keeps every case; A commit that git cannot check out ends its case and not the run; Each commit of the set is real or the case reads none

## Impact

- Code: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_eval_score.py`, `src/devops_cli/roadmap/stage_eval_render.py`, `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Data: `tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/case.json`
- Tests: `tests/roadmap/test_roadmap_stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_verify_eval.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`
- Specs: `openspec/specs/roadmap-stage-eval/spec.md` (by archive)

## Feasibility

- Command output with git 2.55.0. `git worktree add --detach <path> 89682e4100000000000000000000000000000000` and the same command with 40 zeros both end with `fatal: invalid reference`. So the premise of the issue holds.
- `git rev-parse 89682e41` gives `89682e41118206c680e8d2273903d00d61ae140b`, and `git rev-parse 6c15a64a` gives `6c15a64a614941629669a181e3220ae8bc7e27d0`. The second is the squash merge of pull request 3378, the plan of #3372.
- The first hash is the commit `chore(main): release 0.55.0`, made 2 hours 33 minutes after that merge. The set holds the rule that the staging commit of a plan is the parent of its merge commit, because the staging commit is not in the history after a squash (docstring of `stage_eval_cases.py`). 41 of the 45 cases follow the rule. `git rev-parse 6c15a64a^` gives `ecfc9b80816c7e1deeceb24a588a6139bf12ef77`, the commit before the merge, and the facts of the case hold only files that this commit has. So the case takes this parent as `base_commit`, and the data follow the rule that the set states. A checkout of `89682e41` would hold 110 changed files that did not exist when the plan was staged.
- The cases `3331-a-plan-that-changes-a-check` and `3411-a-what-changes-item-that-names` hold 40 zeros, and their notes say the case reads no commit. `git cat-file -t` for the 40 zeros gives an error. A scan of all 45 cases finds exactly these three cases and no other `base_commit` or `merge_commit` that is no commit.
- The code. `checkout_at` in `src/devops_cli/roadmap/clone_git.py` raises `GitOperationError` for a commit that git refuses. In `stage_verify_eval.py` the call sits in the task that `pydantic-evals` runs, which records an error as a failed case, so the verify command ends the case as `failed` and stores the report. In `stage_eval_run.py` the call sits before the `try` of `run_case`, which catches only `AIClientError`, `RoadmapStageError` and `ToolExecutionError`, so `GitOperationError` ends `run_cases`. The test `test_a_commit_that_the_repository_lacks_fails_and_leaves_no_worktree_and_no_folder` shows that `checkout_at` raises for a commit that the repository lacks.
- The spec says that `--dry-run` makes no request to git. So the rule that leaves a case out cannot ask git whether the commit exists. It reads the data of the case. A commit that the data name and that git cannot check out is an error of the run, and it ends its case as `failed`.

## Existing Tool Considered

Git covers the need: `git rev-parse` and `git cat-file -e <hash>^{commit}` say whether a hash is a commit, and `git worktree add` is already the checkout. The all-zero id is the null object id of git, which Git itself uses for "no object". No library gives a better constant, and a new dependency for one 40-character string has no use. The change adds one constant, one property, one function of about 10 lines and one `try` in `run_case`. It deletes no code. The written cost is about 40,000 tokens to build, about 1,000 tokens per year to keep, and about two hours elapsed.
