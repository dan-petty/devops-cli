# Design

## Decisions

- **The Status section records the approval as the merge commit of the pull request on the default branch, named by `git log --follow`, and holds no approving person, no comment URL and no SHA.**: A file cannot hold the SHA of the merge that adds it, and the scope of #3288 makes that merge the approval.
- **The alternatives section uses the heading `## Considered Options`, and a `## Rejected options` section holds the rejected alternatives.**: The alternatives check keeps the `Considered Options` section of each record, as `docs/roadmap/alternatives.md` states, so that heading makes this decision readable to it.
- **The record lands in two groups, each writing about half of it.**: Each step then reads a few sections and writes about 100 lines, which stays inside the step budget of 64000 tokens.
- **The record adopts the container boundary of a separate run Job and no sandbox library, and this change writes no code.**: The owner decision of 2026-10-30 separates privilege by container, and the platform gives that boundary without a second path to keep.
- **The allow-list takes the read-only mark of the MCP exposure table and the path restrictions of its generator.**: Those two tables are the tested record of a command that reads only and takes no path, so the run tool keeps no second list of its own.

## Rejected alternatives

- **Run any command that an issue or a model quotes.**: An issue is untrusted input, and the issue records that `devops --dry-run config unset` deleted a key (#3218).
- **`HostSandbox` with bubblewrap inside the Service pod.**: The owner decision of 2026-10-30 rejects bubblewrap and `unshare` for this path, and `NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py` leaves `bwrap` out of the runner image.
- **A stage Job as the place of the command.**: No stage Job exists: `src/devops_cli/roadmap/run.py:def _run_stage_adapter` runs `plan_stage` in the Service process.
- **A deny list of the known write commands.**: SECURITY.md rule 7 records that the kube-api path filter is a deny list, and a new subresource passes it until the list names it.
