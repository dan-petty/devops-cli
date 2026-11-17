# Design

## Decisions
- **No floor on the scoped coverage report.** `coverage_delta` runs `coverage xml -q --fail-under=0`. The floor of `pyproject.toml` is the floor of the whole suite, which the required check `Tests & Coverage` applies. The strength check bounds the changed lines with diff-cover at 90%.
- **No mutation run and no coverage run without a source file.** `strength_report` checks the active files with `is_mutated_source` of `devops_cli.ci.mutate`, the rule that `select_targets` uses. With no Python file under `src/`, it returns the assertion findings and the note `implement_strength_no_source`.
- **The end of a step owns the by-products.** `run_step` calls `end_step` in its `finally` block, after the reset of a step that is not done. `end_step` writes the disk use line first and then removes `mutants/` and the files of `.data/agent/scratch/`, so the line names what the step wrote. A link is removed as a link.
- **One `du` call per line.** `read_disk_use` runs `du -x -B1 -d 1 <worktree> <home>`. du counts a folder once, at the first argument that holds it, so the worktree folders and the folders of the rest of home add up to the volume. The line names the 8 largest folders. It runs only when `roadmap.implement.in_runner` is true, because outside a runner home is the home of a person.
- **A stop writes the line too.** `_ItemRun.stop` writes it before the push, so a stop outside a step of the agent also leaves the use of the volume in the log.
- **The volume keeps its size.** The root disk of `hog` holds the emptyDirs and had 20 GB free at its lowest point in 3 days, so 6 Jobs with a volume of 16 Gi could put the node under DiskPressure.

## Rejected alternatives
- **Double the volume to 16 Gi.** The owner rule doubles a limit of a job under 80%, but the root disk of the node cannot hold 6 such volumes. The disk use lines of real runs size the volume after #4001 frees the root disk.
- **A watchdog that samples the volume during a step.** It needs a thread beside the agent and a stop path of its own. The cause of the evictions was the false failure, which this change removes, and the line at each step end and stop names any new cause.
- **A separate emptyDir for the scratch folder.** The kubelet evicts the whole pod for any volume over its limit, so a second volume bounds nothing.
