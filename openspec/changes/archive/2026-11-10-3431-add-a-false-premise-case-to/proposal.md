# Proposal: #3431

## Why

The golden set of the verification pass has no plan whose design restates a rule of a file that the plan cites and gets the restatement wrong. The pass can therefore miss a `false_premise` defect of that shape, and no case scores the miss. The plan of PR #3408 is an example: its design said that the existing `missing_path` type names a code change that needs a file the plan does not change, while the cited `src/devops_cli/ai/tasks/roadmap_stage_verify.md` defined the type only for a file that does not exist and that no earlier group creates. The pass read the prompt and reported no finding.

This change adds that plan, before the author corrected the design, as a case of the golden set. A pass that reports no `false_premise` finding for this case fails it.

## What Changes

- Add the case `tests/fixtures/roadmap_eval/stage/3408-a-plan-restates-the-missing-path-rule/` from the plan of PR #3408 at commit `1e7c3bbe`. Its `case.json` holds one `false_premise` defect with the gate `none`, and its evidence is the exact design line and the exact `missing_path` bullet of the prompt.
- Set the `base_commit` of the case to `4e0e2435`, the parent of the plan commit, where the cited prompt still defines `missing_path` only for a missing file.
- Add two tests to `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`. The first asserts the defect type and gate, the two lines of the evidence, that the plan cites the prompt, and that the design quote is a text of the verification input. The second asserts that only a `false_premise` finding finds the defect of the case.
- Set the `pull_request_body` of the case to the body that the stage job wrote with the plan, before the author edited it.
- Add pull request 3408 to the set of reviewed plans in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, because the case adds one reviewed plan.
- Add the case to half B of the fixed split `tests/fixtures/roadmap_eval/stage/split.json`, and set the counts of the whole set to 57 cases, 52 reviewed plans and 318 labelled defects in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py` and `tests/commands/test_roadmap_eval_screen.py`. The test of the set size no longer states the number in its name.
- Put the oracle of the screen in `docs/roadmap/stage.md` in the past tense with its run, because the set now holds one more case that the reviewer can read.
- The change alters no behavior that a consumer observes: it adds one test fixture and its tests. It carries no spec delta.

## Capabilities

No capability changes. The change adds a case to the golden set of the verification pass and a test that checks the case.

## Impact

- Fixtures: `tests/fixtures/roadmap_eval/stage/3408-a-plan-restates-the-missing-path-rule/`, `tests/fixtures/roadmap_eval/stage/split.json`
- Docs: `docs/roadmap/stage.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/commands/test_roadmap_eval_screen.py`
- Code: no code changes.

## Feasibility

- `git show 1e7c3bbe:openspec/changes/3405-the-stage-check-names-the-message/design.md` prints the decision "The defect type exists already and names exactly this defect" and the rejected alternative "The existing `missing_path` type names a code change that needs a file the plan does not change".
- The edit history of the body of PR #3408 (`userContentEdits` of the GitHub GraphQL API) holds the body of 2026-11-04T01:55:37Z, the second of the plan commit. That body says that the prompt names `missing_path` for a code change that needs a file the plan does not change. The word "widens" comes only in the edits of 04:40:59Z and later.
- `git show 4e0e2435:src/devops_cli/ai/tasks/roadmap_stage_verify.md` prints "`missing_path`: the plan names a file that does not exist and that no earlier group creates." The commit is the parent of the plan commit and the commit that the refine of #3405 read.
- `halves` of `src/devops_cli/roadmap/decision_fit.py` with the seed 4326 and the strata `good`, `commit` and `no_commit` gives the recorded halves of the 56 cases again. With the new case it puts the case in half B, and it also moves 42 other cases to the other half.
- `uv run devops roadmap eval verify --dry-run` lists the case after the fixture lands, and `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` asserts its defect and evidence.
- The change fits one pull request.

## Existing Tool Considered

The golden set, the command `devops roadmap eval verify` and the task slot `ai.tasks.verification` already cover the need: `load_cases` reads every case directory under `CASES_DIRECTORY`, and `evaluate_cases` scores each loaded case. The change adds one case and a test and builds no tool. The written cost is about 1,000 tokens to build, about 500 tokens per year to keep and fix it, and about 1 hour elapsed. It deletes no internal code.
