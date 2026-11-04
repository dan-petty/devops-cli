# Design

## Decisions

- **Take the Conventional Commit type and scope from the item title, and append the step title and one issue reference.**: CONTRIBUTING.md makes the item's pull request title the changelog line, so the type and scope of the item are the ones a reader expects on its commits.
- **Read the type and scope with the `commit_type` and `commit_scope` functions of `src/devops_cli/roadmap/commit_title.py`.**: That module already parses a Conventional Commit title for `pull_form.py` and the roadmap jobs, so one parser decides the type and scope of every title.
- **Fall back to `chore` when the item title has no valid Conventional Commit type.**: A missing prefix is a formatting problem. The step finishes with a valid commit instead of stopping the item, and `chore` adds no changelog line.
- **Keep the archive commit title `docs(openspec): archive the change (#N)`.**: CONTEXT.md defines the archive as the last commit of the change folder, which is a docs change, and the form already works.
- **Add the issue reference only when the text does not already end with it.**: A task group title may carry the reference, and one suffix keeps the title valid.
- **Carry the item title in the inputs of a step.**: The commit of a step holds the issue number and the group title, but no item title, and the parser needs the item title for the type and scope. `build_step_inputs` reads the item, and `StepInputs` is built in one place, so one field carries the title to the commit.
- **Test the helper offline with exact input and output strings.**: docs/TESTING.md asks a pure function to be tested with examples, and a unit test needs no job, no git and no network.

## Rejected alternatives

- **Prefix every step commit with a fixed `docs` type and the task group title.**: Task groups have no type or scope (`roadmap-stage` requirement `A task group has a kind`), so a fixed prefix would label a `fix` item as docs and break the changelog line that CONTRIBUTING.md section 4 describes.
- **Reuse the `docs(openspec)` prefix of the archive commit for the steps.**: CONTEXT.md and the issue body give `docs(openspec): archive the change (#2670)` to the archive commit only; the step commit of issue 2670 was a SECURITY.md change.
- **Stop the step when the item title has no Conventional Commit type.**: CONTRIBUTING.md section 4 lists the types and their labels; a missing prefix is not a reason to stop delivery, and `roadmap-implement-job` requirement `A stopped item is Blocked and the job does not retry it` makes a stop expensive.
- **Check the step commit titles with a git hook instead of formatting them.**: CONTRIBUTING.md section 4: `no hook checks the message of a commit on a branch.` A hook would report the defect after the commit and leave the history wrong.
- **Write a second Conventional Commit parser inside the new helper.**: `src/devops_cli/roadmap/commit_title.py` already holds `commit_type` and `commit_scope`, and `pull_form.py` imports them, so a second parser would give two answers for one title.
