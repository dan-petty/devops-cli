# Proposal

## Why

The stage job accepts a plan whose `verify` command is `uv run pytest <file>` and a plan that puts a new test module flat under `tests/`. In the 37 plans of 2026-11-01, about 14 used the pytest form and about 6 used a flat path (#3015). `docs/TESTING.md` says a check runs with `uv run devops`, and that the tests mirror the package tree. The prompt and `openspec/config.yaml` showed `tests/test_feature.py` as their example, which pulled the model to the flat path. Nothing enforced the form.

## What Changes

- `check_proposal` refuses a `verify` command that does not start with `uv run devops`. The one other form is the `! git grep -n <name>` check, which `docs/TESTING.md` names for a deletion and no `devops` command replaces.
- `check_proposal` refuses a new test module in `creates` that is not in the mirror directory of a source file that the plan changes, or in `tests/invariants/`.
- The stage prompt and `openspec/config.yaml` give a mirrored example path, `tests/roadmap/test_feature.py`, and name `uv run devops openspec check` in place of `openspec validate --strict`.
- A test fails if the prompt or the config holds an example test path that is not in a mirror directory.
- `docs/TESTING.md` names `uv run devops openspec check` and `uv run devops k8s image-pins`, the full forms.
- Four recorded cases of the golden set (the plans of #2975, #2977, #2985 and #2990) name the `paths` gate for their verify-form defect, and the replay shows that `check_proposal` refuses them.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A verify command has the project form, A new test module sits in a mirror directory, The prompt and the rules give a mirrored test path

## Impact

- Code: `src/devops_cli/roadmap/stage_form.py` (new), `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Documents: `openspec/config.yaml`, `docs/TESTING.md`
- Tests: `tests/roadmap/test_roadmap_stage_form.py` (new), `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_plan.py`, and the cases `tests/fixtures/roadmap_eval/stage/2116-the-scanner-executor-tests-find-the/case.json`, `tests/fixtures/roadmap_eval/stage/2260-uv-test-pipeline-serve-mcp-and/case.json`, `tests/fixtures/roadmap_eval/stage/2369-the-startup-import-tests-start-56/case.json` and `tests/fixtures/roadmap_eval/stage/2462-devops-ai-cost-report-shows-a/case.json`

## Feasibility

- A scan of the 40 recorded plans under `tests/fixtures/roadmap_eval/stage/` showed 116 `verify` commands, of which 32 do not start with `uv run devops`: 21 are `uv run pytest`, 4 are `! git grep -n`, and the rest are `test -f`, `grep -q`, `uv run ruff` and a coverage run. No plan marked `good` holds one, so the new rule refuses no good plan.
- `docs/TESTING.md` line 62 and `openspec/config.yaml` name `! git grep -n <name> src/ tests/` as a valid `verify` command for a deletion. The issue asks for the `uv run devops` prefix only. The change keeps the `! git grep` form as the one exception, because the documents of the project name it and no `devops` command does its work.
- `docs/TESTING.md` line 205 says a new test may go "into a new flat file named after the behaviour" until the move into the mirror is done. The issue asks to refuse a flat path, and `tests/roadmap/` already mirrors `src/devops_cli/roadmap/`. The change refuses a new test module outside the mirror directory of the source it tests, and treats a top-level module of `src/devops_cli/` as mirrored by `tests/` itself, so the flat path stays valid for such a module.
- The recorded plans list the new test files of their groups in `changes` and not in `creates`, so the `creates` rule does not fire in the replay. Only the verify rule is replayed. The `creates` rule is proved by unit tests of `check_proposal`.
- `uv run devops --help`, `uv run devops ci --help`, `uv run devops openspec --help` and `uv run devops docs --help` showed that `ci docs`, `openspec check` and `docs check` exist, so the examples are real commands.
- The first checks of the implementation: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` for both refusals and the examples, and `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` for the replay.

## Existing Tool Considered

No open, maintained tool or library covers this need. The rule checks the reply schema of this project's stage job against this project's own test layout, and `check_proposal` already holds the other rules of `openspec/config.yaml`. The change adds one module of about 80 lines and two messages. Building it costs about 25000 tokens and one focused hour. Keeping it costs a line in the allowed command set when a new verify form arrives. Fixing it costs a few thousand tokens when the layout of `tests/` changes. It deletes no code.
