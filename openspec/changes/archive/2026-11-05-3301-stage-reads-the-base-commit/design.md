# Design

## Decisions

- **The staged commit is `origin/<default branch>` after the fetch that `read_planned_changes` makes.**: The probe, the branch and the tools need one commit. The fetched default branch is the commit that the job plans for, and it is the same for every item of a round.
- **The job moves the clone to the staged commit with `git merge --ff-only <sha>`, only when a round selects an item.**: The toolbox refuses a HEAD that is not the staged commit (`src/devops_cli/roadmap/stage_tools.py`, lines 77 to 88). A fast-forward moves HEAD, the branch and the index together, and it refuses a diverged clone. Git keeps the HEAD of a clone that is ahead of the staged commit, so the job checks HEAD after the move. The move runs in `plan_stage`, not in `read_stage_selection`, because `devops roadmap explain` reads the selection and writes nothing.
- **The tree read stays `git ls-files`.**: After the fast-forward, the index holds the staged commit. A second read of the tree at the commit would add a git command and change no result.
- **The branch of a new staged item starts at the staged commit, through a `base` argument of `add_worktree`.**: The `base` applies to the create path only. A take-over keeps the tip of the pushed branch, which is the commit that the App wrote.
- **`add_worktree` keeps `origin/main` as the start when no base is given.**: The implement job and the command `devops repos worktrees add` keep their behavior.
- **The probe logic stays as it is.**: The defect is the commit that the probe reads, not the probe. `src/devops_cli/roadmap/stage_probe.py` is unchanged.

## Rejected alternatives

- **Keep HEAD as the staged commit and fetch without moving it.**: The toolbox refuses that checkout, so every plan run with a stale clone would fail. The bug would move from a false "absent" to a refused run.
- **Make the toolbox read files at the staged commit.**: The tools `file_symbols`, `repo_map` and `read_spec` read the working tree. A change to read each tool at a commit rewrites three tools and their tests, which is larger than one fast-forward.
- **Run `git reset --hard origin/main` in the clone.**: A reset destroys local work. A fast-forward refuses it.
- **Run `git switch --detach <sha>` in the clone.**: A detached switch leaves the local commits of the clone unseen. A fast-forward refuses a diverged clone, and the job checks HEAD for a clone that is ahead.
- **Move the clone in `read_stage_selection`.**: `devops roadmap explain` calls that function, and the explain command must write nothing.
- **Start every branch at a fresh `origin/main` and accept a probe commit that differs from it.**: A commit that lands between the probe and the branch would have files the probe did not check. The base argument removes the gap.
- **Pass the base to the take-over path.**: The take-over path reuses a branch that the App already pushed. Its tip is the commit that was staged, so the base does not apply.
