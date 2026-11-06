# Tasks

## 1. Leave out a case that holds no commit, and fix the commits of the set

Kind: behavior. Reads: `src/devops_cli/roadmap/clone_git.py` (`checkout_at`). Changes: `tests/roadmap/test_roadmap_stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_verify_eval.py`, `tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/case.json`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_eval_score.py`, `src/devops_cli/roadmap/stage_eval_render.py`, `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_eval_cases.py`, add the test of the set: the `base_commit` and the `merge_commit` of each case are the full hash of a commit of this repository, or `NO_COMMIT` in a case whose notes say that it reads no commit. Add the tests of `has_commit` and `cases_with_commit`: the split, the order, and the error when no case holds a commit.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py` fails on the base
- [x] 1.2 In `tests/roadmap/test_roadmap_stage_verify_eval.py` and `tests/roadmap/test_roadmap_stage_eval_command.py`, add the command tests of the spec: a left-out case in a live run, in a dry run and in the JSON report, the run of no case, and the replay of a left-out case. In `tests/roadmap/test_roadmap_stage_eval_run.py`, add the test of a repository that lacks the commit, with the run of the other case.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py tests/roadmap/test_roadmap_stage_eval_command.py tests/roadmap/test_roadmap_stage_eval_run.py` fails on the base
- [x] 1.3 In `case.json` of `3372-the-stage-plan-of-a-module`, set `base_commit` to `ecfc9b80816c7e1deeceb24a588a6139bf12ef77` and `merge_commit` to `6c15a64a614941629669a181e3220ae8bc7e27d0`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py` passes
- [x] 1.4 In `stage_eval_cases.py`, add `NO_COMMIT`, `StageCase.has_commit`, `cases_with_commit` and the note of the left-out cases. In `stage_eval_score.py` and `stage_verify_eval.py`, give the two scores the field `left_out`. In `stage_eval_render.py` and `stage_verify_eval.py`, print and write it. In the two commands, apply the rule after `select_cases`, in the dry run and in the live run. In `stage_eval_run.py`, end a case as `failed` when `GitOperationError` stops its checkout. Add the messages.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py tests/roadmap/test_roadmap_stage_eval_command.py tests/roadmap/test_roadmap_stage_eval_run.py tests/roadmap/test_roadmap_stage_eval_cases.py` passes

## 2. Document the rule

Kind: documentation. Changes: `src/devops_cli/lang/en/help.py`, `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`.

- [x] 2.1 In `help.py`, add one sentence to `eval_stage` and to `eval_verify`: a case that holds no commit is left out and named in the report. In `docs/ROADMAP_WORKFLOW.md`, say the same in the text of the live run and of the verify run. Regenerate the command documents.
  - Verification: `uv run devops ci docs` passes

## Criteria

- A test holds that each `base_commit` of the set is either a full hash of a real commit, or a case that the verify command leaves out and names in its report: group 1
- A run of the set does not exit 1 for these two cases: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
