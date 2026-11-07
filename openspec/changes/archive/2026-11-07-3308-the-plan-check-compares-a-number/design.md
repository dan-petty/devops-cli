# Design

## Decisions

- **Read only the files that `git grep` names for the constant names that the plan cites, at the staging commit, and parse them with `ast`.**: The staged tree is untrusted plan input, so the check never imports or runs it. `git grep` finds the assignment of each candidate name under `src/`, and `git show` gives the text of that file only, so the check reads a few files and not the whole tree.
- **Resolve an alias to another integer constant across modules, and skip a name that two modules define with different values.**: `BODY_MAX_CHARS = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` reads as 1000 because `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` is 1000 in `src/devops_cli/config/constants.py`; an ambiguous name has no one staged value to compare.
- **Treat a sentence that names one known constant and holds one candidate number as a claim, and skip a sentence with more than one candidate number.**: A sentence with two numbers can show an example, a note or a second bound. A trial over the existing change folders found that most pairs are a note number, a line number or another bound, so a rule that pairs every number would refuse valid plans.
- **Leave out of the candidate numbers a note reference (`#2714`), a line or test location (`:12`) and a path or version.** These are no claim about a constant.
- **Check the plan fields that render to `proposal.md`, `design.md` and each spec delta, and never the text of a task group.**: The issue names requirements, scenarios and decisions; a task command carries numbers and paths that are no claim about a constant.
- **Skip a constant that the staged tree does not define as a module-level integer assignment.**: A plan may introduce a new constant such as `PLAN_SUMMARY_MAX_CHARS`, and the check holds no value to compare for it. The prompt rule asks the model to cite the existing constant instead of renaming its bound.
- **Pass the constants to `check_proposal` as an explicit mapping, and read them in `Stage._settle` from `self._source` and `self._sha`.**: `StagedTree` holds file names only, and the eval replay reads no git. An explicit mapping keeps the seam small and lets a recorded case hold its values.
- **Carry the constants in `CaseFacts` with an empty default, and pass them through `PlanUnderTest` to `check_proposal`.**: The recorded cases keep no text of a file, so an empty mapping leaves them as they are and a later case can record the values it needs.
- **Name the constant, the plan's number and the staged value in one problem line.**: The model corrects the number in one turn, as `SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40` shows.
- **Add the citation rule to the plan stage prompt beside the rule that asks for the quoted probe lines.**: The model has the read tools, and it writes the plan before the check runs, so the rule makes the first reply pass.
- **Keep the check in a new module `src/devops_cli/roadmap/stage/stage_constants.py` and call it from `check_proposal`.**: `check_proposal` is the one seam that the stage job and the replay both call, so the rule runs in both paths.

## Rejected alternatives

- **Import the staged modules to read the constant values.**: `src/devops_cli/roadmap/stage/stage_probe.py` reads the commit with `git cat-file`, `git grep` and `git log` only, so the check runs no staged code.
- **Find the pairs with a regular expression over the source text.**: `src/devops_cli/roadmap/pull_form.py` holds the docstring `Its pattern `^.{1,60}$` runs in JavaScript` and the assignment `BODY_MAX_CHARS: Final[int] = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`, so a regex over text reads 60 from a docstring and finds no literal for an aliased constant.
- **Read every Python file of the staged tree, with no `git grep` first.**: The tree holds hundreds of files, and a plan cites a few names. `git grep` gives the files to parse and keeps the read inside the command budget.
- **Scan every file of the change folder, `tasks.md` included.**: `src/devops_cli/roadmap/stage/stage_change.py` renders `tasks.md` from `group_text`, where a verify command holds a test path and a number that is no claim about a constant.
- **Pair every number in a sentence with every constant in it.**: A sentence that says `SUMMARY_MAX_CHARS` is 60, while the tree says 47, and the issue says 40 is a counterexample and not a claim. The strict rule skips it.
- **Refuse a plan that names a constant which the staged tree does not define.**: The plan folder `openspec/changes/3200-refuse-a-plan-with-placeholder-or/design.md` names `PLAN_SUMMARY_MAX_CHARS = 47`, which `src/` does not define, so a refusal would stop a valid plan.
- **Read the constants through `StagedTree`.**: The class holds file names only, and every test that builds a tree would need the source and the commit. The explicit mapping leaves the tree and those tests alone.
- **Rely on the check alone and add no prompt rule.**: `src/devops_cli/ai/tasks/roadmap_stage_change.md` asks the model to quote the probe lines in `feasibility`, so the prompt carries a rule that makes a reply pass on the first try.
