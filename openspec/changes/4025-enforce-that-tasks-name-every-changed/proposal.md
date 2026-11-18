# Proposal

## Why

Issue #4025: a task group can omit every path of its `changes` from its `implementation`, so the implement step packs no file for the group and the plan check fails the plan pull request with `group-no-files`. The stage prompt and the stage check must ask for each changed path in a code span.

## What Changes

- The content check `content_problems` in `src/devops_cli/roadmap/stage/stage_change.py` gains `_changed_path_span_problems`, which refuses a group whose `implementation` names a path of `changes` nowhere in a backtick code span, in one message that names every omitted path.
- `src/devops_cli/lang/en/messages.py` gains the message `stage_implementation_missing_paths` in `MESSAGES.roadmap`, which names the group and each omitted path.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` states that the `implementation` of a task group names every path of `changes` in a code span, and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` asserts that sentence.
- `tests/support/builders.py` names the second changed path of its default group in a code span, so every test that asserts a clean plan keeps passing.
- The six recorded good stage plans of the stage golden set and the staged case `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json` name each path of `changes` in a code span, so the replay keeps its good cases.
- The change carries a spec delta because the stage check and the stage prompt are behavior that a consumer observes: two requirements join `roadmap-stage/plan-text`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/plan-text`: A task group names each changed path in a code span, The stage prompt asks for each changed path in a code span

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_group_paths.py`, `tests/support/builders.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2735-the-subprocess-environment-guard-accepts-less/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2739-the-subprocess-environment-guard-accepts-gh/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/plan.json`, `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json`

## Feasibility

- The probe states the module of the issue word for word: The path `step_files.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/step_files.py`. No commit in the history deleted or renamed it. That module holds `def code_spans(text: str) -> tuple[str, ...]:`, the parser of the code spans that the plan reuses.
- The probe keeps the prompt path word for word: The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.
- The probes keep the plan check word for word: The path `plan_check.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/plan_check.py`. No commit in the history deleted or renamed it. The path `src/devops_cli/roadmap/plan_check.py` is a file of the staging commit. The module holds `def _size_problems(proposal: StageProposal, folder: PlanFolder) -> list[PlanProblem]:`.
- The probe keeps the archived design of the group files word for word: The path `openspec/changes/archive/2026-10-30-2772-stage-group-files/design.md` is a file of the staging commit.
- The probes name no line for `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `_size_problems`, `implementation`, `changes`, `StageGroup` and `render_change`, because the bound of 10 commands was reached; this run read them with `read_file` and `search_code` instead, so no premise rests on a probe line there.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` lines 2180 to 2215 shows the content rule and its last text rule: `src/devops_cli/roadmap/stage/stage_change.py:2180:def content_problems(proposal: StageProposal, probes: Sequence[str] = ()) -> list[str]:` and `src/devops_cli/roadmap/stage/stage_change.py:2205:problems.extend(_gate_defect_problems(proposal))`. The defective statement is `problems.extend(_gate_defect_problems(proposal))`: no rule reads the code spans of a group's `implementation`, so group 1 quotes it in its test task.
- The gate-defect rule that group 1 answers is `src/devops_cli/roadmap/stage/stage_change.py:2143:def _gate_defect_problems(proposal: StageProposal) -> list[str]:`, with `src/devops_cli/roadmap/stage/stage_change.py:300:GATE_DEFECT_PATHS: Final[tuple[str, ...]] = (` and `src/devops_cli/roadmap/stage/stage_change.py:304:_FAILS_ON_BASE: Final[str] = "fails on the base"`, so group 1's test quotes the defective text and states that it fails on the base.
- The self-acceptance rule is `src/devops_cli/roadmap/stage/stage_change.py:220:_PLAN_CHECK_FILE: Final[str] = "src/devops_cli/roadmap/stage/stage_change.py"` with `src/devops_cli/roadmap/stage/stage_change.py:221:_SELF_ACCEPTANCE_MARKS: Final[tuple[str, ...]] = (`, so group 1 gives a test that builds the plan's own `StageProposal` (`class StageProposal(_Reply):`) and asserts that `content_problems` returns no problem for it.
- The prompt-rule test and the eval commands are staged as the plan reads them: `src/devops_cli/roadmap/stage/stage_change.py:229:PROMPT_RULE_TEST: Final[str] = "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"`, `src/devops_cli/roadmap/stage/stage_change.py:275:STAGE_EVAL_PROMPT_PATH: Final[str] = "src/devops_cli/ai/tasks/roadmap_stage_change.md"`, `src/devops_cli/roadmap/stage/stage_change.py:290:STAGE_EVAL_REPLAY: Final[str] = "uv run devops roadmap eval stage --replay"`, `src/devops_cli/roadmap/stage/stage_change.py:293:STAGE_EVAL_LIVE: Final[str] = "uv run devops roadmap eval stage --limit"` and `src/devops_cli/roadmap/stage/stage_change.py:298:_STAGE_EVAL_SCORE_WORDS: Final[tuple[str, ...]] = ("score", "before", "after")`, so group 1 replays and group 3 runs the live score with the words score, before and after.
- The plan reader builds the same model: `src/devops_cli/roadmap/plan_read.py:552:return StageGroup(` builds a group from a tasks.md and `src/devops_cli/roadmap/plan_read.py:640:except ValidationError as exc:` turns a schema failure into a read error, so the rule goes in the content check and not in a model validator.
- The replay runs the content rule: `src/devops_cli/roadmap/stage/stage_eval_gates.py:258:return content_problems(plan.proposal)` and `src/devops_cli/roadmap/stage/stage_eval_gates.py:558:good = [r for r in self.replays if r.case.verdict is Verdict.GOOD]` counts a good case as refused when a gate reports a problem.
- The failure that the issue reports stays as the last guard: `src/devops_cli/roadmap/plan_check.py:493:def _size_problems(proposal: StageProposal, folder: PlanFolder) -> list[PlanProblem]:` adds it at `src/devops_cli/roadmap/plan_check.py:518:message = texts.plan_check_group_no_files.format(number=number, title=title)`.
- `search_code` for `"verdict": "good"` gave seven good cases: the six folders of `tests/fixtures/roadmap_eval/stage` whose name starts with `good-`, and `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/case.json`. Each of the seven is restricted: groups 4, 5 and 6 give it the code spans, and no other good case exists.
- The shared builder is `tests/support/builders.py:def make_stage_proposal`; its default group has two paths in `changes` and an `implementation` that names one of them, so group 2 gives the second path its code span and the tests that assert a clean plan keep passing.
- `src/devops_cli/roadmap/stage/stage_change.py:142:MAX_GROUP_CHANGES: Final[int] = 5` bounds a task group, and every group of this plan changes at most three files.
- The rule and its helper are pure functions of their arguments: `content_problems` and `code_spans` need no checkout, no client and no network.
- `_size_problems` needs a checkout of the repository at the head of the plan pull request, because it measures each group on the packed files of that checkout.
- The plan introduces no program: `uv`, `devops`, `pytest` and `git` come from the runner image, and the pod holds `allowPrivilegeEscalation: false`, `capabilities.drop: ALL`, `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `seccompProfile: RuntimeDefault`.
- A failing verify of a group is failure class `test`, whose action is `repair`; a ruff or mypy failure is class `lint` or `types`, whose action is `repair`; a failed model call of the live score is class `provider`, whose action is `retry`.
- The first checks against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_group_paths.py`, `uv run devops ci test tests/roadmap` and `uv run devops roadmap eval stage --replay`; the replay calls no model and needs no network.

## Existing Tool Considered

No open, maintained tool or library covers the rule: the alternatives check of 2026-11-10 found none, and the rule reads the `changes` list and the `implementation` text of a plan of the stage job. The change builds its own code at about 40k tokens to build, keep and fix it, and about 4 hours of elapsed time. It deletes no internal code.

## Dependencies

None.
