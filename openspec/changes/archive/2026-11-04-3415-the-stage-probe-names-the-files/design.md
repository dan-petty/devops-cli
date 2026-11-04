# Design

## Decisions

- **The probe reuses `StagedTree.same_name` from `src/devops_cli/roadmap/stage_paths.py` for the same-name lookup.**: The path check and the probe then apply one rule for a same-name file, with the one bound `SAME_NAME_MAX` of five files, and the rule cannot drift between them.
- **The probe builds the staged tree from the commit with one `git ls-tree -r -z --name-only <sha>` command of its budget, on the first missing cited path, and reuses it for every later path of the run.**: `StagedTree.read` reads the checkout with `git ls-files`, which is not the staging commit; the probe judges the commit that the job stages, and one command for the whole run keeps the bound of `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS`. The read waits for the first missing path, so a run that cites only files at the root spends no command on the tree. When no command is left for the tree read, the path keeps the present missing line with no removal text.
- **A cited path that exists at the root keeps its present line and lists no same-name file.**: The lookup runs only for a path that `git cat-file` reports missing, so a passing result is unchanged and stays one line.
- **A missing path with same-name files gets a root-specific line.**: The present message says the path is no file of the staging commit, and that is false when a file with the name sits under a folder. The new message says the path is no file at the root, then names the candidates, and keeps the removal text. A missing path with no same-name file keeps the present message.
- **The new test joins `tests/roadmap/test_roadmap_stage_probe.py`, and the test that pins the command kinds adds `ls-tree`.**: That module holds the probe tests and their staged repository fixture, and it mirrors the package of `src/devops_cli/roadmap/`. `test_every_command_reads_and_the_checkout_does_not_change` asserts the set of command names, so the tree read joins its set.

## Rejected alternatives

- **Search the tree for the name inside `stage_probe.py` with its own `git grep`.**: `src/devops_cli/roadmap/stage_paths.py` already holds `same_name` with the `SAME_NAME_MAX` bound, so a second search duplicates the rule and can drift from the path check.
- **Report the bare name as missing at the root, as today.**: The report of PR #3336 shows the cost: the plan dismissed `stage_specs.py` although `probes` shows `src/devops_cli/roadmap/stage_specs.py` is a file of the staging commit.
- **Append the same-name sentence to the present missing line.**: The line would say the path is no file of the staging commit and then name a file of that commit, so the planner reads a contradiction.
- **Read the tree at the start of every run.**: A run that cites only files at the root then spends one command on a lookup that it never uses, and the bound leaves out one more item.
- **Read the tree again for each cited path.**: The probe runs at most `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` commands for one item, so one tree read for the whole run keeps the bound.
