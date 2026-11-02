# Design

## Decisions

- **Extend `collect_context`, add no second extractor.** `refine.py` gets `cited_paths(body)` and `cited_identifiers(body)`, built on its two patterns, and its collectors call them. The probe calls them too. The patterns already refuse a shell command (a backtick text with a space is no identifier), a bare word such as `owner/repo` (it has no extension) and a path with `..` or a leading `/`. The probe adds one rule: the extension starts with a letter, so a version such as `0.41` is no path.
- **A new outcome `PremiseFailed`, not a call of the CLI.** `_Planner` has no store and `plan()` returns an outcome. `plan()` returns `StagedChange | OverBudget | PremiseFailed`. `plan_stage` keeps the third kind in `StagePlan.returned`, and `apply_stage` calls `plan_return` and `apply_return` for each. The job does not shell out to `devops roadmap return`.
- **`premise_failed` is a field of `StageProposal`.** The toolbox client and the golden set key on that one class. All plan fields get an empty default, and a validator asks for the full plan when `premise_failed` is not set. A reply with `premise_failed` needs no plan, so the model writes no plan that the job throws away.
- **Probe order and cost.** Paths come first, then identifiers, each in the order of the issue. A present path costs 1 command and a missing path 2 (`git cat-file -e`, then `git log -n1 --diff-filter=DR`). A defined identifier costs 1 (`git grep -E`) and an undefined one 2 (then `git log -n1 -S`). The removal probe runs only for a missing item.
- **The bound is 10 commands per item.** The four cited examples hold 1 to 4 items of at most 2 commands each. 10 covers them and keeps the probe under the 15 second limit of each command. An item that the bound leaves out is listed as not probed.
- **Read-only by construction.** The probe builds each command from a fixed list: `cat-file`, `grep` and `log`, with a `--` before every path. A test runs the probe on a repository and asserts that every command is one of the three and that the repository has no change after.
- **The probe says what it does not know.** A missing item with no commit found reads "no commit in the history deleted or renamed it" or "no commit in the history added or removed it". The prompt tells the model that such an item may be a thing the issue asks to create, which is no false premise.
- **The evidence goes to a public comment.** The job writes the evidence on one line with `safe_text` and masks secrets before the comment, as it does for every model text.
- **The reply to a return of the verification pass may set `premise_failed`, and the job then returns the item.** The planner is the one that reads the finding with its evidence.
- **The gate `FALSE_PREMISE` leaves the pending list and its recorded defects get the gate `none`.** See the rejected alternatives.

## Rejected alternatives

- **Write a second extractor in `stage_probe.py`.** `collect_context` has the patterns already, and the review of the plan asked for one place. Rejected on AGENTS.md rule 3.
- **Shell out to `devops roadmap return` from the job.** The command needs a store and a clone, and the round has both. `plan_return` and `apply_return` are the code of the command, so a call in process is the same write with no subprocess.
- **A new model call to judge the premise.** #3153 added a model pass after the plan. The probe is deterministic and runs before the call, and it costs no token. The model judges only the evidence that the probe gives.
- **Build `FALSE_PREMISE` as a gate of the replay.** `replay_case` reads no git, and `facts.json` of a case holds a thinned tree (the paths of the plan, one file for each suffix and top folder). A gate cannot tell a removed path from a path that never existed on that tree. The premise check runs before the plan, on the live commit, and its test is the #2971 replay on a real temporary repository. Leaving the entry in `PENDING_GATES` would keep a defect that waits for a gate that will not come, so the defects get `none`, which the replay lists as judged by no gate.
- **Ask the model to extract the cited items.** The model cannot run commands, and the patterns of `refine.py` do the work with no call.
- **Probe all items in parallel.** The removal probe is only needed for a missing item, so parallel runs waste commands against the bound.
- **Open a pull request with a note about the false premise.** AGENTS.md rule 2 says to write no compensating code and to return the item with the evidence.
