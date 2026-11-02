# Proposal

## Why

Issue #3153. The stage job checks a plan only with deterministic gates: `check_proposal` (paths and the rules of the schema) and `openspec validate`. The evaluation of 2026-11-02 shows that these gates miss most of the defects that a reviewer finds. A model review with the cited files as context finds more, among them false premises, code that already exists and contrived tests. A merged bad plan blocks a later implement Job.

## What Changes

- New module `src/devops_cli/roadmap/stage_verify.py` and prompt `roadmap_stage_verify.md`. A verification pass makes one `chat_structured` call with the client of the task slot `ai.tasks.verification`. Its input is the issue, the plan, and the first lines of each file that the plan cites, each capped at `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens, with at most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files. Its output is a list of findings. A finding has one of the nine types of `DefectType` (`stage_eval_cases.py`), the place, the problem, and a quote as evidence.
- The pass runs in the planner of `stage.py`, after `check_proposal` and `validate_change` pass and before `_stage_one` opens the draft pull request.
  - A reply with a type outside the nine types fails the schema. The reply goes back once, as every reply that breaks the schema does. A second one stops the item, so no draft opens.
  - A finding of type `missing_path`, `false_premise` or `ignores_existing_code` whose quote is in the issue, the plan or a cited file returns the plan to the planner at most once. The planner gets the findings as the `problem`, and the revised plan passes the gates and the verification again.
  - Every other finding, and every finding of the revised plan, goes into the one comment of the job on the issue, which names the draft pull request. The draft opens. The pass never merges and never marks the pull request ready.
- `plan_stage` takes a `verifier` client. The two callers (`devops roadmap stage` and the stage adapter of the Service) pass the client of the `verification` task. Without a `verifier`, the planner makes no verification call, as the golden-set run of the planner does.
- New command `devops roadmap eval verify`. It runs the pass on each case of the golden set with the model of the `verification` task or `--model`, and prints the recall of the labeled defects (all, and the blocker and major ones), the recall by type, and the findings on the `good` plans. It stores the score as JSON under `.data/roadmap_eval/verify/`. It has `--case`, `--model`, `--limit`, `--json`, `--dry-run`, `--cases` and `--source`. Its dry-run class is `request-plan`. The run uses pydantic-evals, as the eval of intake duplicates does.
- `README.md` is regenerated for the new command. The module text of `stage.py` and the docstrings state the new step.
- Observable behavior changes (a command, a comment and a stop reason), so the change carries a spec delta. It only adds requirements: it modifies and removes none.
- The change fits one pull request.

### Cost of the pass

One call for each plan, and one more after a return. The issue puts it at about 0.03 USD for a plan with `claude-sonnet-5-5`. The eval makes one call for each of the 40 cases of the golden set.

### Out of scope

- The toolbox of the planner (#3037) stays as it is. The pass reads the plan after the planner made it.
- The model of the slot. `ai.tasks.verification` is user configuration (`config.yaml`), and the change does not edit it. A person sets it to `claude-sonnet-5-5`. The gateway fallback to `deepseek-v4.1-flash-1017` is in `k8s/llm/gateway/config.yaml` (#3154).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: ADDED requirements for the verification pass.
- `roadmap-stage-eval`: ADDED requirements for `devops roadmap eval verify`.

## Impact

- Code: `src/devops_cli/roadmap/stage_verify.py` (new), `src/devops_cli/roadmap/stage_verify_eval.py` (new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval.py`, `src/devops_cli/commands/roadmap_eval_verify.py` (new), `src/devops_cli/ai/tasks/roadmap_stage_verify.md` (new), `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `README.md` (regenerated).
- Tests: `tests/roadmap/test_roadmap_stage_verify.py` (new), `tests/roadmap/test_roadmap_stage_verification.py` (new), `tests/roadmap/test_roadmap_stage_verify_eval.py` (new), and the tests of the stage job and its adapter that use the model fake.

## Feasibility

Checked on 2026-11-02 against the repository and its commands:

- The slot exists. `AITasksConfig.verification` is in `src/devops_cli/config/settings.py`, `AIConfig.for_task("verification")` resolves it, and `get_llm_client(task="verification")` builds its client (`ai/client/factory.py` reads `for_task(task)`). `ai/run_store.py` records its model in the setup of a review. One difference from the issue: no review call site uses the slot today (the review runner reads `analysis`). This change adds the first call, so the slot needs no new setting.
- The gateway fallback exists. `k8s/llm/gateway/config.yaml` has `claude-sonnet-5-5: [deepseek-v4.1-flash-1017]` (#3154). A call through the gateway to Sonnet falls back with no code in the CLI.
- The golden set has labeled defects. `tests/fixtures/roadmap_eval/stage/` holds 40 cases: 37 plans with 299 labeled defects of the nine types (20 blocker, 147 major, 100 minor, 32 nit) and 3 `good` plans with none. The loader is `load_cases` in `stage_eval_cases.py`. The set stores the plan and the issue text. It does not store the cited files, so the eval reads them from the checkout of `base_commit` (`checkout_at`, as `eval stage` does).
- `_stage_one` opens the draft after `plan_stage` returns the changes. The checks run in `_Planner._settle` (`check_proposal`, `path_problems`, `validate_change`), so the pass belongs in `_Planner.plan`, after `_settle` returns a `StagedChange`.
- The client contract holds. `chat_structured` validates a reply against a pydantic model, so an enum field refuses an unknown type, and the return of a reply that breaks the schema is the existing `_REPLY_RETURNS` path. Command output: the tests `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_job.py` and `tests/roadmap/test_roadmap_stage_eval_command.py` pass on the base (89 passed, 4 skipped).
- The premise holds. The change needs no code that works around a missing tool.

## Existing Tool Considered

For the eval, pydantic-evals (2.59.0, in `uv.lock`) is adopted: `Dataset.evaluate_sync` runs the cases and a custom `Evaluator` scores each one, as `roadmap/duplicate_eval.py` does. For the pass itself, no open, maintained library reviews a staged OpenSpec plan against the files it cites. Review tools such as promptfoo and deepeval grade a model answer against a rubric. They do not know the plan schema, the nine defect types or the stage job, and they add a Node or Python dependency for one call. So the change builds `stage_verify.py` (about 150 lines), one prompt and one eval module (about 150 lines). Written cost: about 80 000 tokens and 5 hours to build, one prompt and one eval command to keep, and about 20 000 tokens to fix the prompt when a new model scores lower. It deletes no code.
