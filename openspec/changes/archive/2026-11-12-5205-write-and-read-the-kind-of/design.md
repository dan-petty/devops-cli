# Design

## Decisions

- **Write the kind on the files line of each group**: `Kind: <kind>. Reads: ... Changes: ...` is the form that hand-written plans use already (`openspec/changes/2742-bound-the-number-of-prewarm-model/tasks.md`). `KIND_LINE` of `step_files.py` reads it at the start of the line, and the `Reads:` pattern of the reader finds the rest of the line. `TaskGroup.is_behavior` gives the same value as before for each group that the writer makes, because a `manifest` group still starts with a task that fails on the base.
- **Read a word that is no kind as the old form**: hand-written plans name kinds such as `documentation` or `documents`, because `openspec/config.yaml` lists those groups by what they change. The reader of the base reads them by inference, and the head of #3164 holds one. No head that the base reads may break, so the reader keeps that inference, and the item that ends the inference refuses such a word.
- **Infer the kind only for a group of the old form**: a case-first group is `behavior` when it changes a path under `src/` (`changes_source`, the same rule as the #3035 gate) and `manifest` when it does not. The #3035 rule stays as it is: the missing reader change was the cause.
- **State the contract as `file_facts`**: the fields that no file holds are a closed list (`FIELDS_NOT_IN_FILES`), and `file_facts` gives each of them the value of the reader. A changed reference is no fact of the files, because the writer writes only the unchanged ones and the moved-module gate reads only those. The created paths come back in the order of the changed paths, because the files line marks them there.
- **Drop only the last `The change fits one pull request.` line**: the writer adds that line at the end of `## What Changes`, and a model may write the same line as an item of its own (the golden plans of 3183 and 3278).

## Rejected alternatives

- **Change `_kind` alone**: the group then reads as `other` with no test, because `_group` reads the case task only for `behavior`. The `manifest` branch of `_group` is necessary.
- **A serialized plan beside the Markdown**: a hand edit of `tasks.md` makes the two sources disagree, and the active plans on main have no JSON.
- **Refuse a word that is no kind now**: the head of #3164 says `Kind: documentation.` and reads on the base, so the refusal breaks a plan that reads today. The refusal comes with the end of the inference, when a form edit rewrites the line of each old plan.
- **Relax the #3035 rule for case-first groups**: the rule is correct for a `behavior` group, and a relaxed rule lets a test-first group that changes no code through as `behavior`.

## Unchanged references

- `openspec/specs/roadmap-stage/task-groups/spec.md` (living spec): `openspec archive` writes the living spec from the spec delta of the change.
- `openspec/specs/roadmap-plan-check/spec.md` (living spec): `openspec archive` writes the living spec from the spec delta of the change.
