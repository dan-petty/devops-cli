# Proposal: #6080

## Why
The owner rule of 2026-11-16 (#6060) says: "I don't want any tests that check that a manifest or config has any particular value. They should be testing the source code of the project." #6075 deletes those tests and adds a guard. But the plan rules of the Service still ask for them, so each new plan brings them back, or the guard then fails the implement step (#6080). On 2026-11-17 the owner added: "ensure all coverage requirements and fail to pass requirements do not bring back these tests".

Five rules ask for a value test:

1. `openspec/config.yaml` says that a manifest carries a spec delta, and that a scenario is one that a test under `tests/` can assert offline. A scenario of a manifest change can then only be "WHEN a test reads <manifest>".
2. The stage prompt (`src/devops_cli/ai/tasks/roadmap_stage_change.md`) and the refine reply prompt (`src/devops_cli/ai/tasks/roadmap_refine_reply.md`, `acceptance_criteria`) write the same form.
3. `workflow_contract_problems` (#4083) refuses a plan whose group changes a workflow and does not change `tests/invariants/test_workflow_contracts.py`.
4. The scenario check (`_scenario_problem`, #3321, #3423, #4316) refuses a scenario that names a path with no behavior test that names it. A scenario of a manifest names the manifest, so the check asks for a test of that file.
5. The form check (`form_problems`) admits a new test module in `tests/invariants/`, the folder that holds most of the value tests.

## What Changes
- `openspec/config.yaml`, the stage prompt and the refine reply prompt say that a scenario, a criterion and a task group of a manifest, a workflow or a config file names a validator command or a live check as its proof, such as `uv run devops ci --check --only k8s`, `uv run devops k8s validate <path>`, `uv run devops ci --check --only actionlint,zizmor` or `uv run devops k8s searxng-check`, and never a test that reads the file.
- `workflow_contract_problems`, its constants and its message are deleted. Actionlint and zizmor check a workflow.
- The scenario check refuses a scenario that names a manifest, a workflow or a config file that a group changes or creates (a path outside `src/` and `tests/` that is no Markdown document) when the scenario names no validator command or live check. A command that runs tests is no proof, and a behavior test that names the file is no proof. A scenario of the base spec is exempt.
- The form check refuses a new test module in `tests/invariants/`. A new test goes in the folder that mirrors the package of the source code that it tests, and the guard of #6075 refuses a new test that reads a committed manifest or config file.
- `docs/TESTING.md` states the proof form and records that the coverage floor, diff-cover and Fail-to-Pass ask for no value test.
- The golden stage case `good-2950-the-alert-case-is-a-manifest-group` names `uv run devops ci --check --only k8s` as the proof of its dashboard scenario.

The plan check is behavior that the stage job shows to its consumer, so the change carries spec deltas. It fits one pull request.

## Capabilities
- Modified: `roadmap-stage/paths-gate` (the workflow contract rule is removed; a workflow change needs no test).
- Modified: `roadmap-stage/spec-delta` (a scenario of a changed manifest, workflow or config file needs a command proof).
- Modified: `roadmap-stage/tests-gate` (no new test module in `tests/invariants/`).
- Modified: `roadmap-refine/proposal` (a criterion of a manifest, a workflow or a config file names a command proof).

## Impact
- The stage job plans no test that reads a manifest or a config file, so the implement step does not meet the guard of #6075.
- A plan that changes a workflow no longer changes `tests/invariants/test_workflow_contracts.py`.
- The coverage floor (`fail_under = 85`), diff-cover (`--fail-under 90`) and the Fail-to-Pass workflow stay as they are.
- About 370 scenarios in about 105 living specs still have the form "WHEN a test reads <manifest>". The base spec exemption keeps them, and a plan that adds a new scenario uses the new form.

## Feasibility
- `openspec/config.yaml:16` and `:27` at `origin/main` 04e1a8b20 held the delta rule and "Write only scenarios a test under tests/ can assert offline".
- `src/devops_cli/ai/tasks/roadmap_stage_change.md:19` and `:21` restated both rules, and `:33` admitted a new test module in `tests/invariants/`.
- `src/devops_cli/roadmap/stage/stage_paths.py:664` defined `WORKFLOW_CONTRACT_TEST`, and `path_problems` called `workflow_contract_problems`.
- `src/devops_cli/roadmap/stage/stage_change.py:def _scenario_problem` exempted a scenario only when a code span is a command, and a behavior test that named a manifest satisfied it.
- `src/devops_cli/roadmap/stage/stage_form.py:def form_problems` accepted `folder == _INVARIANTS`.
- Not causes, checked: `.github/workflows/fail-to-pass.yml:14` runs only for `src/**` (outside the knowledge base) and `tests/gate/*_checks/**`; `src/devops_cli/roadmap/implement/implement_step.py` replays the base only for a group that `is_behavior`; `.github/workflows/ci.yml:297` runs diff-cover on `.data/coverage.xml`, which holds the Python files of `src/` only.
- `uv run devops ci --check --only k8s` passed with 172 cases in 11 s on 2026-11-17. `verification_problem` of the implement shell policy accepts `uv run devops ci --check --only k8s`, `uv run devops ci --check --only actionlint,zizmor`, `uv run devops k8s validate k8s/devops` and `uv run devops k8s searxng-check`.
- No `devops` command validates the Renovate config: no source file, workflow or pre-commit hook calls `renovate-config-validator`.

## Existing Tool Considered
- Kubeconform (`devops k8s validate`), kube-linter (`devops k8s lint`), the `kubectl kustomize` renders of the `k8s` row of `devops ci`, actionlint and zizmor are the proofs that the rules now name. The change builds no new tool.
- `renovate-config-validator` of Renovate covers the Renovate config, and no `devops` command runs it yet (follow-up).
- Internal code deleted: `workflow_contract_problems`, `WORKFLOW_CONTRACT_TEST`, `WORKFLOW_DIRECTORY`, the message `stage_problem_workflow_contract` and its four tests.
