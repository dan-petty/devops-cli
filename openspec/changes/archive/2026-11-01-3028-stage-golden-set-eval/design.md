# Design

## Decisions

- **The plan is stored as a `StageProposal`, with the groups raw.** The gates and the future gates take a `StageProposal`. A group that the schema refuses (the kind rule) must stay a case, so `plan.json` keeps each group as the dict the model wrote, and the replay validates it group by group. The change folder files are the output of `render_change`, and the merge commit of each case is recorded, so `git show <merge>:<file>` gives the staged text.
- **Old groups get a kind by the rule of their day.** Before #3005 every group had a failing test. So a group with a test task has the kind `behavior`, and a group with none has `other`. The kind rule then refuses the groups that change no path under `src/`, as #3005 counts them.
- **A case records the facts, not the tree.** `facts.json` holds the tracked files that the plan names, the files with the same name as a missing path, one file for each suffix and for each top folder of the tree, and the capabilities that the plan names. A word is a path by the suffixes and top folders of the tree, so those two sets must survive the cut. The builder compared the answer of the gate on the full tree and on the cut tree for every case.
- **The pinned commit is the parent of the merge commit.** The staging commit itself is not in the history of `main` after a squash. The parent of the merge commit is the tree that the plan was reviewed against.
- **A defect names its gate.** `paths`, `kind`, `pending` (a gate is planned: #3011 to #3019) or `none` (a reviewer judges it). The replay checks that a `paths` defect is refused and names each path the case lists. When a gate for a pending type lands, the replay flags every `pending` defect of that type as stale, so the case file changes in the same pull request as the gate.
- **The live score judges the first reply.** The planner already sends a refused reply back, so the final plan always passes the gates. The score is how often the model gets it right before the gates act. A recording client keeps the replies and the calls. The first reply is judged again by the gates, against the tree of the checkout.
- **A schema failure counts for `kind`.** The client sends a reply that breaks the schema back inside one call, so the run sees only a second failure. A case that ends so counts as a `kind` problem of the first reply.
- **The rate has no value for a type without a gate.** The table lists its count of cases and shows a dash. A made-up rate would hide that nobody judges the type.
- **The group `roadmap eval` is in its own small module.** `roadmap_eval.py` holds the Typer group and one line for each subcommand. `roadmap.py` adds the group once. The second pull request of the wave adds its own line.
- **The report goes under the data directory.** `resolve_store_path("roadmap_eval/stage/<time>.json")` puts it where the other stores are, and `--json` prints the same text.
- **The live run checks out the commit in a detached worktree.** `git worktree add --detach` gives the planner a real checkout: it reads the tracked files, measures the groups and runs `openspec validate` on it. The worktree is removed after each case.

## Rejected alternatives

- **Store the change folder files only.** A group that breaks the schema cannot be a `StageProposal`, and old formats differ. A parser for each format would be new code with its own defects. `plan.json` is the typed record, and `render_change` makes the files.
- **Read git in the replay.** The issue says a replay in CI cannot assume a deep clone. The check in the builder shows the facts give the same answer.
- **Fail the replay on a pending defect.** The gates #3011 to #3019 do not exist, and the issue asks that such cases are listed and not failed.
- **Score the final plan.** The planner returns a reply once, so the final plan passes the gates by construction. It would measure nothing about the model.
- **Run the live eval in `devops ci`.** It calls a model through the gateway. The issue and tracker #3027 make it on demand.
- **`pydantic-evals`.** See the proposal: the library adds an evaluator and a report layer for a count that a small function makes.
