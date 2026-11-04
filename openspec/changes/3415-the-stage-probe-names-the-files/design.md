# Design

## Decisions

- **The probe reuses `StagedTree.same_name` from `src/devops_cli/roadmap/stage_paths.py` for the same-name lookup.**: The path check and the probe then apply one rule for a same-name file, with the one bound `SAME_NAME_MAX` of five files, and the rule cannot drift between them.
- **The probe builds the staged tree from the commit with one `git ls-tree -r --name-only <sha>` command of its budget, and reuses it for every cited path of the run.**: `StagedTree.read` reads the checkout with `git ls-files`, which is not the staging commit; the probe judges the commit that the job stages, and one command for the whole run keeps the bound of `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS`.
- **A cited path that exists at the root keeps its present line and lists no same-name file.**: The lookup runs only for a path that `git cat-file` reports missing, so a passing result is unchanged and stays one line.
- **The new test joins `tests/roadmap/test_roadmap_stage_probe.py`.**: That module holds the probe tests and their staged repository fixture, and it mirrors the package of `src/devops_cli/roadmap/`.

## Rejected alternatives

- **Search the tree for the name inside `stage_probe.py` with its own `git grep`.**: `src/devops_cli/roadmap/stage_paths.py` already holds `same_name` with the `SAME_NAME_MAX` bound, so a second search duplicates the rule and can drift from the path check.
- **Report the bare name as missing at the root, as today.**: The report of PR #3336 shows the cost: the plan dismissed `stage_specs.py` although `probes` shows `src/devops_cli/roadmap/stage_specs.py` is a file of the staging commit.
- **Read the tree again for each cited path.**: The probe runs at most `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` commands for one item, so one tree read for the whole run keeps the bound.
