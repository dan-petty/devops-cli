# Proposal

## Why

The plan of #3417 decides the guard premise check of the implement job from the prose of a task: an add verb, the word guard or check, and one code span. A task that names the guard some other way adds nothing the rule reads, and a sentence that names a guard without adding it can return the item to New for no defect (#3453). The plan already holds the names that a behavior group adds in the code spans of its tasks, and no field of the plan records them, so the implement job guesses them from the sentence.

## What Changes

- Add `ADDS_LINE`, `TaskGroup.added_names` and `adds_problem` to `src/devops_cli/roadmap/step_files.py`, so the plan reader and the implement job read the identifiers of the `Adds:` line of a group from one parser.
- Give `StageGroup` the field `adds` in `src/devops_cli/roadmap/stage/stage_change.py`, write the `Adds:` line in `group_text`, and refuse the field on a `manifest` group and an `other` group.
- Name the `adds` field and the `Adds:` line in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`, because both prompt tests compare the prompts with the fields of `StageGroup`.
- Read the line in `_group` of `src/devops_cli/roadmap/plan_read.py`, and raise `PlanReadError` for a name outside a code span.
- Read `TaskGroup.added_names` in `false_premises` of `src/devops_cli/roadmap/premise.py`, delete `added_guard`, `_ADD_VERB`, `_GUARD_SPAN` and their table test, and give the `Adds:` line to the behavior-group fixtures of `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` and `tests/roadmap/implement/test_roadmap_implement_typed_result.py`.
- State the line and the refusal in `docs/roadmap/plan-check.md`, and state in `docs/roadmap/implement.md` that the premise check reads the line and no prose of a task.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/task-groups`: A behavior group writes the identifiers that it adds, The stage prompts ask for the identifiers that a group adds
- `roadmap-plan-check`: The plan reader reads the identifiers that a group adds
- `roadmap-implement-step/inputs`: A task group exposes the identifiers that it adds
- `roadmap-implement-job/stops`: The job checks the premise of a behavior group at the branch tip

## Impact

- Code: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `docs/roadmap/plan-check.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_step_files.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_kind.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/test_premise.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`

## Feasibility

- The probes name the moved modules: "The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." and "The path `src/devops_cli/roadmap/implement_run.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_run.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." Both modules sit at the new paths, so the plan names the new paths and the issue is no false premise.
- The probes give "The path `src/devops_cli/roadmap/plan_read.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/step_files.py` is a file of the staging commit."
- The prose rule that the issue names is at the staged commit: `read_file` of `src/devops_cli/roadmap/premise.py` showed `src/devops_cli/roadmap/premise.py:def added_guard` and `src/devops_cli/roadmap/premise.py:def false_premises`, and `false_premises` calls `added_guard(task.text)` for each task of the group. The staged `_ADD_VERB` already holds `introduce`, so the example of the issue that a task with `introduce` misses the rule is not the failure at this commit; the rule still decides from prose and can both miss a guard and return the item for a sentence that only names one, and the plan removes it for the `Adds:` line.
- `src/devops_cli/roadmap/step_files.py:class TaskGroup` holds `number`, `title`, `tasks`, `text` and `line` only, and `src/devops_cli/roadmap/step_files.py:91:def code_spans(text: str) -> tuple[str, ...]:` with `src/devops_cli/roadmap/step_files.py:36:KIND_LINE: re.Pattern[str] = re.compile(r"^Kind: (?P<kind>\w+)\.", re.M)` show that one structured line of a group has a reader already.
- `src/devops_cli/roadmap/stage/stage_change.py:class StageGroup` holds no `adds` field, and `src/devops_cli/roadmap/stage/stage_change.py:2954:def group_text(index: int, group: StageGroup) -> str:` writes the kind and the files on one line from the message `stage_group_files`, which is staged as `Kind: {kind}. Reads: {reads}. Changes: {changes}.`
- `src/devops_cli/roadmap/stage/stage_change.py:621:def _other_problems(group: StageGroup) -> list[str]:` refuses no `adds`: that is the defective text that group 2 quotes in its test.
- The review finding is right, and group 4 now changes both files. `read_file` of `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` and of `tests/roadmap/implement/test_roadmap_implement_typed_result.py` showed the fixture of `tests/roadmap/implement/test_roadmap_implement_checkpoint.py:class TestAGuardThatTheBranchTipDefines` and of `tests/roadmap/implement/test_roadmap_implement_typed_result.py:class TestTypedResultOfAReturn`, and each of their task texts says `Add the guard _delivery_title` with no `Adds:` line. Once the prose rule goes, `false_premises` reads no name for those two groups and the two tests fail, so group 4 adds the line `Adds: _delivery_title` to each of the two fixtures and runs both modules in its verify.
- `search_code` for `Add the guard` gave three test modules with a guard-add task: `tests/roadmap/test_premise.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` and `tests/roadmap/implement/test_roadmap_implement_typed_result.py`. `search_code` for `added_guard` gave one test module, `tests/roadmap/test_premise.py`. Group 4 changes all three, so no test module is left reading the deleted rule.
- The finding on the missing split prompt is fixed: `list_files` of `src/devops_cli/ai/tasks` shows `roadmap_stage_split.md`, and `tests/roadmap/stage/test_roadmap_stage_kind.py:def test_a_stage_prompt_names_each_kind_and_each_field_of_a_group` and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py:def test_the_keys_of_a_group_in_the_prompts_are_the_fields_of_a_group` read both prompts against the fields of `StageGroup`, so group 2 changes both prompts, both test modules and the field together.
- The finding on the order of group 2 is fixed: the `adds` field and the two prompts land in one group, so the group runs `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` as its verify and no group leaves the two prompt tests failing.
- The finding on the contrived test is fixed: `tests/roadmap/implement/test_roadmap_implement_job.py:def _guard_tasks` builds a group whose first task fails on the base, and each of the three new tests now fails on the base. The group with the `Adds:` line `_delivery_title` names no guard in its task text, so the base runs it and the return fails the test. The group with no `Adds:` line says to add a check beside the guard `_delivery_title`, which the base prose rule matches, so the base returns the item and the run fails the test. The group with `Adds:` `_missing_guard` names the defined guard `_delivery_title` in its task text, so the base returns the item and the run fails the test.
- The finding of 2026-11-14 on group 4 (`false_premise`) is fixed. The plan gave the shared helper `_guard_tasks` of `tests/roadmap/implement/test_roadmap_implement_job.py` the fixed line `Adds:` with `_delivery_title`, but the helper also builds the group of `TestATruePremiseOfABehaviorGroup` from `_missing_guard`. The branch tip defines `_delivery_title`, so that item went back to New and `test_a_behavior_group_whose_guard_the_base_lacks_runs` failed. The helper now writes the `Adds:` line of its argument `name`, so each world names its own guard.
- #5886 (2026-11-15) moved the premise check before the first step of the run, kept the prose rule for this change to replace, and renamed the checkpoint test to `test_the_check_returns_the_item_before_the_step_of_group_one`. Group 4 names the new test.
- `docs/roadmap/implement.md` states the prose rule (an add verb, the word guard or check, and one code span), so group 5 changes it with the guide of the plan check.
- The finding on the import is fixed: `tests/roadmap/test_premise.py:10:from devops_cli.roadmap.premise import added_guard, definition_lines` imports the deleted function, so group 4 deletes that import, the table test `test_a_task_adds_a_guard_only_when_the_identifier_follows_the_guard_word` and the `pytest` import that only that test uses, in the same group as the deletion.
- `src/devops_cli/roadmap/implement/implement_run.py:def _check_premise(self, groups: Sequence[TaskGroup]) -> bool:` (the signature after #5886) keeps its place and its return to New with the definition line, and `read_change` of `src/devops_cli/roadmap/plan_read.py` keeps the one place that reads a group.
- `read_spec` of `roadmap-implement-job/stops` gave the base requirement "The job checks the premise of a behavior group at the branch tip" with four scenarios, and the modified requirement keeps all four names.
- Precondition of `false_premises` in `src/devops_cli/roadmap/premise.py`: a checkout of the repository, because it reads the definitions at the branch tip with `git grep`; the job calls it on the checkout of the runner.
- Precondition of `definition_lines` in `src/devops_cli/roadmap/premise.py`: a checkout of the repository, because it reads the definitions of a commit through `git grep`.
- `read_change` takes a mapping of the change files, so it needs no checkout, no client and no network.
- The plan introduces no new program. `uv run devops ci test` and `uv run devops ci docs` run in the runner image, which holds `uv`, `devops`, `pytest` and `git`, under the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`; the tests write only under `tmp_path`. A failed test is class `test` with action `repair`.
- The live run `uv run devops roadmap eval stage --limit 5` needs a client of the model provider and a network to it, and its failure is class `provider` with action `retry`; the replay `uv run devops roadmap eval stage --replay` calls no model and needs no network.
- The first check of the implementation is `uv run devops ci test tests/roadmap/test_roadmap_step_files.py`, which fails on the base because `TaskGroup.added_names` does not exist.

## Existing Tool Considered

No open tool parses the plan files of this repository, and the change extends the project's own parsers: `code_spans` of `src/devops_cli/roadmap/step_files.py` and the kind line of `src/devops_cli/roadmap/plan_read.py`. The written cost is about 4,000 tokens to build and test, about 1,000 tokens to keep, and about 1 hour elapsed. The change deletes the internal code `added_guard`, `_ADD_VERB` and `_GUARD_SPAN` of `src/devops_cli/roadmap/premise.py`.

## Dependencies

None.
