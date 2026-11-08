# Proposal

## Why

The stage job omits existing tests that assert on a manifest it plans to change (#3972). The implement job cannot edit a test outside its `Changes:` list, because `diff_scope` forbids it, so the runner loops until it spends its token budget and the item stops blocked. The plan must name those tests before staging finishes.

## What Changes

- Add `record_test_references` and `missing_reference_problems` to `src/devops_cli/roadmap/stage/stage_paths.py`, and give `path_problems` the record as an optional argument, so a plan that changes a YAML manifest under `k8s/` names every test file that references it.
- Add the message `stage_problem_missing_perimeter_test` to `src/devops_cli/lang/en/messages.py`.
- Add the `manifest_references` keyword to `check_gates` and `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py`, and pass the record to the `paths` gate.
- Pass the record to `check_gates` in `src/devops_cli/roadmap/plan_recheck.py`, so the merged-plan recheck refuses the same plan.
- Add the `manifest_references` keyword to `gate_arguments` in `src/devops_cli/roadmap/stage/stage_request.py`, record the references in `src/devops_cli/roadmap/stage/stage.py`, and read the record from the case in `src/devops_cli/roadmap/stage/stage_eval_cases.py` and `src/devops_cli/roadmap/stage/stage_eval_gates.py`.
- Add cases to `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` and `tests/roadmap/stage/test_roadmap_stage_request.py`, and the self-acceptance test of this plan to `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`.
- State the rule in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-check.md`.
- The change carries a spec delta because the stage job and its plan check are behavior that a consumer observes: the requirement `A manifest plan names the tests that reference it` joins `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A manifest plan names the tests that reference it

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`, `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`, `tests/roadmap/test_roadmap_plan_recheck.py`

## Feasibility

- The premise holds, and the probes answered word for word: The path `k8s/logging/networkpolicy.yaml` is a file of the staging commit. The path `tests/commands/k8s/test_k8s_logging_stack.py` is a file of the staging commit. That test holds the assertion `len(egress_rules) == 2` over the two egress rules of the manifest.
- The constants that the plan relies on are staged as they are read: `src/devops_cli/roadmap/stage/stage_change.py:208:STAGE_EVAL_TRIGGER_PATHS: Final[tuple[str, ...]] = (` holds `src/devops_cli/roadmap/stage/stage_paths.py` and `src/devops_cli/roadmap/stage/stage_change.py`; `src/devops_cli/roadmap/stage/stage_change.py:217:STAGE_EVAL_REPLAY: Final[str] = "uv run devops roadmap eval stage --replay"` gives the command of the score task; and `src/devops_cli/roadmap/stage/stage_change.py:160:_PLAN_CHECK_FILE: Final[str] = "src/devops_cli/roadmap/stage/stage_change.py"` names the plan check whose change needs the self-acceptance test.
- The rule has a place to run: `src/devops_cli/roadmap/stage/stage_paths.py:def path_problems` joins the missing-path and caller checks, and `src/devops_cli/roadmap/stage/stage_change.py:def check_gates` gives the `paths` gate the result of `path_problems`.
- The job already records a staged search before it judges a reply: `src/devops_cli/roadmap/stage/stage_form.py:def record_search_evidence` takes a search callable, and `_Planner._problems` calls it with the grep of the job, so the new record follows the same shape.
- The replay reads a record from its case and runs no git: `src/devops_cli/roadmap/stage/stage_eval_cases.py:class CaseFacts` holds `search_evidence`, and `src/devops_cli/roadmap/stage/stage_eval_gates.py:class PlanUnderTest` reads it in `of_case`, so the new record joins `CaseFacts` beside it.
- The recheck runs the same gates on a merged plan: `src/devops_cli/roadmap/plan_recheck.py:def _record` calls `check_gates`, so it passes the record too and a merged plan gets the same refusal.
- First check against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py`. Second: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Third: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_request.py`. Fourth: `uv run devops roadmap eval stage --replay`, which calls no model and reaches no network.
- Precondition of the `record_test_references` test: a checkout of the repository in a temporary folder, which the helper `run_git` of `tests/support/roadmap_stage.py` makes.
- Precondition of the job's call: a checkout of the repository at the staged commit, which `_Planner` holds as `self._source`.
- Precondition of the recheck's call: a checkout of the repository at the ref that the pass reads, which `_Pass` holds as `shared.source`.
- The plan changes `src/devops_cli/roadmap/stage/stage_change.py` and `src/devops_cli/roadmap/stage/stage_paths.py`, which `STAGE_EVAL_TRIGGER_PATHS` holds, so group 3 runs the replay and states the score before and after the change. The plan also adds a rule of the plan check, so group 3 gives the test that builds this plan's `StageProposal` and asserts that `content_problems` gives no problem.
- The plan answers the check that refused the earlier reply: it quotes the probe lines, gives the build cost in tokens and hours, names only sample files that a test writes at run time, and lists `src/devops_cli/roadmap/plan_recheck.py` as a caller of `check_gates`.
- The plan adds no gate to `ProposalGate`: the new problem is one of the `paths` gate, as the missing-path and caller problems are. `uv run devops roadmap plan-recheck --source . --branch HEAD` is the check of a merged plan, and the plan runs it after the merge.

## Existing Tool Considered

No open, maintained tool covers the need: this is a plan check inside devops-cli, over the plan of the stage job and the files of its checkout. The change builds its own code, at a written cost of about 150k tokens to build, keep and fix it, and about 16 hours of elapsed time. It extends `src/devops_cli/roadmap/stage/stage_paths.py`, reuses the search that the job already runs, and deletes no code.

## Dependencies

None.
