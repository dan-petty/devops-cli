# Design

## Decisions
- **The mutation run names the files of its targets in `only_mutate`.** The table of the checkout holds the key for the block of `mutmut run` and `mutmut results`, as the test selection does, and the file gets its bytes again after the block. mutmut copies the other files of `source_paths` as they are, so the tests still import them. `mutmut results` reads the same table, so it walks only the files of the targets.
- **The run removes `mutants/` in a `finally`.** The removal comes after `mutmut results`, which reads the meta files of the tree. A run that reaches the timeout or raises removes the tree too. A later group starts a new tree, which costs about 15 s for one target.
- **The home volume is 8 Gi.** The run of #3648 went over 4 GiB. The measured parts of a run are 1.8 GB for the clone, the worktree, the venv and the cache, 68 MB for the tree of the mutation run, and about 0.1 GB for each cache of a check. The limit is twice the value that the kubelet measured. The `ephemeral-storage` limit of 10 Gi covers the home volume, the 1 Gi `/tmp` and the log. The request of 4 Gi is the use of the run of #3648.
- **An eviction gets its class from the status of the pod.** The kubelet writes `Evicted` in `status.reason` and the cause in `status.message`. A message for a volume, a container or a pod over its own storage limit gives `limit_reached`, whose action `raise_limit` asks a person to raise that limit. A message for a node low on a resource gives `ci_infra`, whose action `retry` lets a continuation run the item again. The pod rule comes before the exit status, because the status of the pod is the most sure cause.
- **The exit status 137 needs the container reason `OOMKilled`.** The kubelet kills a container that ignores SIGTERM with SIGKILL too, and then the reason is `Error`. A command of a step has no container reason, so its exit status 137 stays `oom`.
- **The report quotes the message of the kubelet.** The message names the volume and its limit, so the stop comment tells a person which limit to raise.

## Rejected alternatives
- **A new class `evicted`.** `limit_reached` already has the action `raise_limit` and is an infrastructure class in the job grades. A new class needs a new metric label, a row in the action table and a change of the dashboards, and gives no other action.
- **Only a larger volume.** The tree of the mutation run grows with `src/` (723 MB on 2026-11-16), so a fixed volume fills again. The tree also took 130 s of the 145 s of the run.
- **Keep `mutants/` between groups as a cache.** The tree of one target is 68 MB and takes 15 s to make. A tree that stays holds space for the rest of the run, and its mutants of an earlier group are stale.
- **Copy only the target files into `mutants/`.** mutmut copies the whole of `source_paths` before it mutates, and the tests import the other modules from the tree. That needs a patch of mutmut.
