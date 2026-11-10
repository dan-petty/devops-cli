# Proposal: #3431

## Why

The golden set of the verification pass has no plan whose design restates a rule of a file that the plan cites and gets the restatement wrong. The pass can therefore miss a `false_premise` defect of that shape, and no case scores the miss. The plan of PR #3408 is an example: its design said that the existing `missing_path` type names a code change that needs a file the plan does not change, while the cited `src/devops_cli/ai/tasks/roadmap_stage_verify.md` defined the type only for a file that does not exist and that no earlier group creates. The pass read the prompt and reported no finding.

This change adds that plan, before the author corrected the design, as a case of the golden set. A pass that reports no `false_premise` finding for this case fails it.

## What Changes

- Add the case `tests/fixtures/roadmap_eval/stage/3408-a-plan-restates-the-missing-path-rule/` from the plan of PR #3408 at commit `1e7c3bbe`. Its `case.json` holds one `false_premise` defect with the gate `none`, and its evidence is the exact design line and the exact `missing_path` bullet of the prompt.
- Set the `base_commit` of the case to `4e0e2435`, the parent of the plan commit, where the cited prompt still defines `missing_path` only for a missing file.
- Add a test to `tests/roadmap/stage/test_roadmap_stage_verify_eval.py` that asserts the defect type and gate, that each quoted text is a text of the verification input, and that an empty finding list scores one labeled defect and no found defect.
- Add pull request 3408 to the set of reviewed plans in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, because the case adds one reviewed plan.
- The change alters no behavior that a consumer observes: it adds one test fixture and its tests. It carries no spec delta.

## Capabilities

No capability changes. The change adds a case to the golden set of the verification pass and a test that checks the case.

## Impact

- Fixtures: `tests/fixtures/roadmap_eval/stage/3408-a-plan-restates-the-missing-path-rule/`
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`
- Code: no code changes.

## Feasibility

- `git show 1e7c3bbe:openspec/changes/3405-the-stage-check-names-the-message/design.md` prints the decision "The defect type exists already and names exactly this defect" and the rejected alternative "The existing `missing_path` type names a code change that needs a file the plan does not change".
- `git show 4e0e2435:src/devops_cli/ai/tasks/roadmap_stage_verify.md` prints "`missing_path`: the plan names a file that does not exist and that no earlier group creates." The commit is the parent of the plan commit and the commit that the refine of #3405 read.
- `uv run devops roadmap eval verify --dry-run` lists the case after the fixture lands, and `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` asserts its defect and evidence.
- The change fits one pull request.

## Existing Tool Considered

The golden set, the command `devops roadmap eval verify` and the task slot `ai.tasks.verification` already cover the need: `load_cases` reads every case directory under `CASES_DIRECTORY`, and `evaluate_cases` scores each loaded case. The change adds one case and a test and builds no tool. The written cost is about 1,000 tokens to build, about 500 tokens per year to keep and fix it, and about 1 hour elapsed. It deletes no internal code.
