# Design

## Decisions

- **Read the constant values with `ast` from the staged Python files, and resolve a simple alias to another integer constant.**: The staged tree is untrusted plan input, so the check never imports or runs it, and an alias such as `BODY_MAX_CHARS = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` reads without execution.
- **Pair a known constant name with a decimal integer in the same sentence, in either order.**: A wrapped Markdown line breaks a pair, and a whole file pairs unrelated numbers with a constant, while the claim that the issue records sits in one sentence.
- **Check the texts of the reply that render to `proposal.md`, `design.md` and each spec delta, and never the text of a task group.**: `check_proposal` holds the reply and not the rendered files, and the issue names requirements, scenarios and decisions; a task command carries numbers and paths that are no claim about a constant.
- **Skip a constant that the staged tree does not define as a module-level integer assignment.**: A plan may introduce a new constant such as `PLAN_SUMMARY_MAX_CHARS`, and the check holds no value to compare for it.
- **Name the constant, the plan's number and the staged value in one problem line.**: The model corrects the number in one turn, as `SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40` shows.
- **Add the citation rule to the plan stage prompt beside the rule that asks for the quoted probe lines.**: The model has the read tools, and it writes the plan before the check runs, so the rule makes the first reply pass.
- **Keep the check in a new module `src/devops_cli/roadmap/stage_constants.py` and call it from `check_proposal`.**: `check_proposal` is the one seam that the stage job and the replay both call, so the replay proves the rule on the golden set.

## Rejected alternatives

- **Import the staged modules to read the constant values.**: `src/devops_cli/roadmap/stage_probe.py` reads the commit with `git cat-file`, `git grep` and `git log` only, so the check runs no staged code.
- **Find the pairs with a regular expression over the source text.**: `src/devops_cli/roadmap/pull_form.py` holds the docstring `Its pattern `^.{1,60}$` runs in JavaScript` and the assignment `BODY_MAX_CHARS: Final[int] = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`, so a regex over text reads 60 from a docstring and finds no literal for an aliased constant.
- **Scan every file of the change folder, `tasks.md` included.**: `src/devops_cli/roadmap/stage_change.py` renders `tasks.md` from `group_text`, where a verify command holds a test path and a number that is no claim about a constant.
- **Refuse a plan that names a constant which the staged tree does not define.**: The plan folder `openspec/changes/3200-refuse-a-plan-with-placeholder-or/design.md` names `PLAN_SUMMARY_MAX_CHARS = 47`, which `src/` does not define, so a refusal would stop a valid plan.
- **Rely on the check alone and add no prompt rule.**: `src/devops_cli/ai/tasks/roadmap_stage_change.md` asks the model to quote the probe lines in `feasibility`, so the prompt already carries the rule that makes a reply pass on the first try.
