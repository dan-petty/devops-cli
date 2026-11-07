# Proposal

## Why

The stage planner holds two kinds of task group: `behavior`, which is test first, and `other`, which has one repeatable check and no failing-case task. A plan for an alert rule with `promtool` cases, or for a dashboard panel with a query pin, has a failing case first and no place for it. Two agents wrote those tasks by hand on 2026-11-02, in the plans of #3173 and #3171, and the review refused the form. The stage job has no kind that a manifest, a rule file, a dashboard file or a case file takes with its case first (#3251).

## What Changes

- Add the member `MANIFEST = "manifest"` to `GroupKind` in `src/devops_cli/roadmap/stage/stage_change.py`, and add `_manifest_problems`, which refuses a missing `test`, a missing `verify` and a `process`, so `StageGroup.model_validate` accepts a manifest group with a case and refuses one with no case.
- Render a manifest group with its case task first in `_task_texts` and `_task_work_texts` of `src/devops_cli/roadmap/stage/stage_change.py`.
- Add `_CASE_SUFFIXES` and `_is_case_path` to `src/devops_cli/roadmap/stage/stage_form.py`, and add to `form_problems` the rule that an `other` group which creates or changes a case path is refused with a problem that names `other`, `manifest` and the path.
- Add the rule to `form_problems` that a manifest `verify` command is `uv run devops ci test` followed by a path of the group, with a problem that names the command and the form to use.
- Add the message texts `stage_kind_manifest_*`, `stage_problem_manifest_kind` and `stage_problem_manifest_verify` to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`.
- Name the kind `manifest`, its case-first rule and its verify rule in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and in `src/devops_cli/ai/tasks/roadmap_stage_split.md`.
- Read the kind names as a list in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, because the two-name regex no longer matches three kinds, and pin the manifest rules of the prompt there.
- Change the pinned schema message in `tests/roadmap/stage/test_roadmap_stage_kind.py` to the three kinds, and add the tests of the manifest kind and of its render in `tests/roadmap/stage/test_roadmap_stage_manifest.py`.
- Add the replay case `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule` from the hand-written plan of #3173: its group 5 changes the promtool case file and has the kind `other`, so the `paths` gate refuses it and names `manifest`. Update the pinned counts of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.
- Keep the spec delta: the kind, the messages and the prompt of the stage job are behavior that the job and the model observe, so `skip_specs` stays false.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A task group has the kind manifest, A manifest group renders its case first, A case path forces the manifest kind, The manifest verify runs a case of the group, The planner prompt names the manifest kind

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_form.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_kind.py`, `tests/roadmap/stage/test_roadmap_stage_manifest.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/case.json`, `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/plan.json`, `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/issue.txt`, `tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/facts.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`

## Feasibility

- The probes confirm the files that the change touches: "The path `tests/roadmap/stage/test_roadmap_stage_kind.py` is a file of the staging commit.", "The path `src/devops_cli/roadmap/stage/stage_form.py` is a file of the staging commit." and "The path `openspec/changes/archive/2026-10-30-2772-stage-group-files/design.md` is a file of the staging commit."
- The schema and the form check hold the two kinds of today: `src/devops_cli/roadmap/stage/stage_change.py:class GroupKind` holds `BEHAVIOR = "behavior"` and `OTHER = "other"`, and `src/devops_cli/roadmap/stage/stage_form.py:def form_problems` holds the form rules, so the new kind and its two rules have a place to live.
- The issue names `tools.lock` and the probes answer "The path `tools.lock` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/tools_lock/tools.lock`." A named `promtool` command in that lock is out of this change: `src/devops_cli/roadmap/implement/implement_shell_policy.py` holds no `promtool` in `SHELL_PROGRAMS`, so the step's shell cannot run one. The verify rule accepts `uv run devops ci test` only, and the promtool part waits for a new item.
- The case path of the issue's scenarios, `k8s/apps/api/rules_test.yaml`, is no file of the commit and no commit deleted it, so it is a path that a test creates. The tests use the case file `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, which exists at the staged commit.
- The hand-written plan of #3173 is the change folder `openspec/changes/archive/2026-11-06-2950-alternatives-coverage-gauge-searches-per-check/tasks.md`. Its group 5 reads "Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`, `k8s/README.md`." and writes the promtool cases by hand in task 5.1, so the group is `other` and changes a case path.
- The replay gate names the defect: `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _path_gate` runs `check_proposal`, which calls `form_problems`, and `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _status` judges a defect against the problems of the gate that the case names.
- The new case moves the pinned counts of the replay: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` asserts `len(defects) == 74` and `report.judged() == (69, 306)`, so the group that adds the case updates both.
- The plan changes `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_form.py` and `src/devops_cli/ai/tasks/roadmap_stage_change.md`, which `src/devops_cli/roadmap/stage/stage_change.py:STAGE_EVAL_TRIGGER_PATHS` holds, so group 5 runs `uv run devops roadmap eval stage --replay` with the score before and after the change.
- The plan adds a rule of the plan check in a behavior group of `src/devops_cli/roadmap/stage/stage_change.py`, so group 1 gives the test that builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it, as `src/devops_cli/roadmap/stage/stage_change.py:def _self_acceptance_problems` asks.
- The first checks run against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_manifest.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_kind.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` and `uv run devops openspec check`.
- A call of `check_proposal` needs a checkout of the repository for its `StagedTree` and its file reader: the replay reads the fixtures of its case and no git, and the tests build the tree in memory, so no test needs a network or a client of a service.
- A call of `group_text` needs no precondition: it reads a validated `StageGroup` and the messages, with no checkout and no client.

## Existing Tool Considered

No open, maintained tool covers this need. The rule is a project-internal form of the devops-cli stage plan, and the planner, the kind table and the replay are devops-cli code. The change builds its own code: about 70k tokens to build and about 15k tokens a year to keep and fix, for about 300 changed lines and 7 tests. The elapsed time is about 8 hours. The change deletes no internal code.

## Dependencies

None.
