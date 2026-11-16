# Proposal: #5960 The strength check fits in the home volume of the runner

## Why
#5960: on 2026-11-16 the kubelet evicted the runner pod of #3648 after 2 h 7 min: `Usage of EmptyDir volume "home" exceeds the limit "4Gi".` The runner ignored SIGTERM and the kubelet killed it at the end of the grace period, with exit status 137 and the container reason `Error`. Since #5892 the strength check runs `uv run mutmut run` in the worktree. mutmut 3.8.1 writes a mutated copy of each file of `source_paths` into `mutants/`, and the tree stays after the run. The Service then gave the stop the class `oom` from the exit status 137 alone, with the action `raise_limit` for a memory limit. More memory does not help.

## What Changes
- The mutation run of the strength check sets `only_mutate` of `[tool.mutmut]` to the files of its targets while `mutmut run` and `mutmut results` run, and removes `mutants/` after it reads the results.
- The runner template gets a home volume of 8 Gi and `ephemeral-storage` of 4 Gi requested and 10 Gi at most.
- The report of a runner Job reads the reason and the message of the pod and the reason of the terminated container. A pod that the kubelet evicted for a storage limit of its own gets `limit_reached`, and the report quotes the message of the kubelet. A pod evicted for a node low on a resource gets `ci_infra`. The exit status 137 gives `oom` only with the container reason `OOMKilled`, or with no container reason.

## Capabilities
- Modified: `roadmap-implement-job/stops` (the report reads the reason of the container, and a new requirement classifies an evicted pod) and `roadmap-implement-job/repair` (the mutation run mutates only the files of its targets and removes its tree).

## Impact
- A runner Job asks the scheduler for 4 Gi of storage, not 2 Gi. The runner Jobs run on node hog, which had 68 GB of free disk on 2026-11-16.
- A command of a step keeps its class: it has no container reason, so its exit status 137 stays `oom`.
- The stage Job and the planner run Job do not run the strength check, so their volumes stay.
- The change fits one pull request.

## Feasibility
- The events of the pod on 2026-11-16 (Loki, `kubernetes-events`): `Evicted` with the message above at 08:05:32Z, then `ExceededGracePeriod`.
- mutmut 3.8.1 source in the venv: `copy_src_dir` copies each file of `source_paths`, `create_file_mutants` writes a mutated copy of each file that `Config.should_mutate` accepts and copies the others, and `walk_mutatable_files` applies `only_mutate` to `mutmut results` too.
- Measured on 2026-11-16 in a blobless clone of `origin/main` with a fresh uv cache on one file system (hard links, as on the volume): clone 144 MB, worktree 112 MB, uv cache 1.1 GB, venv 1.5 GB, all together 1.8 GB. The kubelet counts a file with several hard links once (`pkg/volume/util/fs/fs.go`). The mutation run of the strength check on one target (`retry_after` of `src/devops_cli/roadmap/failure.py`) wrote 723 MB into `mutants/` in 145 s. With `only_mutate` it wrote 68 MB in 15 s, with the same 3 surviving mutants. A strict mypy run of two files added 107 MB.
- The run of #3648 held more than 4 GiB. The measured parts give 2.6 GB, so its other files were at least 1.6 GB. The new limit is twice the 4 GiB that the run went over.

## Existing Tool Considered
- mutmut's own setting `only_mutate` limits the tree, and `shutil.rmtree` removes it. No code of our own copies or filters files.
- The kubelet already writes the cause of an eviction in `status.reason` and `status.message` of the pod, and the Kubernetes client reads them. The change adds three fields to the evidence of the classifier and no new class.
