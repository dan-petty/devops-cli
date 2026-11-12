# Proposal: #5205

## Why

The stage job pushes plans that its own plan reader refuses (#5205). #3981 added the group kind `manifest` to the stage writer and changed no line of the reader. The writer renders a `manifest` group with the tasks of a `behavior` group and writes no `Kind:` line, so the reader reads it as `behavior`. A `manifest` group that changes no path under `src/` then breaks the #3035 rule `stage_kind_no_source`, and `read_change` raises `PlanReadError`. So fix-plan, the Plan Check, plan-recheck and implement cannot read #4963 (group 3) and #5032 (groups 3 and 4). The reader also drops `## Unchanged references` of `design.md`, which the writer writes, so a valid move plan fails the moved-module gate after a round trip.

## What Changes

- The writer puts the kind of each task group on its files line: `Kind: <kind>. Reads: <reads>. Changes: <changes>.`. The implement split renders its new groups with `group_text`, so they get the line too, and `measure_groups` counts it.
- The reader takes the kind from the `Kind:` line for each value of `GroupKind`. A `manifest` group reads with its case task as `test`.
- A group of the old form reads by inference: a plan written before this change has no `Kind:` line, and a hand edit of that time may name a word that is no kind, such as `Kind: documentation.`. A group whose first task fails on the base is then `behavior` when it changes a path under `src/`, else `manifest`. Each other group is `other`. A later item (`refactor(roadmap): end the kind inference of the plan reader`) writes the line into each old plan and ends the inference.
- The reader reads `## Unchanged references` into `references`, and drops only the last `The change fits one pull request.` line of `## What Changes`, the line that the writer adds.
- `plan_read.FIELDS_NOT_IN_FILES` names the five fields that no file holds, and `plan_read.file_facts` gives a proposal as the reader gives it back. Property tests hold `read_change(render_change(p)) == file_facts(p)` and the fixed point of a read plan.
- The text of `stage_kind_no_source` names `manifest` for a group that changes only a rule, a dashboard or a case file, and `other` for a group with no test.
- The change has spec deltas: the files of a plan and the text of a refused reply are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/task-groups`: a task group writes its kind on its files line, and the problem text of a `behavior` group with no source names `manifest`.
- `roadmap-plan-check`: the reader reads the kind, the unchanged references and every fact that the files hold.

## Impact

- Code: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_plan_read.py`, the snapshots and the tests that hold a rendered files line, the plan heads of #4963, #5032 and #5182 in `tests/fixtures/roadmap/plan_heads/`, and one `manifest` case in the golden set. The plan heads are records: `CONST_DOCS_INVENTORY` of `src/devops_cli/config/constants.py` lists them, so `devops docs check` does not resolve their old commands.
- Documents: `docs/TESTING.md`, `docs/roadmap/plan-check.md`, `k8s/README.md`.

## Feasibility

- `git show --stat 847616309` (#3981) changes `stage_change.py`, the prompts and the tests, and no line of `plan_read.py`.
- At `origin/main` 050a6ef72, `_kind` of `plan_read.py` gives only `behavior` or `other`, and `_group` has no `manifest` branch. `read_change` of the change folder at the head of #4963 (9c4b2cf75c64) raises `PlanReadError` for group 3 (`stage_kind_no_source`), and the head of #5032 (7fd165f69611) for group 3. The Plan Check jobs 131044430778 and 131118707993 report the same errors.
- `_design_file` of `stage_change.py` writes `## Unchanged references`, and `read_change` gives an empty `references` list for that file.
- A run of the reader of `origin/main` over the change folders at the heads of the 151 plan pull requests of the Service (8 open, 143 closed since 2026-10-29) reads 52 of them. The PR comment holds the table of each head on the base and on the branch.
- One head names a word that is no kind: #3164 (merged) says `Kind: documentation.` in group 2, a hand edit at ef3ecb7d8 after the plan of the Service (bd6ab5557). The reader of the base reads it as `other`. The issue asks for a read error on such a word, and its criterion and the rule of the owner say that no head that the base reads is refused on the branch. So the reader keeps the inference of the base for such a word, and the item that ends the inference refuses it.
- The golden plans of `tests/fixtures/roadmap_eval/stage/` 3183 and 3278 hold `The change fits one pull request.` in `what_changes`, and the reader of the base dropped it.

## Existing Tool Considered

OpenSpec has no field for the kind of a task group, and `openspec validate` checks only the spec deltas, so `tasks.md` stays the format of this project. A serialized plan (pydantic JSON beside the Markdown) gives an exact round trip, and is rejected: persons and the implement agent read and edit the Markdown, so a hand edit makes two sources disagree, and the active plans on main have no JSON. Hypothesis (pinned in `pyproject.toml`) generates the plans of the property tests, and syrupy holds the snapshots. The change builds only the reader branches and `file_facts`: about 1.5 M tokens and 4 hours to build, about 30 s of CI for the new tests, and about 0.3 M tokens for each reader defect that a property test finds. It deletes the rule that read every `The change fits one pull request.` line as the line of the writer.

## Dependencies

None.
