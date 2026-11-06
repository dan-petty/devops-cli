# Design

## Decisions

- **Extend `plan-recheck` and add no command.**: The command already reads each change folder of the default branch and calls the stage gates with no model. A second command would repeat the reader and the gate calls.
- **`check_gates` gives the problems of `check_proposal` under the name of their gate, and `check_proposal` joins them.**: The call that builds each list is the only place that knows the gate. The enum `ProposalGate` holds the names. A new gate adds one member and one line to `check_gates`, and a test fails when a member has no line. Every other caller keeps the flat list.
- **The gate names are finer than the gates of the replay.**: The replay (`devops roadmap eval stage --replay`) runs `check_proposal` as its one gate `paths`. The names of `ProposalGate` split that gate. The gate `content` and the gate `criteria` keep their names.
- **A refusal of `plan-recheck` has the gate `read` when the plan reader refuses the folder, `openspec` for a finding of `openspec validate`, or a name of `ProposalGate`.**: The three sources are the three checks that `plan-recheck` already runs.
- **`--branch <ref>` takes a ref of the clone, and the command fetches nothing for it.**: A person passes `HEAD` with `--source .` to judge the checkout, or `origin/<branch>` to judge a pushed branch. The fetch of the default branch stays as it is.
- **The branch is judged on its own tree.**: A branch that moves or deletes a file can make a gate refuse a merged plan. The path gate reads the tree of the branch for the branch and the tree of the default branch for the default branch. Both sides use the code that runs, so the report shows what the tree changes. A gate that a person adds shows its hits in its own gate list of the same report.
- **A refusal that both sides hold is listed once, with the side `both`.**: The branch holds most of the refusals of the default branch. One line for each refusal keeps the report short and loses no fact.
- **The run with `--branch` takes 33 seconds on `origin/main`, against 22 seconds with no option.**: Measured on 2026-11-06 with `uv run devops roadmap plan-recheck --source . --branch HEAD`: 55 folders on `main` and 57 on the branch. The second pass reads the folders of the branch and runs the same checks, so the time grows by about half. The limit of AGENTS.md rule 5 is 300 seconds.
- **A refusal is new when the branch holds it and the default branch does not hold the same folder, gate and message.**: A folder that only the branch holds has every refusal new. A refusal that only the default branch holds is not new.
- **Every added refusal is a case to review.**: A refusal on a merged plan can be a hit or a false refusal. Only a person decides which. The report claims no proof.
- **A folder that the reader refuses is listed as not read, and the run goes on.**: The reader raises `PlanReadError` for such a folder. `plan-recheck` does not catch `ValidationError`, which #3591 removes from the reader.
- **The issues that closed or stayed open are read once for both sides.**: A folder of a closed issue gets `cleanup` on both sides. The store is read one time for each issue.
- **`plan-recheck` judges less than the stage job, and the documents say so.**: It gives `check_proposal` no `probes`, `overlaps`, `search_evidence` or `plan_creates`. It does not measure groups, scan for secrets or check the staging title, and it calls no model. A refusal is therefore a case to review, and an accepted plan can still fail the job.

## Rejected alternatives

- **Add a command.**: It repeats the reader and the gate calls of `plan-recheck`.
- **Add a git mode to the replay of `eval stage`.**: The replay reads no git and builds its tree from a list of files. A git mode needs a new checkout path in the replay.
- **Match the text of a sentence to a gate.**: The sentences are prose and change. A match breaks without a test failing.
- **Run each gate on its own from `plan-recheck`.**: `check_proposal` runs all gates in one call, and the job calls it the same way. Two call paths can drift.
- **Report every refusal of the branch as new.**: The default branch holds most of the same refusals, so the report would not show what the branch changes.
- **Catch `ValidationError` in `plan-recheck`.**: That hides a reader defect. #3591 fixes the reader.
