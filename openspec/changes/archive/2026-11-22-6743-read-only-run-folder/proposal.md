# Proposal: #6743

## Why
#3700 mounts the run folder read-only in `publish`. Argo CD applies the template at the merge, and the runner image takes new code only at a release, so the code must be ready first. Today `publish` makes its new repository in the run folder, and on a read-only mount it fails with EROFS. Closes #6743.

## What Changes
- The `publish` of implement, fix-checks, fix-conflict and stage makes its new repository in the temporary folder.
- A `prepare` that the plan leaves out prints the plan and writes an ended state with the reason; `publish` prints the reason and exits 0.
- The dry run of `run-job` shows the containers of the shape of the template, which it reads from the manifests of the checkout.
- The refusal outside a runner names a run-job command for one item, with `--item <number>`.
- The catalog reads the container `runner` or `agent`.
- The disk-use line names the worktree and the home.

## Capabilities
- `roadmap-implement-runner`: publish writes no run folder, the left-out reason, the dry run.
- `roadmap-implement-job/runner-job`: the disk-use line.

## Impact
- Each change works on the template of one container of today and on the three containers of #3700. The temporary folder of the runner is 1 Gi, which holds the repository of a push (158 MB).

## Feasibility
`publish_patch` makes its repository in `tempfile.mkdtemp(dir=scratch)`, and the callers gave the run folder or the data folder. With no `scratch`, it uses the temporary folder.

## Existing Tool Considered
None applies: the change moves a folder and adds a log line in the project's own code.
