# The plan recheck

`devops roadmap plan-recheck` judges again each change folder that the default branch holds. A plan
is judged once, when the stage job writes it. A later gate can strand an old plan. A delivered plan
can stay Planned. The folder of a closed issue stays in every count. This command shows all three.

## What it reads

The command reads `origin/<default branch>` of the model clone, or of the clone that `--source`
names. It reads each folder `openspec/changes/<issue>-<slug>/`, the open issues, and the issue of
each folder that is not open. It calls no model and writes nothing to git or to GitHub.

For each folder it runs the same checks as [plan-check](plan-check.md): the plan reader
(`read_change`), the stage gates (`check_gates`, the gates of `check_proposal`) and
`openspec validate --strict`.

## What the pass judges less than the job

The stage job judges a plan on the commit that it stages, with facts that the pass does not have.
A refusal of the pass is therefore a case to review, and a plan that the pass accepts can still
fail the job. The pass does not give these to the gates, and it does not run these checks:

- The premise probe. The job refuses a `feasibility` that quotes no line of the probe.
- The open pull requests. The job refuses a plan that omits an open pull request that changes a
  path the item cites. The pass reads no pull request.
- The recorded search. The job records the hits of each negative-search literal at the staged
  commit. The pass records no search, so the gate `search` judges only the created paths.
- The plans of the other open items. The job refuses a path that such a plan creates. The pass does
  not read them.
- The size of the groups. The job refuses a group above `roadmap.stage.step_tokens`. The pass
  measures no group.
- The secret scan of the plan files and the check of the staging title.
- The review of a model. The pass calls no model.

The pass judges a plan on the tree of the default branch, or on the tree of the branch that a person
names. The job judges it on the tree of the commit that it staged.

## The result of a folder

Each folder gets one result. The first rule that holds gives it.

| Result | Meaning |
| :--- | :--- |
| `cleanup` | The issue of the folder is closed. Run `openspec archive`, or delete the folder. |
| `delivered` | Every file that the plan marks `(new)` is on the default branch. The issue is not closed yet. |
| `new-plan` | The plan does not read, or it fails a gate or `openspec validate`. The first line below the folder is the first problem. |
| `rewrite` | The plan passes every check, but it has no `design.md` or no `Verification:` line. A mechanical rewrite can add them. |
| `ok` | None of the above. |

A plan with no `Verification:` line usually fails the plan reader, because a group needs a command or a manual process. So the command shows such a plan as `new-plan`, with the reader error as the reason. The result `rewrite` is for a plan that passes every check and lacks only the `design.md` or the `Verification:` line.

The command does not tell a sample path from a stale path. A path that the tree lacks is a
`new-plan` problem.

## The gate of a refusal

Each refusal of a `new-plan` folder prints with the name of its gate, in square brackets. The gate
`read` is a folder that the plan reader refuses. The gate `openspec` is a finding of
`openspec validate`. The other gates are the members of `ProposalGate`, the gates that
`check_proposal` runs:

| Gate | What it refuses |
| :--- | :--- |
| `spec-delta` | A spec delta that the plan needs and lacks, or that it does not need, or a bad requirement or capability. |
| `content` | A text that is too short or a placeholder, a `feasibility` that quotes no probe line, a task that names a message and changes no message file, and a plan that builds its own code and gives no cost. |
| `citation` | A citation of a file that the staged commit does not hold as cited: a `path:line:text` line with other text, or a `path:def name` symbol that the file lacks. |
| `form` | A task text of one word, a `verify` command outside the project form, and a new test module outside the mirror directories. |
| `eval-replay` | A plan that changes the stage prompt or a module of the stage checks and holds no task that runs the replay and states the score before and after. |
| `paths` | A path that the tree lacks and that no group up to the one that names it creates. |
| `what-changes` | A path in a `What Changes` item that no group lists in `changes` or `creates`. |
| `move-prefix` | A move of a prefix that leaves a module of it out of `changes`. |
| `move-verify` | A move group whose `! git grep` literal names one module of the prefix. |
| `search` | A negative-search literal with no recorded hit, or that a created source path keeps. |
| `criteria` | An acceptance criterion of the issue that no entry of `criteria` holds. |
| `dependencies` | An open pull request that changes a cited path and that `dependencies` does not name. |
| `creates` | A path that the plan of another open item creates too. |

The replay of [the stage job](../ROADMAP_WORKFLOW.md#measure-the-stage-job) runs all of the gates
of `ProposalGate` as its one gate `paths`. So the names here are finer than the names of the replay.
The report ends with the number of refusals for each gate. A person who adds a gate adds a member
to `ProposalGate`, and the report then shows the hits of that gate under its name.

## The counts

A folder of a closed issue is in no count. The report prints these counts for the other folders:

- how many folders have no `Verification:` line, so the implement step requires no plan command;
- how many folders the plan reader refuses;
- the number of folders for each result.

## Compare a branch with the default branch

`--branch <ref>` takes a ref of the clone, such as `HEAD` or `origin/<branch>`. The command fetches
nothing for the ref. It reads each change folder of the ref on the tree of the ref, with the same
plan reader and the same gates, and it judges the default branch as it does without the option. It
calls no model. After the report of the default branch it prints:

- the number of folders on each side;
- the result of each folder of the branch, and the number of folders for each result;
- for each gate, the number of refusals on each side, and one line for each refusal. The line starts
  with `both` when the two sides hold the same refusal, or with the name of the side that holds it;
- the refusals that the branch adds, as `New refusals on <ref>`. A refusal is new when the default
  branch holds no refusal with the same folder, gate and message. Each one is marked as a
  `case to review`;
- the folders that the plan reader refuses on the branch, as `Not read on <ref>`.

A refusal that the branch adds is a case to review, not a proven false refusal. It can be a hit of
the gate or a false refusal. Only a person decides which. A folder that the reader refuses does not
stop the run.

Use the option in three ways:

- On a plan branch, `New refusals` lists what the plan adds.
- On a branch that moves or deletes a file, `New refusals` lists the merged plans that now name a
  file the branch lacks.
- On a branch that adds a gate, both sides use the new gate, so `New refusals` stays empty. The
  lines under the name of the new gate list its refusals. Use `--source .` in the checkout of the
  branch, so that the command runs the code of the branch.

## Policy

A new gate on merged plans only reports until this pass has run. The pass shows which plans the
gate strands. A person then decides, for each plan, to rewrite it, to plan it again, or to clean it
up. The pass closes no issue.

| Option | What it does |
| :--- | :--- |
| `--repo <owner/name>` | The repository. Without it, the origin of the checkout. |
| `--source <path>` | The clone to read. Without it, the model clone. |
| `--branch <ref>` | A ref of the clone. Compare its change folders with the default branch. |
| `--json` | Print the folders, the counts and the refusals of each gate as JSON. With `--branch`, the key `branch` holds the comparison. |
| `--dry-run` | Make no request: print the reads that a run makes, with placeholders. |

## Where the rules are

[roadmap-plan-recheck](../../openspec/specs/roadmap-plan-recheck/spec.md) holds the requirements.
