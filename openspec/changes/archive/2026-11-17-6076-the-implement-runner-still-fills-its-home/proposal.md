# Proposal: #6076 The implement runner still fills its home volume

## Why
#6076: the kubelet evicted the implement runner pods of #3458 (21:09 UTC) and #3782 (23:29 UTC) on 2026-11-16 with `Usage of EmptyDir volume "home" exceeds the limit "8Gi".`, after #5960 raised the volume from 4 Gi. In each run, a fix step of the scoped check `strength` changed `src/devops_cli/roadmap/implement/implement_strength.py`, which is outside its plan, wrote `.data/agent/scratch/probe_mutation.py` and ran it. The pod was evicted 101 s and 186 s later. Both agents went after a false failure: `coverage xml` applies the `fail_under = 85` of `[tool.coverage.report]` to a scoped run, which covers a small part of `src`, so the strength check failed for every item. The eviction stops the Job at once and leaves no line about what filled the volume.

## What Changes
- The coverage report of the strength check takes no floor of its own. diff-cover at 90% still bounds the changed lines.
- A change with no Python file under `src/` runs only the assertion scan of the strength check, and the report says why.
- The end of each step of the agent removes `mutants/` and empties `.data/agent/scratch/`, done, stopped or with an error.
- In a runner Job, the end of each step and each stop write the disk use of the home volume and its largest folders to the Job log.

## Capabilities
- Modified: `roadmap-implement-job/repair` (the coverage floor and the change with no source file), `roadmap-implement-job/runner-job` (the disk use line) and `roadmap-implement-step/exit-checks` (the end of a step removes the by-products, and the ignored-file scenario of the stray files).

## Impact
- No fix step starts for a strength failure that the item cannot fix, and a change of tests, manifests or documents runs no coverage run of `src`.
- A scratch file lives for one step. The prompt of the step says so.
- The volume stays at 8 Gi and the storage request at 4 Gi. The root disk of node `hog` holds the emptyDirs, and it had 20 GB free at its lowest point from 2026-11-14 to 2026-11-17, so the runner volume does not grow (#4001).
- The change fits one pull request.

## Feasibility
- The pod logs in Loki (`service_name="devops-cli-job"`): the last command of both pods is `uv run python .data/agent/scratch/probe_mutation.py`, and both agents read the coverage code before it (`uv run coverage xml -q --fail-under=0` in #3458). The eviction events are in `kubernetes-events`.
- A real run on 2026-11-17: `uv run pytest --cov=src --cov-report= --cov-fail-under=0 tests/roadmap/implement/test_roadmap_implement_strength.py`, then `uv run coverage xml -q`, exits 2 with `Coverage failure: total of 17 is less than fail-under=85` (coverage 7.17.3).
- A default `uv run mutmut run` of this repository wrote 322 MB into `mutants/` in 152 s on the devcontainer, so a mutation run alone does not explain 6 GB in 101 s to 186 s. The disk use line names the writer of the next eviction.
- `node_filesystem_avail_bytes{instance="hog",mountpoint="/"}`: 20 GB at 2026-11-17 00:08 UTC and 43 GB at 02:00 UTC, of 236 GB. The kubelet reports 224 GB of allocatable ephemeral storage.

## Existing Tool Considered
- `coverage xml --fail-under=0` is the option of coverage.py for a report with no floor.
- GNU `du -x -B1 -d 1` measures the folders, with each folder counted once over its arguments, as the kubelet counts the volume. `format_bytes` of the output package formats the sizes.
- `shutil.rmtree` removes the by-products. No code of our own walks the tree.
